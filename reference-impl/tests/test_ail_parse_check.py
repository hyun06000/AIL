"""Tests for the ail_parse_check builtin.

ail_parse_check is the pure self-reflection primitive — it takes a
string, returns ok(source) if it parses as AIL, error(message) if it
does not. Introduced in 2026-04-22 so AIL programs can evaluate other
AIL programs' syntactic validity without executing them. Distinct from
eval_ail which runs the code.
"""
from ail import run, compile_source, MockAdapter


def _run_ok(source: str, input_text: str = ""):
    """Helper: run a program and return the value on the confident result."""
    result, _trace = run(source, input=input_text, adapter=MockAdapter())
    return result.value


def test_parse_check_accepts_valid_program():
    src = """
pure fn check(s: Text) -> Boolean {
    return is_ok(ail_parse_check(s))
}
entry main(x: Text) {
    return check("entry main(x: Text) { return 42 }")
}
"""
    assert _run_ok(src) is True


def test_parse_check_rejects_invalid_program():
    src = """
pure fn check(s: Text) -> Boolean {
    return is_ok(ail_parse_check(s))
}
entry main(x: Text) {
    return check("pure fn broken( syntax error")
}
"""
    assert _run_ok(src) is False


def test_parse_check_error_contains_message():
    src = """
pure fn describe(s: Text) -> Text {
    r = ail_parse_check(s)
    if is_error(r) { return unwrap_error(r) }
    return "OK"
}
entry main(x: Text) {
    return describe("entry main(x: Text) { return [unterminated")
}
"""
    msg = _run_ok(src)
    # Error string is produced by the parser; we don't pin its exact text,
    # only that ail_parse_check surfaced *some* error description.
    assert isinstance(msg, str)
    assert msg != "OK"
    assert len(msg) > 0


def test_parse_check_ok_preserves_source():
    # ok(src) should carry the source back as the inner value.
    src = """
pure fn roundtrip(s: Text) -> Text {
    r = ail_parse_check(s)
    return unwrap_or(r, "FAIL")
}
entry main(x: Text) {
    return roundtrip("entry main(x: Text) { return 1 }")
}
"""
    assert _run_ok(src) == "entry main(x: Text) { return 1 }"


def test_parse_check_is_pure():
    # A pure fn that calls ail_parse_check must compile (no PurityError).
    # If ail_parse_check were accidentally not registered as pure, this
    # would raise at parse time.
    src = """
pure fn validate(s: Text) -> Boolean {
    return is_ok(ail_parse_check(s))
}
entry main(x: Text) { return validate("entry main(x: Text) { return 0 }") }
"""
    compile_source(src)  # must not raise
    assert _run_ok(src) is True


def test_parse_check_does_not_execute_the_inner_program():
    # The inner program has an intent with a goal that, if executed, would
    # dispatch to the model adapter. ail_parse_check must only parse, not
    # execute; therefore the mock adapter is never invoked and the outer
    # program's value is just the Result metadata (is_ok == true).
    # The inner is built at runtime via string concatenation so the AIL
    # parser only sees the outer program's escaped quotes.
    src = """
pure fn is_good(s: Text) -> Boolean {
    return is_ok(ail_parse_check(s))
}
entry main(x: Text) {
    inner = join([
        "intent foo(x: Text) -> Text { goal: whatever } ",
        "entry main(x: Text) { return foo(\\"hi\\") }"
    ], "")
    return is_good(inner)
}
"""
    # This would fail (mock doesn't know "foo") if ail_parse_check were
    # executing instead of just parsing. It passes because it only parses.
    assert _run_ok(src) is True
