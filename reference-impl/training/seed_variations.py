"""Produce dataset/05_variations.jsonl — variations on core patterns.

For each shape we've already taught (factorial, sum_range, vowel
count, etc.), we want the training set to show the SAME program
applied to DIFFERENT specific values. This teaches the model to
copy the shape rather than memorise the literal. One variation per
pattern is too few; three or four is the sweet spot.

No new features are introduced — every entry uses constructs the
earlier seed files already exercise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ail import compile_source, run, MockAdapter


OUT_PATH = Path(__file__).parent / "dataset" / "05_variations.jsonl"


def factorial_prog(n: int) -> str:
    return (
        'pure fn factorial(n: Number) -> Number {\n'
        '    if n <= 1 { return 1 }\n'
        '    return n * factorial(n - 1)\n'
        '}\n'
        f'entry main(x: Text) {{ return factorial({n}) }}'
    )


def sum_range_prog(lo: int, hi: int) -> str:
    return (
        'pure fn sum_range(lo: Number, hi: Number) -> Number {\n'
        '    total = 0\n'
        '    for i in range(lo, hi + 1) { total = total + i }\n'
        '    return total\n'
        '}\n'
        f'entry main(x: Text) {{ return sum_range({lo}, {hi}) }}'
    )


def count_vowels_prog(word: str) -> str:
    return (
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
        f'entry main(x: Text) {{ return count_vowels("{word}") }}'
    )


def word_count_prog(text: str) -> str:
    return (
        'pure fn word_count(s: Text) -> Number {\n'
        '    return length(split(trim(s), " "))\n'
        '}\n'
        f'entry main(x: Text) {{ return word_count("{text}") }}'
    )


def max_of_prog(nums: list[int]) -> str:
    return (
        'pure fn max_of(nums: Number) -> Number {\n'
        '    best = get(nums, 0)\n'
        '    for n in nums {\n'
        '        if n > best { best = n }\n'
        '    }\n'
        '    return best\n'
        '}\n'
        f'entry main(x: Text) {{ return max_of({nums}) }}'
    )


def fib_prog(n: int) -> str:
    return (
        'pure fn fib(n: Number) -> Number {\n'
        '    if n <= 1 { return n }\n'
        '    return fib(n - 1) + fib(n - 2)\n'
        '}\n'
        f'entry main(x: Text) {{ return fib({n}) }}'
    )


def square_prog(n: int) -> str:
    return (
        'pure fn square(n: Number) -> Number { return n * n }\n'
        f'entry main(x: Text) {{ return square({n}) }}'
    )


def char_count_prog(word: str) -> str:
    return (
        'pure fn char_count(s: Text) -> Number { return length(s) }\n'
        f'entry main(x: Text) {{ return char_count("{word}") }}'
    )


def palindrome_prog(word: str) -> str:
    return (
        'pure fn reverse_text(s: Text) -> Text {\n'
        '    chars = split(s, "")\n'
        '    out = ""\n'
        '    for i in range(0, length(chars)) {\n'
        '        out = join([out, get(chars, length(chars) - 1 - i)], "")\n'
        '    }\n'
        '    return out\n'
        '}\n'
        'pure fn is_palindrome(s: Text) -> Boolean {\n'
        '    return lower(s) == reverse_text(lower(s))\n'
        '}\n'
        f'entry main(x: Text) {{ if is_palindrome("{word}") {{ return "yes" }} return "no" }}'
    )


import math as _math

def _factorial(n):
    return 1 if n <= 1 else n * _factorial(n - 1)

def _fib(n):
    return n if n <= 1 else _fib(n - 1) + _fib(n - 2)

def _count_vowels(s):
    return sum(1 for c in s.lower() if c in "aeiou")


SAMPLES: list[dict] = []


def add(id_: str, prompt: str, ail: str, category: str, expected=None,
        input_text: str = ""):
    entry = {
        "id": f"var_{id_}",
        "prompt": prompt,
        "ail_source": ail,
        "category": category,
        "input_text": input_text,
        "source_of_sample": "hand_written",
    }
    if expected is not None:
        entry["expected"] = str(expected)
    SAMPLES.append(entry)


# ----- factorial variations -----
for n in (4, 5, 8, 9):
    add(f"factorial_{n}", f"compute the factorial of {n}",
        factorial_prog(n), "pure_fn", _factorial(n))

# ----- sum_range variations -----
for lo, hi in ((1, 10), (1, 50), (5, 15), (10, 20)):
    add(f"sum_range_{lo}_{hi}", f"sum the integers from {lo} to {hi}",
        sum_range_prog(lo, hi), "pure_fn", sum(range(lo, hi + 1)))

# ----- vowel count variations -----
for w in ("hello", "Mississippi", "banana", "programming"):
    add(f"vowels_{w.lower()}", f"count the vowels in '{w}'",
        count_vowels_prog(w), "pure_fn", _count_vowels(w))

# ----- word count variations -----
for text in ("the quick brown fox",
             "to be or not to be",
             "a b c d e f g h"):
    key = text.split()[0] + "_" + str(len(text.split()))
    add(f"words_{key}", f"how many words are in '{text}'",
        word_count_prog(text), "pure_fn", len(text.split()))

# ----- max_of variations -----
for nums in ([5, 2, 9, 1, 7], [100, 50, 200, 75], [-3, -1, -10, -5]):
    nums_str = "_".join(str(n) for n in nums).replace("-", "m")
    add(f"max_{nums_str}", f"find the maximum of {nums}",
        max_of_prog(nums), "pure_fn", max(nums))

# ----- fib variations -----
for n in (5, 7, 8, 12):
    add(f"fib_{n}", f"return the {n}th Fibonacci number (0-indexed)",
        fib_prog(n), "pure_fn", _fib(n))

# ----- square variations -----
for n in (6, 11, 15, 20):
    add(f"square_{n}", f"what is {n} squared",
        square_prog(n), "pure_fn", n * n)

# ----- char count variations -----
for w in ("hello", "programming", "supercalifragilistic", "ok"):
    add(f"chars_{w[:6]}", f"how many characters are in the word '{w}'",
        char_count_prog(w), "pure_fn", len(w))

# ----- palindrome variations -----
for w, exp in (("racecar", "yes"), ("hello", "no"),
               ("madam", "yes"), ("python", "no"),
               ("level", "yes"), ("noon", "yes"),
               ("world", "no"), ("rotor", "yes")):
    add(f"palin_{w}", f"is '{w}' a palindrome (yes or no)?",
        palindrome_prog(w), "pure_fn", exp)


# ----- simple arithmetic variations (common prompts) -----
def simple_arith(expr: str) -> str:
    return f'entry main(x: Text) {{ return {expr} }}'

for label, expr, exp in (("add_13_29", "13 + 29", "42"),
                         ("mul_7_8", "7 * 8", "56"),
                         ("sub_100_37", "100 - 37", "63"),
                         ("div_144_12", "144 / 12", "12"),
                         ("mod_17_5", "17 % 5", "2")):
    add(f"arith_{label}", f"compute {expr.replace('*', 'times').replace('+', 'plus').replace('-', 'minus').replace('/', 'divided by').replace('%', 'mod')}",
        simple_arith(expr), "pure_fn", exp)


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    good: list[dict] = []
    bad: list[tuple[str, str]] = []

    def _norm(s):
        s = str(s).strip().lower()
        return s[:-2] if s.endswith(".0") else s

    for spec in SAMPLES:
        try:
            compile_source(spec["ail_source"])
            result, _ = run(spec["ail_source"], input=spec.get("input_text", ""),
                            adapter=MockAdapter())
        except Exception as e:
            bad.append((spec["id"], f"{type(e).__name__}: {e}"))
            continue
        if spec["category"] == "pure_fn":
            exp = spec.get("expected")
            if exp is None or _norm(result.value) != _norm(exp):
                bad.append((spec["id"],
                            f"answer {result.value!r} != {exp!r}"))
                continue
        good.append(spec)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for e in good:
            json.dump(e, f, ensure_ascii=False)
            f.write("\n")

    print(f"wrote {len(good)}/{len(SAMPLES)} → "
          f"{OUT_PATH.relative_to(Path.cwd())}", file=sys.stderr)
    if bad:
        print(f"dropped ({len(bad)}):", file=sys.stderr)
        for sid, why in bad:
            print(f"  {sid}: {why[:120]}", file=sys.stderr)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
