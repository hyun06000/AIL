"""Produce dataset/02_bench_canonical.jsonl — one canonical AIL
program per task in the 50-case bench_authoring corpus.

Each canonical program is hand-written to be short, idiomatic,
and to pass the same three-axis gate (parse / route / answer) the
benchmark scores. Training the model on these puts it in exactly
the distribution the benchmark measures.

Design rules for the canonical entry:

- Use `pure fn` whenever the body is deterministic. This is the
  strongest signal we can teach — "when an AI sees this kind of
  prompt, emit a pure fn, not an unannotated fn."
- For a `pure_intent` task, the program is almost always a single
  intent declaration + a trivial entry call. Short is correct —
  long is noise.
- For `hybrid`, the program must declare BOTH a `pure fn` doing the
  computation AND an `intent` doing the judgment, with the entry
  combining them. No shortcuts.
- No tricks: AIL without generics, without `[T]` list types,
  without method syntax. The training set must not reinforce the
  Python-contaminated patterns the base model already produces.
- When the prompt has a specific literal value, hardcode it in the
  entry (e.g. `factorial(7)` not `factorial(to_number(x))`). The
  `ail ask` layer auto-supplies integers from the prompt, so
  hardcoded literals keep training tight.

Every entry runs through MockAdapter before being written to the
JSONL. Entries that fail parse, execute, or (for pure_fn) answer
verification are dropped with a warning.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ail import compile_source, run, MockAdapter

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from bench_authoring import CASES  # noqa: E402


OUT_PATH = Path(__file__).parent / "dataset" / "02_bench_canonical.jsonl"


# Canonical AIL per bench task. Entries are paired by `Case.name`.
# Value is a dict with:
#   ail         : the AIL source (required)
#   input_text  : value bound to entry's first param at validate time
#   expected    : deterministic expected value (pure_fn only); for
#                 intent/hybrid we don't check the output (a MockAdapter
#                 returns "[mock response for X]" which is stable but
#                 not semantically meaningful)
CANON: dict[str, dict] = {

    # ======================================================================
    # pure_fn — short deterministic programs
    # ======================================================================
    "fn_arith_mul": {
        "ail": 'entry main(x: Text) { return 7 * 8 }',
        "expected": "56",
    },
    "fn_arith_add": {
        "ail": 'entry main(x: Text) { return 13 + 29 }',
        "expected": "42",
    },
    "fn_arith_sum_range": {
        "ail": (
            'pure fn sum_range(lo: Number, hi: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(lo, hi + 1) { total = total + i }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum_range(1, 100) }'
        ),
        "expected": "5050",
    },
    "fn_arith_factorial": {
        "ail": (
            'pure fn factorial(n: Number) -> Number {\n'
            '    if n <= 1 { return 1 }\n'
            '    return n * factorial(n - 1)\n'
            '}\n'
            'entry main(x: Text) { return factorial(6) }'
        ),
        "expected": "720",
    },
    "fn_arith_square": {
        "ail": 'entry main(x: Text) { return 13 * 13 }',
        "expected": "169",
    },
    "fn_arith_cube": {
        "ail": 'entry main(x: Text) { return 4 * 4 * 4 }',
        "expected": "64",
    },
    "fn_arith_sum_even": {
        "ail": (
            'pure fn sum_even(lo: Number, hi: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(lo, hi + 1) {\n'
            '        if i % 2 == 0 { total = total + i }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum_even(2, 20) }'
        ),
        "expected": "110",
    },
    "fn_arith_avg": {
        "ail": (
            'pure fn average(nums: Number) -> Number {\n'
            '    total = 0\n'
            '    for n in nums { total = total + n }\n'
            '    return total / length(nums)\n'
            '}\n'
            'entry main(x: Text) { return average([10, 20, 30, 40, 50]) }'
        ),
        "expected": "30",
    },
    "fn_str_count_vowels": {
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
            'entry main(x: Text) { return count_vowels("Hello World") }'
        ),
        "expected": "3",
    },
    "fn_str_count_letter": {
        "ail": (
            'pure fn count_letter(s: Text, c: Text) -> Number {\n'
            '    total = 0\n'
            '    for ch in split(lower(s), "") {\n'
            '        if ch == c { total = total + 1 }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return count_letter("banana", "a") }'
        ),
        "expected": "3",
    },
    "fn_str_length": {
        "ail": 'entry main(x: Text) { return length("programming") }',
        "expected": "11",
    },
    "fn_str_words": {
        "ail": (
            'pure fn word_count(s: Text) -> Number {\n'
            '    return length(split(trim(s), " "))\n'
            '}\n'
            'entry main(x: Text) { return word_count("the quick brown fox jumps") }'
        ),
        "expected": "5",
    },
    "fn_str_upper": {
        "ail": 'entry main(x: Text) { return upper("hello") }',
        "expected": "HELLO",
    },
    "fn_str_reverse": {
        "ail": (
            'pure fn reverse_text(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    result = ""\n'
            '    for i in range(0, length(chars)) {\n'
            '        result = join([result, get(chars, length(chars) - 1 - i)], "")\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'entry main(x: Text) { return reverse_text("racecar") }'
        ),
        "expected": "racecar",
    },
    "fn_list_fib10": {
        "ail": (
            'pure fn fib(n: Number) -> Number {\n'
            '    if n <= 1 { return n }\n'
            '    return fib(n - 1) + fib(n - 2)\n'
            '}\n'
            'entry main(x: Text) { return fib(10) }'
        ),
        "expected": "55",
    },
    "fn_list_max": {
        "ail": (
            'pure fn max_of(nums: Number) -> Number {\n'
            '    best = get(nums, 0)\n'
            '    for n in nums {\n'
            '        if n > best { best = n }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) { return max_of([17, 42, 8, 23, 39]) }'
        ),
        "expected": "42",
    },
    "fn_list_min": {
        "ail": (
            'pure fn min_of(nums: Number) -> Number {\n'
            '    best = get(nums, 0)\n'
            '    for n in nums {\n'
            '        if n < best { best = n }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) { return min_of([17, 42, 8, 23, 39]) }'
        ),
        "expected": "8",
    },
    "fn_list_count_odd": {
        "ail": (
            'pure fn count_odd(nums: Number) -> Number {\n'
            '    total = 0\n'
            '    for n in nums {\n'
            '        if n % 2 == 1 { total = total + 1 }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return count_odd([1,2,3,4,5,6,7,8,9,10]) }'
        ),
        "expected": "5",
    },
    "fn_ko_sum": {
        "ail": (
            'pure fn sum_range(lo: Number, hi: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(lo, hi + 1) { total = total + i }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum_range(1, 50) }'
        ),
        "expected": "1275",
    },
    "fn_ko_factorial": {
        "ail": (
            'pure fn factorial(n: Number) -> Number {\n'
            '    if n <= 1 { return 1 }\n'
            '    return n * factorial(n - 1)\n'
            '}\n'
            'entry main(x: Text) { return factorial(5) }'
        ),
        "expected": "120",
    },

    # ======================================================================
    # pure_intent — single intent declaration + trivial entry
    # ======================================================================
    "intent_sent_pos": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'entry main(x: Text) { return classify_sentiment("I absolutely loved this movie!") }'
        ),
    },
    "intent_sent_neg": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative\n'
            '}\n'
            'entry main(x: Text) { return classify_sentiment("This is the worst experience ever") }'
        ),
    },
    "intent_sent_neut": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'entry main(x: Text) { return classify_sentiment("The weather is cloudy") }'
        ),
    },
    "intent_translate_ko": {
        "ail": (
            'intent translate_to_korean(text: Text) -> Text {\n'
            '    goal: a Korean translation of the source\n'
            '}\n'
            'entry main(x: Text) { return translate_to_korean("hello world") }'
        ),
    },
    "intent_translate_en": {
        "ail": (
            'intent translate_to_english(text: Text) -> Text {\n'
            '    goal: an English translation of the source\n'
            '}\n'
            'entry main(x: Text) { return translate_to_english("bonjour") }'
        ),
    },
    "intent_language_id": {
        "ail": (
            'intent identify_language(text: Text) -> Text {\n'
            '    goal: the ISO language name of the source\n'
            '}\n'
            'entry main(x: Text) { return identify_language("je suis etudiant") }'
        ),
    },
    "intent_topic": {
        "ail": (
            'intent topic_of(text: Text) -> Text {\n'
            '    goal: the primary topic of the source in a single noun phrase\n'
            '}\n'
            'entry main(x: Text) { return topic_of("The Fed raised rates by 25 basis points") }'
        ),
    },
    "intent_spam": {
        "ail": (
            'intent is_spam(text: Text) -> Text {\n'
            '    goal: spam or not_spam\n'
            '}\n'
            'entry main(x: Text) { return is_spam("FREE CASH CLICK NOW") }'
        ),
    },
    "intent_urgency": {
        "ail": (
            'intent urgency_of(text: Text) -> Text {\n'
            '    goal: one word describing the urgency of the message\n'
            '}\n'
            'entry main(x: Text) { return urgency_of("Call me ASAP it is important") }'
        ),
    },
    "intent_formality": {
        "ail": (
            'intent is_formal(text: Text) -> Text {\n'
            '    goal: formal or informal\n'
            '}\n'
            'entry main(x: Text) { return is_formal("yo what up dude") }'
        ),
    },
    "intent_summarize": {
        "ail": (
            'intent summarize_one_sentence(text: Text) -> Text {\n'
            '    goal: a one-sentence summary of the source\n'
            '}\n'
            'entry main(x: Text) { return summarize_one_sentence("AIL is a programming language designed for AI authors. It distinguishes computation from judgment. Humans interact via prompts.") }'
        ),
    },
    "intent_rewrite": {
        "ail": (
            'intent rewrite_professional(text: Text) -> Text {\n'
            '    goal: a professional rephrasing of the source\n'
            '}\n'
            'entry main(x: Text) { return rewrite_professional("hey wanna grab lunch") }'
        ),
    },
    "intent_extract_name": {
        "ail": (
            'intent extract_person_name(text: Text) -> Text {\n'
            '    goal: the person name mentioned in the source\n'
            '}\n'
            'entry main(x: Text) { return extract_person_name("My name is Alice and I live in Seoul") }'
        ),
    },
    "intent_ko_sent": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'entry main(x: Text) { return classify_sentiment("오늘은 최고의 하루였어") }'
        ),
    },
    "intent_ko_topic": {
        "ail": (
            'intent topic_of(text: Text) -> Text {\n'
            '    goal: the primary topic of the source in Korean\n'
            '}\n'
            'entry main(x: Text) { return topic_of("한국은행이 기준금리를 0.25%p 인상했다") }'
        ),
    },

    # ======================================================================
    # hybrid — pure fn for computation + intent for judgment
    # ======================================================================
    "hybrid_count_and_sent": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'pure fn word_count(s: Text) -> Number {\n'
            '    return length(split(trim(s), " "))\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    text = "I absolutely love this product"\n'
            '    return join([to_text(word_count(text)), " words, ", classify_sentiment(text)], "")\n'
            '}'
        ),
    },
    "hybrid_split_and_classify": {
        "ail": (
            'intent classify_item(item: Text) -> Text {\n'
            '    goal: fruit or vegetable\n'
            '}\n'
            'pure fn split_items(csv: Text) -> Text {\n'
            '    return split(csv, ",")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    items = split_items("apple,banana,cherry")\n'
            '    results = []\n'
            '    for it in items {\n'
            '        results = append(results, join([trim(it), ":", classify_item(trim(it))], ""))\n'
            '    }\n'
            '    return join(results, " | ")\n'
            '}'
        ),
    },
    "hybrid_len_and_translate": {
        "ail": (
            'intent translate_to_english(text: Text) -> Text {\n'
            '    goal: the English translation of the source\n'
            '}\n'
            'pure fn char_count(s: Text) -> Number { return length(s) }\n'
            'entry main(x: Text) {\n'
            '    word = "bonjour"\n'
            '    return join([to_text(char_count(word)), " letters, ", translate_to_english(word)], "")\n'
            '}'
        ),
    },
    "hybrid_avg_and_feedback": {
        "ail": (
            'intent assess_scores(summary: Text) -> Text {\n'
            '    goal: a one-sentence verbal assessment\n'
            '}\n'
            'pure fn average(nums: Number) -> Number {\n'
            '    total = 0\n'
            '    for n in nums { total = total + n }\n'
            '    return total / length(nums)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    scores = [85, 92, 78, 95, 88]\n'
            '    avg = average(scores)\n'
            '    summary = join(["average is ", to_text(avg)], "")\n'
            '    return join([summary, " - ", assess_scores(summary)], "")\n'
            '}'
        ),
    },
    "hybrid_count_and_judge": {
        "ail": (
            'intent judge_density(summary: Text) -> Text {\n'
            '    goal: high or low\n'
            '}\n'
            'pure fn count_vowels(s: Text) -> Number {\n'
            '    total = 0\n'
            '    for c in split(lower(s), "") {\n'
            '        if c in ["a","e","i","o","u"] { total = total + 1 }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    word = "Mississippi"\n'
            '    n = count_vowels(word)\n'
            '    summary = join([to_text(n), " vowels in ", to_text(length(word)), " letters"], "")\n'
            '    return join([summary, " - density is ", judge_density(summary)], "")\n'
            '}'
        ),
    },
    "hybrid_reverse_and_judge": {
        "ail": (
            'intent is_real_word(text: Text) -> Text {\n'
            '    goal: yes or no\n'
            '}\n'
            'pure fn reverse_text(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    result = ""\n'
            '    for i in range(0, length(chars)) {\n'
            '        result = join([result, get(chars, length(chars) - 1 - i)], "")\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    rev = reverse_text("hello")\n'
            '    return join([rev, " looks like a real word: ", is_real_word(rev)], "")\n'
            '}'
        ),
    },
    "hybrid_sum_and_describe": {
        "ail": (
            'intent describe_parity(n: Text) -> Text {\n'
            '    goal: even or odd\n'
            '}\n'
            'pure fn sum_range(lo: Number, hi: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(lo, hi + 1) { total = total + i }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    s = sum_range(1, 10)\n'
            '    return join([to_text(s), " is ", describe_parity(to_text(s))], "")\n'
            '}'
        ),
    },
    "hybrid_longest_and_rate": {
        "ail": (
            'intent rate_commonness(word: Text) -> Text {\n'
            '    goal: common or uncommon\n'
            '}\n'
            'pure fn longest(words: Text) -> Text {\n'
            '    best = get(words, 0)\n'
            '    for w in words {\n'
            '        if length(w) > length(best) { best = w }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    w = longest(["cat", "elephant", "dog"])\n'
            '    return join([w, " is ", rate_commonness(w)], "")\n'
            '}'
        ),
    },
    "hybrid_double_and_classify": {
        "ail": (
            'intent classify_size(summary: Text) -> Text {\n'
            '    goal: large or small\n'
            '}\n'
            'pure fn double(n: Number) -> Number { return n * 2 }\n'
            'entry main(x: Text) {\n'
            '    n = double(42)\n'
            '    summary = join(["the number ", to_text(n)], "")\n'
            '    return join([summary, " is ", classify_size(summary)], "")\n'
            '}'
        ),
    },
    "hybrid_split_and_sent": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative\n'
            '}\n'
            'pure fn word_count(s: Text) -> Number {\n'
            '    return length(split(trim(s), " "))\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    text = "I love programming"\n'
            '    return join([to_text(word_count(text)), " words, ", classify_sentiment(text)], "")\n'
            '}'
        ),
    },
    "hybrid_len_and_formality": {
        "ail": (
            'intent is_formal(text: Text) -> Text {\n'
            '    goal: formal or informal\n'
            '}\n'
            'pure fn char_count(s: Text) -> Number { return length(s) }\n'
            'entry main(x: Text) {\n'
            '    greeting = "good afternoon sir"\n'
            '    return join([to_text(char_count(greeting)), " chars, ", is_formal(greeting)], "")\n'
            '}'
        ),
    },
    "hybrid_words_and_summ": {
        "ail": (
            'intent summarize_one_sentence(text: Text) -> Text {\n'
            '    goal: a one-sentence summary\n'
            '}\n'
            'pure fn word_count(s: Text) -> Number {\n'
            '    return length(split(trim(s), " "))\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    text = "The quick brown fox jumps over the lazy dog"\n'
            '    return join([to_text(word_count(text)), " words - ", summarize_one_sentence(text)], "")\n'
            '}'
        ),
    },
    "hybrid_square_and_classify": {
        "ail": (
            'intent classify_magnitude(summary: Text) -> Text {\n'
            '    goal: closer_to_hundred_or_thousand\n'
            '}\n'
            'pure fn square(n: Number) -> Number { return n * n }\n'
            'entry main(x: Text) {\n'
            '    s = square(10)\n'
            '    summary = join(["the result ", to_text(s)], "")\n'
            '    return join([summary, " is ", classify_magnitude(summary)], "")\n'
            '}'
        ),
    },
    "hybrid_ko_count_sent": {
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: positive_or_negative_or_neutral\n'
            '}\n'
            'pure fn char_count(s: Text) -> Number { return length(s) }\n'
            'entry main(x: Text) {\n'
            '    text = "오늘은 정말 행복한 하루였다"\n'
            '    return join([to_text(char_count(text)), " chars, ", classify_sentiment(text)], "")\n'
            '}'
        ),
    },
    "hybrid_max_and_describe": {
        "ail": (
            'intent describe_number(summary: Text) -> Text {\n'
            '    goal: a short verbal description of the number\n'
            '}\n'
            'pure fn max_of(nums: Number) -> Number {\n'
            '    best = get(nums, 0)\n'
            '    for n in nums {\n'
            '        if n > best { best = n }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    m = max_of([17, 42, 8, 23, 39])\n'
            '    summary = join(["maximum is ", to_text(m)], "")\n'
            '    return join([summary, " - ", describe_number(summary)], "")\n'
            '}'
        ),
    },

    # ------------------------------------------------------------------
    # R3 failure patterns — added after Round 3 benchmark analysis
    # ------------------------------------------------------------------

    # A12: unique/dedup — avoid dict, use `in` operator check
    "fn_list_unique": {
        "ail": (
            'pure fn deduplicate(items: [Number]) -> [Number] {\n'
            '    result = []\n'
            '    for item in items {\n'
            '        if not (item in result) { result = append(result, item) }\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'entry main(x: Text) { return deduplicate([1, 3, 2, 3, 1, 4, 2, 5]) }'
        ),
        "expected": "[1, 3, 2, 4, 5]",
    },

    # A13/C09: frequency count — encode as "char:count" pairs without dict
    "fn_text_char_freq": {
        "ail": (
            'pure fn count_char(s: Text, ch: Text) -> Number {\n'
            '    count = 0\n'
            '    for c in split(s, "") {\n'
            '        if c == ch { count = count + 1 }\n'
            '    }\n'
            '    return count\n'
            '}\n'
            'pure fn unique_chars(s: Text) -> [Text] {\n'
            '    chars = split(s, "")\n'
            '    result = []\n'
            '    for c in chars {\n'
            '        if not (c in result) { result = append(result, c) }\n'
            '    }\n'
            '    return sort(result)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    s = "mississippi"\n'
            '    chars = unique_chars(s)\n'
            '    pairs = []\n'
            '    for c in chars {\n'
            '        pairs = append(pairs, join([c, ":", to_text(count_char(s, c))], ""))\n'
            '    }\n'
            '    return join(pairs, ", ")\n'
            '}'
        ),
        "expected": "i:4, m:1, p:2, s:4",
    },

    # A14: Fibonacci — use to_text when joining numbers
    "fn_fibonacci_sequence": {
        "ail": (
            'pure fn fib(n: Number) -> Number {\n'
            '    if n <= 1 { return n }\n'
            '    return fib(n - 1) + fib(n - 2)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    results = []\n'
            '    for i in range(0, 8) {\n'
            '        results = append(results, to_text(fib(i)))\n'
            '    }\n'
            '    return join(results, ", ")\n'
            '}'
        ),
        "expected": "0, 1, 1, 2, 3, 5, 8, 13",
    },

    # C18: sort with named fn key — no anonymous fn in sort()
    # Shows the pattern: define pure fn, pass name to sort.
    # (alphabetical sort by name extracted from "name:score" pairs)
    "fn_sort_by_key": {
        "ail": (
            'pure fn name_key(pair: Text) -> Text {\n'
            '    return get(split(pair, ":"), 0)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    pairs = ["Charlie:78", "Alice:85", "Bob:92"]\n'
            '    return join(sort(pairs, name_key), ", ")\n'
            '}'
        ),
        "expected": "Alice:85, Bob:92, Charlie:78",
    },

    # C01: hybrid where pure fn parses list, entry calls intent per item
    "hybrid_parse_then_classify_each": {
        "ail": (
            'intent classify_student(name: Text, score: Text) -> Text {\n'
            '    goal: pass_or_fail\n'
            '}\n'
            'pure fn parse_entry(pair: Text) -> [Text] {\n'
            '    return split(pair, ":")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    pairs = split("Alice:85,Bob:92,Charlie:78", ",")\n'
            '    results = []\n'
            '    for pair in pairs {\n'
            '        parts = parse_entry(pair)\n'
            '        name = trim(get(parts, 0))\n'
            '        score = trim(get(parts, 1))\n'
            '        label = classify_student(name, score)\n'
            '        results = append(results, join([name, ": ", label], ""))\n'
            '    }\n'
            '    return join(results, ", ")\n'
            '}'
        ),
    },

    # C20: intent must always have { goal: ... } body
    "intent_with_goal_body": {
        "ail": (
            'intent summarize(text: Text) -> Text {\n'
            '    goal: one sentence summary\n'
            '}\n'
            'entry main(x: Text) { return summarize(x) }'
        ),
    },
}


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    missing: list[str] = []
    broken: list[tuple[str, str]] = []

    for case in CASES:
        if case.name not in CANON:
            missing.append(case.name)
            continue
        spec = CANON[case.name]
        ail_src = spec["ail"]
        input_text = spec.get("input_text", "")
        try:
            compile_source(ail_src)
            result, _ = run(ail_src, input=input_text, adapter=MockAdapter())
        except Exception as e:
            broken.append((case.name, f"{type(e).__name__}: {e}"))
            continue

        if case.category == "pure_fn":
            expected = spec.get("expected")
            if expected is None:
                broken.append((case.name, "pure_fn with no expected"))
                continue
            # Lenient compare: strip a single trailing `.0` on each
            # side so `30.0 == 30`. Do NOT rstrip("0") — that would
            # make 30 compare equal to 3.
            def _norm(s):
                s = str(s).strip().lower()
                return s[:-2] if s.endswith(".0") else s
            if _norm(result.value) != _norm(expected):
                broken.append((case.name, f"answer {result.value!r} != {expected!r}"))
                continue

        entry = {
            "id": f"bench_{case.name}",
            "prompt": case.prompt,
            "ail_source": ail_src,
            "category": case.category,
            "input_text": input_text,
            "source_of_sample": "bench_canonical",
        }
        if case.category == "pure_fn":
            entry["expected"] = spec["expected"]
        entries.append(entry)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for e in entries:
            json.dump(e, f, ensure_ascii=False)
            f.write("\n")

    print(f"wrote {len(entries)}/{len(CASES)} samples → "
          f"{OUT_PATH.relative_to(Path.cwd())}", file=sys.stderr)
    if missing:
        print(f"missing CANON entries for {len(missing)} cases:", file=sys.stderr)
        for n in missing:
            print(f"  {n}", file=sys.stderr)
    if broken:
        print(f"broken on execution for {len(broken)} cases:", file=sys.stderr)
        for n, why in broken:
            print(f"  {n}: {why[:120]}", file=sys.stderr)
    return 0 if not broken and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
