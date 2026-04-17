"""Tests for the authoring layer — natural-language prompt → AIL → answer.

These exercise the full four-step flow using a MockAdapter whose canned
responses stand in for the LLM author's output. No API key, no network.

The retry loop is also covered: an author that first emits invalid AIL
and then corrects itself must converge; one that never corrects must
surface the error transparently.
"""
from __future__ import annotations

import pytest

from ail import ask, AuthoringError
from ail.runtime.model import ModelResponse


class ScriptedAuthor:
    """Author adapter that returns a pre-scripted sequence of AIL sources.

    Intent-name "__author_ail__" is matched; other intent names (those
    inside the generated program itself) return an empty string. A real
    integration test would use a real model; these unit tests pin the
    authoring mechanics independently of model quality.
    """
    name = "scripted-author"

    def __init__(self, author_responses, intent_responses=None):
        self._author_queue = list(author_responses)
        self._intent_responses = intent_responses or {}
        self.call_log = []

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None):
        intent_name = context.get("_intent_name", "unknown")
        self.call_log.append(intent_name)
        if intent_name == "__author_ail__":
            if not self._author_queue:
                raise AssertionError("author_queue exhausted")
            source = self._author_queue.pop(0)
            return ModelResponse(
                value=source, confidence=0.95,
                model_id="scripted-author-1",
                raw={"goal": goal},
            )
        # A canned response for embedded intents inside generated programs
        value = self._intent_responses.get(intent_name, "")
        return ModelResponse(
            value=value, confidence=0.9,
            model_id="scripted-intent-1",
            raw={},
        )


# ---------- happy path ----------


def test_ask_returns_computed_value():
    # The author emits a trivially correct program; the runtime executes.
    # The test verifies the authoring layer returns the answer, not the
    # AIL source. The human sees "42", not the code that produced it.
    author = ScriptedAuthor(author_responses=[
        'entry main(x: Text) { return 42 }'
    ])
    result = ask("give me 42", adapter=author)
    assert result.value == 42
    assert result.retries == 0
    assert result.errors == []
    assert result.ail_source.startswith("entry main")


def test_ask_exposes_ail_source_for_transparency():
    # The ask() caller should still be able to see what the AI wrote,
    # for auditing or debugging. Default human-facing output is the
    # value; the source is available via the AskResult.
    src = 'pure fn double(n: Number) -> Number { return n * 2 }\nentry main(x: Text) { return double(21) }'
    result = ask("double 21", adapter=ScriptedAuthor([src]))
    assert result.value == 42
    assert "pure fn double" in result.ail_source


def test_ask_threads_through_an_intent_call():
    # Generated program itself contains an intent. The scripted adapter
    # answers that intent too. Confirms ask() runs end-to-end through
    # the full (author + executor + intent-dispatch) pipeline.
    author = ScriptedAuthor(
        author_responses=[
            'intent classify(t: Text) -> Text { goal: a_label }\n'
            'entry main(x: Text) { return classify("hi") }'
        ],
        intent_responses={"classify": "positive"},
    )
    result = ask("classify this", adapter=author)
    assert result.value == "positive"


# ---------- retry on parse failure ----------


def test_ask_retries_on_parse_error():
    # First attempt is malformed; second is correct. ask() must retry
    # and feed the parse error back to the author.
    author = ScriptedAuthor(author_responses=[
        'entry main( {',              # obvious parse error
        'entry main(x: Text) { return 7 }',
    ])
    result = ask("number please", adapter=author, max_retries=3)
    assert result.value == 7
    assert result.retries == 1
    assert len(result.errors) == 1
    assert "ParseError" in result.errors[0]


def test_ask_retries_on_purity_error():
    # Author emits a pure fn that calls an intent — caught by the
    # purity checker. ask() should retry.
    author = ScriptedAuthor(author_responses=[
        ('intent classify(t: Text) -> Text { goal: label }\n'
         'pure fn wrap(t: Text) -> Text { return classify(t) }\n'
         'entry main(x: Text) { return wrap("hi") }'),
        'entry main(x: Text) { return "ok" }',
    ])
    result = ask("do the thing", adapter=author, max_retries=3)
    assert result.value == "ok"
    assert result.retries == 1
    assert "PurityError" in result.errors[0]


def test_ask_raises_when_retry_budget_exhausted():
    # The author can never produce valid AIL. After the retry budget,
    # AuthoringError is raised and carries the partial history.
    author = ScriptedAuthor(author_responses=[
        'nonsense',
        'more nonsense',
        'still broken',
    ])
    with pytest.raises(AuthoringError) as ei:
        ask("impossible", adapter=author, max_retries=2)
    assert ei.value.partial is not None
    assert len(ei.value.partial.errors) == 3   # all three attempts failed


# ---------- fence stripping ----------


def test_ask_tolerates_markdown_fence_in_authors_output():
    # Small models sometimes wrap AIL in a ```ail ... ``` fence despite
    # being told not to. The authoring layer strips the fence before
    # parsing.
    fenced = '```ail\nentry main(x: Text) { return 99 }\n```'
    result = ask("get 99", adapter=ScriptedAuthor([fenced]))
    assert result.value == 99


def test_ask_tolerates_ail_run_cli_wrapping():
    # Observed failure mode (bench_authoring.py): model emits a shell
    # invocation rather than raw source: `ail run "fn add(...)..."`.
    # The extractor unwraps this in one shot — no retry needed.
    cli_wrapped = (
        'ail run "fn add(a: Number, b: Number) -> Number { return a + b }\\n'
        'entry main(x: Text) { return add(13, 29) }"'
    )
    result = ask("add 13 and 29", adapter=ScriptedAuthor([cli_wrapped]))
    assert result.value == 42


def test_ask_tolerates_backtick_then_ail_run_wrapping():
    # Observed combination: backticks around an ail-run shell string.
    # Both layers must come off (single-backticks first, then `ail run`).
    # Use \\\" inside the Python literal to embed escaped quotes the way
    # the model would in a shell string.
    wrapped = (
        '`ail run "pure fn char_count(s: Text) -> Number { return length(s) }\\n'
        'entry main(x: Text) { return char_count(\\"banana\\") }"`'
    )
    result = ask("count chars in banana", adapter=ScriptedAuthor([wrapped]))
    assert result.value == 6


# ---------- wiring: author model identity ----------


def test_ask_records_author_model():
    author = ScriptedAuthor(author_responses=['entry main(x: Text) { return 1 }'])
    result = ask("anything", adapter=author)
    assert result.author_model == "scripted-author"


def test_ask_call_log_shows_author_then_intent_order():
    # Confirms the authoring step happens once, then the generated
    # program is executed (and its intent, if any, runs at execution
    # time — not at authoring time).
    author = ScriptedAuthor(
        author_responses=[
            'intent label(t: Text) -> Text { goal: a_label }\n'
            'entry main(x: Text) { return label(x) }'
        ],
        intent_responses={"label": "LABELED"},
    )
    result = ask("label me", adapter=author, input_text="hello")
    assert result.value == "LABELED"
    assert author.call_log[0] == "__author_ail__"
    # The embedded intent runs after the authoring step:
    assert "label" in author.call_log[1:]
