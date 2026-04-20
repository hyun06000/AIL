"""Produce dataset/06_advanced.jsonl — feature-coverage programs for
language surfaces the earlier seed files under-represent.

Covered here (≥ 3 programs each where feasible):
  - `match` with literal arms and with `with confidence > N` guards
  - `attempt { try ... }` confidence-priority cascades
  - `Result` threading through a pipeline (ok / error / is_ok / unwrap_or)
  - `stdlib/language` imports (classify, summarize, translate)
  - `stdlib/utils` imports (word_count, average, unique)
  - Korean-prompt hybrid programs
  - `in` / `not in` membership
  - Nested control flow (fn calling fn calling fn)

Every entry is run through MockAdapter before being emitted;
failures are dropped with a note.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ail import compile_source, run, MockAdapter


OUT_PATH = Path(__file__).parent / "dataset" / "06_advanced.jsonl"


SAMPLES: list[dict] = [

    # ───────── match with literal arms (pure fn) ───────────────────
    {
        "id": "adv_match_literal_number",
        "prompt": "given the day-of-week number (0 = Sunday .. 6 = Saturday), return 'weekend' or 'weekday'",
        "category": "pure_fn",
        "ail_source": (
            'pure fn day_kind(d: Number) -> Text {\n'
            '    return match d {\n'
            '        0 => "weekend",\n'
            '        6 => "weekend",\n'
            '        _ => "weekday"\n'
            '    }\n'
            '}\n'
            'entry main(x: Text) { return day_kind(0) }'
        ),
        "expected": "weekend",
    },
    {
        "id": "adv_match_literal_text",
        "prompt": "map 'rock' / 'paper' / 'scissors' to what they beat",
        "category": "pure_fn",
        "ail_source": (
            'pure fn beats(choice: Text) -> Text {\n'
            '    return match choice {\n'
            '        "rock" => "scissors",\n'
            '        "paper" => "rock",\n'
            '        "scissors" => "paper",\n'
            '        _ => "unknown"\n'
            '    }\n'
            '}\n'
            'entry main(x: Text) { return beats("paper") }'
        ),
        "expected": "rock",
    },
    {
        "id": "adv_match_wildcard",
        "prompt": "for a color name, return 'primary' if red/blue/yellow else 'other'",
        "category": "pure_fn",
        "ail_source": (
            'pure fn primary_or_other(color: Text) -> Text {\n'
            '    return match color {\n'
            '        "red" => "primary",\n'
            '        "blue" => "primary",\n'
            '        "yellow" => "primary",\n'
            '        _ => "other"\n'
            '    }\n'
            '}\n'
            'entry main(x: Text) { return primary_or_other("green") }'
        ),
        "expected": "other",
    },

    # ───────── match with confidence guards (hybrid) ───────────────
    {
        "id": "adv_match_confidence_reply",
        "prompt": "classify input sentiment; if confidence > 0.8 reply confidently, else hedge",
        "category": "pure_intent",
        "ail_source": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return match classify_sentiment("I love this") {\n'
            '        "positive" with confidence > 0.8 => "strongly positive",\n'
            '        "negative" with confidence > 0.8 => "strongly negative",\n'
            '        _ with confidence > 0.5 => "somewhat uncertain",\n'
            '        _ => "too uncertain"\n'
            '    }\n'
            '}'
        ),
    },
    {
        "id": "adv_match_confidence_three_way",
        "prompt": "label urgency; high confidence wins outright, low confidence falls back to neutral",
        "category": "pure_intent",
        "ail_source": (
            'intent urgency_of(text: Text) -> Text {\n'
            '    goal: urgent_or_calm\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return match urgency_of("meeting at 3pm tomorrow") {\n'
            '        "urgent" with confidence > 0.85 => "CRITICAL",\n'
            '        "calm" with confidence > 0.85 => "RELAXED",\n'
            '        _ => "REVIEW_MANUALLY"\n'
            '    }\n'
            '}'
        ),
    },

    # ───────── attempt cascades ─────────────────────────────────────
    {
        "id": "adv_attempt_number",
        "prompt": "extract the first number from the text, preferring direct parse, then token scan, then model",
        "category": "hybrid",
        "ail_source": (
            'pure fn direct_parse(text: Text) -> Number { return to_number(trim(text)) }\n'
            'pure fn scan_tokens(text: Text) -> Number {\n'
            '    for t in split(text, " ") {\n'
            '        n = to_number(t)\n'
            '        if is_ok(n) { return n }\n'
            '    }\n'
            '    return error("no number")\n'
            '}\n'
            'intent infer_number(text: Text) -> Text { goal: the single number in the text }\n'
            'entry main(x: Text) {\n'
            '    return attempt {\n'
            '        try direct_parse(x)\n'
            '        try scan_tokens(x)\n'
            '        try infer_number(x)\n'
            '    }\n'
            '}'
        ),
        "input_text": "order number 42 ready",
    },
    {
        "id": "adv_attempt_lookup",
        "prompt": "look up a country code; if not in table, ask the model",
        "category": "hybrid",
        "ail_source": (
            'pure fn table_lookup(code: Text) -> Text {\n'
            '    if code == "KR" { return "South Korea" }\n'
            '    if code == "US" { return "United States" }\n'
            '    if code == "JP" { return "Japan" }\n'
            '    return error("unknown code")\n'
            '}\n'
            'intent name_from_code(code: Text) -> Text {\n'
            '    goal: the country name matching a two-letter code\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return attempt {\n'
            '        try table_lookup("KR")\n'
            '        try name_from_code("KR")\n'
            '    }\n'
            '}'
        ),
    },
    {
        "id": "adv_attempt_fallback",
        "prompt": "pick the cheapest available strategy that returns a confident answer",
        "category": "pure_fn",
        "ail_source": (
            'pure fn cheap(x: Number) -> Number { return x + 1 }\n'
            'pure fn expensive(x: Number) -> Number { return x * 10 }\n'
            'entry main(xs: Text) {\n'
            '    return attempt {\n'
            '        try cheap(5)\n'
            '        try expensive(5)\n'
            '    }\n'
            '}'
        ),
        "expected": "6",
    },

    # ───────── Result threading ─────────────────────────────────────
    {
        "id": "adv_result_divide",
        "prompt": "safely divide two numbers; return error on divide by zero",
        "category": "pure_fn",
        "ail_source": (
            'pure fn safe_div(a: Number, b: Number) -> Number {\n'
            '    if b == 0 { return error("divide by zero") }\n'
            '    return ok(a / b)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    r = safe_div(10, 2)\n'
            '    if is_ok(r) { return to_text(unwrap(r)) }\n'
            '    return unwrap_error(r)\n'
            '}'
        ),
        "expected": "5",
    },
    {
        "id": "adv_result_divide_err",
        "prompt": "safely divide, showing the error path when divisor is zero",
        "category": "pure_fn",
        "ail_source": (
            'pure fn safe_div(a: Number, b: Number) -> Number {\n'
            '    if b == 0 { return error("divide by zero") }\n'
            '    return ok(a / b)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    r = safe_div(10, 0)\n'
            '    if is_ok(r) { return to_text(unwrap(r)) }\n'
            '    return unwrap_error(r)\n'
            '}'
        ),
        "expected": "divide by zero",
    },
    {
        "id": "adv_result_parse_list",
        "prompt": "parse a list of CSV numbers; skip bad rows and count good ones",
        "category": "pure_fn",
        "ail_source": (
            'pure fn parse_one(s: Text) -> Number {\n'
            '    n = to_number(trim(s))\n'
            '    if is_error(n) { return error("bad number") }\n'
            '    return ok(n)\n'
            '}\n'
            'pure fn count_good(raw: Text) -> Number {\n'
            '    good = 0\n'
            '    for s in split(raw, ",") {\n'
            '        if is_ok(parse_one(s)) { good = good + 1 }\n'
            '    }\n'
            '    return good\n'
            '}\n'
            'entry main(x: Text) { return count_good("3,7,xx,12,abc,2") }'
        ),
        "expected": "4",
    },
    {
        "id": "adv_unwrap_or_default",
        "prompt": "parse a number with a default of 0 if parsing fails",
        "category": "pure_fn",
        "ail_source": (
            'entry main(x: Text) { return unwrap_or(to_number("not a number"), 0) }'
        ),
        "expected": "0",
    },

    # ───────── stdlib/language imports ──────────────────────────────
    {
        "id": "adv_stdlib_classify",
        "prompt": "classify the input's sentiment using the stdlib classifier",
        "category": "pure_intent",
        "ail_source": (
            'import classify from "stdlib/language"\n'
            'entry main(text: Text) {\n'
            '    return classify(text, "positive_negative_or_neutral")\n'
            '}'
        ),
        "input_text": "I love this",
    },
    {
        "id": "adv_stdlib_summarize",
        "prompt": "summarize the input in at most 30 tokens",
        "category": "pure_intent",
        "ail_source": (
            'import summarize from "stdlib/language"\n'
            'entry main(text: Text) { return summarize(text, 30) }'
        ),
        "input_text": "The Fed raised rates by 25 basis points today after three months of stable inflation numbers.",
    },
    {
        "id": "adv_stdlib_translate",
        "prompt": "translate the input into Korean",
        "category": "pure_intent",
        "ail_source": (
            'import translate from "stdlib/language"\n'
            'entry main(text: Text) { return translate(text, "Korean") }'
        ),
        "input_text": "hello world",
    },

    # ───────── stdlib/utils imports ─────────────────────────────────
    {
        "id": "adv_stdlib_word_count",
        "prompt": "count words in the input using the stdlib utility",
        "category": "pure_fn",
        "ail_source": (
            'import word_count from "stdlib/utils"\n'
            'entry main(text: Text) { return word_count(text) }'
        ),
        "input_text": "one two three four five",
        "expected": "5",
    },
    {
        "id": "adv_stdlib_average",
        "prompt": "average the numbers using the stdlib utility",
        "category": "pure_fn",
        "ail_source": (
            'import average from "stdlib/utils"\n'
            'entry main(x: Text) { return average([10, 20, 30, 40, 50]) }'
        ),
        "expected": "30",
    },
    {
        "id": "adv_stdlib_unique",
        "prompt": "remove duplicates from the list using the stdlib utility",
        "category": "pure_fn",
        "ail_source": (
            'import unique from "stdlib/utils"\n'
            'entry main(x: Text) { return unique([1, 2, 2, 3, 1, 4]) }'
        ),
        "expected": "[1, 2, 3, 4]",
    },

    # ───────── Korean hybrid programs ───────────────────────────────
    {
        "id": "adv_ko_chars_sent",
        "prompt": "한국어 텍스트의 글자 수를 세고, 문장의 감정을 분류해줘",
        "category": "hybrid",
        "ail_source": (
            'intent classify_tone(text: Text) -> Text {\n'
            '    goal: 문장의 톤을 한국어로 분류\n'
            '}\n'
            'pure fn char_count(s: Text) -> Number { return length(s) }\n'
            'entry main(text: Text) {\n'
            '    return join([to_text(char_count(text)), "자, ", classify_tone(text)], "")\n'
            '}'
        ),
        "input_text": "오늘은 정말 기분이 좋은 하루였다",
    },
    {
        "id": "adv_ko_summarize_and_length",
        "prompt": "한국어 문장을 요약하고, 요약문이 몇 자인지도 같이 알려줘",
        "category": "hybrid",
        "ail_source": (
            'intent summarize_ko(text: Text) -> Text {\n'
            '    goal: 문장을 한국어로 한 문장 요약\n'
            '}\n'
            'pure fn char_count(s: Text) -> Number { return length(s) }\n'
            'entry main(text: Text) {\n'
            '    s = summarize_ko(text)\n'
            '    return join([s, " (", to_text(char_count(s)), "자)"], "")\n'
            '}'
        ),
        "input_text": "어제 저녁에 친구들과 모여 한강에서 라면과 치킨을 먹으며 늦게까지 이야기했다.",
    },
    {
        "id": "adv_ko_word_split_and_count",
        "prompt": "한국어 문장에서 공백으로 단어를 나누어 단어 수를 세고 결과를 한 줄로 반환해줘",
        "category": "pure_fn",
        "ail_source": (
            'pure fn word_count(s: Text) -> Number {\n'
            '    return length(split(trim(s), " "))\n'
            '}\n'
            'entry main(text: Text) {\n'
            '    return join([to_text(word_count(text)), "단어"], "")\n'
            '}'
        ),
        "input_text": "오늘 날씨가 정말 좋다",
        "expected": "4단어",
    },

    # ───────── membership (in / not in) ─────────────────────────────
    {
        "id": "adv_membership_known",
        "prompt": "given a color, return 'primary' if it's in the primary set, else 'other'",
        "category": "pure_fn",
        "ail_source": (
            'pure fn is_primary(color: Text) -> Text {\n'
            '    primaries = ["red", "blue", "yellow"]\n'
            '    if color in primaries { return "primary" }\n'
            '    return "other"\n'
            '}\n'
            'entry main(x: Text) { return is_primary("red") }'
        ),
        "expected": "primary",
    },
    {
        "id": "adv_not_in_filter",
        "prompt": "from a word list, return words that are NOT common stopwords",
        "category": "pure_fn",
        "ail_source": (
            'pure fn keep_nonstops(words: Text) -> Text {\n'
            '    stops = ["a", "the", "is", "in", "on"]\n'
            '    out = []\n'
            '    for w in words {\n'
            '        if lower(w) not in stops { out = append(out, w) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) { return join(keep_nonstops(["The","cat","is","on","the","mat"]), " ") }'
        ),
        "expected": "cat mat",
    },

    # ───────── nested fn calling fn ──────────────────────────────────
    {
        "id": "adv_nested_sum_of_squares",
        "prompt": "sum the squares of the first N integers",
        "category": "pure_fn",
        "ail_source": (
            'pure fn square(n: Number) -> Number { return n * n }\n'
            'pure fn sum_of_squares(n: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(1, n + 1) { total = total + square(i) }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum_of_squares(5) }'
        ),
        "expected": "55",
    },
    {
        "id": "adv_nested_count_words_of_length",
        "prompt": "count how many words in a sentence have exactly K letters",
        "category": "pure_fn",
        "ail_source": (
            'pure fn len_eq(w: Text, k: Number) -> Boolean { return length(w) == k }\n'
            'pure fn count_k_letter(text: Text, k: Number) -> Number {\n'
            '    total = 0\n'
            '    for w in split(trim(text), " ") {\n'
            '        if len_eq(w, k) { total = total + 1 }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return count_k_letter("the cat sat on the mat", 3) }'
        ),
        "expected": "5",
    },

    # ───────── more hybrid shapes for variety ───────────────────────
    {
        "id": "adv_hybrid_temp_judge",
        "prompt": "convert F to C and describe whether that's hot or cold in a word",
        "category": "hybrid",
        "ail_source": (
            'intent classify_temp(summary: Text) -> Text {\n'
            '    goal: cold or mild or hot\n'
            '}\n'
            'pure fn f_to_c(f: Number) -> Number { return (f - 32) * 5 / 9 }\n'
            'entry main(x: Text) {\n'
            '    c = f_to_c(95)\n'
            '    summary = join(["temperature ", to_text(c), "C"], "")\n'
            '    return join([summary, " - ", classify_temp(summary)], "")\n'
            '}'
        ),
    },
    {
        "id": "adv_hybrid_count_rate",
        "prompt": "count the words and give a short descriptor of the length",
        "category": "hybrid",
        "ail_source": (
            'intent describe_length(summary: Text) -> Text { goal: short or long }\n'
            'pure fn word_count(s: Text) -> Number {\n'
            '    return length(split(trim(s), " "))\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    text = "this is a tiny sentence"\n'
            '    summary = join([to_text(word_count(text)), " words"], "")\n'
            '    return join([summary, " - ", describe_length(summary)], "")\n'
            '}'
        ),
    },
    {
        "id": "adv_hybrid_digit_sum",
        "prompt": "sum the digits of a number and say whether the sum is even or odd",
        "category": "hybrid",
        "ail_source": (
            'intent even_or_odd(summary: Text) -> Text { goal: even or odd }\n'
            'pure fn digit_sum(n: Number) -> Number {\n'
            '    total = 0\n'
            '    cur = n\n'
            '    for i in range(0, 20) {\n'
            '        if cur == 0 { return total }\n'
            '        total = total + cur % 10\n'
            '        cur = (cur - cur % 10) / 10\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    s = digit_sum(127)\n'
            '    summary = join(["digit sum ", to_text(s)], "")\n'
            '    return join([summary, " - ", even_or_odd(summary)], "")\n'
            '}'
        ),
    },

    # ───────── more pure_fn shapes ──────────────────────────────────
    {
        "id": "adv_pure_celsius_table",
        "prompt": "convert a Celsius value to Fahrenheit",
        "category": "pure_fn",
        "ail_source": (
            'pure fn c_to_f(c: Number) -> Number { return c * 9 / 5 + 32 }\n'
            'entry main(x: Text) { return c_to_f(100) }'
        ),
        "expected": "212",
    },
    {
        "id": "adv_pure_count_matching",
        "prompt": "count elements equal to a target in a list",
        "category": "pure_fn",
        "ail_source": (
            'pure fn count_eq(items: Number, target: Number) -> Number {\n'
            '    total = 0\n'
            '    for it in items { if it == target { total = total + 1 } }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return count_eq([1,2,3,2,4,2,5], 2) }'
        ),
        "expected": "3",
    },
    {
        "id": "adv_pure_gcd",
        "prompt": "compute the greatest common divisor of two numbers",
        "category": "pure_fn",
        "ail_source": (
            'pure fn gcd(a: Number, b: Number) -> Number {\n'
            '    if b == 0 { return a }\n'
            '    return gcd(b, a % b)\n'
            '}\n'
            'entry main(x: Text) { return gcd(48, 18) }'
        ),
        "expected": "6",
    },
    {
        "id": "adv_pure_is_prime",
        "prompt": "check whether a number is prime",
        "category": "pure_fn",
        "ail_source": (
            'pure fn is_prime(n: Number) -> Boolean {\n'
            '    if n < 2 { return false }\n'
            '    for d in range(2, n) {\n'
            '        if d * d > n { return true }\n'
            '        if n % d == 0 { return false }\n'
            '    }\n'
            '    return true\n'
            '}\n'
            'entry main(x: Text) { if is_prime(29) { return "yes" } return "no" }'
        ),
        "expected": "yes",
    },
]


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _norm(s):
        s = str(s).strip().lower()
        return s[:-2] if s.endswith(".0") else s

    good: list[dict] = []
    bad: list[tuple[str, str]] = []

    for spec in SAMPLES:
        try:
            compile_source(spec["ail_source"])
            result, _ = run(spec["ail_source"],
                            input=spec.get("input_text", ""),
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
        entry = {
            "id": spec["id"],
            "prompt": spec["prompt"],
            "ail_source": spec["ail_source"],
            "category": spec["category"],
            "input_text": spec.get("input_text", ""),
            "source_of_sample": "hand_written",
        }
        if spec["category"] == "pure_fn":
            entry["expected"] = spec["expected"]
        good.append(entry)

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
