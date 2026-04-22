"""Tests for `perform clock.now()` — the time effect added to close
the hardcoded-timestamp gap the news-dashboard case study surfaced.
"""
import re

from ail import run, MockAdapter


def _run(source: str):
    # Use the mock adapter because programs here might declare intents
    # we don't want to hit a real model for.
    return run(source, adapter=MockAdapter())


def test_clock_now_default_returns_iso_utc():
    src = '''
entry main(x: Text) {
    t = perform clock.now()
    return t
}
'''
    result, _ = _run(src)
    # ISO-8601 UTC shape: YYYY-MM-DDTHH:MM:SSZ
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", result.value), (
        f"unexpected timestamp shape: {result.value!r}"
    )


def test_clock_now_iso_explicit():
    src = '''
entry main(x: Text) {
    t = perform clock.now("iso")
    return t
}
'''
    result, _ = _run(src)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", result.value)


def test_clock_now_unix():
    src = '''
entry main(x: Text) {
    t = perform clock.now("unix")
    return t
}
'''
    result, _ = _run(src)
    # Unix epoch seconds — ten digits in the 2020s–2030s range.
    assert re.match(r"^\d{10}$", result.value)
    epoch = int(result.value)
    # Rough sanity — year between 2024 and 2099
    assert 1_704_067_200 <= epoch <= 4_102_444_800


def test_clock_now_carries_effect_origin():
    """Provenance requirement from the reference card: every value
    produced by an effect carries an effect-origin node."""
    src = '''
entry main(x: Text) {
    t = perform clock.now()
    return has_effect_origin(t)
}
'''
    result, _ = _run(src)
    assert result.value is True


def test_clock_now_cannot_be_called_from_pure_fn():
    """pure fn rejects any body containing perform (by parse-time
    check). Guards the case where the authoring model might try to
    sneak clock.now into a pure helper.
    """
    import pytest
    from ail import compile_source
    from ail.parser import PurityError
    src = '''
    pure fn bad(x: Text) -> Text {
        perform clock.now()
        return x
    }
    entry main(x: Text) { return bad(x) }
    '''
    with pytest.raises(PurityError):
        compile_source(src)
