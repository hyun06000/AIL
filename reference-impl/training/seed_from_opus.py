"""Produce dataset/04_opus_canonical.jsonl — one canonical AIL program
per prompt in benchmarks/prompts.json (Opus 50-prompt corpus).

The Opus corpus is a separate set from bench_authoring.CASES and the
seed in seed_from_bench.py. Both corpora intentionally overlap in
spirit (factorial, vowels, sentiment, hybrids…) but with different
specific prompts, inputs, and expected answers. This seed doubles
our training set by providing canonical AIL for the OTHER 50 prompts
too, which is exactly the distribution the `bench_vs_python.py` and
`benchmark.py` tools score against.

Design rules (same as seed_from_bench.py):
- Use `pure fn` when the body is deterministic.
- Hardcode prompt literals in the entry so input_text doesn't matter.
- No generics, no list-type annotations, no method syntax.
- For intent-only prompts: one intent declaration + trivial entry.
- For hybrid prompts: pure fn for computation + intent for judgment,
  entry combines both in a single return.

Every entry is run through MockAdapter before writing. Entries that
fail parse, purity, execution, or (for pure_fn) answer check are
dropped with a warning.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ail import compile_source, run, MockAdapter


REPO_ROOT = Path(__file__).parent.parent.parent
PROMPTS_PATH = REPO_ROOT / "benchmarks" / "prompts.json"
OUT_PATH = Path(__file__).parent / "dataset" / "04_opus_canonical.jsonl"


# Canonical AIL per Opus prompt. Keyed by the prompt id (A01 ... C20).
# `ail` is the program; `expected` (when set) lets the pure_fn gate
# validate the answer. Leave `expected` unset (or null) for intent /
# hybrid prompts where the answer depends on the model; the validator
# skips the answer check for those.
CANON: dict[str, dict] = {

    # ───────── A: Pure computation, ground truth = fn only ─────────

    "A01": {
        "ail": (
            'pure fn factorial(n: Number) -> Number {\n'
            '    if n <= 1 { return 1 }\n'
            '    return n * factorial(n - 1)\n'
            '}\n'
            'entry main(x: Text) { return factorial(7) }'
        ),
        "expected": "5040",
    },

    "A02": {
        "ail": (
            'pure fn reverse_text(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    out = ""\n'
            '    for i in range(0, length(chars)) {\n'
            '        out = join([out, get(chars, length(chars) - 1 - i)], "")\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) { return reverse_text("hello world") }'
        ),
        "expected": "dlrow olleh",
    },

    "A03": {
        "ail": (
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
            'entry main(x: Text) { return count_vowels("Programming is fun") }'
        ),
        "expected": "5",
    },

    "A04": {
        "ail": (
            'pure fn max_of(nums: Number) -> Number {\n'
            '    best = get(nums, 0)\n'
            '    for n in nums {\n'
            '        if n > best { best = n }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) { return max_of([34, 12, 89, 3, 56, 72]) }'
        ),
        "expected": "89",
    },

    "A05": {
        "ail": (
            'pure fn sort_words(text: Text) -> Text {\n'
            '    words = split(text, " ")\n'
            '    sorted = []\n'
            '    for w in words {\n'
            '        inserted = false\n'
            '        new_sorted = []\n'
            '        for s in sorted {\n'
            '            if inserted == false {\n'
            '                if w < s {\n'
            '                    new_sorted = append(new_sorted, w)\n'
            '                    inserted = true\n'
            '                }\n'
            '            }\n'
            '            new_sorted = append(new_sorted, s)\n'
            '        }\n'
            '        if inserted == false {\n'
            '            new_sorted = append(new_sorted, w)\n'
            '        }\n'
            '        sorted = new_sorted\n'
            '    }\n'
            '    return join(sorted, " ")\n'
            '}\n'
            'entry main(x: Text) { return sort_words("banana cherry apple date") }'
        ),
        "expected": "apple banana cherry date",
    },

    "A06": {
        "ail": (
            'pure fn sum_even(lo: Number, hi: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(lo, hi + 1) {\n'
            '        if i % 2 == 0 { total = total + i }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum_even(1, 100) }'
        ),
        "expected": "2550",
    },

    "A07": {
        "ail": (
            'pure fn f_to_c(f: Number) -> Number {\n'
            '    return (f - 32) * 5 / 9\n'
            '}\n'
            'entry main(x: Text) { return f_to_c(98.6) }'
        ),
        "expected": "37",
    },

    "A08": {
        "ail": (
            'pure fn count_long_words(text: Text, min_len: Number) -> Number {\n'
            '    total = 0\n'
            '    for w in split(trim(text), " ") {\n'
            '        if length(w) > min_len { total = total + 1 }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return count_long_words("the quick brown fox jumps over the lazy dog", 3) }'
        ),
        "expected": "5",
    },

    "A09": {
        "ail": (
            'pure fn label(n: Number) -> Text {\n'
            '    if n % 15 == 0 { return "FizzBuzz" }\n'
            '    if n % 3 == 0 { return "Fizz" }\n'
            '    if n % 5 == 0 { return "Buzz" }\n'
            '    return to_text(n)\n'
            '}\n'
            'pure fn fizzbuzz(up_to: Number) -> Text {\n'
            '    parts = []\n'
            '    for i in range(1, up_to + 1) {\n'
            '        parts = append(parts, label(i))\n'
            '    }\n'
            '    return join(parts, ", ")\n'
            '}\n'
            'entry main(x: Text) { return fizzbuzz(20) }'
        ),
        "expected": "1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz, 16, 17, Fizz, 19, Buzz",
    },

    "A10": {
        "ail": (
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
            'entry main(x: Text) {\n'
            '    if is_palindrome("racecar") { return "true" }\n'
            '    return "false"\n'
            '}'
        ),
        "expected": "true",
    },

    "A11": {
        "ail": (
            'pure fn average(nums: Number) -> Number {\n'
            '    total = 0\n'
            '    for n in nums { total = total + n }\n'
            '    return total / length(nums)\n'
            '}\n'
            'entry main(x: Text) { return average([85, 92, 78, 95, 88]) }'
        ),
        "expected": "87.6",
    },

    "A12": {
        "ail": (
            'pure fn dedupe(items: Number) -> Number {\n'
            '    seen = []\n'
            '    for it in items {\n'
            '        if it not in seen { seen = append(seen, it) }\n'
            '    }\n'
            '    return seen\n'
            '}\n'
            'entry main(x: Text) { return dedupe([1, 3, 2, 3, 1, 4, 2, 5]) }'
        ),
        # Result value is a list → stringified as [1, 3, 2, 4, 5]
        "expected": "[1, 3, 2, 4, 5]",
    },

    "A13": {
        "ail": (
            'pure fn char_freq(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    keys = []\n'
            '    counts = []\n'
            '    for c in chars {\n'
            '        if c in keys {\n'
            '            new_counts = []\n'
            '            i = 0\n'
            '            for k in keys {\n'
            '                if k == c {\n'
            '                    new_counts = append(new_counts, get(counts, i) + 1)\n'
            '                } else {\n'
            '                    new_counts = append(new_counts, get(counts, i))\n'
            '                }\n'
            '                i = i + 1\n'
            '            }\n'
            '            counts = new_counts\n'
            '        } else {\n'
            '            keys = append(keys, c)\n'
            '            counts = append(counts, 1)\n'
            '        }\n'
            '    }\n'
            '    parts = []\n'
            '    i = 0\n'
            '    for k in keys {\n'
            '        parts = append(parts, join([k, ":", to_text(get(counts, i))], ""))\n'
            '        i = i + 1\n'
            '    }\n'
            '    return join(parts, ", ")\n'
            '}\n'
            'entry main(x: Text) { return char_freq("mississippi") }'
        ),
        "expected": "m:1, i:4, s:4, p:2",
    },

    "A14": {
        "ail": (
            'pure fn fib_n(n: Number) -> Number {\n'
            '    result = []\n'
            '    a = 0\n'
            '    b = 1\n'
            '    for i in range(0, n) {\n'
            '        result = append(result, a)\n'
            '        next_val = a + b\n'
            '        a = b\n'
            '        b = next_val\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'entry main(x: Text) { return fib_n(10) }'
        ),
        "expected": "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]",
    },

    "A15": {
        "ail": (
            'pure fn divisible_by(nums: Number, d: Number) -> Number {\n'
            '    out = []\n'
            '    for n in nums {\n'
            '        if n % d == 0 { out = append(out, n) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) { return divisible_by([15, 23, 8, 42, 16, 4, 31], 4) }'
        ),
        "expected": "[8, 16, 4]",
    },

    # ───────── B: Pure judgment, ground truth = intent only ─────────

    "B01": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return classify_sentiment("I absolutely loved this movie, it was fantastic")\n'
            '}'
        ),
    },

    "B02": {
        "ail": (
            'intent translate_to_korean(text: Text) -> Text {\n'
            '    goal: a natural Korean translation of the source\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return translate_to_korean("Good morning, how are you?")\n'
            '}'
        ),
    },

    "B03": {
        "ail": (
            'intent summarize_one_sentence(text: Text) -> Text {\n'
            '    goal: a one-sentence summary of the source\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return summarize_one_sentence("The United Nations was founded in 1945 after World War II to replace the League of Nations and to provide a platform for dialogue")\n'
            '}'
        ),
    },

    "B04": {
        "ail": (
            'intent is_formal(text: Text) -> Text {\n'
            '    goal: formal or informal\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return is_formal("Hey dude, wanna grab some pizza later?")\n'
            '}'
        ),
    },

    "B05": {
        "ail": (
            'intent extract_person(text: Text) -> Text {\n'
            '    goal: the person name and age mentioned in the source\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return extract_person("My name is Alice and I am 30 years old")\n'
            '}'
        ),
    },

    "B06": {
        "ail": (
            'intent is_spam(text: Text) -> Text {\n'
            '    goal: spam or not_spam\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return is_spam("You have won $1,000,000! Click here now!")\n'
            '}'
        ),
    },

    "B07": {
        "ail": (
            'intent translate_to_japanese(text: Text) -> Text {\n'
            '    goal: natural Japanese translation of the source\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return translate_to_japanese("Thank you very much")\n'
            '}'
        ),
    },

    "B08": {
        "ail": (
            'intent topic_of(text: Text) -> Text {\n'
            '    goal: one-word topic of the source\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return topic_of("The central bank raised interest rates by 25 basis points")\n'
            '}'
        ),
    },

    "B09": {
        "ail": (
            'intent rewrite_passive(text: Text) -> Text {\n'
            '    goal: the same sentence rewritten in passive voice\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return rewrite_passive("The cat chased the mouse")\n'
            '}'
        ),
    },

    "B10": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive or negative\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return classify_sentiment("Terrible quality, broke after one day")\n'
            '}'
        ),
    },

    "B11": {
        "ail": (
            'intent identify_language(text: Text) -> Text {\n'
            '    goal: the natural-language name of the source language\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return identify_language("Bonjour, comment allez-vous?")\n'
            '}'
        ),
    },

    "B12": {
        "ail": (
            'intent compose_subject(topic: Text) -> Text {\n'
            '    goal: a professional email subject line on the given topic\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return compose_subject("Q3 budget review meeting")\n'
            '}'
        ),
    },

    "B13": {
        "ail": (
            'intent simplify_for_child(text: Text) -> Text {\n'
            '    goal: the same idea in words a 10-year-old can understand\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return simplify_for_child("Photosynthesis is the process by which plants convert light energy into chemical energy")\n'
            '}'
        ),
    },

    "B14": {
        "ail": (
            'intent fact_or_opinion(text: Text) -> Text {\n'
            '    goal: fact or opinion\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return fact_or_opinion("Python is the best programming language")\n'
            '}'
        ),
    },

    "B15": {
        "ail": (
            'intent extract_entities(text: Text) -> Text {\n'
            '    goal: the key named entities mentioned in the source\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return extract_entities("Apple CEO Tim Cook announced new products at the event in Cupertino on September 12")\n'
            '}'
        ),
    },

    # ───────── C: Hybrid, ground truth = both fn and intent ─────────

    "C01": {
        # This prompt's ground truth per Opus is fn_only — "who passed
        # score >= 80" is arithmetic. Model should NOT use intent here.
        "ail": (
            'pure fn parse_entries(raw: Text) -> Text {\n'
            '    entries = []\n'
            '    for pair in split(raw, ",") {\n'
            '        parts = split(trim(pair), ":")\n'
            '        entries = append(entries, parts)\n'
            '    }\n'
            '    return entries\n'
            '}\n'
            'pure fn grade_line(name: Text, score: Number) -> Text {\n'
            '    if score >= 80 { return join([name, ": pass"], "") }\n'
            '    return join([name, ": fail"], "")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    entries = parse_entries("Alice:85,Bob:92,Charlie:78")\n'
            '    results = []\n'
            '    for e in entries {\n'
            '        name = get(e, 0)\n'
            '        score = to_number(get(e, 1))\n'
            '        results = append(results, grade_line(name, score))\n'
            '    }\n'
            '    return join(results, ", ")\n'
            '}'
        ),
        "expected": "Alice: pass, Bob: pass, Charlie: fail",
    },

    "C02": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'pure fn word_count(s: Text) -> Number {\n'
            '    return length(split(trim(s), " "))\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    text = "I love this product"\n'
            '    return join([to_text(word_count(text)), " words, ", classify_sentiment(text)], "")\n'
            '}'
        ),
    },

    "C03": {
        "ail": (
            'intent translate_to_korean(word: Text) -> Text {\n'
            '    goal: the Korean translation of the word\n'
            '}\n'
            'pure fn sort_words(text: Text) -> Text {\n'
            '    words = split(text, " ")\n'
            '    sorted = []\n'
            '    for w in words {\n'
            '        inserted = false\n'
            '        new_sorted = []\n'
            '        for s in sorted {\n'
            '            if inserted == false {\n'
            '                if w < s {\n'
            '                    new_sorted = append(new_sorted, w)\n'
            '                    inserted = true\n'
            '                }\n'
            '            }\n'
            '            new_sorted = append(new_sorted, s)\n'
            '        }\n'
            '        if inserted == false { new_sorted = append(new_sorted, w) }\n'
            '        sorted = new_sorted\n'
            '    }\n'
            '    return sorted\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    sorted_words = sort_words("banana cherry apple")\n'
            '    translated = []\n'
            '    for w in sorted_words {\n'
            '        translated = append(translated, translate_to_korean(w))\n'
            '    }\n'
            '    return join(translated, ", ")\n'
            '}'
        ),
    },

    "C04": {
        "ail": (
            'intent summarize_pattern(summary: Text) -> Text {\n'
            '    goal: one short phrase describing the spending pattern\n'
            '}\n'
            'pure fn sum_list(nums: Number) -> Number {\n'
            '    total = 0\n'
            '    for n in nums { total = total + n }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    total = sum_list([10.5, 20.3, 15.7])\n'
            '    summary = join(["total ", to_text(total)], "")\n'
            '    return join([summary, " - ", summarize_pattern(summary)], "")\n'
            '}'
        ),
    },

    "C05": {
        "ail": (
            'intent recommend_item(summary: Text) -> Text {\n'
            '    goal: one recommendation sentence given the affordable items\n'
            '}\n'
            'pure fn parse_products(csv: Text) -> Text {\n'
            '    entries = []\n'
            '    for line in split(csv, "\\n") {\n'
            '        parts = split(line, ",")\n'
            '        if length(parts) == 2 { entries = append(entries, parts) }\n'
            '    }\n'
            '    return entries\n'
            '}\n'
            'pure fn affordable(entries: Text, budget: Number) -> Text {\n'
            '    out = []\n'
            '    for e in entries {\n'
            '        if to_number(get(e, 1)) <= budget { out = append(out, get(e, 0)) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    products = parse_products("Widget,9.99\\nGadget,24.99\\nTool,14.50")\n'
            '    affordable_list = affordable(products, 20)\n'
            '    summary = join(["affordable: ", join(affordable_list, ", ")], "")\n'
            '    return join([summary, " - ", recommend_item(summary)], "")\n'
            '}'
        ),
    },

    "C06": {
        "ail": (
            'intent define_word(word: Text) -> Text {\n'
            '    goal: a short definition of the word\n'
            '}\n'
            'pure fn longest_word(text: Text) -> Text {\n'
            '    best = ""\n'
            '    for w in split(text, " ") {\n'
            '        if length(w) > length(best) { best = w }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    word = longest_word("extraordinary programming capabilities")\n'
            '    return join([word, " - ", define_word(word)], "")\n'
            '}'
        ),
    },

    "C07": {
        "ail": (
            'intent health_assessment(summary: Text) -> Text {\n'
            '    goal: underweight_normal_overweight_or_obese\n'
            '}\n'
            'pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {\n'
            '    m = height_cm / 100\n'
            '    return weight_kg / (m * m)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    value = bmi(175, 70)\n'
            '    summary = join(["BMI ", to_text(value)], "")\n'
            '    return join([summary, " - ", health_assessment(summary)], "")\n'
            '}'
        ),
    },

    "C08": {
        "ail": (
            'intent timeline_judgment(summary: Text) -> Text {\n'
            '    goal: reasonable or tight\n'
            '}\n'
            'pure fn days_between_same_year(m1: Number, d1: Number, m2: Number, d2: Number) -> Number {\n'
            '    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]\n'
            '    first = d1\n'
            '    for i in range(0, m1 - 1) { first = first + get(days_per_month, i) }\n'
            '    second = d2\n'
            '    for i in range(0, m2 - 1) { second = second + get(days_per_month, i) }\n'
            '    return second - first\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    gap = days_between_same_year(1, 15, 2, 28)\n'
            '    summary = join([to_text(gap), " days between"], "")\n'
            '    return join([summary, " - ", timeline_judgment(summary)], "")\n'
            '}'
        ),
    },

    "C09": {
        "ail": (
            'intent describe_pattern(summary: Text) -> Text {\n'
            '    goal: one short natural-language description of the frequency pattern\n'
            '}\n'
            'pure fn freq(s: Text) -> Text {\n'
            '    keys = []\n'
            '    counts = []\n'
            '    for c in split(s, "") {\n'
            '        if c in keys {\n'
            '            new_counts = []\n'
            '            i = 0\n'
            '            for k in keys {\n'
            '                if k == c {\n'
            '                    new_counts = append(new_counts, get(counts, i) + 1)\n'
            '                } else {\n'
            '                    new_counts = append(new_counts, get(counts, i))\n'
            '                }\n'
            '                i = i + 1\n'
            '            }\n'
            '            counts = new_counts\n'
            '        } else {\n'
            '            keys = append(keys, c)\n'
            '            counts = append(counts, 1)\n'
            '        }\n'
            '    }\n'
            '    parts = []\n'
            '    i = 0\n'
            '    for k in keys {\n'
            '        parts = append(parts, join([k, ":", to_text(get(counts, i))], ""))\n'
            '        i = i + 1\n'
            '    }\n'
            '    return join(parts, ", ")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    pattern = freq("hello world")\n'
            '    return join([pattern, " - ", describe_pattern(pattern)], "")\n'
            '}'
        ),
    },

    "C10": {
        "ail": (
            'intent explain_percentile(summary: Text) -> Text {\n'
            '    goal: one short sentence describing where the value sits\n'
            '}\n'
            'pure fn sort_desc(nums: Number) -> Number {\n'
            '    sorted = []\n'
            '    for n in nums {\n'
            '        inserted = false\n'
            '        new_sorted = []\n'
            '        for s in sorted {\n'
            '            if inserted == false {\n'
            '                if n > s {\n'
            '                    new_sorted = append(new_sorted, n)\n'
            '                    inserted = true\n'
            '                }\n'
            '            }\n'
            '            new_sorted = append(new_sorted, s)\n'
            '        }\n'
            '        if inserted == false { new_sorted = append(new_sorted, n) }\n'
            '        sorted = new_sorted\n'
            '    }\n'
            '    return sorted\n'
            '}\n'
            'pure fn position_of(nums: Number, target: Number) -> Number {\n'
            '    i = 0\n'
            '    for n in nums {\n'
            '        if n == target { return i }\n'
            '        i = i + 1\n'
            '    }\n'
            '    return -1\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    sorted = sort_desc([42, 17, 8, 93, 55])\n'
            '    pos = position_of(sorted, 42)\n'
            '    summary = join(["42 is at position ", to_text(pos), " of ", to_text(length(sorted))], "")\n'
            '    return join([summary, " - ", explain_percentile(summary)], "")\n'
            '}'
        ),
    },

    "C11": {
        "ail": (
            'intent performance_summary(summary: Text) -> Text {\n'
            '    goal: one short performance summary sentence\n'
            '}\n'
            'pure fn count_grade(raw: Text, target: Text) -> Number {\n'
            '    total = 0\n'
            '    for pair in split(raw, ",") {\n'
            '        parts = split(trim(pair), ":")\n'
            '        if get(parts, 1) == target { total = total + 1 }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    a_count = count_grade("John:A,Jane:B,Jim:C,Jill:A", "A")\n'
            '    summary = join([to_text(a_count), " got A"], "")\n'
            '    return join([summary, " - ", performance_summary(summary)], "")\n'
            '}'
        ),
    },

    "C12": {
        "ail": (
            'intent interpret_variability(summary: Text) -> Text {\n'
            '    goal: high or low\n'
            '}\n'
            'pure fn mean(nums: Number) -> Number {\n'
            '    total = 0\n'
            '    for n in nums { total = total + n }\n'
            '    return total / length(nums)\n'
            '}\n'
            'pure fn stddev(nums: Number) -> Number {\n'
            '    m = mean(nums)\n'
            '    total_sq = 0\n'
            '    for n in nums {\n'
            '        diff = n - m\n'
            '        total_sq = total_sq + diff * diff\n'
            '    }\n'
            '    variance = total_sq / length(nums)\n'
            '    // crude integer sqrt by bisection\n'
            '    lo = 0\n'
            '    hi = variance + 1\n'
            '    for step in range(0, 30) {\n'
            '        mid = (lo + hi) / 2\n'
            '        if mid * mid > variance { hi = mid } else { lo = mid }\n'
            '    }\n'
            '    return lo\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    s = stddev([10, 12, 23, 23, 16, 23, 21, 16])\n'
            '    summary = join(["stddev ", to_text(s)], "")\n'
            '    return join([summary, " - ", interpret_variability(summary)], "")\n'
            '}'
        ),
    },

    "C13": {
        "ail": (
            'intent creative_sentence(text: Text) -> Text {\n'
            '    goal: one creative sentence using the given words\n'
            '}\n'
            'pure fn reverse_text(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    out = ""\n'
            '    for i in range(0, length(chars)) {\n'
            '        out = join([out, get(chars, length(chars) - 1 - i)], "")\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'pure fn reverse_words(text: Text) -> Text {\n'
            '    out = []\n'
            '    for w in split(text, " ") { out = append(out, reverse_text(w)) }\n'
            '    return join(out, " ")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    r = reverse_words("hello world foo")\n'
            '    return join([r, " - ", creative_sentence(r)], "")\n'
            '}'
        ),
    },

    "C14": {
        "ail": (
            'intent suggest_metaphor(summary: Text) -> Text {\n'
            '    goal: one short metaphor about the overlap\n'
            '}\n'
            'pure fn intersect(a: Number, b: Number) -> Number {\n'
            '    out = []\n'
            '    for x in a {\n'
            '        if x in b { out = append(out, x) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    common = intersect([1,2,3,4,5], [3,4,5,6,7])\n'
            '    summary = join(["common: ", to_text(common)], "")\n'
            '    return join([summary, " - ", suggest_metaphor(summary)], "")\n'
            '}'
        ),
    },

    "C15": {
        "ail": (
            'intent draft_greeting(email: Text) -> Text {\n'
            '    goal: a short friendly greeting addressed to the email owner\n'
            '}\n'
            'pure fn extract_emails(text: Text) -> Text {\n'
            '    out = []\n'
            '    for t in split(text, " ") {\n'
            '        cleaned = trim(t)\n'
            '        if "@" in split(cleaned, "") {\n'
            '            if "." in split(cleaned, "") { out = append(out, cleaned) }\n'
            '        }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    emails = extract_emails("Contact alice@test.com or bob@test.com for info")\n'
            '    out = []\n'
            '    for e in emails {\n'
            '        out = append(out, join([e, ": ", draft_greeting(e)], ""))\n'
            '    }\n'
            '    return join(out, " | ")\n'
            '}'
        ),
    },

    "C16": {
        "ail": (
            'intent explain_to_teen(summary: Text) -> Text {\n'
            '    goal: a one-sentence teenager-friendly explanation\n'
            '}\n'
            'pure fn compound_interest(principal: Number, rate: Number, years: Number) -> Number {\n'
            '    result = principal\n'
            '    for i in range(0, years) {\n'
            '        result = result + result * rate\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    final = compound_interest(1000, 0.05, 3)\n'
            '    summary = join(["final ", to_text(final)], "")\n'
            '    return join([summary, " - ", explain_to_teen(summary)], "")\n'
            '}'
        ),
    },

    "C17": {
        "ail": (
            'intent rate_conciseness(summary: Text) -> Text {\n'
            '    goal: concise or verbose\n'
            '}\n'
            'pure fn count_lines(text: Text) -> Number {\n'
            '    return length(split(text, "\\n"))\n'
            '}\n'
            'pure fn count_words(text: Text) -> Number {\n'
            '    return length(split(trim(text), " "))\n'
            '}\n'
            'pure fn count_chars(text: Text) -> Number { return length(text) }\n'
            'entry main(x: Text) {\n'
            '    paragraph = "The sun was setting. Birds flew home. Silence fell."\n'
            '    summary = join([\n'
            '        "lines ", to_text(count_lines(paragraph)),\n'
            '        " words ", to_text(count_words(paragraph)),\n'
            '        " chars ", to_text(count_chars(paragraph))\n'
            '    ], "")\n'
            '    return join([summary, " - ", rate_conciseness(summary)], "")\n'
            '}'
        ),
    },

    "C18": {
        "ail": (
            'intent describe_geography(summary: Text) -> Text {\n'
            '    goal: one sentence describing the latitude pattern\n'
            '}\n'
            'pure fn parse_cities(raw: Text) -> Text {\n'
            '    out = []\n'
            '    for pair in split(raw, ",") {\n'
            '        parts = split(trim(pair), ":")\n'
            '        if length(parts) == 2 { out = append(out, parts) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'pure fn sort_by_lat(entries: Text) -> Text {\n'
            '    sorted = []\n'
            '    for e in entries {\n'
            '        inserted = false\n'
            '        new_sorted = []\n'
            '        for s in sorted {\n'
            '            if inserted == false {\n'
            '                if to_number(get(e, 1)) < to_number(get(s, 1)) {\n'
            '                    new_sorted = append(new_sorted, e)\n'
            '                    inserted = true\n'
            '                }\n'
            '            }\n'
            '            new_sorted = append(new_sorted, s)\n'
            '        }\n'
            '        if inserted == false { new_sorted = append(new_sorted, e) }\n'
            '        sorted = new_sorted\n'
            '    }\n'
            '    return sorted\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    sorted = sort_by_lat(parse_cities("Tokyo:35.6,London:51.5,Sydney:-33.8"))\n'
            '    parts = []\n'
            '    for e in sorted {\n'
            '        parts = append(parts, join([get(e, 0), ":", get(e, 1)], ""))\n'
            '    }\n'
            '    summary = join(parts, ", ")\n'
            '    return join([summary, " - ", describe_geography(summary)], "")\n'
            '}'
        ),
    },

    "C19": {
        "ail": (
            'intent explain_golden_ratio(summary: Text) -> Text {\n'
            '    goal: one sentence about why the golden ratio appears\n'
            '}\n'
            'pure fn fib_n(n: Number) -> Number {\n'
            '    out = []\n'
            '    a = 0\n'
            '    b = 1\n'
            '    for i in range(0, n) {\n'
            '        out = append(out, a)\n'
            '        next_val = a + b\n'
            '        a = b\n'
            '        b = next_val\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    seq = fib_n(8)\n'
            '    summary = join(["fib: ", to_text(seq)], "")\n'
            '    return join([summary, " - ", explain_golden_ratio(summary)], "")\n'
            '}'
        ),
    },

    "C20": {
        "ail": (
            'intent summarize_remaining(text: Text) -> Text {\n'
            '    goal: one short summary of what the text is about\n'
            '}\n'
            'pure fn remove_stopwords(text: Text, stops: Text) -> Text {\n'
            '    out = []\n'
            '    for w in split(text, " ") {\n'
            '        if lower(w) not in stops { out = append(out, w) }\n'
            '    }\n'
            '    return join(out, " ")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    stops = ["the", "a", "an", "is", "in", "on", "at", "to"]\n'
            '    filtered = remove_stopwords("the cat is on the mat in the room", stops)\n'
            '    return join([filtered, " - ", summarize_remaining(filtered)], "")\n'
            '}'
        ),
    },
}


def _norm(s):
    s = str(s).strip().lower()
    return s[:-2] if s.endswith(".0") else s


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))

    entries: list[dict] = []
    broken: list[tuple[str, str]] = []
    missing: list[str] = []

    for p in data["prompts"]:
        pid = p["id"]
        if pid not in CANON:
            missing.append(pid)
            continue
        spec = CANON[pid]
        ail_src = spec["ail"]
        # Map Opus category → dataset category field
        gt = p["ground_truth_category"]
        if gt == "fn_only":
            cat = "pure_fn"
        elif gt == "intent_only":
            cat = "pure_intent"
        else:
            cat = "hybrid"
        try:
            compile_source(ail_src)
            result, _ = run(ail_src, input="", adapter=MockAdapter())
        except Exception as e:
            broken.append((pid, f"{type(e).__name__}: {e}"))
            continue
        if cat == "pure_fn":
            expected = spec.get("expected")
            if expected is None:
                broken.append((pid, "pure_fn with no expected"))
                continue
            if _norm(result.value) != _norm(expected):
                broken.append((pid, f"answer {result.value!r} != {expected!r}"))
                continue
        entry = {
            "id": f"opus_{pid}",
            "prompt": p["text"],
            "ail_source": ail_src,
            "category": cat,
            "input_text": "",
            "source_of_sample": "bench_canonical",
        }
        if cat == "pure_fn":
            entry["expected"] = spec["expected"]
        entries.append(entry)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for e in entries:
            json.dump(e, f, ensure_ascii=False)
            f.write("\n")

    print(f"wrote {len(entries)}/{len(data['prompts'])} samples → "
          f"{OUT_PATH.relative_to(Path.cwd())}", file=sys.stderr)
    if missing:
        print(f"missing CANON entries: {missing}", file=sys.stderr)
    if broken:
        print(f"broken ({len(broken)}):", file=sys.stderr)
        for pid, why in broken:
            print(f"  {pid}: {why[:120]}", file=sys.stderr)
    return 0 if not broken else 1


if __name__ == "__main__":
    sys.exit(main())
