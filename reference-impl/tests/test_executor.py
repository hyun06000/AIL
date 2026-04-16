"""Tests for the AIL executor."""
from __future__ import annotations

import pytest

from ail_mvp import run
from ail_mvp.runtime import MockAdapter
from ail_mvp.runtime.model import ModelResponse


class ScriptedAdapter(MockAdapter):
    """Mock adapter that returns scripted responses per intent name."""

    def __init__(self, scripts: dict[str, tuple] | None = None):
        super().__init__()
        self.scripts = scripts or {}
        self.calls: list[str] = []

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None) -> ModelResponse:
        name = context.get("_intent_name", "")
        self.calls.append(name)
        if name in self.scripts:
            value, conf = self.scripts[name]
            return ModelResponse(value=value, confidence=conf,
                                 model_id="scripted", raw={})
        return ModelResponse(value=f"[no script for {name}]", confidence=0.5,
                             model_id="scripted", raw={})


def test_simple_intent_invocation():
    src = """
    intent greet(name: Text) -> Text {
        goal: Text warm greeting
    }
    entry main(name: Text) {
        return greet(name)
    }
    """
    adapter = ScriptedAdapter({"greet": ("Hello!", 0.95)})
    result, trace = run(src, input="World", adapter=adapter)
    assert result.value == "Hello!"
    assert result.confidence == pytest.approx(0.95)
    assert adapter.calls == ["greet"]


def test_context_inheritance_resolves_fields():
    src = """
    context base {
        register: "neutral"
        audience: "general"
    }
    context fancy extends base {
        override register: "formal"
        extra: "value"
    }
    intent do(x: Text) -> Text { goal: Text }
    entry main(x: Text) {
        with context fancy:
            y = do(x)
        return y
    }
    """
    captured: dict = {}

    class Captor(MockAdapter):
        def invoke(self, *, goal, constraints, context, inputs,
                   expected_type=None, examples=None):
            captured["context"] = dict(context)
            return ModelResponse(value="ok", confidence=0.9,
                                 model_id="captor", raw={})

    result, trace = run(src, input="hi", adapter=Captor())
    # Context reaching the adapter should show inherited + overridden fields
    assert captured["context"]["register"] == "formal"
    assert captured["context"]["audience"] == "general"
    assert captured["context"]["extra"] == "value"


def test_branch_selects_matching_arm():
    src = """
    intent classify(x: Text) -> Text { goal: label }
    intent positive(x: Text) -> Text { goal: Text }
    intent negative(x: Text) -> Text { goal: Text }
    entry main(x: Text) {
        c = classify(x)
        branch c {
            [c == "pos"]      => r = positive(x)
            [c == "neg"]      => r = negative(x)
            [otherwise]       => r = positive(x)
        }
        return r
    }
    """
    adapter = ScriptedAdapter({
        "classify": ("neg", 0.9),
        "negative": ("careful reply", 0.88),
        "positive": ("warm reply", 0.88),
    })
    result, trace = run(src, input="this is sad", adapter=adapter)
    assert result.value == "careful reply"
    assert "negative" in adapter.calls
    assert "positive" not in adapter.calls


def test_branch_otherwise_fires_when_no_arm_matches():
    src = """
    intent classify(x: Text) -> Text { goal: label }
    intent fallback(x: Text) -> Text { goal: Text }
    entry main(x: Text) {
        c = classify(x)
        branch c {
            [c == "pos"]      => r = classify(x)
            [otherwise]       => r = fallback(x)
        }
        return r
    }
    """
    adapter = ScriptedAdapter({
        "classify": ("unknown_label", 0.8),
        "fallback": ("caught by otherwise", 0.8),
    })
    result, trace = run(src, input="?", adapter=adapter)
    assert result.value == "caught by otherwise"


def test_low_confidence_handler_fires():
    src = """
    intent suggest(pref: Text) -> Text {
        goal: Text concrete suggestion
        on_low_confidence(threshold: 0.7) {
            a = perform human_ask("what do you want?")
            return a
        }
    }
    entry main(pref: Text) { return suggest(pref) }
    """
    adapter = ScriptedAdapter({"suggest": ("unsure...", 0.4)})
    answered: list = []

    def fake_human(q, *, expect="text"):
        answered.append(q)
        return "pizza"

    result, trace = run(src, input="hungry", adapter=adapter, ask_human=fake_human)
    assert result.value == "pizza"
    assert len(answered) == 1  # human was asked exactly once


def test_low_confidence_handler_does_not_fire_when_confident():
    src = """
    intent suggest(pref: Text) -> Text {
        goal: Text
        on_low_confidence(threshold: 0.7) {
            a = perform human_ask("what do you want?")
            return a
        }
    }
    entry main(pref: Text) { return suggest(pref) }
    """
    adapter = ScriptedAdapter({"suggest": ("pizza", 0.95)})
    asks: list = []

    def fake_human(q, *, expect="text"):
        asks.append(q)
        return "should not be called"

    result, trace = run(src, input="hungry", adapter=adapter, ask_human=fake_human)
    assert result.value == "pizza"
    assert asks == []  # handler did not fire


# ---------- membership operator (Q4) ----------


def test_membership_in_list_true():
    src = """
    entry main(x: Text) {
        result = x in ["a", "b", "c"]
        return result
    }
    """
    result, _ = run(src, input="b", adapter=MockAdapter())
    assert result.value is True


def test_membership_in_list_false():
    src = """
    entry main(x: Text) {
        result = x in ["a", "b", "c"]
        return result
    }
    """
    result, _ = run(src, input="z", adapter=MockAdapter())
    assert result.value is False


