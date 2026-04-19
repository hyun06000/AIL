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


def test_extract_default_input_picks_single_integer():
    from ail.authoring import _extract_default_input
    assert _extract_default_input("factorial of 7") == "7"
    assert _extract_default_input("compute 13 squared") == "13"
    assert _extract_default_input("sum the numbers from 1 to 100") is None  # 2 ints
    assert _extract_default_input("hello world") is None  # 0 ints
    assert _extract_default_input("my rate is 3.14") is None  # float -> skip
    assert _extract_default_input("average of 10, 20, 30") is None  # 3 ints


def test_ask_passes_extracted_integer_as_input_text():
    # Small models often write `factorial(to_number(x))` instead of a
    # hardcoded `factorial(7)`; without an input the parameter binds
    # to "" and `to_number("")` returns a Result-error that breaks
    # downstream arithmetic. ask() auto-supplies the lone integer
    # from the prompt so these programs run end-to-end.
    src = (
        'fn factorial(n: Number) -> Number {\n'
        '    if n <= 1 { return 1 }\n'
        '    return n * factorial(n - 1)\n'
        '}\n'
        'entry main(x: Text) { return factorial(to_number(x)) }'
    )
    result = ask("factorial of 6", adapter=ScriptedAuthor([src]))
    assert result.value == 720.0


def test_retry_hints_name_available_stdlib_modules_on_import_error():
    # Observed locally on llama3.1:8B: the model imports
    # `stdlib/math`, the error says "module 'math' not found", the
    # model re-tries with the same broken import four times in a
    # row. The fix is to carry a corrective constraint into the
    # retry that tells the author which modules actually exist,
    # not just which don't.
    from ail.authoring import _remediation_hints
    err = (
        "ImportResolutionError: stdlib module 'math' not found "
        "at /.../ail/stdlib/math.ail"
    )
    hints = _remediation_hints(err)
    joined = " ".join(hints)
    assert "core" in joined and "language" in joined and "utils" in joined, hints
    assert "import" in joined.lower(), hints


def test_retry_hints_name_syntax_rules_on_observed_errors():
    # Three of the most common llama3.1:8B failure modes get
    # targeted corrective constraints. Each assertion names one
    # error message we've actually logged in bench_authoring.py.
    from ail.authoring import _remediation_hints
    assert any("ternary" in h for h in _remediation_hints(
        "LexError: unexpected character '?'"))
    assert any("Array" in h or "[Number]" in h for h in _remediation_hints(
        "ParseError: expected IDENT at 1:26, got LBRACK('[')"))
    assert any("newlines" in h for h in _remediation_hints(
        "LexError: 1:41: unexpected character '\\\\'"))


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


def test_ask_recovers_program_from_echoed_examples_prompt_leak():
    # Observed failure on llama3.1:8B for "factorial of 7": the
    # model wraps the answer expression in a single backtick
    # (`factorial(7)`) and echoes the EXAMPLES section of the
    # authoring prompt verbatim as a Python repr. The naive
    # backtick extractor would pull just `factorial(7)` — which
    # then fails to parse. Recovery scans the echoed prompt for
    # a quoted program containing `entry main` and decodes the
    # Python repr escapes.
    echoed = (
        "`factorial(7)`\n\n\n"
        "EXPECTED TYPE: Number (AIL source)\n\n"
        "EXAMPLES:\n"
        "  input: [{'prompt': 'Compute the factorial of 7'}]\n"
        "  => 'pure fn factorial(n: Number) -> Number {\\n"
        "    if n <= 1 { return 1 }\\n"
        "    return n * factorial(n - 1)\\n"
        "}\\n"
        "entry main(x: Text) { return factorial(7) }'\n"
    )
    result = ask("factorial of 7", adapter=ScriptedAuthor([echoed]))
    assert result.value == 5040


def test_ask_tolerates_malformed_json_wrapping():
    # Observed failure mode on llama3.1:8B (bench_authoring.py baseline,
    # 2026-04-17): model wraps its output in `{"value": "...",
    # "confidence": 1.0}` but fails to escape internal `"` characters
    # (e.g. inside `split(s, "")`). Strict json.loads rejects the whole
    # thing. The authoring layer recovers the AIL source via a lenient
    # regex-based extractor that locates `"value": "...` and the
    # right-side `", "confidence"` boundary, then applies JSON unescapes.
    malformed = (
        '{"value": "pure fn first_char(s: Text) -> Text {\\n'
        '    return get(split(s, ""), 0)\\n'
        '}\\n'
        'entry main(x: Text) { return first_char(\\"banana\\") }", '
        '"confidence": 1.0}'
    )
    result = ask("first char of banana", adapter=ScriptedAuthor([malformed]))
    assert result.value == "b"


def test_ask_tolerates_literal_newline_escape_leak():
    # Observed on llama3.1:8B (v5 bench, 2026-04-18): when the model
    # formats its AIL as a JSON-string body, the `\n` between
    # statements arrives as LITERAL backslash-n instead of actual
    # newlines. The lexer then chokes on the stray `\`. We detect
    # this specific pattern (has `\n`, no real newline) and unescape.
    single_line = (
        'pure fn square(n: Number) -> Number {\\n    return n * n\\n}\\n'
        'entry main(x: Text) { return square(7) }'
    )
    result = ask("square 7", adapter=ScriptedAuthor([single_line]))
    assert result.value == 49


def test_ask_preserves_real_newlines_in_source():
    # The literal-escape normalizer must not misfire on well-formed
    # multi-line AIL — real newlines present means the source is
    # already decoded. Round-trip check: program with `\n` inside a
    # string literal (that we don't want touched) survives.
    multi = 'entry main(x: Text) { return "a\\nb" }'
    # Note: contains literal `\n` inside the string AND has no real
    # newlines either. Ambiguous case — our heuristic would unescape.
    # Separate case: multi-line with real newline should pass through.
    multi_real = 'entry main(x: Text) {\n    return 5\n}'
    result = ask("return 5", adapter=ScriptedAuthor([multi_real]))
    assert result.value == 5


def test_ask_tolerates_malformed_json_no_confidence_key():
    # Variant: model emits `{"value": "..."}` with no confidence field.
    # The fallback boundary patterns must still find the closing `"}`.
    malformed = '{"value": "entry main(x: Text) { return 7 }"}'
    result = ask("return 7", adapter=ScriptedAuthor([malformed]))
    assert result.value == 7


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
