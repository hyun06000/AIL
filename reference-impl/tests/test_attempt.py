"""Tests for `attempt` blocks — confidence-priority cascade.

`attempt { try E1; try E2; ... }` evaluates each try left-to-right and
returns the first result that qualifies: not a Result-typed error AND
with confidence >= threshold (default 0.7). If none qualify, the last
try's result is returned with its own (low) confidence so the caller
can detect the fallthrough.

The returned value carries an `attempt` origin node identifying which
try index was selected.
"""
from __future__ import annotations

from ail_mvp import run
from ail_mvp.runtime import MockAdapter


# ---------- basic selection ----------


def test_first_try_wins_when_confidence_sufficient():
    # A pure fn always returns confidence 1.0 — the first try always wins.
    src = """
    pure fn fast(x: Number) -> Number { return x * 2 }
    entry main(x: Text) {
        return attempt {
            try fast(5)
            try fast(99)
        }
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 10
    assert result.origin.kind == "attempt"
    assert result.origin.name == "0"   # index 0 selected


def test_second_try_selected_when_first_is_low_confidence():
    # A low-confidence intent falls through to the next try.
    src = """
    intent guess(x: Text) -> Text { goal: label }
    pure fn fallback(x: Text) -> Text { return "fallback" }
    entry main(x: Text) {
        return attempt {
            try guess(x)
            try fallback(x)
        }
    }
    """
    adapter = MockAdapter(responses={"guess": "uncertain"},
                          default_confidence=0.3)
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.value == "fallback"
    assert result.origin.kind == "attempt"
    assert result.origin.name == "1"


def test_first_try_selected_when_confidence_above_threshold():
    src = """
    intent guess(x: Text) -> Text { goal: label }
    pure fn fallback(x: Text) -> Text { return "fallback" }
    entry main(x: Text) {
        return attempt {
            try guess(x)
            try fallback(x)
        }
    }
    """
    adapter = MockAdapter(responses={"guess": "confident_result"},
                          default_confidence=0.9)
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.value == "confident_result"
    assert result.origin.name == "0"


# ---------- error-result handling ----------


def test_result_error_falls_through():
    # A try that returns error(...) does NOT qualify, regardless of
    # confidence. The next try is evaluated.
    src = """
    pure fn try_number(x: Text) -> Number { return to_number(x) }
    pure fn default_answer(x: Text) -> Number { return 0 }
    entry main(x: Text) {
        return attempt {
            try try_number(x)
            try default_answer(x)
        }
    }
    """
    # to_number("abc") returns error(...) -> first try fails
    result, _ = run(src, input="abc", adapter=MockAdapter())
    assert result.value == 0
    assert result.origin.name == "1"


def test_result_ok_qualifies():
    src = """
    pure fn try_number(x: Text) -> Number { return to_number(x) }
    pure fn default_answer(x: Text) -> Number { return 0 }
    entry main(x: Text) {
        return attempt {
            try try_number(x)
            try default_answer(x)
        }
    }
    """
    # to_number("42") returns ok(42) — NOT an error, qualifies.
    result, _ = run(src, input="42", adapter=MockAdapter())
    # Note: to_number returns a Result ok-wrapped value. The first try
    # produces that Result; since it's not an error AND confidence is
    # 1.0, it qualifies and is returned as-is.
    assert result.origin.name == "0"


# ---------- fallthrough when nothing qualifies ----------


def test_all_low_confidence_returns_last():
    src = """
    intent guess_a(x: Text) -> Text { goal: label }
    intent guess_b(x: Text) -> Text { goal: label }
    entry main(x: Text) {
        return attempt {
            try guess_a(x)
            try guess_b(x)
        }
    }
    """
    adapter = MockAdapter(responses={"guess_a": "ga", "guess_b": "gb"},
                          default_confidence=0.2)
    result, _ = run(src, input="hello", adapter=adapter)
    # Neither qualified. Last try returned; confidence stays at 0.2.
    assert result.value == "gb"
    assert result.confidence == 0.2
    # Origin still records the fallback selection for audit.
    assert result.origin.name == "1"


# ---------- origin chain ----------


def test_attempt_origin_preserves_upstream_lineage():
    # The selected try's original origin must be reachable through the
    # attempt origin's parent chain.
    src = """
    intent classify(x: Text) -> Text { goal: label }
    entry main(x: Text) {
        return attempt {
            try classify(x)
        }
    }
    """
    adapter = MockAdapter(responses={"classify": "ok"},
                          default_confidence=0.95)
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.origin.kind == "attempt"
    # The parent of the attempt origin is the intent origin.
    assert len(result.origin.parents) == 1
    assert result.origin.parents[0].kind == "intent"
    assert result.origin.parents[0].name == "classify"
    # has_intent_origin walks the full tree:
    assert result.origin.has_kind("intent") is True


def test_attempt_pure_fallback_has_no_intent_in_origin():
    # When the attempt falls back to a pure fn, the intent never ran AS
    # the value source; but the intent still evaluated (to determine it
    # didn't qualify). The returned value's origin reflects the pure fn,
    # NOT the intent.
    src = """
    intent guess(x: Text) -> Text { goal: label }
    pure fn fallback(x: Text) -> Text { return "safe" }
    entry main(x: Text) {
        return attempt {
            try guess(x)
            try fallback(x)
        }
    }
    """
    adapter = MockAdapter(responses={"guess": "uncertain"},
                          default_confidence=0.2)
    result, _ = run(src, input="hello", adapter=adapter)
    # Result came from fallback (pure fn). Origin must not contain intent.
    assert result.origin.has_kind("intent") is False
    assert result.origin.has_kind("fn") is True


# ---------- pure fn composition ----------


def test_pure_fn_can_contain_attempt_of_pure_tries():
    # attempt itself is not impure; only the tries it contains matter.
    src = """
    pure fn small(n: Number) -> Number { return n }
    pure fn big(n: Number) -> Number { return n * 1000 }
    pure fn choose(n: Number) -> Number {
        return attempt {
            try small(n)
            try big(n)
        }
    }
    entry main(x: Text) { return choose(7) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 7


def test_pure_fn_cannot_attempt_an_intent():
    # A pure fn's attempt block also inherits purity: intents inside
    # any try are rejected at parse time.
    from ail_mvp.parser import PurityError
    import pytest
    src = """
    intent guess(x: Text) -> Text { goal: label }
    pure fn sneaky(x: Text) -> Text {
        return attempt {
            try guess(x)
        }
    }
    entry main(x: Text) { return sneaky(x) }
    """
    with pytest.raises(PurityError) as ei:
        run(src, input="hello", adapter=MockAdapter())
    assert "guess" in str(ei.value)


# ---------- parser rejects empty attempt ----------


def test_empty_attempt_rejected():
    from ail_mvp.parser import ParseError
    import pytest
    src = """
    entry main(x: Text) {
        return attempt { }
    }
    """
    with pytest.raises(ParseError):
        run(src, input="", adapter=MockAdapter())