def test_membership_not_in():
    src = """
    entry main(x: Text) {
        result = x not in ["a", "b"]
        return result
    }
    """
    r1, _ = run(src, input="c", adapter=MockAdapter())
    assert r1.value is True
    r2, _ = run(src, input="a", adapter=MockAdapter())
    assert r2.value is False


def test_membership_against_intent_result():
    """The classify example pattern: use an intent output as the element."""
    src = """
    intent classify(x: Text) -> Text { goal: label }
    entry main(input: Text) {
        label = classify(input)
        is_valid = label in ["positive", "negative", "neutral"]
        return is_valid
    }
    """
    adapter = ScriptedAdapter({"classify": ("positive", 0.9)})
    result, _ = run(src, input="some text", adapter=adapter)
    assert result.value is True
    # Confidence is min of element (0.9) and collection (literal, 1.0) = 0.9
    assert abs(result.confidence - 0.9) < 1e-9


def test_membership_in_branch_condition():
    """Using `in` inside a branch arm — the classify.ail use case."""
    src = """
    intent classify(x: Text) -> Text { goal: label }
    entry main(input: Text) {
        label = classify(input)
        branch label {
            [label in ["positive", "great", "love"]] => result = "warm"
            [label in ["negative", "bad", "hate"]]   => result = "careful"
            [otherwise]                              => result = "neutral"
        }
        return result
    }
    """
    adapter = ScriptedAdapter({"classify": ("great", 0.88)})
    result, _ = run(src, input="something", adapter=adapter)
    assert result.value == "warm"


# ---------- evolve block integration ----------


def test_evolve_no_change_when_metric_healthy():
    """An evolving intent whose metric stays above threshold does not evolve."""
    src = """
    intent classify(x: Text) -> Text { goal: label }
    evolve classify {
        metric: score
        when score < 0.7 {
            retune threshold: within [0.4, 0.9]
        }
        rollback_on: score < 0.3
        history: keep_last 5
    }
    entry main(x: Text) { return classify(x) }
    """
    adapter = ScriptedAdapter({"classify": ("positive", 0.95)})
    # confidence-as-metric is 0.95, well above threshold 0.7
    for _ in range(20):
        result, trace = run(src, input="hi", adapter=adapter)
        assert result.value == "positive"
    # Confirm no version_applied events in last trace
    assert not any(e.kind == "evolution_version_applied" for e in trace.entries)


def test_evolve_triggers_modification_when_metric_drops():
    """Feeding a low-confidence result eventually triggers retune."""
    src = """
    intent classify(x: Text) -> Text { goal: label }
    evolve classify {
        metric: score
        when score < 0.7 {
            retune threshold: within [0.4, 0.9]
        }
        rollback_on: score < 0.2
        history: keep_last 5
    }
    entry main(x: Text) { return classify(x) }
    """
    # Confidence of 0.3 is below the 0.7 threshold
    adapter = ScriptedAdapter({"classify": ("bad", 0.3)})
    last_trace = None
    for _ in range(20):
        _, last_trace = run(src, input="hi", adapter=adapter)
    # One instance of run = one executor = one supervisor, so each call
    # starts fresh. Instead, construct one Executor and invoke many times.


def test_evolve_triggers_modification_with_persistent_executor():
    """Using a persistent executor across many invocations, verify that
    enough low-metric calls trigger a modification."""
    from ail_mvp import compile_source
    from ail_mvp.runtime.executor import Executor

    src = """
    intent classify(x: Text) -> Text { goal: label }
    evolve classify {
        metric: score
        when score < 0.7 {
            retune threshold: within [0.4, 0.9]
        }
        rollback_on: score < 0.2
        history: keep_last 5
    }
    entry main(x: Text) { return classify(x) }
    """
    program = compile_source(src)
    adapter = ScriptedAdapter({"classify": ("bad", 0.3)})
    executor = Executor(program, adapter)

    # Run the entry 15 times through the same executor so the supervisor
    # accumulates samples
    for _ in range(15):
        executor.run_entry({"x": "hi"})

    sup = executor.supervisors["classify"]
    applied = [e for e in sup.events if e.kind == "version_applied"]
    assert len(applied) >= 1
    assert sup.active_version_id != 0
    # The retune target is 'threshold', midpoint of [0.4, 0.9] = 0.65
    assert sup.active_parameters()["threshold"] == 0.65


def test_evolve_custom_metric_fn_overrides_default():
    """A caller-supplied metric_fn overrides the confidence-as-metric default."""
    from ail_mvp import compile_source
    from ail_mvp.runtime.executor import Executor

    src = """
    intent classify(x: Text) -> Text { goal: label }
    evolve classify {
        metric: external_score
        when external_score < 0.7 {
            retune threshold: within [0.4, 0.9]
        }
        rollback_on: external_score < 0.2
        history: keep_last 5
    }
    entry main(x: Text) { return classify(x) }
    """
    program = compile_source(src)
    # High confidence from the model, but the caller says the metric is low
    adapter = ScriptedAdapter({"classify": ("x", 0.95)})

    def external_metric(name, value, conf):
        return (0.3, 0.4)  # metric=0.3 (< 0.7), rollback_value=0.4 (>= 0.2)

    executor = Executor(program, adapter, metric_fn=external_metric)
    for _ in range(15):
        executor.run_entry({"x": "hi"})

    sup = executor.supervisors["classify"]
    assert sup.active_version_id != 0  # modification happened
