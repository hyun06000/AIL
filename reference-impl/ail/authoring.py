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
from .stdlib import ImportResolutionError


# The language reference card. We try two locations so the same code
# works in both shapes:
#   1. A copy bundled INSIDE the package (`ail/reference_card.md`) —
#      this is what wheel users get. It ships with every release and
#      is kept identical to the canonical spec by tests/test_spec_bundled.py.
#   2. The canonical spec file in the repo's `spec/` directory —
#      this is what contributors on a fresh checkout hit when the
#      bundled copy hasn't been refreshed yet. Picked up via
#      `Path(__file__).parent.parent.parent / "spec" / ...`.
# First file found wins; the fallback in `_load_reference_card` runs
# only if neither exists (edge case, e.g. installing the source tar
# without the spec file).
_SPEC_CANDIDATES = [
    Path(__file__).parent / "reference_card.md",
    Path(__file__).parent.parent.parent / "spec" / "08-reference-card.ai.md",
]


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
    author_prompt_tokens: int = 0
    author_completion_tokens: int = 0


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
    # If the caller didn't pin an input and the prompt contains a bare
    # integer, pass that integer as the input. Small models frequently
    # parameterize the entry (`factorial(to_number(x))`) even after
    # being told to hardcode; without an input the bound x is empty,
    # `to_number("")` returns a Result-wrapped error, and simple
    # programs blow up (e.g. a factorial recurses forever because its
    # `n <= 1` base case never matches the error value). Supplying the
    # obvious integer rescues the common case with zero author-side
    # cost. Falls back silently on ambiguous prompts (multiple numbers,
    # floats, Korean numerals, etc.).
    if input_text is None:
        input_text = _extract_default_input(prompt)

    errors: list[str] = []
    ail_source = ""
    author_model = _adapter_name(adapter)

    # Catches every error class that is recoverable by re-prompting the
    # author. LexError / ParseError / PurityError fire at compile time;
    # ImportResolutionError fires later when the program tries to resolve
    # an import that doesn't exist. All are author mistakes and worth a
    # retry with the error fed back in.
    _retryable = (LexError, ParseError, PurityError, ImportResolutionError)

    result = None
    trace = Trace()
    total_author_prompt_tokens = 0
    total_author_completion_tokens = 0
    for attempt in range(max_retries + 1):
        ail_source, author_tokens = _author_write_ail(
            prompt=prompt,
            reference_card=reference_card,
            adapter=adapter,
            prior_errors=errors,
        )
        total_author_prompt_tokens += author_tokens["prompt_tokens"]
        total_author_completion_tokens += author_tokens["completion_tokens"]
        try:
            compile_source(ail_source)   # parse + purity
            result, trace = run(ail_source, input=input_text, adapter=adapter)
        except _retryable as e:
            errors.append(f"{type(e).__name__}: {e}")
            if attempt == max_retries:
                partial = AskResult(
                    value=None, confidence=0.0,
                    ail_source=ail_source, retries=attempt,
                    trace=Trace(), author_model=author_model,
                    errors=list(errors),
                    author_prompt_tokens=total_author_prompt_tokens,
                    author_completion_tokens=total_author_completion_tokens,
                )
                raise AuthoringError(
                    f"author failed to produce valid AIL after {attempt + 1} tries; "
                    f"last error: {errors[-1]}",
                    partial=partial,
                ) from e
            continue
        break
    else:
        raise AuthoringError("author loop exited unexpectedly")

    assert result is not None   # loop must have set it on break

    return AskResult(
        value=result.value,
        confidence=result.confidence,
        ail_source=ail_source,
        retries=attempt,
        trace=trace,
        author_model=author_model,
        errors=list(errors),
        author_prompt_tokens=total_author_prompt_tokens,
        author_completion_tokens=total_author_completion_tokens,
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
    raw = response.raw or {}
    tokens = {
        "prompt_tokens": raw.get("prompt_tokens") or raw.get("input_tokens") or 0,
        "completion_tokens": raw.get("completion_tokens") or raw.get("output_tokens") or 0,
    }
    return _coerce_to_ail_source(response.value), tokens


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

    When `json.loads` fails (the model's AIL value contains unescaped
    `"` characters, a frequent failure mode on 8B-class models), fall
    back to a lenient regex-based extraction. `bench_authoring.py`
    showed this wrapper-leak was the dominant cause of hybrid-case
    failures on llama3.1:8B — the model correctly wrapped its output
    in `{"value": "..."}` but forgot to escape internal quotes, so
    strict JSON parsing rejected it and the parser then barfed on the
    leading `{`. The lenient path recovers the AIL source anyway.
    """
    stripped = s.strip()
    if not stripped.startswith("{"):
        return s
    import json as _json
    try:
        obj = _json.loads(stripped)
    except _json.JSONDecodeError:
        lenient = _lenient_value_extract(stripped)
        return lenient if lenient is not None else s
    if isinstance(obj, dict):
        for k in ("value", "source", "code", "output", "program", "ail"):
            if k in obj and isinstance(obj[k], str):
                return obj[k]
        str_values = [v for v in obj.values() if isinstance(v, str)]
        if str_values:
            return max(str_values, key=len)
    return s


def _lenient_value_extract(s: str) -> str | None:
    """Recover the AIL source from `{"value": "...", ...}` when strict
    JSON parsing fails.

    Strategy: locate the `"value":` key, take everything from the
    opening `"` up to the right-side boundary (`", "confidence"` if
    present, else `", "<any other key>"`, else the final `"}`).
    Unescape JSON escape sequences.

    Returns the extracted AIL source string, or None if no plausible
    value region could be found. Conservative: if in doubt, returns
    None so the caller keeps the original string unchanged.
    """
    import re
    m = re.search(r'"value"\s*:\s*"', s)
    if not m:
        return None
    start = m.end()
    # Preferred right boundary: the confidence field's opening quote.
    # Use the LAST occurrence — the AIL source may contain the literal
    # substring `"confidence"` as a string constant inside its own code.
    boundary_patterns = [
        r'"\s*,\s*"confidence"',
        r'"\s*,\s*"[A-Za-z_]+"\s*:',
        r'"\s*}\s*$',
    ]
    body = s[start:]
    for pattern in boundary_patterns:
        matches = list(re.finditer(pattern, body))
        if matches:
            end = matches[-1].start()
            return _unescape_json_string(body[:end])
    # Fallback: right-most `"` in the string.
    last_quote = body.rfind('"')
    if last_quote > 0:
        return _unescape_json_string(body[:last_quote])
    return None


def _unescape_json_string(s: str) -> str:
    """Apply the standard JSON escape sequences to a raw extracted
    value. Handles \\n, \\t, \\r, \\", \\\\, \\/. Unknown escapes pass
    through literally (preserving the backslash), which is safer than
    dropping characters when the value contains shell-style escapes
    the model used incorrectly.
    """
    out: list[str] = []
    i = 0
    mapping = {
        'n': '\n', 't': '\t', 'r': '\r',
        '"': '"', '\\': '\\', '/': '/',
    }
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s) and s[i + 1] in mapping:
            out.append(mapping[s[i + 1]])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _build_authoring_goal() -> str:
    # Deliberately verbose. Small models read the prompt literally; saying
    # "return the answer" makes them return the answer itself, not code
    # that computes the answer. We hammer the distinction multiple ways.
    #
    # The second half — the fn/intent decision block — addresses the
    # issue Opus 4 flagged in CLAUDE.md: small models cannot choose
    # between `fn` (computation) and `intent` (judgment) without
    # concrete rules. The abstract constraint
    # `prefer_pure_fn_over_fn_when_no_llm_call_is_needed` by itself was
    # insufficient — bench_authoring.py showed 8B-class models would
    # either avoid `intent` entirely or declare one and never call it.
    # The explicit rules and the hybrid example in `_authoring_examples`
    # work together to pin the correct pattern.
    import os
    variant = os.environ.get("AIL_AUTHOR_PROMPT_VARIANT")
    if variant == "tutorial":
        # Tutorial-derived prompt. Source of truth: spec/09-fewshot-
        # tutorial.ai.md. Two things distinguish this from the default:
        #   (a) decision rules in table form (more compact than the
        #       default prose lists)
        #   (b) explicit intent-goal text constraints — the default
        #       prompt does not warn the model that the parser reads
        #       goal text as expressions, so commas / em-dashes / the
        #       word `for` inside a goal break parsing. C16 in the
        #       Opus 50 corpus is a documented case
        #       ("for a teenager" → ParseError "expected `in`").
        # Used by the v1.8.4 A/B benchmark to measure prompt-only lift
        # on a base model.
        return _tutorial_authoring_goal()
    base = (
        "You are an AIL source-code author. Your output is source code, "
        "not an answer. The 'value' field of your response MUST be a "
        "string containing a complete AIL program. When the user says "
        "'return 42', you write AIL code that prints 42 — you do NOT "
        "put 42 in the value field. When the user says 'count vowels', "
        "you write AIL code that counts vowels — you do NOT put a number "
        "in the value field. The value is always AIL source text, no "
        "exceptions. Read the EXAMPLES carefully — they show what the "
        "value field should contain for each kind of prompt.\n\n"
        "DECIDING fn vs intent — this is the most important choice you "
        "make when writing AIL. Every subtask routes through one of:\n\n"
        "USE `fn` (or `pure fn`) WHEN the answer is computable:\n"
        "  * counting, summing, averaging, any arithmetic\n"
        "  * parsing, splitting, joining, slicing, reversing text\n"
        "  * sorting, filtering, deduplicating, taking first N\n"
        "  * comparing numbers or strings\n"
        "  * converting types (to_number, to_text, upper, lower)\n"
        "  * iterating a bounded collection to accumulate a result\n"
        "  * anything with one deterministic, mechanical answer\n\n"
        "USE `intent` WHEN the answer requires judgment about meaning:\n"
        "  * classifying sentiment, tone, topic, or category\n"
        "  * summarizing natural-language text\n"
        "  * translating between languages\n"
        "  * judging whether a word is formal, rare, unique, polite\n"
        "  * rewriting text in a different style\n"
        "  * extracting facts that require reading comprehension\n"
        "  * any subjective or meaning-based interpretation\n\n"
        "HYBRID: many prompts need BOTH. 'Count the words in X and "
        "classify its sentiment' → one `pure fn` counts, one `intent` "
        "classifies, the entry combines them. If the prompt has an "
        "'and' joining a computable subtask with a judgment subtask, "
        "you almost certainly want a hybrid program.\n\n"
        "WHEN UNSURE, prefer `fn`. Only reach for `intent` when the "
        "subtask genuinely cannot be expressed as computation.\n\n"
        "CRITICAL RULE: if you declare an `intent`, the entry MUST "
        "actually call it — either directly, or via a `fn` that calls "
        "it. An intent that is declared but never invoked is an "
        "authoring error. Trace every entry return value back to the "
        "subtasks that produce it.\n\n"
        "Simple arithmetic (factorial, sum, count, fibonacci, etc.) — "
        "write a short `pure fn` inline and call it from the entry. "
        "DO NOT import anything for these. The only stdlib modules "
        "that exist are `stdlib/core`, `stdlib/language`, and "
        "`stdlib/utils`; any other import (`stdlib/math`, `stdlib/io`, "
        "etc.) is an error — those modules exist in Python but NOT in "
        "AIL.\n\n"
        "FORBIDDEN SYNTAX — the AIL parser rejects every item below. "
        "These are Python habits that break in AIL:\n"
        "  * List type annotations ARE supported: `items: [Number]`, "
        "`items: [Text]`, `-> [Number]` are all valid. However dict/map "
        "types are NOT: `{Text: Number}`, `Array<Text>`, `Tuple[A, B]`.\n"
        "  * Dict / map types and literals: `{Text: Number}`, `{}`, "
        "`{\"a\": 1}`. AIL has NO map type. For key-value data, encode "
        "as `\"key:value\"` text and use `split()` to parse.\n"
        "  * Dict subscript assignment: `d[key] = val`. Not valid. "
        "Build output as a list of strings and join at the end.\n"
        "  * Keyword arguments: `fn(x=5)`, `sort(nums, reverse=true)`, "
        "`join(items, sep=\",\")`. AIL uses positional arguments only. "
        "For descending sort: `reverse(sort(x))`.\n"
        "  * Exponentiation `**`: `x ** 2` is not valid. Write "
        "`x * x` for squares; implement repeated multiplication in a "
        "`pure fn` for higher powers.\n"
        "  * Import with dot or alias: `import stdlib.utils`, "
        "`import X as Y`. Write `import sum_list from \"stdlib/utils\"`.\n"
        "  * `reverse()` on a Text value: `reverse(s)` where `s` is "
        "Text returns a list of characters, not a string. To reverse a "
        "string, write: `join(reverse(split(s, \"\")), \"\")`.\n"
        "  * Python keywords: `def`, `lambda`, `None`, `elif`, `pass`, "
        "`True`, `False`, `while`. AIL equivalents: `fn`/`pure fn`/"
        "`intent`, no-null (use `\"\"` or `0`), `else if`, no pass, "
        "`true`/`false`, `for x in range(...)`.\n"
        "  * Calling `intent` from inside a `pure fn`. A `pure fn` CANNOT "
        "call an intent — doing so is a purity violation. Only the `entry` "
        "block coordinates fn and intent. Pattern: `pure fn` parses/computes "
        "→ `entry` calls both fn and intent and assembles the result.\n"
        "When in doubt about a syntax pattern, write it out with "
        "explicit `for` loops and `if` branches — those always work."
    )
    # ────────────────────────────────────────────────────────────────
    # Optional v2 FORBIDDEN-SYNTAX extension.
    # Enabled by AIL_AUTHOR_PROMPT_VARIANT=v2 at inference time. The
    # block enumerates concrete syntax patterns observed (in the Opus
    # 50-prompt benchmark on qwen2.5-coder:14b) to leak from the
    # model's Python training into AIL output. Keeping it behind a
    # flag makes the A/B measurable: same model, same corpus, only
    # the prompt differs.
    # ────────────────────────────────────────────────────────────────
    if variant == "v2":
        base += (
            "\n\n"
            "FORBIDDEN SYNTAX — the AIL parser will reject every item "
            "below. Do NOT emit any of them. The model's Python training "
            "makes these tempting; suppress them explicitly.\n"
            "  * Dict/map type annotations: `Dict[K,V]`, `{Text: Number}`, "
            "`Tuple[Number, Text]`, `Array<Text>`. List annotations "
            "`[Number]` and `[Text]` ARE valid. Map types are not.\n"
            "  * Ternary operator: `a ? b : c`. Use an explicit `if a { "
            "return b } else { return c }` or `if a { ... }` followed "
            "by a return.\n"
            "  * stdlib imports that do not exist: `stdlib/math`, "
            "`stdlib/io`, `stdlib/string(s)`, `stdlib/json`, "
            "`stdlib/datetime`, `stdlib/re`. Only `stdlib/core`, "
            "`stdlib/language`, and `stdlib/utils` exist.\n"
            "  * Method-call syntax on non-objects: `\"hello\".upper()`. "
            "Write `upper(\"hello\")`. Same for `.split()`, `.length`, "
            "`.append(x)`.\n"
            "  * List comprehensions: `[x * 2 for x in xs]`. Write a "
            "`for` loop that appends to a list.\n"
            "  * Python-only keywords: `def`, `lambda`, `None`, `elif`, "
            "`pass`. AIL uses `fn` / `pure fn` / `intent`, full `if / "
            "else if / else`, and has no null sentinel.\n"
            "  * Capitalised booleans: `True`, `False`. AIL uses "
            "lowercase `true`, `false`.\n"
            "If the task seems to need any of the forbidden patterns, "
            "re-express the computation using only the forms the "
            "reference card shows."
        )
    return base


def _tutorial_authoring_goal() -> str:
    """Prompt body derived from spec/09-fewshot-tutorial.ai.md.

    Differences from the default prompt:
      - Decision rules in table form (table parses faster for AI
        readers than prose bullet lists).
      - Adds INTENT GOAL TEXT constraints (lexer/parser limits on
        `goal:` body) — not present in any other variant. Closes the
        documented C16-class failure where goal prose contains
        commas, em-dashes, or AIL keywords.
      - Reuses the existing FORBIDDEN-SYNTAX content from v2 in a
        compressed form so the variant is self-contained.
      - The 3 demonstration examples paired with this prompt come
        from `_tutorial_examples()` (see `_authoring_examples`).
    """
    return (
        "You are an AIL source-code author. Your output is source code, "
        "not an answer. The 'value' field of your response MUST be a "
        "complete AIL program that, when executed, produces the answer "
        "the user asked for. When the user says 'factorial of 7' you "
        "write AIL that computes 5040 — you do NOT put 5040 in value. "
        "Read the EXAMPLES carefully — they show what the value field "
        "looks like for each kind of prompt.\n\n"
        "DECISION TABLE — fn vs intent.\n\n"
        "| Task | Use | Why |\n"
        "|------|-----|-----|\n"
        "| Add 7 + 5 | pure fn | Computable. |\n"
        "| Sort [3,1,2] | pure fn | Algorithm. |\n"
        "| Count vowels | pure fn | Iterate + compare. |\n"
        "| Parse \"Alice:85\" | pure fn | Split structured data. |\n"
        "| Classify \"I love this\" | intent | Requires meaning. |\n"
        "| Translate to Korean | intent | Cross-language meaning. |\n"
        "| Summarise paragraph | intent | Judgment. |\n"
        "| Spam detection | intent | Subjective. |\n"
        "| Generate creative title | intent | New language. |\n\n"
        "Rule of thumb: write the algorithm if you can. Use intent "
        "only when you need to know what words MEAN. When unsure, "
        "default to pure fn. Hybrid programs declare BOTH.\n\n"
        "EVERY DECLARED `intent` MUST BE INVOKED in the entry. An "
        "intent that is declared and never called is an authoring "
        "error.\n\n"
        "INTENT GOAL TEXT — non-obvious constraint. The parser reads "
        "the text after `goal:` as AIL expressions, so the body must "
        "be syntactically clean:\n"
        "  * ASCII only — no unicode dashes (`-` not `\\u2014`), no "
        "ellipsis (`...` not `\\u2026`).\n"
        "  * No commas in goal text. Commas are only valid inside "
        "list literals and argument lists.\n"
        "  * No colons — the leading `goal:` already used the colon.\n"
        "  * Avoid AIL keywords as words inside the goal: for, in, "
        "if, else, return, true, false, attempt, try, match, branch, "
        "with, evolve, effect, entry, import, pure, fn, intent, "
        "perform. The boolean operators and / or / not are tolerated.\n"
        "  * Keep it terse — usually under 12 words. Long prose goals "
        "are NOT better than short ones.\n"
        "  * Good: `goal: positive_or_negative`. Good: `goal: the "
        "single most salient topic word`. BAD: `goal: classify, "
        "for example, as positive or negative`.\n\n"
        "FORBIDDEN SYNTAX — the parser will reject every item below. "
        "The model's Python prior makes these tempting; suppress them.\n"
        "  * List type annotations ARE supported: `items: [Number]`, "
        "`-> [Text]` are valid. Dict/map types are NOT: `{Text: Number}`, "
        "`Tuple[A, B]`, `Array<Text>`.\n"
        "  * Dict / map types and literals: `{Text: Number}`, `{}`, "
        "`{\"k\": 1}`. AIL has NO map type. Encode key-value pairs as "
        "`\"key:value\"` text and parse with `split()`.\n"
        "  * Dict subscript assignment: `d[key] = val`. Not valid.\n"
        "  * Keyword arguments: `fn(x=5)`, `sort(nums, reverse=true)`, "
        "`join(items, sep=\",\")`. AIL positional only. Descending: `reverse(sort(x))`.\n"
        "  * Exponentiation `**`: write `x * x` for squares; implement "
        "repeated multiplication in a `pure fn` for higher powers.\n"
        "  * `reverse()` on Text: returns a list, not a string. To "
        "reverse a string: `join(reverse(split(s, \"\")), \"\")`.\n"
        "  * Ternary: `a ? b : c`. Use `if a { return b } else { "
        "return c }`.\n"
        "  * Slice subscript: `xs[a:b]`. Use `slice(xs, a, b)`.\n"
        "  * Method calls: `\"hello\".upper()` → `upper(\"hello\")`. "
        "`xs.append(x)` → `xs = append(xs, x)`.\n"
        "  * List comprehensions: `[x*2 for x in xs]`. Write a `for` "
        "loop with `append`.\n"
        "  * Python keywords: `def`, `lambda`, `None`, `elif`, `pass`, "
        "`True`, `False`. AIL: `fn`, no null, `else if`, `true`/`false`.\n"
        "  * `while`. Use `for x in range(...)`.\n"
        "  * f-strings `f\"{x}\"`. Use `join([\"text \", to_text(x)], "
        "\"\")`.\n"
        "  * Import with dot or alias: `import stdlib.utils`, "
        "`import X as Y`. Write `import sum_list from \"stdlib/utils\"`.\n"
        "  * Calling `intent` from inside `pure fn`. `pure fn` CANNOT call "
        "an intent. Only `entry` coordinates between fn and intent.\n\n"
        "STDLIB — only `stdlib/core`, `stdlib/language`, `stdlib/utils` "
        "exist. NEVER import `stdlib/math`, `stdlib/io`, etc."
    )


def _build_authoring_constraints(prior_errors: list[str]) -> list[str]:
    base = [
        "program_has_exactly_one_entry_declaration",
        "entry_signature_is_main_with_one_Text_parameter",
        "entry_returns_the_answer_directly",
        "use_pure_fn_for_computation_use_intent_for_judgment",
        "hybrid_prompts_declare_both_fn_and_intent",
        "every_declared_intent_must_be_invoked_in_entry",
        "no_markdown_fence_in_output",
    ]
    # If we've retried, include the prior error text as a correction
    # hint AND any error-specific remediation. Small models otherwise
    # repeat the same mistake: an `ImportResolutionError` for a
    # non-existent module kept recurring because the error said what
    # was missing but not what is available.
    if prior_errors:
        last = prior_errors[-1]
        base.append("previous_attempt_failed_with: " + last)
        for hint in _remediation_hints(last):
            base.append(hint)
    return base


def _extract_default_input(prompt: str) -> Any:
    """Pick a plausible default `input_text` from the NL prompt.

    Conservative on purpose — we only want to populate `input_text`
    when the signal is unambiguous, otherwise we leave it None and
    let the model hardcode. Two cases fire:

    1. Exactly one integer literal in the prompt → pass it as the
       input string (e.g. "factorial of 7" → "7"). Covers the most
       common shape of single-value arithmetic prompts.
    2. Otherwise → None, preserving prior behavior.

    Multiple numbers ("average of 10, 20, 30"), floats, negative
    numbers, and hex are all deliberately NOT handled here — they
    belong in the program the author writes, not in the input channel.
    """
    import re
    ints = re.findall(r"(?<![.\d])\b(-?\d+)\b(?![.\d])", prompt)
    if len(ints) == 1:
        return ints[0]
    return None


def _remediation_hints(error_text: str) -> list[str]:
    """Map a parse/import error to concrete corrective constraints.

    Small models can self-correct when told what the RIGHT move is,
    not just what went wrong. This is error-class pattern matching —
    crude on purpose; each branch addresses an observed failure mode
    from local runs and bench_authoring.py.
    """
    hints: list[str] = []
    if "ImportResolutionError" in error_text:
        hints.append(
            "stdlib_has_only_three_modules: core, language, utils — "
            "DO_NOT_import_math_io_string_or_other_names"
        )
        hints.append(
            "for_arithmetic_factorial_fibonacci_etc_write_a_pure_fn_inline_no_import"
        )
    if "unexpected character '?'" in error_text:
        hints.append(
            "no_ternary_operator_in_AIL_use_if_else_instead"
        )
    if "LBRACK" in error_text and "IDENT" in error_text:
        hints.append(
            "no_list_type_annotations_like_[Number]_or_[Text]_"
            "use_bare_Any_or_Number_or_Text_in_signatures"
        )
    if "LBRACE" in error_text and ("IDENT" in error_text or "top-level" not in error_text):
        hints.append(
            "AIL_has_no_dict_type_no_dict_literals_no_{}_syntax_"
            "encode_key_value_data_as_key:value_text_and_parse_with_split"
        )
    if "EQ" in error_text and "RPAREN" in error_text:
        hints.append(
            "no_keyword_arguments_in_AIL_use_positional_args_only_"
            "no_fn(x=5)_no_join(items_sep=',')"
        )
    if "STAR" in error_text and "unexpected" in error_text:
        hints.append(
            "no_**_exponentiation_in_AIL_write_x_*_x_for_squares_"
            "implement_pow_as_a_pure_fn_with_a_for_loop"
        )
    if "unexpected character '\\\\'" in error_text or "unexpected character '\\'" in error_text:
        hints.append(
            "do_not_escape_newlines_as_backslash_n_emit_real_newlines"
        )
    if "LBRACE" in error_text and "top-level" in error_text:
        hints.append(
            "output_must_be_raw_AIL_source_not_wrapped_in_a_JSON_object"
        )
    # "Unexpected '!' at column 17" pattern — the model wrote prose
    # like "What a mouthful!" and abandoned code entirely. The retry
    # gets a strong reset: nothing but AIL source, starts with a
    # keyword, period. Observed on llama3.1:8B for complex Korean
    # bill-splitting prompts (hyun06000, 2026-04-20).
    if "unexpected character '!'" in error_text:
        hints.append(
            "output_must_start_with_fn_or_pure_or_intent_or_import_or_entry_"
            "NO_prose_NO_explanation_NO_markdown_just_AIL_source"
        )
    # Generic catch-all for "unexpected top-level token" errors where
    # the first token is clearly English (What, Let, Here, The, etc.)
    # — the model wrote an explanation instead of code.
    if "top-level token IDENT" in error_text and any(
        w in error_text for w in (
            "'What'", "'Let'", "'Here'", "'The'", "'This'", "'A'", "'I'",
        )
    ):
        hints.append(
            "previous_output_was_prose_not_code_emit_pure_AIL_only"
        )
    return hints


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
        candidate = s[1:end].strip()
        # Sanity check: if the backtick-wrapped content is obviously
        # incomplete (no `entry` declaration), look for a full program
        # echoed later in the response instead. Observed on
        # llama3.1:8B for "factorial of 7": the model wraps
        # `factorial(7)` in a single backtick and then echoes the
        # prompt's examples section verbatim, which contains a full
        # AIL program as a quoted Python string. The fallback tries to
        # recover it; otherwise we keep the short candidate and let
        # the parser reject it so the retry loop engages.
        if "entry" in candidate:
            s = candidate
        else:
            recovered = _recover_echoed_program(s)
            s = recovered if recovered is not None else candidate
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
    # Case 5b: trailing markdown fence + prose after the AIL.
    # Observed on gemma2:9B for complex prompts: the model emits raw
    # AIL, closes it with ``` on its own line, and appends a prose
    # "Explanation:" block. Our leading-fence stripper didn't match
    # (no opening fence), so the stray ``` survived and the lexer
    # choked at the backtick on the closing line.
    # Truncate at the first ``` that appears on its own line AFTER
    # any substantive AIL content (keyword `entry` or `fn` has
    # already been seen above it).
    s = _truncate_at_trailing_fence(s)
    # Case 6: source has literal `\n` (backslash + n) but no real
    # newlines — the model emitted its AIL as a JSON string body
    # (escaping newlines) and wrote it to an output channel that
    # didn't strip the escapes. Observed on llama3.1:8B for prompts
    # like "count words in X": the entire program lands on line 1
    # with `\n` between statements, which the lexer rejects with
    # `LexError: unexpected character '\'`. Conservative: only
    # unescape when there are literally zero real newlines in the
    # source, so we don't damage legitimate `\n` sequences inside
    # string literals of a multi-line program.
    s = _normalize_literal_escapes(s)
    return s


def _truncate_at_trailing_fence(s: str) -> str:
    """Cut off a stray markdown code-fence (and the prose that
    follows it) sitting after the AIL program.

    Triggered when the source already contains real AIL content
    (an `entry`, `fn`, or `intent` keyword above the cut) and
    then a standalone ``` line appears. The closing fence is
    what gemma2:9B — and chatty models in general — add when
    they want to explain the program after writing it.

    Conservative: does nothing if no substantive AIL keyword is
    seen before the fence, or if there are multiple ``` lines
    (those should be handled by the fenced-block extractor
    earlier, not here).
    """
    import re
    fence_match = re.search(r"(^|\n)\s*```\s*(\n|$)", s)
    if fence_match is None:
        return s
    head = s[: fence_match.start()]
    # Only truncate if there's substantive AIL content above.
    if not any(kw in head for kw in ("entry ", "pure fn ", "fn ",
                                     "intent ", "import ")):
        return s
    return head.rstrip()


def _normalize_literal_escapes(s: str) -> str:
    """Decode JSON-style escapes if the source has none of the real
    characters they stand in for.

    Triggered when the model emitted AIL as a JSON string body and
    the transport layer didn't apply JSON decoding. Only runs if
    `\\n` is present AND no actual newline is present — that pairing
    uniquely identifies the leak; any legitimate multi-line program
    fails the precondition and passes through unchanged.
    """
    if "\\n" not in s or "\n" in s:
        return s
    return (
        s.replace("\\n", "\n")
         .replace("\\t", "\t")
         .replace("\\r", "\r")
         .replace('\\"', '"')
         .replace("\\'", "'")
    )


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

    Accepts variants: `ail run`, `ail-go run`, `python -m ail.cli run`,
    optional `--input ...` flags. Any leading non-quote prefix up to the
    first quote, then everything up to the last quote, is treated as the
    AIL source. Embedded `\\n` and `\\"` sequences are unescaped because
    the model was string-quoting the source for shell.
    """
    stripped = s.lstrip()
    triggers = ("ail run", "ail-go run", "ail-go", "python -m ail",
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


def _recover_echoed_program(text: str) -> Optional[str]:
    """When the model echoes the prompt's examples as quoted strings
    and gives no real output, try to lift a complete AIL program out
    of the echo.

    Looks for `'...entry main...'` (single-quoted, as Python repr
    would render it) or `"...entry main..."` (double-quoted) with
    JSON-style `\\n` escapes, and returns the decoded body. Returns
    None if no plausible program is found — the caller then keeps
    whatever short candidate it had and the retry loop engages on
    the parse failure.
    """
    import re
    # Look for a quoted string that contains `entry main`. Greedy to
    # the closing quote matching the opening one.
    for open_q, close_q in (("'", "'"), ('"', '"')):
        pattern = re.escape(open_q) + r"[^" + re.escape(close_q) + r"]*entry main[^" + re.escape(close_q) + r"]*" + re.escape(close_q)
        match = re.search(pattern, text)
        if match:
            body = match.group(0)[1:-1]   # strip the quotes
            # Decode `\n`, `\"`, `\\` the way Python repr would.
            body = (body.replace("\\n", "\n")
                        .replace("\\t", "\t")
                        .replace('\\"', '"')
                        .replace("\\'", "'")
                        .replace("\\\\", "\\"))
            return body.strip()
    return None


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
    import os as _os
    if _os.environ.get("AIL_AUTHOR_PROMPT_VARIANT") == "tutorial":
        # Override with the 3 examples paired with the tutorial prompt.
        # Source: spec/09-fewshot-tutorial.ai.md steps 5, 9, 12.
        return _tutorial_examples()
    return [
        # Simple arithmetic — pins the shape small models need for
        # "factorial of N", "sum 1 to N", "N squared" prompts. Replaces
        # a trivial `return 42` example that taught very little and let
        # the model anchor too strongly on the later hybrid template
        # (observed failure: `ail ask "factorial of 7"` on llama3.1:8B
        # kept inventing `import factorial from "stdlib/math"` + an
        # unused sentiment intent because the hybrid example was its
        # only concrete `fn`-centric anchor).
        (
            [{"prompt": "Compute the factorial of 7"}],
            (
                'pure fn factorial(n: Number) -> Number {\n'
                '    if n <= 1 { return 1 }\n'
                '    return n * factorial(n - 1)\n'
                '}\n'
                'entry main(x: Text) { return factorial(7) }'
            ),
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
        # List input — pins the correct pattern for prompts that give
        # a literal list of numbers (e.g. "average of [85, 92, 78]").
        # Shows: inline list literal in entry body (fine), bare type
        # annotation `Any` (not `[Number]`), join() for string output.
        (
            [{"prompt": "Calculate the average of [85, 92, 78, 95, 88]"}],
            (
                'pure fn average(nums: Any) -> Number {\n'
                '    total = 0\n'
                '    for n in nums { total = total + n }\n'
                '    return total / length(nums)\n'
                '}\n'
                'entry main(x: Text) {\n'
                '    nums = [85, 92, 78, 95, 88]\n'
                '    return average(nums)\n'
                '}'
            ),
        ),
        # Hybrid: one computable subtask AND one judgment subtask in
        # the same program. Shows the canonical shape for "count X and
        # also judge X" prompts. Keep it short — the goal is to pin
        # shape, not demonstrate complexity.
        (
            [{"prompt": "Count the words in 'I love this' and classify its sentiment"}],
            (
                'intent classify_sentiment(text: Text) -> Text {\n'
                '    goal: positive_or_negative\n'
                '}\n'
                'pure fn word_count(s: Text) -> Number {\n'
                '    return length(split(trim(s), " "))\n'
                '}\n'
                'entry main(x: Text) {\n'
                '    text = "I love this"\n'
                '    return join([to_text(word_count(text)), " ", classify_sentiment(text)], "")\n'
                '}'
            ),
        ),
    ] + _v3_extra_examples()


def _tutorial_examples() -> list[tuple[list[Any], Any]]:
    """Three examples that pair with the tutorial-style prompt.

    Drawn directly from spec/09-fewshot-tutorial.ai.md to keep the
    in-context demonstration aligned with the prose tutorial: pure fn
    (step 5 factorial), pure intent (step 9 sentiment), hybrid (step
    12 word_count + sentiment composition).
    """
    return [
        # Step 5 — pure fn computation.
        (
            [{"prompt": "factorial of 7"}],
            (
                'pure fn factorial(n: Number) -> Number {\n'
                '    if n <= 1 { return 1 }\n'
                '    return n * factorial(n - 1)\n'
                '}\n'
                'entry main(x: Text) { return factorial(7) }'
            ),
        ),
        # Step 9 — pure intent (LLM-only).
        (
            [{"prompt": "Is 'great!' positive or negative sentiment?"}],
            (
                'intent classify_sentiment(text: Text) -> Text {\n'
                '    goal: positive_or_negative\n'
                '}\n'
                'entry main(x: Text) { return classify_sentiment("great!") }'
            ),
        ),
        # Step 12 — hybrid: pure fn + intent in the same program.
        (
            [{"prompt": "Count the words in 'I love this' and classify its sentiment"}],
            (
                'intent classify_sentiment(text: Text) -> Text {\n'
                '    goal: positive_or_negative\n'
                '}\n'
                'pure fn word_count(s: Text) -> Number {\n'
                '    return length(split(trim(s), " "))\n'
                '}\n'
                'entry main(x: Text) {\n'
                '    text = "I love this"\n'
                '    return join([to_text(word_count(text)), " ", classify_sentiment(text)], "")\n'
                '}'
            ),
        ),
    ]


def _v3_extra_examples() -> list[tuple[list[Any], Any]]:
    """Additional hybrid-specific few-shots, behind AIL_AUTHOR_PROMPT_VARIANT=v3.

    The v1 prompt + v2 FORBIDDEN block both produced 15% parse / 10%
    routing on the 20 C-category prompts (qwen2.5-coder:14b, Opus 50
    corpus, 2026-04-20). The null result on v2 ruled out "the model
    needs to be told what NOT to write." The remaining prompt-layer
    lever is demonstration: more few-shot examples that exhibit the
    exact hybrid shapes the benchmark is asking for.

    Three additions, each a different hybrid shape the base four
    don't cover:

      - numeric compute + categorical judgment (BMI → category)
      - aggregate + interpretive phrase (scores → comment)
      - text transform + describe (reverse each word → describe)

    Returns [] unless the env var is set, preserving v1 behaviour.
    """
    import os as _os
    if _os.environ.get("AIL_AUTHOR_PROMPT_VARIANT") != "v3":
        return []
    return [
        # Shape: numeric compute → intent that categorises the number.
        # Mirrors benchmark C07 (BMI + assessment) and C16 (compound
        # interest + teenager explanation).
        (
            [{"prompt": "Calculate BMI from height 175cm and weight 70kg and give a short health category"}],
            (
                'intent health_category(summary: Text) -> Text {\n'
                '    goal: underweight_normal_overweight_or_obese\n'
                '}\n'
                'pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {\n'
                '    meters = height_cm / 100\n'
                '    return weight_kg / (meters * meters)\n'
                '}\n'
                'entry main(x: Text) {\n'
                '    value = bmi(175, 70)\n'
                '    summary = join(["BMI ", to_text(value)], "")\n'
                '    return join([summary, " - ", health_category(summary)], "")\n'
                '}'
            ),
        ),
        # Shape: aggregate over a list → intent interprets the number.
        # Mirrors C04 (total + spending summary), C11 (count grades +
        # performance summary), C12 (stddev + variability comment),
        # C17 (counts + conciseness rating).
        (
            [{"prompt": "Compute the average of scores 85, 92, 78 and give a short performance comment"}],
            (
                'intent performance_comment(summary: Text) -> Text {\n'
                '    goal: one short phrase describing the performance level\n'
                '}\n'
                'pure fn average(nums: Number) -> Number {\n'
                '    total = 0\n'
                '    for n in nums { total = total + n }\n'
                '    return total / length(nums)\n'
                '}\n'
                'entry main(x: Text) {\n'
                '    avg = average([85, 92, 78])\n'
                '    summary = join(["average ", to_text(avg)], "")\n'
                '    return join([summary, " - ", performance_comment(summary)], "")\n'
                '}'
            ),
        ),
        # Shape: text transform → intent describes / comments on the
        # transformed text. Mirrors C13 (reverse each word + creative
        # sentence), C20 (remove stopwords + summarize).
        (
            [{"prompt": "Reverse each word in 'hello world' and describe the result in one short phrase"}],
            (
                'intent describe_playfully(text: Text) -> Text {\n'
                '    goal: one short playful phrase describing the text\n'
                '}\n'
                'pure fn reverse_text(s: Text) -> Text {\n'
                '    chars = split(s, "")\n'
                '    result = ""\n'
                '    for i in range(0, length(chars)) {\n'
                '        result = join([result, get(chars, length(chars) - 1 - i)], "")\n'
                '    }\n'
                '    return result\n'
                '}\n'
                'pure fn reverse_each_word(text: Text) -> Text {\n'
                '    words = split(text, " ")\n'
                '    out = []\n'
                '    for w in words { out = append(out, reverse_text(w)) }\n'
                '    return join(out, " ")\n'
                '}\n'
                'entry main(x: Text) {\n'
                '    reversed = reverse_each_word("hello world")\n'
                '    return join([reversed, " - ", describe_playfully(reversed)], "")\n'
                '}'
            ),
        ),
    ]


def _load_reference_card() -> str:
    for candidate in _SPEC_CANDIDATES:
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    # Neither the bundled copy nor the dev-repo path resolved. Return a
    # terse fallback that names the essential constructs. Programs
    # generated under this fallback will be simple but may still run.
    # This path fires only for unusual install shapes (sdist extracted
    # without the spec, editable install pointed at a truncated tree).
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
