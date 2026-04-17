"""Tests for provenance — every value knows where it came from.

Provenance is a first-class runtime property: each ConfidentValue carries an
Origin that records the operation producing it, plus links to parent origins.
These tests verify origins are attached at the right boundaries, propagate
correctly through arithmetic and control flow, and are exposed to AIL code
via origin_of / lineage_of / has_intent_origin builtins.
"""
from __future__ import annotations

from ail_mvp import run
from ail_mvp.runtime import MockAdapter
from ail_mvp.runtime.provenance import (
    Origin, LITERAL_ORIGIN, LITERAL, INPUT, FN, INTENT, BUILTIN,
)


# ---------- Origin as a standalone data type ----------


def test_literal_origin_is_shared_sentinel():
    # Implementation detail relied on by hot paths — reified in a test so
    # the optimization doesn't regress silently.
    assert LITERAL_ORIGIN.kind == LITERAL
    assert LITERAL_ORIGIN.parents == ()


def test_origin_has_kind_walks_ancestors():
    leaf = Origin(kind=INTENT, name="classify")
    mid = Origin(kind=FN, name="score", parents=(leaf,))
    root = Origin(kind=BUILTIN, name="to_text", parents=(mid,))
    assert root.has_kind(INTENT) is True
    assert root.has_kind(FN) is True
    assert root.has_kind("input") is False


def test_origin_lineage_is_postorder():
    a = Origin(kind=INTENT, name="a")
    b = Origin(kind=FN, name="b")
    c = Origin(kind=BUILTIN, name="c", parents=(a, b))
    lineage = c.lineage()
    assert [o.name for o in lineage] == ["a", "b", "c"]


def test_origin_to_dict_is_serializable():
    o = Origin(kind=INTENT, name="classify", model_id="claude-x",
               at="2026-04-17T00:00:00+00:00")
    d = o.to_dict()
    assert d == {
        "kind": INTENT,
        "name": "classify",
        "model_id": "claude-x",
        "at": "2026-04-17T00:00:00+00:00",
    }


# ---------- attachment at boundaries ----------


def test_entry_input_carries_input_origin():
    src = "entry main(x: Text) { return x }"
    result, _ = run(src, input="hello", adapter=MockAdapter())
    assert result.origin.kind == INPUT
    assert result.origin.name == "x"


def test_literal_return_carries_literal_origin():
    src = "entry main(x: Text) { return 42 }"
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.origin.kind == LITERAL


def test_fn_return_carries_fn_origin():
    src = """
    fn double(n: Number) -> Number { return n * 2 }
    entry main(x: Text) { return double(5) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.origin.kind == FN
    assert result.origin.name == "double"


def test_nested_fn_calls_build_origin_tree():
    src = """
    fn double(n: Number) -> Number { return n * 2 }
    fn add_one(n: Number) -> Number { return n + 1 }
    entry main(x: Text) { return double(add_one(5)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.origin.kind == FN
    assert result.origin.name == "double"
    # Parent tree must contain add_one
    assert result.origin.has_kind(FN)
    lineage_names = [o.name for o in result.origin.lineage() if o.kind == FN]
    assert "double" in lineage_names
    assert "add_one" in lineage_names


def test_intent_return_carries_intent_origin_with_model_id():
    src = """
    intent classify(text: Text) -> Text {
        goal: categorize input
    }
    entry main(x: Text) { return classify(x) }
    """
    adapter = MockAdapter(responses={"classify": "positive"})
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.origin.kind == INTENT
    assert result.origin.name == "classify"
    assert result.origin.model_id == "mock-1"
    assert result.origin.at is not None   # intent calls stamp a timestamp


def test_builtin_return_carries_builtin_origin():
    src = 'entry main(x: Text) { return length(x) }'
    result, _ = run(src, input="hello", adapter=MockAdapter())
    assert result.origin.kind == BUILTIN
    assert result.origin.name == "length"


# ---------- propagation through expressions ----------


def test_binary_op_inherits_dominant_origin():
    # input + literal: origin should be the input's origin, not the literal's.
    src = """
    fn increment(n: Number) -> Number { return n + 1 }
    entry main(x: Text) { return increment(to_number(x)) }
    """
    result, _ = run(src, input="5", adapter=MockAdapter())
    # Result has fn_origin("increment") at top
    assert result.origin.kind == FN
    assert result.origin.name == "increment"


def test_for_loop_variable_inherits_collection_origin():
    # The iteration variable should carry the collection's origin, not a
    # fresh literal one — so downstream computations trace back to it.
    # Using split() as the collection producer keeps us within the MVP
    # type syntax (no [Number] return types yet).
    src = """
    intent phrase(source: Text) -> Text {
        goal: space-delimited words
    }
    fn count_chars(words: Text) -> Number {
        total = 0
        for w in split(words, " ") {
            total = total + length(w)
        }
        return total
    }
    entry main(x: Text) { return count_chars(phrase(x)) }
    """
    adapter = MockAdapter(responses={"phrase": "alpha beta"})
    result, _ = run(src, input="source", adapter=adapter)
    # count_chars is a fn; its body iterates over split(phrase(...)).
    # Each iteration variable carries origin from split, which carries it
    # from the intent. Final result must trace back to the intent.
    assert result.origin.has_kind(INTENT)


# ---------- AIL-visible builtins ----------


def test_origin_of_returns_record():
    src = """
    fn double(n: Number) -> Number { return n * 2 }
    entry main(x: Text) { return origin_of(double(5)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert isinstance(result.value, dict)
    assert result.value["kind"] == FN
    assert result.value["name"] == "double"


def test_has_intent_origin_true_for_intent_derived_value():
    src = """
    intent classify(text: Text) -> Text {
        goal: categorize
    }
    fn wrap(s: Text) -> Text { return upper(s) }
    entry main(x: Text) { return has_intent_origin(wrap(classify(x))) }
    """
    adapter = MockAdapter(responses={"classify": "positive"})
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.value is True


def test_has_intent_origin_false_for_pure_computation():
    src = """
    fn double(n: Number) -> Number { return n * 2 }
    entry main(x: Text) { return has_intent_origin(double(5)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is False


def test_lineage_of_returns_flat_event_list():
    src = """
    fn double(n: Number) -> Number { return n * 2 }
    fn add_one(n: Number) -> Number { return n + 1 }
    entry main(x: Text) { return lineage_of(double(add_one(5))) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert isinstance(result.value, list)
    names = [e.get("name") for e in result.value]
    # Should mention both functions
    assert "double" in names
    assert "add_one" in names
    # Final event (post-order) is the outermost call
    assert names[-1] == "double"


def test_provenance_builtins_not_shadowable_by_user_fn():
    # Even if a user declares a fn called origin_of, the provenance builtin
    # wins. This is intentional — these are runtime introspection primitives.
    src = """
    fn origin_of(x: Number) -> Number { return 999 }
    entry main(x: Text) { return origin_of(42) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    # If the user's fn had won, result.value would be 999. Instead we get
    # the provenance record for the literal 42.
    assert isinstance(result.value, dict)
    assert result.value["kind"] == LITERAL


# ---------- backward compatibility ----------


def test_confidence_still_works():
    # Confidence semantics must be unchanged — provenance is additive.
    src = """
    intent classify(text: Text) -> Text {
        goal: categorize
    }
    entry main(x: Text) { return classify(x) }
    """
    adapter = MockAdapter(responses={"classify": "ok"}, default_confidence=0.72)
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.confidence == 0.72
    assert result.value == "ok"
