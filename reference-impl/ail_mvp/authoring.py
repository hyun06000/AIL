"""Authoring layer — the AI-as-programmer runtime interface.

Completes the intended AIL interaction model:

    human prompt (NL)  ─►  AI writes AIL  ─►  runtime executes  ─►  result

Until now, the runtime only implemented the last two steps. The AI-writes-AIL
step happened at development time, baked into .ail files committed to the
repo. That meant using AIL felt like using a regular programming language
(write a file, run the interpreter) — which contradicted the core philosophy
("humans never read AIL code; they express intent in natural language").

This module adds the missing layer: `ask(prompt)` takes a natural-language
prompt, delegates to an LLM author that emits AIL, validates and executes
it, and returns the result. The human sees only their question and the
answer; the AIL code is transparent infrastructure.

Design choices:

- The *author* (the LLM that writes AIL) uses the same adapter as the
  *runner* (the LLM that answers intent calls during execution). In the
  common case these are the same model. A future extension could pick a
  stronger author and a cheaper runner, but that distinction is premature.
- On parse or purity failure, we feed the error back to the author and
  ask for a corrected program. Up to `max_retries` attempts; after that
  we surface the last error. Small models occasionally fumble syntax on
  first try, so self-repair is worth the round trip.
- The reference card (`spec/08-reference-card.ai.md`) is the author's
  complete language manual. We read it at import time and splice it
  into the system prompt. Keeping the spec as the single source of
  truth means improvements to the spec flow directly into authoring.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import compile_source, run
from .parser import ParseError, PurityError
from .parser.lexer import LexError
from .runtime import ConfidentValue, ModelAdapter, Trace
from .runtime.json_parsing import parse_value_confidence


# Path to the language reference card, relative to the installed package.
# `parent.parent` is `reference-impl/`, from which we reach the repo root
# and then the spec directory.
_SPEC_PATH = Path(__file__).parent.parent.parent / "spec" / "08-reference-card.ai.md"


@dataclass
class AskResult:
    """The full record of one ask() invocation.

    For everyday use, only `value` matters. The other fields exist for
    transparency — if you want to see what the AI wrote, how many retries
    it took, or inspect the trace, it's all here.
    """
    value: Any
    confidence: float
    ail_source: str
    retries: int
    trace: Trace
    author_model: str
    errors: list[str] = field(default_factory=list)


class AuthoringError(RuntimeError):
    """Raised when the author cannot produce a runnable AIL program
    within the retry budget. The underlying parse/purity/runtime errors
    are available on the `errors` attribute of the partial AskResult.
    """
    def __init__(self, msg: str, *, partial: Optional[AskResult] = None):
        super().__init__(msg)
        self.partial = partial


def ask(
    prompt: str,
    *,
    adapter: Optional[ModelAdapter] = None,
    max_retries: int = 3,
    input_text: Any = None,
) -> AskResult:
    """Translate a natural-language prompt into AIL, execute it, return the result.

    Parameters:
      prompt        The human's request in plain English (or Korean, or
                    anything the chosen model can read).
      adapter       Model adapter used both to author the AIL and to
                    answer any intent calls during execution. If None,
                    uses the same default-adapter logic as `run()`.
      max_retries   How many times to re-prompt the author if the
                    previous attempt had a parse or purity error.
      input_text    Optional value to bind to the entry's first
                    parameter. Most prompts embed all information they
                    need, so this is usually left None.

    Returns an AskResult with .value being the final answer.

    Raises AuthoringError if the author cannot produce a runnable
    program within the retry budget.
    """
    adapter = adapter or _default_adapter()
    reference_card = _load_reference_card()

    errors: list[str] = []
    ail_source = ""
    author_model = _adapter_name(adapter)

    for attempt in range(max_retries + 1):
        ail_source = _author_write_ail(
            prompt=prompt,
            reference_card=reference_card,
            adapter=adapter,
            prior_errors=errors,
        )
        try:
            compile_source(ail_source)   # parse + purity
        except (LexError, ParseError, PurityError) as e:
            errors.append(f"{type(e).__name__}: {e}")
            if attempt == max_retries:
                partial = AskResult(
                    value=None, confidence=0.0,
                    ail_source=ail_source, retries=attempt,
                    trace=Trace(), author_model=author_model,
                    errors=list(errors),
                )
                raise AuthoringError(
                    f"author failed to produce valid AIL after {attempt + 1} tries; "
                    f"last error: {errors[-1]}",
                    partial=partial,
                ) from e
            continue
        break
    else:
        # Should be unreachable given the raise above, but keep mypy quiet.
        raise AuthoringError("author loop exited unexpectedly")

    # Execute. Any runtime error (including intent failures) is surfaced
    # to the caller rather than swallowed — the human asked a question;
    # they deserve to see an explanation when something went wrong.
    result, trace = run(ail_source, input=input_text, adapter=adapter)

    return AskResult(
        value=result.value,
        confidence=result.confidence,
        ail_source=ail_source,
        retries=attempt,
        trace=trace,
        author_model=author_model,
        errors=list(errors),
    )


# --- internals ---

def _author_write_ail(
    *,
    prompt: str,
    reference_card: str,
    adapter: ModelAdapter,
    prior_errors: list[str],
) -> str:
    """Invoke the adapter as an AIL author and return the raw AIL source.

    We reuse the adapter's intent-execution pathway rather than building a
    parallel prompt plumbing. An author call is just an intent with a
    carefully constructed goal and a plain-text expected type. The
    adapter's `invoke` returns a ModelResponse whose `value` we
    interpret as the AIL source.

    Small models often ignore instructions about which JSON key to use
    and produce shapes like {"output": "...", "type": "Text"} or
    {"code": "..."}. We tolerate any top-level string value as the AIL
    source — the key name is cosmetic once we've extracted the content.
    """
    goal = _build_authoring_goal()
    constraints = _build_authoring_constraints(prior_errors)

    response = adapter.invoke(
        goal=goal,
        constraints=constraints,
        context={
            "_intent_name": "__author_ail__",
            "reference_card": reference_card,
        },
        inputs={"prompt": prompt},
        expected_type="Text (AIL source)",
        examples=_authoring_examples(),
    )
    return _coerce_to_ail_source(response.value)


def _coerce_to_ail_source(raw: Any) -> str:
    """Extract AIL source from whatever shape the model returned.

    Accepts, in order:
      1. A plain string — the ideal case; used directly.
      2. A dict with a "value" key holding a string.
      3. A dict with any other top-level string value (accommodates
         models that call the field "output", "code", "source", etc.).
      4. A nested string found via the tolerant JSON extractor.
      5. A final str() fallback so we always return a string to parse.

    The value is passed through _strip_source_fence to remove markdown
    fences the model may have added despite being told not to.
    """
    if isinstance(raw, str):
        return _strip_source_fence(_unwrap_json_if_any(raw))
    if isinstance(raw, dict):
        # Preferred key — honored when the model followed instructions.
        if "value" in raw and isinstance(raw["value"], str):
            return _strip_source_fence(raw["value"])
        # Any other top-level string. Take the longest one, which is
        # almost always the code (versus a short "type" marker).
        str_values = [v for v in raw.values() if isinstance(v, str)]
        if str_values:
            longest = max(str_values, key=len)
            return _strip_source_fence(longest)
    # Last-ditch: stringify and let the tolerant parser try.
    unwrapped, _ = parse_value_confidence(str(raw))
    if isinstance(unwrapped, str):
        return _strip_source_fence(unwrapped)
    return _strip_source_fence(str(raw))


def _unwrap_json_if_any(s: str) -> str:
    """If `s` is itself a JSON object wrapping the AIL source, unwrap it.

    This handles the case where the adapter returned a string containing
    JSON rather than a parsed dict — common when adapters fall through
    their JSON detection on unexpected shapes.
    """
    stripped = s.strip()
    if not stripped.startswith("{"):
        return s
    import json as _json
    try:
        obj = _json.loads(stripped)
    except _json.JSONDecodeError:
        return s
    if isinstance(obj, dict):
        for k in ("value", "source", "code", "output", "program", "ail"):
            if k in obj and isinstance(obj[k], str):
                return obj[k]
        str_values = [v for v in obj.values() if isinstance(v, str)]
        if str_values:
            return max(str_values, key=len)
    return s


def _build_authoring_goal() -> str:
    # Deliberately verbose. Small models read the prompt literally; saying
    # "return the answer" makes them return the answer itself, not code
    # that computes the answer. We hammer the distinction multiple ways.
    return (
        "You are an AIL source-code author. Your output is source code, "
        "not an answer. The 'value' field of your response MUST be a "
        "string containing a complete AIL program. When the user says "
        "'return 42', you write AIL code that prints 42 — you do NOT "
        "put 42 in the value field. When the user says 'count vowels', "
        "you write AIL code that counts vowels — you do NOT put a number "
        "in the value field. The value is always AIL source text, no "
        "exceptions. Read the EXAMPLES carefully — they show what the "
        "value field should contain for each kind of prompt."
    )


def _build_authoring_constraints(prior_errors: list[str]) -> list[str]:
    base = [
        "program_has_exactly_one_entry_declaration",
        "entry_signature_is_main_with_one_Text_parameter",
        "entry_returns_the_answer_directly",
        "prefer_pure_fn_over_fn_when_no_llm_call_is_needed",
        "use_intent_only_when_the_task_requires_judgment",
        "no_markdown_fence_in_output",
    ]
    # If we've retried, include the prior error text as a correction hint.
    if prior_errors:
        base.append("previous_attempt_failed_with: " + prior_errors[-1])
    return base


def _strip_source_fence(text: str) -> str:
    """Extract AIL source from a possibly-prose-wrapped response.

    Tolerates three shapes the model commonly produces:
      1. Raw AIL — returned unchanged.
      2. AIL wrapped in a ``` fence at the very start — fence stripped.
      3. AIL embedded inside explanatory prose with one or more ``` fenced
         blocks — the longest fenced block is extracted (likely the code,
         versus a shorter inline snippet).

    The third case appears whenever the model ignores "no prose" and
    writes a paragraph like "Here is the code: ```ail ...```" — common
    enough on small models that we should just absorb it.
    """
    s = text.strip()
    # Case 2: starts with a triple-backtick fence — strip wrapping.
    if s.startswith("```"):
        nl = s.find("\n")
        if nl >= 0:
            body = s[nl + 1:]
            if body.endswith("```"):
                body = body[:-3]
            s = body.strip()
    # Case 2b: single-backtick wrapping of the whole content.
    elif s.startswith("`") and s.endswith("`") and len(s) >= 2:
        s = s[1:-1].strip()
    # Case 2c: starts with a single backtick, has a closing backtick
    # somewhere, then trailing prose (e.g. an OUTPUT/CONFIDENCE block
    # appended by a chatty model). Extract the content of the first
    # backtick-delimited region.
    elif s.startswith("`") and "`" in s[1:]:
        end = s.index("`", 1)
        s = s[1:end].strip()
    # Case 3: prose with embedded fence(s). Find them all and take the
    # longest content block. Handles ```ail, ```, ```python (model
    # mislabeling), etc.
    else:
        blocks = _extract_fenced_blocks(s)
        if blocks:
            s = max(blocks, key=len).strip()
    # Case 4: model wrapped the source in a CLI invocation
    # (`ail run "..."` or `ail-go run "..."`). Strip the wrapper and
    # unescape the embedded source. This was the dominant failure mode
    # observed in tools/bench_authoring.py against llama3.1:8B; fixing
    # it here is a pure tolerance win that doesn't perturb the prompt.
    s = _strip_ail_run_wrapper(s)
    # Case 5: small models occasionally use single quotes for string
    # literals (`'banana'`) — common in Python and shell, never valid
    # AIL. Replace ' with " on stripped source. The risk (legitimate
    # apostrophe inside a "..." string) is theoretical in practice;
    # programs containing apostrophe data should use the input channel,
    # not embed the literal in source.
    s = _normalize_single_quotes(s)
    return s


def _normalize_single_quotes(s: str) -> str:
    """Convert ' to " in extracted AIL source.

    Conservative when possible: if the source contains zero `'`, do
    nothing. Otherwise replace globally. Done after fence/wrapper
    extraction so we never touch the user's actual prose, only the
    candidate AIL we believe the model intended.
    """
    if "'" not in s:
        return s
    return s.replace("'", '"')


def _strip_ail_run_wrapper(s: str) -> str:
    """If `s` looks like `ail run "..."`, extract the quoted body.

    Accepts variants: `ail run`, `ail-go run`, `python -m ail_mvp.cli run`,
    optional `--input ...` flags. Any leading non-quote prefix up to the
    first quote, then everything up to the last quote, is treated as the
    AIL source. Embedded `\\n` and `\\"` sequences are unescaped because
    the model was string-quoting the source for shell.
    """
    stripped = s.lstrip()
    triggers = ("ail run", "ail-go run", "ail-go", "python -m ail_mvp",
                "python -m ail")
    if not any(stripped.startswith(t) for t in triggers):
        return s
    q_open = s.find('"')
    if q_open < 0:
        return s
    q_close = s.rfind('"')
    if q_close <= q_open:
        return s
    body = s[q_open + 1:q_close]
    # Unescape what the model thought was shell-string content.
    body = body.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
    return body.strip()


def _extract_fenced_blocks(text: str) -> list[str]:
    """Return the contents of every ``` ... ``` block in `text`."""
    blocks: list[str] = []
    i = 0
    while True:
        start = text.find("```", i)
        if start < 0:
            break
        # Skip the opening fence's first line (may include a language tag).
        body_start = text.find("\n", start + 3)
        if body_start < 0:
            break
        end = text.find("```", body_start + 1)
        if end < 0:
            break
        blocks.append(text[body_start + 1:end])
        i = end + 3
    return blocks


def _authoring_examples() -> list[tuple[list[Any], Any]]:
    """Few-shot pairs that pin the authoring shape.

    Each (inputs, output) pair demonstrates that 'output' is an AIL
    SOURCE STRING, not the result of running the AIL. Small models
    anchor strongly to demonstrated format, so two or three examples
    reliably correct the "return the answer literally" failure mode.

    Keep the example programs short — their role is to show shape, not
    range. The reference card already supplies the full surface.
    Empirical note: bench_authoring.py shows that ADDING more examples
    can hurt — the model starts emitting more elaborate code that hits
    edge cases (e.g. unsupported `[Number]` type syntax in fn
    signatures). Fewer, simpler examples win.
    """
    return [
        (
            [{"prompt": "Return the number 42"}],
            'entry main(x: Text) { return 42 }',
        ),
        (
            [{"prompt": "Count the vowels in 'Hello World'"}],
            (
                'pure fn is_vowel(c: Text) -> Boolean {\n'
                '    return c in ["a", "e", "i", "o", "u"]\n'
                '}\n'
                'pure fn count_vowels(s: Text) -> Number {\n'
                '    total = 0\n'
                '    for c in split(lower(s), "") {\n'
                '        if is_vowel(c) { total = total + 1 }\n'
                '    }\n'
                '    return total\n'
                '}\n'
                'entry main(x: Text) { return count_vowels("Hello World") }'
            ),
        ),
        (
            [{"prompt": "Is 'great!' positive or negative sentiment?"}],
            (
                'intent classify_sentiment(text: Text) -> Text {\n'
                '    goal: positive_or_negative\n'
                '}\n'
                'entry main(x: Text) { return classify_sentiment("great!") }'
            ),
        ),
    ]


def _load_reference_card() -> str:
    try:
        return _SPEC_PATH.read_text(encoding="utf-8")
    except OSError:
        # If the spec is not reachable from the installed package
        # (e.g. packaged without the repo), return a terse fallback
        # that names the essential constructs. Programs generated
        # under this fallback will be simple but may still run.
        return (
            "AIL is an AI-native language. A program has one "
            "`entry main(input: Text) { return EXPR }` plus optional "
            "fn/pure fn/intent declarations. Builtins: length, split, "
            "join, append, range, to_text, to_number, upper, lower, "
            "trim, get, ok, error, is_ok, is_error, unwrap, unwrap_or."
        )


def _adapter_name(adapter: ModelAdapter) -> str:
    return getattr(adapter, "name", adapter.__class__.__name__)


def _default_adapter() -> ModelAdapter:
    # Reuse the top-level package's default-adapter logic so `ask()`
    # and `run()` behave consistently with env vars.
    from . import _default_adapter as pkg_default
    return pkg_default()
