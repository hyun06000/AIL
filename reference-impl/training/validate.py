"""Gate-check every sample before it enters the training set.

A sample enters the gold set only if all four gates pass:

  1. `compile_source` accepts the AIL code (parser + purity)
  2. The purity checker raises no violations for any `pure fn`
     declaration (purity is a subset of (1) on current AIL, but we
     check explicitly so the script stays honest if the language
     changes)
  3. `run(..., adapter=MockAdapter())` executes without exception
  4. For `pure_fn` samples: the output equals the declared `expected`.

Samples that fail any gate are reported but dropped. The idea is
simple — the fine-tuned model should never be trained on a program
the current runtime would reject.

Output:
  - writes a "validated" JSONL to stdout (pass-through of valid rows)
  - prints a per-category pass/fail table to stderr
  - exits 0 if every sample passed, 1 otherwise
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from ail import compile_source, run, MockAdapter
from ail.parser import ParseError, PurityError
from ail.parser.lexer import LexError


REQUIRED_FIELDS = {"id", "prompt", "ail_source", "category", "source_of_sample"}
VALID_CATEGORIES = {"pure_fn", "pure_intent", "hybrid"}
VALID_SOURCES = {
    "existing_example",
    "bench_canonical",
    "hand_written",
    "r3_fixes",             # 09_r3_fixes.jsonl — canonical fixes for R3 failure patterns
    "cat_b_reinforcement",  # 10_cat_b_reinforcement.jsonl — pure_intent/hybrid counterweight for v5
}


def _gate_parse(sample: dict) -> str | None:
    try:
        compile_source(sample["ail_source"])
        return None
    except (LexError, ParseError, PurityError) as e:
        return f"{type(e).__name__}: {e}"


def _gate_run(sample: dict) -> tuple[str | None, Any]:
    """Execute the program. Return (error_or_None, produced_value)."""
    input_text = sample.get("input_text")
    try:
        result, _ = run(sample["ail_source"],
                        input=input_text if input_text is not None else "",
                        adapter=MockAdapter())
        return None, result.value
    except Exception as e:
        return f"{type(e).__name__}: {e}", None


def _trim_dot_zero(s: str) -> str:
    return s[:-2] if s.endswith(".0") else s


def _gate_answer(sample: dict, actual: Any) -> str | None:
    """Only meaningful for pure_fn: the executed answer must equal
    the declared expected value. Lenient compare drops a single
    trailing `.0` on each side (so `30.0 == 30`) but does NOT strip
    arbitrary trailing zeros — that misfire would make `30` and `3`
    compare equal."""
    if sample["category"] != "pure_fn":
        return None
    expected = sample.get("expected")
    if expected is None:
        return "pure_fn sample has no `expected` — cannot validate answer"
    a = _trim_dot_zero(str(actual).strip().lower())
    b = _trim_dot_zero(str(expected).strip().lower())
    if a != b:
        return f"answer mismatch: got {actual!r}, expected {expected!r}"
    return None


def _required_fields_missing(sample: dict) -> list[str]:
    return sorted(REQUIRED_FIELDS - sample.keys())


def _validate_one(sample: dict) -> tuple[bool, str | None]:
    missing = _required_fields_missing(sample)
    if missing:
        return False, f"missing fields: {missing}"
    if sample["category"] not in VALID_CATEGORIES:
        return False, f"bad category: {sample['category']!r}"
    if sample["source_of_sample"] not in VALID_SOURCES:
        return False, f"bad source_of_sample: {sample['source_of_sample']!r}"

    err = _gate_parse(sample)
    if err:
        return False, f"parse: {err}"
    err, actual = _gate_run(sample)
    if err:
        return False, f"run: {err}"
    err = _gate_answer(sample, actual)
    if err:
        return False, err
    return True, None


def _load_jsonl(paths: list[Path]) -> list[dict]:
    samples: list[dict] = []
    for p in paths:
        for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"{p}:{line_no}: bad JSON: {e}", file=sys.stderr)
                sys.exit(2)
    return samples


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--quiet", action="store_true",
                   help="suppress per-sample pass/fail lines")
    args = p.parse_args()

    samples = _load_jsonl(args.files)

    passed: list[dict] = []
    failed: list[tuple[dict, str]] = []
    for s in samples:
        ok, why = _validate_one(s)
        if ok:
            passed.append(s)
            if not args.quiet:
                print(f"[PASS] {s['id']:40s}  {s['category']:12s}  "
                      f"{s['source_of_sample']}", file=sys.stderr)
        else:
            failed.append((s, why or "?"))
            print(f"[FAIL] {s.get('id','?'):40s}  {s.get('category','?'):12s}  "
                  f"{why}", file=sys.stderr)

    # Per-category summary
    total = len(samples)
    cat_total = Counter(s.get("category", "?") for s in samples)
    cat_pass = Counter(s["category"] for s in passed)
    print(file=sys.stderr)
    print("=" * 64, file=sys.stderr)
    print(f"TOTAL  {len(passed):3d}/{total:3d} passed", file=sys.stderr)
    for cat in sorted(cat_total):
        print(f"  {cat:12s}  {cat_pass[cat]:3d}/{cat_total[cat]:3d}",
              file=sys.stderr)
    print("=" * 64, file=sys.stderr)

    # Emit the validated pass-through to stdout so callers can pipe:
    #   python validate.py dataset/*.jsonl > validated.jsonl
    for s in passed:
        json.dump(s, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
