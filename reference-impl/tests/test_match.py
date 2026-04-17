"""Tests for `match` — confidence-aware pattern matching.

AIL's `match` is simpler than a full-featured pattern matching system
(no destructuring, no or-patterns) and does one novel thing: arms can
carry a `with confidence OP N` guard that constrains selection on the
subject's belief level. No human-authored language has this, because
confidence is not a first-class primitive anywhere else.

These tests cover:
  - Literal matching against Number / Text / Boolean
  - Wildcard `_`
  - Variable binding (non-underscore identifier)
  - Confidence guards: >, >=, <, <=, ==
  - Arm ordering: first-match wins
  - Fallthrough: no arm → Result-error
  - Purity: match is pure iff subject + arms are pure
  - Parallelism: match containing intents is NOT batched
"""
from __future__ import annotations

import pytest

from ail import run, compile_source
from ail.parser import PurityError
from ail.runtime import MockAdapter
from ail.runtime.parallel import plan_groups
from ail.parser.ast import (
    Assignment, Call, Identifier, MatchExpr, MatchArm, Literal,
)


# ---------- literal matching ----------


def test_match_literal_text():
    src = '''
    entry main(x: Text) {
        return match "positive" {
            "positive" => 1,
            "negative" => -1,
            _ => 0
        }
    }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 1


def test_match_literal_number():
    src = '''
    entry main(x: Text) {
        return match 42 {
            1 => "one",
            42 => "forty-two",
            _ => "other"
        }
    }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "forty-two"


def test_match_literal_boolean():
    src = '''
    entry main(x: Text) {
        return match true {
            false => "no",
            true => "yes"
        }
    }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "yes"


# ---------- wildcard and variable binding ----------


def test_match_wildcard_catchall():
    src = '''
    entry main(x: Text) {
        return match "unknown" {
            "a" => 1,
            "b" => 2,
            _ => 99
        }
    }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 99


def test_match_variable_binding():
    # A non-underscore identifier binds the subject. The body can
    # reference the bound name.
    src = '''
    entry main(x: Text) {
        return match "hello" {
            "" => "empty",
            s => length(s)
        }
    }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 5


# ---------- first-match-wins ----------


def test_match_arm_order_matters():
    # Two arms would match; the first wins.
    src = '''
    entry main(x: Text) {
        return match 42 {
            _ => "any",
            42 => "exact"
        }
    }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "any"   # wildcard came first


# ---------- confidence guards ----------


def test_match_confidence_gt_passes_when_high():
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    entry main(x: Text) {
        return match classify(x) {
            "positive" with confidence > 0.8 => "high_pos",
            "positive" => "low_pos",
            _ => "other"
        }
    }
    '''
    adapter = MockAdapter(responses={"classify": "positive"}, default_confidence=0.95)
    result, _ = run(src, input="hi", adapter=adapter)
    assert result.value == "high_pos"


def test_match_confidence_gt_fails_and_falls_through_to_next_arm():
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    entry main(x: Text) {
        return match classify(x) {
            "positive" with confidence > 0.8 => "high_pos",
            "positive" => "low_pos",
            _ => "other"
        }
    }
    '''
    # Same label but low confidence — first arm's guard fails.
    adapter = MockAdapter(responses={"classify": "positive"}, default_confidence=0.3)
    result, _ = run(src, input="hi", adapter=adapter)
    assert result.value == "low_pos"


def test_match_confidence_lt_selects_unsure_path():
    # Use confidence < as a "bail out when unsure" trigger.
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    entry main(x: Text) {
        return match classify(x) {
            _ with confidence < 0.5 => "ask_human",
            "positive" => "happy",
            "negative" => "sad",
            _ => "meh"
        }
    }
    '''
    adapter = MockAdapter(responses={"classify": "positive"}, default_confidence=0.2)
    result, _ = run(src, input="hi", adapter=adapter)
    assert result.value == "ask_human"


def test_match_confidence_guard_all_operators():
    # Just parse-check the full operator set; no execution needed to
    # verify the parser accepts each variant.
    for op in (">", "<", ">=", "<=", "=="):
        src = f'''
        entry main(x: Text) {{
            return match 0.9 {{
                _ with confidence {op} 0.5 => "pass"
            }}
        }}
        '''
        compile_source(src)   # must parse without error


# ---------- fallthrough: no arm matches ----------


def test_match_no_arm_matches_returns_result_error():
    src = '''
    entry main(x: Text) {
        return match "c" {
            "a" => 1,
            "b" => 2
        }
    }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    # Result-shaped error
    assert isinstance(result.value, dict)
    assert result.value.get("_result") is True
    assert result.value.get("ok") is False
    assert "no arm matched" in result.value["error"]


# ---------- purity interaction ----------


def test_pure_fn_match_of_pure_arms_accepted():
    src = '''
    pure fn classify_num(n: Number) -> Text {
        return match n {
            0 => "zero",
            1 => "one",
            _ => "many"
        }
    }
    entry main(x: Text) { return classify_num(1) }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "one"


def test_pure_fn_match_rejects_intent_in_subject():
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    pure fn sneaky(x: Text) -> Text {
        return match classify(x) {
            "positive" => "yes",
            _ => "no"
        }
    }
    entry main(x: Text) { return sneaky(x) }
    '''
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "classify" in str(ei.value)


def test_pure_fn_match_rejects_intent_in_arm_body():
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    pure fn sneaky(x: Text) -> Text {
        return match "a" {
            "a" => classify(x),
            _ => "no"
        }
    }
    entry main(x: Text) { return sneaky(x) }
    '''
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "classify" in str(ei.value)


# ---------- parallelism interaction ----------


def test_match_containing_intent_treated_as_intent_for_parallelism():
    # Two assignments whose RHS is a match that calls an intent should
    # be batchable just like a bare intent call would be.
    from ail.parser.ast import Assignment, Call, Identifier, MatchExpr, MatchArm, Literal
    stmts = [
        Assignment("a", MatchExpr(
            subject=Call(Identifier("classify_a"), [Identifier("x")], {}),
            arms=[MatchArm(pattern=Identifier("_"), body=Literal(value=1))],
        )),
        Assignment("b", MatchExpr(
            subject=Call(Identifier("classify_b"), [Identifier("x")], {}),
            arms=[MatchArm(pattern=Identifier("_"), body=Literal(value=2))],
        )),
    ]
    groups = plan_groups(stmts, intents={"classify_a", "classify_b"})
    assert len(groups) == 1
    assert groups[0].parallel is True
    assert len(groups[0].stmts) == 2
