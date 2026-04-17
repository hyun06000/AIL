"""Benchmark the authoring layer against a small local model.

Runs a curated set of natural-language prompts through `ask()`, records
which ones produced the expected answer, prints a scoreboard, and
optionally writes a JSON report. Designed to run against a local Ollama
model — no API costs, repeatable, fast (each prompt is one HTTP round
trip plus parsing).

Usage:

    # Baseline run with default model (env AIL_OLLAMA_MODEL or llama3.1):
    python tools/bench_authoring.py

    # Specific model + retries:
    AIL_OLLAMA_MODEL=gemma2:latest python tools/bench_authoring.py --retries 2

    # Save a JSON report for later comparison:
    python tools/bench_authoring.py --json-out bench-baseline.json

The benchmark covers a deliberately diverse range of task shapes:
literal returns, arithmetic, recursion, loops, string handling, list
ops, and intent calls. A prompt's expected answer is checked by an
optional `check` callable; if absent, exact string equality with
`expected` is used.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable, Optional

from ail_mvp import ask, AuthoringError


@dataclass
class Case:
    name: str            # short identifier, also category-grouped by prefix
    prompt: str          # the natural-language input
    expected: Any        # canonical expected answer (string or value)
    check: Optional[Callable[[Any], bool]] = None   # custom matcher
    notes: str = ""

    def passes(self, actual: Any) -> bool:
        if self.check is not None:
            return self.check(actual)
        # Default: lenient equality — coerce both to strings, strip
        # whitespace, lowercase. Small models often format numbers
        # differently (5050 vs 5050.0) and this avoids spurious failures.
        a = str(actual).strip().lower().rstrip("0").rstrip(".")
        b = str(self.expected).strip().lower().rstrip("0").rstrip(".")
        return a == b


# Curated benchmark. Mix of difficulties and task shapes. Add to it as
# real failure modes come up — that's how a benchmark earns its keep.
CASES: list[Case] = [
    # --- arithmetic (should be trivial) ---
    Case("arith_mul",       "what is 7 times 8",                expected=56),
    Case("arith_add",       "compute 13 plus 29",                expected=42),
    Case("arith_sum_range", "sum the numbers from 1 to 100",     expected=5050),
    Case("arith_factorial", "compute the factorial of 6",        expected=720),
    Case("arith_square",    "what is 13 squared",                expected=169),

    # --- string ---
    Case("str_count_vowels", "count the vowels in 'Hello World'", expected=3),
    Case("str_count_letter", "count how many times 'a' appears in 'banana'",
         expected=3),
    Case("str_length",       "how many characters are in the word 'programming'",
         expected=11),

    # --- list / loop ---
    Case("list_fib10",       "give me the 10th fibonacci number",
         expected=55,
         notes="0,1,1,2,3,5,8,13,21,34,55 — could be 0- or 1-indexed; check both"),
    Case("list_max",         "what is the maximum of 17, 42, 8, 23, 39",
         expected=42),

    # --- multilingual ---
    Case("ko_sum",           "1부터 50까지의 합",                  expected=1275),
    Case("ko_factorial",     "5의 팩토리얼을 계산해줘",              expected=120),
]


# Some checks are loose by design — e.g. fib10 could be 1-indexed (55)
# or 0-indexed (34, with 0,1,1,2,...). Patch in custom checkers.
def _fib10_check(v):
    s = str(v).strip().rstrip("0").rstrip(".")
    return s in ("55", "34")


for c in CASES:
    if c.name == "list_fib10":
        c.check = _fib10_check


@dataclass
class CaseResult:
    name: str
    prompt: str
    expected: Any
    actual: Any
    passed: bool
    error: Optional[str]
    retries: int
    elapsed_s: float
    ail_source: str


def run_case(case: Case, *, retries: int) -> CaseResult:
    t0 = time.perf_counter()
    try:
        result = ask(case.prompt, max_retries=retries)
    except AuthoringError as e:
        return CaseResult(
            name=case.name, prompt=case.prompt, expected=case.expected,
            actual=None, passed=False,
            error=f"{type(e).__name__}: {e}",
            retries=(len(e.partial.errors) - 1) if e.partial else -1,
            elapsed_s=time.perf_counter() - t0,
            ail_source=(e.partial.ail_source if e.partial else ""),
        )
    except Exception as e:
        return CaseResult(
            name=case.name, prompt=case.prompt, expected=case.expected,
            actual=None, passed=False,
            error=f"{type(e).__name__}: {e}",
            retries=-1, elapsed_s=time.perf_counter() - t0, ail_source="",
        )
    elapsed = time.perf_counter() - t0
    return CaseResult(
        name=case.name, prompt=case.prompt, expected=case.expected,
        actual=result.value, passed=case.passes(result.value),
        error=None, retries=result.retries, elapsed_s=elapsed,
        ail_source=result.ail_source,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark `ail ask` authoring quality")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--json-out", type=str, default=None,
                        help="Path to write detailed JSON report")
    parser.add_argument("--verbose", action="store_true",
                        help="Print AIL source for every case")
    args = parser.parse_args()

    print(f"Running {len(CASES)} benchmark cases (retries={args.retries})...")
    print()
    results: list[CaseResult] = []
    for case in CASES:
        r = run_case(case, retries=args.retries)
        results.append(r)
        mark = "✓" if r.passed else "✗"
        actual_repr = repr(r.actual) if r.actual is not None else "(error)"
        print(f"  {mark} {case.name:20s}  {actual_repr:30s}  "
              f"retries={r.retries:2d}  {r.elapsed_s:5.1f}s")
        if args.verbose or not r.passed:
            if r.error:
                print(f"      error: {r.error}")
            if r.ail_source:
                # First-line + length is usually enough to spot the issue
                first_line = r.ail_source.splitlines()[0] if r.ail_source else "(empty)"
                print(f"      ail (first line, total {len(r.ail_source)} chars): {first_line}")

    print()
    passed = sum(1 for r in results if r.passed)
    print(f"PASS RATE: {passed}/{len(results)}  ({100*passed/len(results):.0f}%)")
    total_time = sum(r.elapsed_s for r in results)
    print(f"TOTAL TIME: {total_time:.1f}s")
    print(f"AVG RETRIES (passing only): "
          f"{(sum(r.retries for r in results if r.passed) / max(passed, 1)):.2f}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({
                "cases": [asdict(r) for r in results],
                "pass_count": passed,
                "total": len(results),
                "total_seconds": total_time,
            }, f, indent=2, default=str)
        print(f"\nJSON report written to {args.json_out}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
