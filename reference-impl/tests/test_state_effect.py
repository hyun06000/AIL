"""Tests for the state effect family — state.read/write/has/delete.

Exercises the cross-request memory primitive (L2 v2 case study Gap #4).
The agentic server points AIL_STATE_DIR at .ail/state/keyval/ on start;
these tests use a tmp dir directly via the env var so they don't need
to spin up a project.
"""
import os

import pytest

from ail import run, MockAdapter


def _run(source, *, state_dir=None):
    if state_dir is not None:
        os.environ["AIL_STATE_DIR"] = str(state_dir)
    elif "AIL_STATE_DIR" in os.environ:
        del os.environ["AIL_STATE_DIR"]
    return run(source, adapter=MockAdapter())


def test_state_write_then_read_round_trip(tmp_path):
    src = '''
entry main(x: Text) {
    w = perform state.write("counter", 7)
    if is_error(w) { return unwrap_error(w) }
    r = perform state.read("counter")
    if is_error(r) { return unwrap_error(r) }
    return to_text(unwrap(r))
}
'''
    result, _ = _run(src, state_dir=tmp_path)
    assert result.value == "7"


def test_state_persists_across_separate_runs(tmp_path):
    write_src = '''
entry main(x: Text) {
    w = perform state.write("name", "alice")
    return to_text(is_ok(w))
}
'''
    read_src = '''
entry main(x: Text) {
    r = perform state.read("name")
    if is_error(r) { return "missing" }
    return unwrap(r)
}
'''
    _run(write_src, state_dir=tmp_path)
    result, _ = _run(read_src, state_dir=tmp_path)
    # State written in run #1 is visible in run #2 — the cross-request
    # promise the news-dashboard case study identified as missing.
    assert result.value == "alice"


def test_state_has_reflects_writes(tmp_path):
    src = '''
entry main(x: Text) {
    before = perform state.has("answer")
    perform state.write("answer", 42)
    after = perform state.has("answer")
    return join([to_text(before), ",", to_text(after)], "")
}
'''
    result, _ = _run(src, state_dir=tmp_path)
    assert result.value == "false,true"


def test_state_delete_removes_key(tmp_path):
    src = '''
entry main(x: Text) {
    perform state.write("temp", 1)
    d = perform state.delete("temp")
    h = perform state.has("temp")
    return join([to_text(unwrap(d)), ",", to_text(h)], "")
}
'''
    result, _ = _run(src, state_dir=tmp_path)
    assert result.value == "true,false"


def test_state_read_missing_key_returns_error(tmp_path):
    src = '''
entry main(x: Text) {
    r = perform state.read("never_set")
    return to_text(is_error(r))
}
'''
    result, _ = _run(src, state_dir=tmp_path)
    assert result.value == "true"


def test_state_rejects_invalid_keys(tmp_path):
    src = '''
entry main(x: Text) {
    r = perform state.write("../../etc/passwd", "x")
    return to_text(is_error(r))
}
'''
    result, _ = _run(src, state_dir=tmp_path)
    # Path-traversal-style keys are rejected by the key character whitelist.
    assert result.value == "true"


def test_state_without_dir_returns_descriptive_error():
    src = '''
entry main(x: Text) {
    r = perform state.read("k")
    return unwrap_error(r)
}
'''
    # No state_dir → AIL_STATE_DIR unset → explanatory error not crash.
    result, _ = _run(src, state_dir=None)
    msg = result.value
    assert "state directory" in msg.lower() or "AIL_STATE_DIR" in msg


def test_state_round_trips_lists_and_numbers(tmp_path):
    src = '''
entry main(x: Text) {
    perform state.write("nums", [1, 2, 3])
    r = perform state.read("nums")
    if is_error(r) { return "fail" }
    nums = unwrap(r)
    return to_text(length(nums))
}
'''
    result, _ = _run(src, state_dir=tmp_path)
    assert result.value == "3"


def test_state_write_atomic_no_partial_files(tmp_path):
    """The write-temp-then-rename guarantee: a successful write
    leaves only the final file, no .tmp leftover."""
    src = '''
entry main(x: Text) {
    perform state.write("k", "v")
    return "done"
}
'''
    _run(src, state_dir=tmp_path)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["k.json"]


def test_state_cannot_be_called_from_pure_fn():
    """All perform calls — including state — are forbidden in pure fn."""
    import pytest
    from ail import compile_source
    from ail.parser import PurityError
    src = '''
    pure fn sneaky(x: Text) -> Text {
        perform state.write("k", "v")
        return x
    }
    entry main(x: Text) { return sneaky(x) }
    '''
    with pytest.raises(PurityError):
        compile_source(src)
