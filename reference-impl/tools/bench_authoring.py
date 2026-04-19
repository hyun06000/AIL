"""Benchmark the authoring layer against a local or API model.

Measures three distinct qualities of `ail ask`:

  1. PARSE RATE — fraction of prompts that produced a program the parser
     accepted (after up to `--retries` self-repair rounds). Infrastructure
     floor — if this is low, nothing else matters.

  2. fn/intent SELECTION ACCURACY — fraction of prompts where the
     author's routing decision (pure computation vs. judgment) matched
     the prompt's category. This is the language's core promise. When
     this is low, AIL has failed at what Opus 4 (in CLAUDE.md) called
     the fn/intent decision problem.

  3. ANSWER CORRECTNESS — fraction of prompts whose final value matches
     the expected answer. Only meaningful for `pure_fn` cases; for
     intent-using cases the answer is a language model's output and
     not canonically verifiable in isolation.

Usage:

    # Default model (env AIL_OLLAMA_MODEL or llama3.1:latest):
    python tools/bench_authoring.py

    # A specific model with fewer retries:
    AIL_OLLAMA_MODEL=gemma2:latest python tools/bench_authoring.py --retries 1

    # Filter by category (speeds up iteration on one axis):
    python tools/bench_authoring.py --category pure_fn

    # Save a JSON report for later comparison:
    python tools/bench_authoring.py --json-out bench-baseline.json

The corpus (50 cases, tagged by category) is defined inline below.
Adding to it is cheap — just append a Case. Keep the balance across
categories so no single axis dominates.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Optional

from ail import ask, AuthoringError, compile_source
from ail.parser.ast import FnDecl, IntentDecl, ImportDecl


def _trim_dot_zero(s: str) -> str:
    """Return `s` without a single trailing `.0` suffix. Idempotent.

    Used to reconcile Python's `str(42.0) == "42.0"` against
    `str(42) == "42"` without clobbering legitimate digit characters.
    """
    if s.endswith(".0"):
        return s[:-2]
    return s


@dataclass
class Case:
    """One benchmark entry.

    - `category` tags whether this prompt is expected to be solved with
      deterministic computation only (`pure_fn`), with a language-model
      judgment call (`pure_intent`), or with both combined (`hybrid`).
    - `expected` is the canonical answer for pure_fn cases only. For
      intent-using cases it is None (the LLM-generated answer varies by
      model).
    - `check` overrides the default lenient string-equality match.
    """
    name: str
    prompt: str
    category: str              # "pure_fn" | "pure_intent" | "hybrid"
    expected: Any = None
    check: Optional[Callable[[Any], bool]] = None
    notes: str = ""

    def answer_ok(self, actual: Any) -> bool:
        """Lenient numeric/string match — drop only a single trailing
        ".0" suffix on each side, then compare. Only meaningful when
        `expected` is set (pure_fn cases).

        The previous version used `.rstrip("0").rstrip(".")` which
        greedily ate any trailing `0`, so `str(30)` became `"3"` and
        the check mis-reported mismatches on anything ending in zero
        (30, 110, 120, 5050 — the bug hid itself by silently failing
        tasks whose expected values happened to end in a zero digit).
        """
        if self.expected is None:
            return True   # non-deterministic cases: no answer check
        if self.check is not None:
            return self.check(actual)
        a = _trim_dot_zero(str(actual).strip().lower())
        b = _trim_dot_zero(str(self.expected).strip().lower())
        return a == b


# --- corpus ----------------------------------------------------------------
# 50 cases, balanced across categories. Growing this corpus is how the
# benchmark stays honest as the language and author evolve.

CASES: list[Case] = [
    # ======================================================================
    # pure_fn (20) — deterministic computation, no LLM judgment needed
    # ======================================================================
    Case("fn_arith_mul",        "what is 7 times 8",               "pure_fn", 56),
    Case("fn_arith_add",        "compute 13 plus 29",              "pure_fn", 42),
    Case("fn_arith_sum_range",  "sum the numbers from 1 to 100",   "pure_fn", 5050),
    Case("fn_arith_factorial",  "compute the factorial of 6",      "pure_fn", 720),
    Case("fn_arith_square",     "what is 13 squared",              "pure_fn", 169),
    Case("fn_arith_cube",       "what is 4 cubed",                 "pure_fn", 64),
    Case("fn_arith_sum_even",   "sum of even numbers from 2 to 20", "pure_fn", 110),
    Case("fn_arith_avg",        "average of 10, 20, 30, 40, 50",   "pure_fn", 30),
    Case("fn_str_count_vowels", "count the vowels in 'Hello World'", "pure_fn", 3),
    Case("fn_str_count_letter", "count how many times 'a' appears in 'banana'",
         "pure_fn", 3),
    Case("fn_str_length",       "how many characters are in the word 'programming'",
         "pure_fn", 11),
    Case("fn_str_words",        "how many words are in 'the quick brown fox jumps'",
         "pure_fn", 5),
    Case("fn_str_upper",        "uppercase the word 'hello'",      "pure_fn", "HELLO"),
    Case("fn_str_reverse",      "reverse the string 'racecar'",    "pure_fn", "racecar"),
    Case("fn_list_fib10",       "give me the 10th fibonacci number",
         "pure_fn", 55,
         notes="0- or 1-indexed; accepts 55 or 34"),
    Case("fn_list_max",         "what is the maximum of 17, 42, 8, 23, 39",
         "pure_fn", 42),
    Case("fn_list_min",         "what is the minimum of 17, 42, 8, 23, 39",
         "pure_fn", 8),
    Case("fn_list_count_odd",   "count the odd numbers in 1,2,3,4,5,6,7,8,9,10",
         "pure_fn", 5),
    Case("fn_ko_sum",           "1부터 50까지의 합",                "pure_fn", 1275),
    Case("fn_ko_factorial",     "5의 팩토리얼을 계산해줘",           "pure_fn", 120),

    # ======================================================================
    # pure_intent (15) — requires LLM judgment; no way to compute
    # ======================================================================
    Case("intent_sent_pos",     "Is 'I absolutely loved this movie!' a positive or negative sentiment?",
         "pure_intent"),
    Case("intent_sent_neg",     "Classify 'This is the worst experience ever' as positive or negative",
         "pure_intent"),
    Case("intent_sent_neut",    "Classify 'The weather is cloudy' as positive, negative, or neutral",
         "pure_intent"),
    Case("intent_translate_ko", "Translate 'hello world' to Korean",
         "pure_intent"),
    Case("intent_translate_en", "Translate 'bonjour' to English",
         "pure_intent"),
    Case("intent_language_id",  "What language is 'je suis étudiant' written in?",
         "pure_intent"),
    Case("intent_topic",        "What is the main topic of 'The Fed raised rates by 25 basis points'?",
         "pure_intent"),
    Case("intent_spam",         "Classify this as spam or not spam: 'FREE CASH CLICK NOW'",
         "pure_intent"),
    Case("intent_urgency",      "Detect the urgency in 'Call me ASAP it's important'",
         "pure_intent"),
    Case("intent_formality",    "Is 'yo what up dude' formal or informal?",
         "pure_intent"),
    Case("intent_summarize",    "Summarize in one sentence: 'AIL is a programming language designed for AI authors. It distinguishes computation from judgment. Humans interact via prompts.'",
         "pure_intent"),
    Case("intent_rewrite",      "Rewrite 'hey wanna grab lunch' in a professional tone",
         "pure_intent"),
    Case("intent_extract_name", "Extract the person name from 'My name is Alice and I live in Seoul'",
         "pure_intent"),
    Case("intent_ko_sent",      "이 문장의 감정을 분류해줘: '오늘은 최고의 하루였어'",
         "pure_intent"),
    Case("intent_ko_topic",     "'한국은행이 기준금리를 0.25%p 인상했다' 의 주제는?",
         "pure_intent"),

    # ======================================================================
    # hybrid (15) — deterministic computation AND judgment in one program
    # ======================================================================
    Case("hybrid_count_and_sent",
         "Count the words in 'I absolutely love this product' and also classify its sentiment",
         "hybrid"),
    Case("hybrid_split_and_classify",
         "Split 'apple,banana,cherry' by comma and classify each as fruit or vegetable",
         "hybrid"),
    Case("hybrid_len_and_translate",
         "Count letters in 'bonjour' and translate it to English",
         "hybrid"),
    Case("hybrid_avg_and_feedback",
         "Given scores 85, 92, 78, 95, 88, compute the average and give a one-sentence verbal assessment",
         "hybrid"),
    Case("hybrid_count_and_judge",
         "Count the vowels in 'Mississippi' and tell me whether that is a high or low vowel density",
         "hybrid"),
    Case("hybrid_reverse_and_judge",
         "Reverse the word 'hello' and tell me if the reversed string looks like a real English word",
         "hybrid"),
    Case("hybrid_sum_and_describe",
         "Sum the numbers 1 through 10 and classify whether the result is even or odd",
         "hybrid"),
    Case("hybrid_longest_and_rate",
         "Find the longest word in 'cat elephant dog' and rate how common it is",
         "hybrid"),
    Case("hybrid_double_and_classify",
         "Double the number 42 and classify whether the result is 'large' (>100) or 'small'",
         "hybrid"),
    Case("hybrid_split_and_sent",
         "Split 'I love programming' by space and classify the overall sentiment",
         "hybrid"),
    Case("hybrid_len_and_formality",
         "Count characters in 'good afternoon sir' and judge if the greeting is formal",
         "hybrid"),
    Case("hybrid_words_and_summ",
         "Count the words in 'The quick brown fox jumps over the lazy dog' and summarize what this sentence describes",
         "hybrid"),
    Case("hybrid_square_and_classify",
         "Compute 10 squared, then classify whether the result is closer to a hundred or a thousand",
         "hybrid"),
    Case("hybrid_ko_count_sent",
         "'오늘은 정말 행복한 하루였다' 의 글자 수를 세고, 문장의 감정을 분류해줘",
         "hybrid"),
    Case("hybrid_max_and_describe",
         "Find the maximum of 17, 42, 8, 23, 39 and give a short verbal description of that number",
         "hybrid"),
]


# fib10 accepts 0- or 1-indexed interpretations.
def _fib10_check(v: Any) -> bool:
    s = str(v).strip().rstrip("0").rstrip(".")
    return s in ("55", "34")


for c in CASES:
    if c.name == "fn_list_fib10":
        c.check = _fib10_check


# --- structural analysis ---------------------------------------------------

def _classify_authored_program(
    source: str,
    trace_entries: list,
) -> dict:
    """Inspect the authored AIL source + its execution trace to decide
    how the author routed the task.

    Returns a dict with:
      declared_fn   : number of FnDecl in the parsed program
      declared_pure : number of pure FnDecl
      declared_intent : number of locally-declared IntentDecl
      imports_stdlib_intent : bool — imports any stdlib module that is
          intent-only (stdlib/language, stdlib/core)
      dispatched_intent : int — number of `intent_call` trace entries
      used_intent : bool — author routed through an LLM for at least
          one subtask (dispatched >= 1 OR any local intent decl got
          invoked). Primary routing signal.
      used_fn : bool — author wrote at least one fn / pure fn decl.

    If the source does not parse, every count is 0 and used_* are False.
    """
    report = {
        "declared_fn": 0, "declared_pure": 0,
        "declared_intent": 0, "imports_stdlib_intent": False,
        "dispatched_intent": 0, "used_intent": False, "used_fn": False,
    }
    try:
        prog = compile_source(source)
    except Exception:
        # Unparseable. Fall back to trace-only signal.
        report["dispatched_intent"] = sum(
            1 for e in trace_entries if e.kind == "intent_call"
        )
        report["used_intent"] = report["dispatched_intent"] > 0
        return report

    intent_only_stdlibs = {"stdlib/language", "stdlib/core"}
    for d in prog.declarations:
        if isinstance(d, FnDecl):
            report["declared_fn"] += 1
            if d.purity == "pure":
                report["declared_pure"] += 1
        elif isinstance(d, IntentDecl):
            report["declared_intent"] += 1
        elif isinstance(d, ImportDecl):
            if getattr(d, "module", "") in intent_only_stdlibs:
                report["imports_stdlib_intent"] = True

    report["dispatched_intent"] = sum(
        1 for e in trace_entries if e.kind == "intent_call"
    )
    # "Used intent" means the author routed at least one subtask through
    # the LLM — by declaring an intent, by importing a stdlib intent, or
    # by dispatching one at runtime.
    report["used_intent"] = (
        report["declared_intent"] > 0
        or report["imports_stdlib_intent"]
        or report["dispatched_intent"] > 0
    )
    report["used_fn"] = report["declared_fn"] > 0
    return report


def _routing_ok(category: str, structural: dict) -> bool:
    """Did the author choose the correct fn/intent mix for this category?

    - pure_fn: no intent usage at all (no dispatch, no decl, no intent import)
    - pure_intent: at least one intent usage
    - hybrid: at least one intent usage AND at least one fn decl
    """
    if category == "pure_fn":
        return not structural["used_intent"]
    if category == "pure_intent":
        return structural["used_intent"]
    if category == "hybrid":
        return structural["used_intent"] and structural["used_fn"]
    return False


# --- run harness -----------------------------------------------------------

@dataclass
class CaseResult:
    name: str
    prompt: str
    category: str
    expected: Any
    actual: Any
    parsed: bool          # author produced valid, parseable AIL
    routing_ok: bool      # fn/intent selection matched category
    answer_ok: bool       # final value matched expected (pure_fn only)
    error: Optional[str]
    retries: int
    elapsed_s: float
    ail_source: str
    structural: dict = field(default_factory=dict)


def run_case(case: Case, *, retries: int) -> CaseResult:
    t0 = time.perf_counter()
    try:
        result = ask(case.prompt, max_retries=retries)
    except AuthoringError as e:
        # Parse/purity failure after retries — routing and answer both fail.
        partial = e.partial
        return CaseResult(
            name=case.name, prompt=case.prompt, category=case.category,
            expected=case.expected, actual=None,
            parsed=False, routing_ok=False, answer_ok=False,
            error=f"{type(e).__name__}: {e}",
            retries=(len(partial.errors) - 1) if partial else -1,
            elapsed_s=time.perf_counter() - t0,
            ail_source=partial.ail_source if partial else "",
        )
    except Exception as e:
        return CaseResult(
            name=case.name, prompt=case.prompt, category=case.category,
            expected=case.expected, actual=None,
            parsed=False, routing_ok=False, answer_ok=False,
            error=f"{type(e).__name__}: {e}",
            retries=-1, elapsed_s=time.perf_counter() - t0, ail_source="",
        )

    structural = _classify_authored_program(
        result.ail_source, result.trace.entries
    )
    routing_ok = _routing_ok(case.category, structural)
    answer_ok = case.answer_ok(result.value) if case.category == "pure_fn" else True

    return CaseResult(
        name=case.name, prompt=case.prompt, category=case.category,
        expected=case.expected, actual=result.value,
        parsed=True, routing_ok=routing_ok, answer_ok=answer_ok,
        error=None, retries=result.retries,
        elapsed_s=time.perf_counter() - t0,
        ail_source=result.ail_source, structural=structural,
    )


def _print_case_line(r: CaseResult) -> None:
    # Three glyphs, one per metric — so you can see at a glance which
    # dimension failed without reading details.
    p_mark = "P" if r.parsed else "·"
    r_mark = "R" if r.routing_ok else "·"
    a_mark = "A" if r.answer_ok else "·"
    actual_repr = repr(r.actual) if r.actual is not None else "(error)"
    if len(actual_repr) > 28:
        actual_repr = actual_repr[:25] + "..."
    print(
        f"  [{p_mark}{r_mark}{a_mark}] {r.category:12s} {r.name:26s}  "
        f"{actual_repr:30s}  retries={r.retries:2d}  {r.elapsed_s:5.1f}s"
    )


def _print_summary(results: list[CaseResult]) -> None:
    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    total = len(results)
    n_parse = sum(1 for r in results if r.parsed)
    n_route = sum(1 for r in results if r.routing_ok)
    n_answer_fn = sum(1 for r in results
                      if r.category == "pure_fn" and r.answer_ok and r.parsed)
    n_fn_total = sum(1 for r in results if r.category == "pure_fn")

    print()
    print("=" * 60)
    print(f"PARSE RATE:          {n_parse}/{total} ({100*n_parse/total:.0f}%)")
    print(f"ROUTING ACCURACY:    {n_route}/{total} ({100*n_route/total:.0f}%)  "
          "(fn vs. intent decision)")
    if n_fn_total:
        print(f"ANSWER CORRECT (fn): {n_answer_fn}/{n_fn_total} "
              f"({100*n_answer_fn/n_fn_total:.0f}%)  (pure_fn cases only)")
    print("-" * 60)
    for cat in ("pure_fn", "pure_intent", "hybrid"):
        if cat not in by_cat:
            continue
        rs = by_cat[cat]
        pc = sum(1 for r in rs if r.parsed)
        rc = sum(1 for r in rs if r.routing_ok)
        ac = sum(1 for r in rs if r.answer_ok and r.parsed)
        line = f"  {cat:12s}  parse {pc:2d}/{len(rs)}  route {rc:2d}/{len(rs)}"
        if cat == "pure_fn":
            line += f"  answer {ac:2d}/{len(rs)}"
        print(line)
    print("=" * 60)
    total_time = sum(r.elapsed_s for r in results)
    print(f"TOTAL TIME: {total_time:.1f}s  "
          f"(avg {total_time/total:.1f}s/case)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark `ail ask` authoring quality"
    )
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--category", choices=("pure_fn", "pure_intent", "hybrid"),
                        default=None, help="Run only cases of this category")
    parser.add_argument("--limit", type=int, default=None,
                        help="Run only the first N cases (after category filter)")
    parser.add_argument("--json-out", type=str, default=None,
                        help="Path to write detailed JSON report")
    parser.add_argument("--verbose", action="store_true",
                        help="Print AIL source for every case")
    args = parser.parse_args()

    cases = CASES
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} benchmark cases (retries={args.retries})...")
    print("  glyphs:  [P]arse  [R]oute  [A]nswer   · = failed")
    print()
    results: list[CaseResult] = []
    for case in cases:
        r = run_case(case, retries=args.retries)
        results.append(r)
        _print_case_line(r)
        if args.verbose or not (r.parsed and r.routing_ok):
            if r.error:
                print(f"      error: {r.error}")
            if r.ail_source:
                first_line = r.ail_source.splitlines()[0]
                print(f"      ail (first line, {len(r.ail_source)} chars): "
                      f"{first_line[:100]}")
            if r.structural:
                print(f"      structural: {r.structural}")

    _print_summary(results)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({
                "cases": [asdict(r) for r in results],
                "summary": {
                    "total": len(results),
                    "parsed": sum(1 for r in results if r.parsed),
                    "routed": sum(1 for r in results if r.routing_ok),
                    "answered_fn": sum(
                        1 for r in results
                        if r.category == "pure_fn" and r.answer_ok and r.parsed
                    ),
                    "total_seconds": sum(r.elapsed_s for r in results),
                },
            }, f, indent=2, default=str)
        print(f"\nJSON report written to {args.json_out}")

    # Exit 0 iff all three dimensions pass on every case.
    all_ok = all(r.parsed and r.routing_ok and r.answer_ok for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
