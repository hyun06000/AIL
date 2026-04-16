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
