"""Produce dataset/03_handwritten.jsonl — samples that cover language
features the existing examples and bench-canonical sources under-
represent.

Target coverage, with at least 3 samples per feature:

  - `attempt` with confidence threshold + Result fallthrough
  - `match` with `with confidence > N` guards
  - `pure fn` using Result return types (ok / error / is_ok / unwrap_or)
  - Nested pure fn composition (no short-circuit to a single expression)
  - `in` / `not in` membership, `%` modulo
  - Imports from stdlib/utils and stdlib/language
  - Multi-line Korean input preserved through the pipeline

Every entry runs through MockAdapter before being written. Broken
entries are reported and dropped. The harvester is idempotent —
re-run whenever the list below changes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ail import compile_source, run, MockAdapter


OUT_PATH = Path(__file__).parent / "dataset" / "03_handwritten.jsonl"


SAMPLES: list[dict] = [

    # -------- `attempt` + confidence + Result ----------------------
    {
        "id": "hand_attempt_cascade_number",
        "prompt": "extract a number from the input — try a direct parse, "
                  "then scan tokens for the first parseable, and only then "
                  "ask the model",
        "category": "hybrid",
        "ail": (
            'pure fn direct_parse(text: Text) -> Number {\n'
            '    return to_number(trim(text))\n'
            '}\n'
            'pure fn scan_tokens(text: Text) -> Number {\n'
            '    for t in split(text, " ") {\n'
            '        parsed = to_number(t)\n'
            '        if is_ok(parsed) { return parsed }\n'
            '    }\n'
            '    return error("no numeric token found")\n'
            '}\n'
            'intent infer_number(text: Text) -> Text {\n'
            '    goal: the single number in the text or the word unknown\n'
            '}\n'
            'entry main(text: Text) {\n'
            '    return attempt {\n'
            '        try direct_parse(text)\n'
            '        try scan_tokens(text)\n'
            '        try infer_number(text)\n'
            '    }\n'
            '}'
        ),
        "input_text": "order #17 is ready",
    },

    # -------- `match` with confidence guards -----------------------
    {
        "id": "hand_match_confidence_sentiment",
        "prompt": "classify the input as positive, negative, or neutral, "
                  "but treat low-confidence classifications as uncertain",
        "category": "pure_intent",
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'entry main(text: Text) {\n'
            '    return match classify_sentiment(text) {\n'
            '        "positive" with confidence > 0.8 => "strong positive",\n'
            '        "negative" with confidence > 0.8 => "strong negative",\n'
            '        _ with confidence > 0.6 => "somewhat uncertain",\n'
            '        _ => "too uncertain to say"\n'
            '    }\n'
            '}'
        ),
        "input_text": "this is the best day ever",
    },

    # -------- Result type threaded through pure fn -----------------
    {
        "id": "hand_result_divide",
        "prompt": "safely divide the first input number by the second; "
                  "return an error string if the divisor is zero",
        "category": "pure_fn",
        "ail": (
            'pure fn safe_div(a: Number, b: Number) -> Number {\n'
            '    if b == 0 { return error("divide by zero") }\n'
            '    return ok(a / b)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    r = safe_div(10, 2)\n'
            '    if is_ok(r) { return unwrap(r) }\n'
            '    return unwrap_error(r)\n'
            '}'
        ),
        "expected": "5",
    },

    # -------- Nested pure fn composition, no intent ----------------
    {
        "id": "hand_nested_fib_tree",
        "prompt": "compute fib(7) + fib(9) using the naive recursive definition",
        "category": "pure_fn",
        "ail": (
            'pure fn fib(n: Number) -> Number {\n'
            '    if n <= 1 { return n }\n'
            '    return fib(n - 1) + fib(n - 2)\n'
            '}\n'
            'entry main(x: Text) { return fib(7) + fib(9) }'
        ),
        "expected": "47",
    },
    {
        "id": "hand_nested_sum_of_squares",
        "prompt": "sum the squares of 1 through 5",
        "category": "pure_fn",
        "ail": (
            'pure fn square(n: Number) -> Number { return n * n }\n'
            'pure fn sum_of_squares(lo: Number, hi: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(lo, hi + 1) { total = total + square(i) }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum_of_squares(1, 5) }'
        ),
        "expected": "55",
    },

    # -------- membership / modulo ----------------------------------
    {
        "id": "hand_membership_fizz_only",
        "prompt": "among 1..15 return only the multiples of 3 joined by comma",
        "category": "pure_fn",
        "ail": (
            'pure fn fizz_only(n: Number) -> Text {\n'
            '    picks = []\n'
            '    for i in range(1, n + 1) {\n'
            '        if i % 3 == 0 { picks = append(picks, to_text(i)) }\n'
            '    }\n'
            '    return join(picks, ",")\n'
            '}\n'
            'entry main(x: Text) { return fizz_only(15) }'
        ),
        "expected": "3,6,9,12,15",
    },
    {
        "id": "hand_not_in_filter",
        "prompt": "from the list [apple, banana, apple, cherry, banana, date], "
                  "drop duplicates and return the remaining words joined by comma",
        "category": "pure_fn",
        "ail": (
            'pure fn dedupe(items: Text) -> Text {\n'
            '    seen = []\n'
            '    for it in items {\n'
            '        if it not in seen { seen = append(seen, it) }\n'
            '    }\n'
            '    return seen\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return join(dedupe(["apple","banana","apple","cherry","banana","date"]), ",")\n'
            '}'
        ),
        "expected": "apple,banana,cherry,date",
    },

    # -------- stdlib imports ---------------------------------------
    {
        "id": "hand_stdlib_word_count",
        "prompt": "count the words in the input text using the stdlib utility",
        "category": "pure_fn",
        "ail": (
            'import word_count from "stdlib/utils"\n'
            'entry main(text: Text) { return word_count(text) }'
        ),
        "input_text": "the quick brown fox jumps",
        "expected": "5",
    },
    {
        "id": "hand_stdlib_classify",
        "prompt": "classify the input text's sentiment using the stdlib intent",
        "category": "pure_intent",
        "ail": (
            'import classify from "stdlib/language"\n'
            'entry main(text: Text) {\n'
            '    return classify(text, "positive_negative_or_neutral")\n'
            '}'
        ),
        "input_text": "I love this",
    },

    # -------- Korean hybrid preserving Unicode through pipeline ----
    {
        "id": "hand_ko_chars_and_tone",
        "prompt": "한국어 텍스트의 글자 수를 세고 톤을 분류해줘",
        "category": "hybrid",
        "ail": (
            'intent classify_tone(text: Text) -> Text {\n'
            '    goal: 문장의 톤을 한국어로 분류\n'
            '}\n'
            'pure fn char_count(s: Text) -> Number { return length(s) }\n'
            'entry main(text: Text) {\n'
            '    return join([to_text(char_count(text)), "자, ", classify_tone(text)], "")\n'
            '}'
        ),
        "input_text": "오늘 정말 행복한 하루였어",
    },

    # -------- Multi-parameter hybrid -------------------------------
    {
        "id": "hand_letters_and_translate",
        "prompt": "given an English word, count its letters and give "
                  "the Korean translation, separated by a dash",
        "category": "hybrid",
        "ail": (
            'intent translate_to_korean(text: Text) -> Text {\n'
            '    goal: Korean translation of the source\n'
            '}\n'
            'pure fn letter_count(s: Text) -> Number { return length(s) }\n'
            'entry main(word: Text) {\n'
            '    return join([to_text(letter_count(word)), " letters - ", translate_to_korean(word)], "")\n'
            '}'
        ),
        "input_text": "programming",
    },

    # -------- Simple but shows literal-everything pattern ----------
    {
        "id": "hand_palindrome_check",
        "prompt": "is the input word a palindrome? return yes or no",
        "category": "pure_fn",
        "ail": (
            'pure fn reverse_text(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    result = ""\n'
            '    for i in range(0, length(chars)) {\n'
            '        result = join([result, get(chars, length(chars) - 1 - i)], "")\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'pure fn is_palindrome(s: Text) -> Boolean {\n'
            '    return lower(s) == reverse_text(lower(s))\n'
            '}\n'
            'entry main(word: Text) {\n'
            '    if is_palindrome(word) { return "yes" }\n'
            '    return "no"\n'
            '}'
        ),
        "input_text": "racecar",
        "expected": "yes",
    },
    {
        "id": "hand_palindrome_check_no",
        "prompt": "is the word 'hello' a palindrome? return yes or no",
        "category": "pure_fn",
        "ail": (
            'pure fn reverse_text(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    result = ""\n'
            '    for i in range(0, length(chars)) {\n'
            '        result = join([result, get(chars, length(chars) - 1 - i)], "")\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'pure fn is_palindrome(s: Text) -> Boolean {\n'
            '    return lower(s) == reverse_text(lower(s))\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    if is_palindrome("hello") { return "yes" }\n'
            '    return "no"\n'
            '}'
        ),
        "expected": "no",
    },

    # -------- Harder computation -----------------------------------
    {
        "id": "hand_prime_check",
        "prompt": "is 29 prime? return yes or no",
        "category": "pure_fn",
        "ail": (
            'pure fn is_prime(n: Number) -> Boolean {\n'
            '    if n < 2 { return false }\n'
            '    for d in range(2, n) {\n'
            '        if d * d > n { return true }\n'
            '        if n % d == 0 { return false }\n'
            '    }\n'
            '    return true\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    if is_prime(29) { return "yes" }\n'
            '    return "no"\n'
            '}'
        ),
        "expected": "yes",
    },
    {
        "id": "hand_gcd",
        "prompt": "compute the greatest common divisor of 48 and 18",
        "category": "pure_fn",
        "ail": (
            'pure fn gcd(a: Number, b: Number) -> Number {\n'
            '    if b == 0 { return a }\n'
            '    return gcd(b, a % b)\n'
            '}\n'
            'entry main(x: Text) { return gcd(48, 18) }'
        ),
        "expected": "6",
    },

    # -------- Small hybrid -----------------------------------------
    {
        "id": "hand_hybrid_title_and_translate",
        "prompt": "uppercase the first letter of each word in the input, "
                  "then translate the whole thing to Korean",
        "category": "hybrid",
        "ail": (
            'intent translate_to_korean(text: Text) -> Text {\n'
            '    goal: natural Korean translation of the source\n'
            '}\n'
            'pure fn titlecase(s: Text) -> Text {\n'
            '    words = split(s, " ")\n'
            '    out = []\n'
            '    for w in words {\n'
            '        if length(w) > 0 {\n'
            '            first = upper(slice(w, 0, 1))\n'
            '            rest = slice(w, 1, length(w))\n'
            '            out = append(out, join([first, rest], ""))\n'
            '        }\n'
            '    }\n'
            '    return join(out, " ")\n'
            '}\n'
            'entry main(text: Text) {\n'
            '    titled = titlecase(text)\n'
            '    return join([titled, " -> ", translate_to_korean(titled)], "")\n'
            '}'
        ),
        "input_text": "hello world",
    },
]


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    broken: list[tuple[str, str]] = []

    def _norm(s):
        s = str(s).strip().lower()
        return s[:-2] if s.endswith(".0") else s

    for spec in SAMPLES:
        sid = spec["id"]
        ail_src = spec["ail"]
        input_text = spec.get("input_text", "")
        try:
            compile_source(ail_src)
            result, _ = run(ail_src, input=input_text, adapter=MockAdapter())
        except Exception as e:
            broken.append((sid, f"{type(e).__name__}: {e}"))
            continue

        if spec["category"] == "pure_fn":
            expected = spec.get("expected")
            if expected is None:
                broken.append((sid, "pure_fn with no expected"))
                continue
            if _norm(result.value) != _norm(expected):
                broken.append((sid, f"answer {result.value!r} != {expected!r}"))
                continue

        entry = {
            "id": sid,
            "prompt": spec["prompt"],
            "ail_source": ail_src,
            "category": spec["category"],
            "input_text": input_text,
            "source_of_sample": "hand_written",
        }
        if spec["category"] == "pure_fn":
            entry["expected"] = spec["expected"]
        entries.append(entry)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for e in entries:
            json.dump(e, f, ensure_ascii=False)
            f.write("\n")

    print(f"wrote {len(entries)}/{len(SAMPLES)} samples → "
          f"{OUT_PATH.relative_to(Path.cwd())}", file=sys.stderr)
    if broken:
        print(f"broken {len(broken)}:", file=sys.stderr)
        for sid, why in broken:
            print(f"  {sid}: {why[:120]}", file=sys.stderr)
    return 0 if not broken else 1


if __name__ == "__main__":
    sys.exit(main())
