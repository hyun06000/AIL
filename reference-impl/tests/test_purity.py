"""Tests for structural purity contracts.

A `pure fn` is a statically-enforced promise that a function:
  1. Performs no side effects (no `perform` statements).
  2. Calls no intents (no LLM involvement).
  3. Calls no other non-pure fns (transitively deterministic).
  4. Calls no unverifiable builtins (`eval_ail`).

The purity checker runs at parse time. Violations raise PurityError —
the program is rejected before it ever executes.

Composed with provenance (Phase 1): any value returned from a pure fn is
guaranteed to have `has_intent_origin(value) == false`.
"""
from __future__ import annotations

import pytest

from ail_mvp import run, compile_source
from ail_mvp.parser import PurityError
from ail_mvp.runtime import MockAdapter


# ---------- positive cases: well-formed pure fns ----------


def test_pure_fn_with_only_builtins_accepted():
    src = """
    pure fn word_count(text: Text) -> Number {
        return length(split(text, " "))
    }
    entry main(x: Text) { return word_count(x) }
    """
    result, _ = run(src, input="a b c d", adapter=MockAdapter())
    assert result.value == 4


def test_pure_fn_calling_another_pure_fn_accepted():
    src = """
    pure fn double(n: Number) -> Number { return n * 2 }
    pure fn quadruple(n: Number) -> Number { return double(double(n)) }
    entry main(x: Text) { return quadruple(5) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 20


def test_pure_fn_with_control_flow_accepted():
    # if / for / membership — none violate purity by themselves.
    src = """
    pure fn classify_size(n: Number) -> Text {
        if n < 10 { return "small" }
        if n < 100 { return "medium" }
        return "large"
    }
    entry main(x: Text) { return classify_size(42) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "medium"


def test_pure_fn_can_use_provenance_builtins():
    # origin_of, lineage_of, has_intent_origin are metadata reads — pure.
    src = """
    pure fn is_llm_touched(x: Number) -> Boolean {
        return has_intent_origin(x)
    }
    entry main(x: Text) { return is_llm_touched(42) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is False


# ---------- negative cases: purity violations ----------


def test_pure_fn_calling_intent_rejected():
    src = """
    intent classify(text: Text) -> Text {
        goal: label
    }
    pure fn wrap(text: Text) -> Text { return classify(text) }
    entry main(x: Text) { return wrap(x) }
    """
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "classify" in str(ei.value)
    assert "intent" in str(ei.value).lower()


def test_pure_fn_calling_perform_rejected():
    src = """
    pure fn ask_user(q: Text) -> Text {
        answer = perform human_ask(q)
        return answer
    }
    entry main(x: Text) { return ask_user("hi") }
    """
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "perform" in str(ei.value)


def test_pure_fn_calling_non_pure_fn_rejected():
    src = """
    fn tainted(x: Number) -> Number { return x }
    pure fn depends_on_tainted(x: Number) -> Number {
        return tainted(x) + 1
    }
    entry main(x: Text) { return depends_on_tainted(5) }
    """
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "tainted" in str(ei.value)


def test_pure_fn_calling_eval_ail_rejected():
    src = """
    pure fn run_code(s: Text) -> Text {
        return eval_ail(s, "")
    }
    entry main(x: Text) { return run_code("...") }
    """
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "eval_ail" in str(ei.value)


def test_pure_fn_calling_unknown_name_rejected():
    # A name not resolvable to pure fn or trusted builtin is conservatively
    # rejected — we cannot prove it is pure.
    src = """
    pure fn mystery(x: Number) -> Number {
        return mystery_helper(x)
    }
    entry main(x: Text) { return mystery(5) }
    """
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "mystery_helper" in str(ei.value)


def test_pure_fn_violation_inside_if_branch_rejected():
    # Violations nested inside control flow are caught.
    src = """
    intent classify(text: Text) -> Text {
        goal: label
    }
    pure fn sneaky(x: Text) -> Text {
        if length(x) > 0 {
            return classify(x)
        }
        return "empty"
    }
    entry main(x: Text) { return sneaky(x) }
    """
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "classify" in str(ei.value)


def test_pure_fn_violation_inside_for_loop_rejected():
    src = """
    intent label(text: Text) -> Text {
        goal: tag
    }
    pure fn sneaky(xs: Text) -> Text {
        result = []
        for w in split(xs, " ") {
            result = append(result, label(w))
        }
        return join(result, ",")
    }
    entry main(x: Text) { return sneaky(x) }
    """
    with pytest.raises(PurityError) as ei:
        compile_source(src)
    assert "label" in str(ei.value)


# ---------- interaction with provenance ----------


def test_pure_fn_output_has_no_intent_origin():
    # The key compositional guarantee: a pure-fn value proves its
    # independence from LLM output at runtime too.
    src = """
    pure fn compute(n: Number) -> Number { return n * 3 + 1 }
    entry main(x: Text) { return has_intent_origin(compute(10)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is False


# ---------- backward compatibility ----------


def test_default_fn_still_works():
    # Existing (unqualified) fns continue to work exactly as before.
    # They can call intents; no static restriction applies.
    src = """
    intent classify(text: Text) -> Text {
        goal: label
    }
    fn pipeline(text: Text) -> Text {
        return classify(text)
    }
    entry main(x: Text) { return pipeline(x) }
    """
    # Should parse and run without error.
    adapter = MockAdapter(responses={"classify": "ok"})
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.value == "ok"


def test_default_fn_has_default_purity():
    # Confirm the AST field is populated correctly.
    src = "fn plain(x: Number) -> Number { return x } entry main(x: Text) { return 0 }"
    program = compile_source(src)
    fns = [d for d in program.declarations if hasattr(d, "purity")]
    assert fns[0].name == "plain"
    assert fns[0].purity == "default"


def test_pure_fn_has_pure_purity():
    src = "pure fn plain(x: Number) -> Number { return x } entry main(x: Text) { return 0 }"
    program = compile_source(src)
    fns = [d for d in program.declarations if hasattr(d, "purity")]
    assert fns[0].name == "plain"
    assert fns[0].purity == "pure"
