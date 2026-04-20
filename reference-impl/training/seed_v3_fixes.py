"""Produce dataset/07_v3_fixes.jsonl — samples targeting the v2 benchmark
failure modes.

Created 2026-04-20 after the ail-coder:7b v2 benchmark identified two
dominant failure classes that weren't represented in the 205-sample v2
training set:

  1. Hybrid programs pairing numeric compute with an intent call — the
     v2 model's weakest category (45% parse).
  2. Programs that need the newly-added math builtins (round, sqrt,
     floor, ceil, pow). The v2 model never saw these used inside AIL,
     so when a benchmark prompt asked for BMI or std-dev it produced
     unparseable code.
  3. fn signatures using parametric type annotations (List[Number],
     Map[Text, Number], Result[Text]). Spec §2.3 says these are valid;
     no existing dataset sample exercised them, so the model either
     omitted them or produced malformed ones.

Each sample is validated exactly like the other seed files (parse +
purity + run via MockAdapter, with pure_fn outputs matched against
expected). Failures are logged and dropped.

Idempotent — re-run whenever SAMPLES changes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ail import compile_source, run, MockAdapter


OUT_PATH = Path(__file__).parent / "dataset" / "07_v3_fixes.jsonl"


SAMPLES: list[dict] = [

    # ================================================================
    # Math builtins inside pure fn — round / sqrt / floor / ceil / pow
    # ================================================================
    {
        "id": "v3_bmi_round",
        "prompt": "calculate BMI from height 175cm and weight 70kg, rounded to 2 decimal places",
        "category": "pure_fn",
        "ail": (
            'pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {\n'
            '    h_m = height_cm / 100\n'
            '    return round(weight_kg / pow(h_m, 2), 2)\n'
            '}\n'
            'entry main(x: Text) { return bmi(175, 70) }'
        ),
        "expected": "22.86",
    },
    {
        "id": "v3_euclidean_distance",
        "prompt": "compute the Euclidean distance between points (3,4) and (0,0)",
        "category": "pure_fn",
        "ail": (
            'pure fn distance(x: Number, y: Number) -> Number {\n'
            '    return sqrt(pow(x, 2) + pow(y, 2))\n'
            '}\n'
            'entry main(x: Text) { return distance(3, 4) }'
        ),
        "expected": "5",
    },
    {
        "id": "v3_compound_interest",
        "prompt": "compute compound interest on 1000 at 5% for 3 years, rounded to 2 decimals",
        "category": "pure_fn",
        "ail": (
            'pure fn compound(p: Number, r: Number, t: Number) -> Number {\n'
            '    return round(p * pow(1 + r, t), 2)\n'
            '}\n'
            'entry main(x: Text) { return compound(1000, 0.05, 3) }'
        ),
        "expected": "1157.63",
    },
    {
        "id": "v3_floor_ceil_pair",
        "prompt": "floor 2.9 and ceil 2.1, return as dash-joined",
        "category": "pure_fn",
        "ail": (
            'pure fn f(x: Number) -> Number { return floor(x) }\n'
            'pure fn c(x: Number) -> Number { return ceil(x) }\n'
            'entry main(x: Text) {\n'
            '    return join([to_text(f(2.9)), to_text(c(2.1))], "-")\n'
            '}'
        ),
        "expected": "2-3",
    },
    {
        "id": "v3_stddev_population",
        "prompt": "compute the population standard deviation of [2, 4, 4, 4, 5, 5, 7, 9]",
        "category": "pure_fn",
        "ail": (
            'pure fn sum_list(xs: List[Number]) -> Number {\n'
            '    total = 0\n'
            '    for x in xs { total = total + x }\n'
            '    return total\n'
            '}\n'
            'pure fn stddev(xs: List[Number]) -> Number {\n'
            '    n = length(xs)\n'
            '    mean = sum_list(xs) / n\n'
            '    sq_diff = 0\n'
            '    for x in xs { sq_diff = sq_diff + pow(x - mean, 2) }\n'
            '    return round(sqrt(sq_diff / n), 3)\n'
            '}\n'
            'entry main(x: Text) { return stddev([2, 4, 4, 4, 5, 5, 7, 9]) }'
        ),
        "expected": "2",
    },
    {
        "id": "v3_hypotenuse",
        "prompt": "compute hypotenuse of a right triangle with legs 5 and 12",
        "category": "pure_fn",
        "ail": (
            'pure fn hypotenuse(a: Number, b: Number) -> Number {\n'
            '    return sqrt(a * a + b * b)\n'
            '}\n'
            'entry main(x: Text) { return hypotenuse(5, 12) }'
        ),
        "expected": "13",
    },
    {
        "id": "v3_circle_area",
        "prompt": "compute the area of a circle with radius 5, rounded to 4 decimal places",
        "category": "pure_fn",
        "ail": (
            'pure fn area(r: Number) -> Number {\n'
            '    return round(3.14159265 * pow(r, 2), 4)\n'
            '}\n'
            'entry main(x: Text) { return area(5) }'
        ),
        "expected": "78.5398",
    },

    # ================================================================
    # Parametric type annotations — List[T], Map[K,V], Result[T]
    # ================================================================
    {
        "id": "v3_parametric_sum",
        "prompt": "sum a list of numbers",
        "category": "pure_fn",
        "ail": (
            'pure fn sum(xs: List[Number]) -> Number {\n'
            '    total = 0\n'
            '    for x in xs { total = total + x }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum([1, 2, 3, 4, 5]) }'
        ),
        "expected": "15",
    },
    {
        "id": "v3_parametric_max",
        "prompt": "find the largest number in a list",
        "category": "pure_fn",
        "ail": (
            'pure fn largest(xs: List[Number]) -> Number {\n'
            '    best = get(xs, 0)\n'
            '    for x in xs {\n'
            '        if x > best { best = x }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) { return largest([34, 12, 89, 3, 56, 72]) }'
        ),
        "expected": "89",
    },
    {
        "id": "v3_parametric_average",
        "prompt": "compute the average of a list of scores",
        "category": "pure_fn",
        "ail": (
            'pure fn average(scores: List[Number]) -> Number {\n'
            '    total = 0\n'
            '    for s in scores { total = total + s }\n'
            '    return total / length(scores)\n'
            '}\n'
            'entry main(x: Text) { return average([85, 92, 78, 95, 88]) }'
        ),
        "expected": "87.6",
    },
    {
        "id": "v3_parametric_filter_even",
        "prompt": "return only the even numbers from a list",
        "category": "pure_fn",
        "ail": (
            'pure fn only_even(xs: List[Number]) -> List[Number] {\n'
            '    out = []\n'
            '    for x in xs {\n'
            '        if x % 2 == 0 { out = append(out, x) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return join(only_even([1, 2, 3, 4, 5, 6, 7, 8]), ",")\n'
            '}'
        ),
        "expected": "2,4,6,8",
    },
    {
        "id": "v3_parametric_result_safe_div",
        "prompt": "safely divide two numbers; return a Result with an error on divide-by-zero",
        "category": "pure_fn",
        "ail": (
            'pure fn safe_div(a: Number, b: Number) -> Result[Number] {\n'
            '    if b == 0 { return error("divide by zero") }\n'
            '    return ok(a / b)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    r = safe_div(42, 6)\n'
            '    if is_ok(r) { return unwrap(r) }\n'
            '    return 0\n'
            '}'
        ),
        "expected": "7",
    },

    # ================================================================
    # Hybrid — numeric fn + intent judgment (benchmark-shaped)
    # ================================================================
    {
        "id": "v3_hybrid_bmi_health",
        "prompt": "calculate BMI from height 175cm weight 70kg and comment on health",
        "category": "hybrid",
        "ail": (
            'intent health_comment(bmi: Number) -> Text {\n'
            '    goal: a short health comment based on the BMI value\n'
            '}\n'
            'pure fn compute_bmi(h_cm: Number, w_kg: Number) -> Number {\n'
            '    return round(w_kg / pow(h_cm / 100, 2), 2)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    b = compute_bmi(175, 70)\n'
            '    return join([to_text(b), " — ", health_comment(b)], "")\n'
            '}'
        ),
        "input_text": "",
    },
    {
        "id": "v3_hybrid_word_count_sentiment",
        "prompt": "count words in the text and classify sentiment",
        "category": "hybrid",
        "ail": (
            'intent classify_sentiment(text: Text) -> Text {\n'
            '    goal: sentiment as positive or negative or neutral\n'
            '}\n'
            'pure fn word_count(text: Text) -> Number {\n'
            '    return length(split(text, " "))\n'
            '}\n'
            'entry main(text: Text) {\n'
            '    n = word_count(text)\n'
            '    s = classify_sentiment(text)\n'
            '    return join([to_text(n), " words, ", s], "")\n'
            '}'
        ),
        "input_text": "I love this product",
    },
    {
        "id": "v3_hybrid_avg_performance",
        "prompt": "compute the average of scores and describe the performance",
        "category": "hybrid",
        "ail": (
            'intent describe_performance(avg: Number) -> Text {\n'
            '    goal: brief natural-language performance summary\n'
            '}\n'
            'pure fn avg(xs: List[Number]) -> Number {\n'
            '    total = 0\n'
            '    for x in xs { total = total + x }\n'
            '    return round(total / length(xs), 2)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    a = avg([72, 85, 90, 68, 77])\n'
            '    return join([to_text(a), ": ", describe_performance(a)], "")\n'
            '}'
        ),
        "input_text": "",
    },
    {
        "id": "v3_hybrid_parse_scores_pass_fail",
        "prompt": "parse 'Alice:85,Bob:60,Carol:92' and list who passed (>=80)",
        "category": "hybrid",
        "ail": (
            'pure fn pass_or_fail(score: Number) -> Text {\n'
            '    if score >= 80 { return "pass" }\n'
            '    return "fail"\n'
            '}\n'
            'pure fn parse_entry(e: Text) -> Text {\n'
            '    parts = split(e, ":")\n'
            '    name = get(parts, 0)\n'
            '    score = to_number(get(parts, 1))\n'
            '    return join([name, ": ", pass_or_fail(score)], "")\n'
            '}\n'
            'entry main(text: Text) {\n'
            '    entries = split(text, ",")\n'
            '    out = []\n'
            '    for e in entries { out = append(out, parse_entry(e)) }\n'
            '    return join(out, "; ")\n'
            '}'
        ),
        "input_text": "Alice:85,Bob:60,Carol:92",
    },
    {
        "id": "v3_hybrid_total_and_advice",
        "prompt": "sum the expenses and suggest a budgeting tip",
        "category": "hybrid",
        "ail": (
            'intent budget_tip(total: Number) -> Text {\n'
            '    goal: one-sentence budgeting advice given the total\n'
            '}\n'
            'pure fn sum_list(xs: List[Number]) -> Number {\n'
            '    total = 0\n'
            '    for x in xs { total = total + x }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    total = sum_list([12.5, 28.99, 7.4, 45.0, 16.8])\n'
            '    return join([to_text(total), " — ", budget_tip(total)], "")\n'
            '}'
        ),
        "input_text": "",
    },
    {
        "id": "v3_hybrid_sort_describe",
        "prompt": "sort the list [42, 17, 8, 93, 55] descending and describe the spread",
        "category": "hybrid",
        "ail": (
            'intent describe_spread(top: Number, bot: Number) -> Text {\n'
            '    goal: one-line description of the range between top and bot\n'
            '}\n'
            'pure fn desc_sort(xs: List[Number]) -> List[Number] {\n'
            '    return reverse(sort(xs))\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    s = desc_sort([42, 17, 8, 93, 55])\n'
            '    top = get(s, 0)\n'
            '    bot = get(s, length(s) - 1)\n'
            '    return join([to_text(s), " — ", describe_spread(top, bot)], "")\n'
            '}'
        ),
        "input_text": "",
    },
    {
        "id": "v3_hybrid_count_classify_text",
        "prompt": "count characters in a text and decide if it's concise or verbose",
        "category": "hybrid",
        "ail": (
            'intent classify_length(n: Number) -> Text {\n'
            '    goal: concise or verbose based on character count\n'
            '}\n'
            'pure fn count_chars(s: Text) -> Number { return length(s) }\n'
            'entry main(text: Text) {\n'
            '    n = count_chars(text)\n'
            '    return join([to_text(n), " chars — ", classify_length(n)], "")\n'
            '}'
        ),
        "input_text": "Hello world, this is a short message.",
    },
    {
        "id": "v3_hybrid_dedupe_summarize",
        "prompt": "remove duplicates from the list and summarize what remains",
        "category": "hybrid",
        "ail": (
            'intent summarize_items(items: List[Text]) -> Text {\n'
            '    goal: one-sentence summary of the unique items\n'
            '}\n'
            'pure fn dedupe(items: List[Text]) -> List[Text] {\n'
            '    seen = []\n'
            '    for it in items {\n'
            '        if it not in seen { seen = append(seen, it) }\n'
            '    }\n'
            '    return seen\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    unique = dedupe(["apple", "banana", "apple", "cherry", "banana"])\n'
            '    return join([join(unique, ","), " — ", summarize_items(unique)], "")\n'
            '}'
        ),
        "input_text": "",
    },
    {
        "id": "v3_hybrid_interest_explain",
        "prompt": "compute compound interest then explain the result to a layperson",
        "category": "hybrid",
        "ail": (
            'intent explain_interest(principal: Number, final: Number) -> Text {\n'
            '    goal: layperson explanation of the interest gain\n'
            '}\n'
            'pure fn final_amount(p: Number, r: Number, t: Number) -> Number {\n'
            '    return round(p * pow(1 + r, t), 2)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    final = final_amount(1000, 0.05, 3)\n'
            '    return join([to_text(final), " — ", explain_interest(1000, final)], "")\n'
            '}'
        ),
        "input_text": "",
    },
    {
        "id": "v3_hybrid_days_assessment",
        "prompt": "compute days from today-minus-10 to today, then call it tight or loose",
        "category": "hybrid",
        "ail": (
            'intent timeline_ok(days: Number) -> Text {\n'
            '    goal: one word tight reasonable or loose\n'
            '}\n'
            'pure fn diff(days_ago: Number) -> Number { return days_ago }\n'
            'entry main(x: Text) {\n'
            '    d = diff(10)\n'
            '    return join([to_text(d), " days — ", timeline_ok(d)], "")\n'
            '}'
        ),
        "input_text": "",
    },
    {
        "id": "v3_hybrid_char_freq_describe",
        "prompt": "count the length of the text and describe the character pattern",
        "category": "hybrid",
        "ail": (
            'intent describe_pattern(text: Text) -> Text {\n'
            '    goal: brief description of the text shape\n'
            '}\n'
            'pure fn char_count(s: Text) -> Number { return length(s) }\n'
            'entry main(text: Text) {\n'
            '    n = char_count(text)\n'
            '    return join([to_text(n), " chars: ", describe_pattern(text)], "")\n'
            '}'
        ),
        "input_text": "mississippi",
    },
    {
        "id": "v3_hybrid_reverse_creative",
        "prompt": "reverse each word in the text then use them in a creative sentence",
        "category": "hybrid",
        "ail": (
            'intent creative_sentence(words: List[Text]) -> Text {\n'
            '    goal: one playful sentence using the supplied words\n'
            '}\n'
            'pure fn reverse_text(s: Text) -> Text {\n'
            '    chars = split(s, "")\n'
            '    out = ""\n'
            '    for i in range(0, length(chars)) {\n'
            '        out = join([out, get(chars, length(chars) - 1 - i)], "")\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'pure fn reverse_each(text: Text) -> List[Text] {\n'
            '    words = split(text, " ")\n'
            '    out = []\n'
            '    for w in words { out = append(out, reverse_text(w)) }\n'
            '    return out\n'
            '}\n'
            'entry main(text: Text) {\n'
            '    rev = reverse_each(text)\n'
            '    return join([join(rev, " "), " — ", creative_sentence(rev)], "")\n'
            '}'
        ),
        "input_text": "hello world foo",
    },
    {
        "id": "v3_hybrid_intersection_metaphor",
        "prompt": "find the common elements of two lists and describe the overlap as a metaphor",
        "category": "hybrid",
        "ail": (
            'intent metaphor(overlap: List[Number]) -> Text {\n'
            '    goal: a short metaphor describing the shared elements\n'
            '}\n'
            'pure fn common(a: List[Number], b: List[Number]) -> List[Number] {\n'
            '    out = []\n'
            '    for x in a {\n'
            '        if x in b { out = append(out, x) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    c = common([1,2,3,4,5], [3,4,5,6,7])\n'
            '    return join([to_text(c), " — ", metaphor(c)], "")\n'
            '}'
        ),
        "input_text": "",
    },

    # ================================================================
    # Pure intent — broaden B coverage beyond existing set
    # ================================================================
    {
        "id": "v3_intent_fact_or_opinion",
        "prompt": "determine whether the input sentence is fact or opinion",
        "category": "pure_intent",
        "ail": (
            'intent fact_or_opinion(text: Text) -> Text {\n'
            '    goal: the single word fact or opinion\n'
            '}\n'
            'entry main(text: Text) { return fact_or_opinion(text) }'
        ),
        "input_text": "Python is the best programming language",
    },
    {
        "id": "v3_intent_language_detect",
        "prompt": "detect the language of the input sentence",
        "category": "pure_intent",
        "ail": (
            'intent detect_language(text: Text) -> Text {\n'
            '    goal: the language name in English\n'
            '}\n'
            'entry main(text: Text) { return detect_language(text) }'
        ),
        "input_text": "Bonjour, comment allez-vous?",
    },
    {
        "id": "v3_intent_simplify_for_child",
        "prompt": "simplify the input text for a 10-year-old reader",
        "category": "pure_intent",
        "ail": (
            'intent simplify(text: Text) -> Text {\n'
            'goal: plain English version suitable to a young child\n'
            '}\n'
            'entry main(text: Text) { return simplify(text) }'
        ),
        "input_text": "Photosynthesis is the process by which plants convert light energy into chemical energy.",
    },

    # ================================================================
    # Pure fn — benchmark-shaped standalone tasks
    # ================================================================
    {
        "id": "v3_fn_factorial_7",
        "prompt": "calculate 7 factorial",
        "category": "pure_fn",
        "ail": (
            'pure fn factorial(n: Number) -> Number {\n'
            '    if n <= 1 { return 1 }\n'
            '    return n * factorial(n - 1)\n'
            '}\n'
            'entry main(x: Text) { return factorial(7) }'
        ),
        "expected": "5040",
    },
    {
        "id": "v3_fn_reverse_words_sort",
        "prompt": "sort the words in 'banana cherry apple date' alphabetically",
        "category": "pure_fn",
        "ail": (
            'pure fn sort_words(s: Text) -> Text {\n'
            '    return join(sort(split(s, " ")), " ")\n'
            '}\n'
            'entry main(x: Text) { return sort_words("banana cherry apple date") }'
        ),
        "expected": "apple banana cherry date",
    },
    {
        "id": "v3_fn_sum_evens",
        "prompt": "sum all even numbers from 1 to 100 inclusive",
        "category": "pure_fn",
        "ail": (
            'pure fn sum_evens(n: Number) -> Number {\n'
            '    total = 0\n'
            '    for i in range(1, n + 1) {\n'
            '        if i % 2 == 0 { total = total + i }\n'
            '    }\n'
            '    return total\n'
            '}\n'
            'entry main(x: Text) { return sum_evens(100) }'
        ),
        "expected": "2550",
    },
    {
        "id": "v3_fn_words_longer_than_3",
        "prompt": "in 'the quick brown fox jumps over the lazy dog', count words with more than 3 chars",
        "category": "pure_fn",
        "ail": (
            'pure fn long_words(text: Text, min_len: Number) -> Number {\n'
            '    count = 0\n'
            '    for w in split(text, " ") {\n'
            '        if length(w) > min_len { count = count + 1 }\n'
            '    }\n'
            '    return count\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return long_words("the quick brown fox jumps over the lazy dog", 3)\n'
            '}'
        ),
        "expected": "5",
    },
    {
        "id": "v3_fn_fahrenheit_to_celsius",
        "prompt": "convert 98.6 Fahrenheit to Celsius",
        "category": "pure_fn",
        "ail": (
            'pure fn f_to_c(f: Number) -> Number {\n'
            '    return round((f - 32) * 5 / 9, 1)\n'
            '}\n'
            'entry main(x: Text) { return f_to_c(98.6) }'
        ),
        "expected": "37",
    },
    {
        "id": "v3_fn_fizzbuzz",
        "prompt": "FizzBuzz from 1 to 15, return as comma-joined",
        "category": "pure_fn",
        "ail": (
            'pure fn fizzbuzz(n: Number) -> Text {\n'
            '    out = []\n'
            '    for i in range(1, n + 1) {\n'
            '        if i % 15 == 0 { out = append(out, "FizzBuzz") }\n'
            '        else if i % 3 == 0 { out = append(out, "Fizz") }\n'
            '        else if i % 5 == 0 { out = append(out, "Buzz") }\n'
            '        else { out = append(out, to_text(i)) }\n'
            '    }\n'
            '    return join(out, ",")\n'
            '}\n'
            'entry main(x: Text) { return fizzbuzz(15) }'
        ),
        "expected": "1,2,Fizz,4,Buzz,Fizz,7,8,Fizz,Buzz,11,Fizz,13,14,FizzBuzz",
    },
    {
        "id": "v3_fn_palindrome_racecar",
        "prompt": "is 'racecar' a palindrome?",
        "category": "pure_fn",
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
            'entry main(x: Text) { return is_palindrome("racecar") }'
        ),
        "expected": "true",
    },
    {
        "id": "v3_fn_dedupe_list",
        "prompt": "remove duplicates from [1, 3, 2, 3, 1, 4, 2, 5]",
        "category": "pure_fn",
        "ail": (
            'pure fn dedupe(xs: List[Number]) -> List[Number] {\n'
            '    seen = []\n'
            '    for x in xs {\n'
            '        if x not in seen { seen = append(seen, x) }\n'
            '    }\n'
            '    return seen\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return join(dedupe([1, 3, 2, 3, 1, 4, 2, 5]), ",")\n'
            '}'
        ),
        "expected": "1,3,2,4,5",
    },
    {
        "id": "v3_fn_fibonacci_10",
        "prompt": "generate the first 10 Fibonacci numbers",
        "category": "pure_fn",
        "ail": (
            'pure fn fib_list(n: Number) -> List[Number] {\n'
            '    out = [0, 1]\n'
            '    for i in range(2, n) {\n'
            '        a = get(out, i - 1)\n'
            '        b = get(out, i - 2)\n'
            '        out = append(out, a + b)\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) { return join(fib_list(10), ",") }'
        ),
        "expected": "0,1,1,2,3,5,8,13,21,34",
    },
    {
        "id": "v3_fn_divisible_by_4",
        "prompt": "from [15, 23, 8, 42, 16, 4, 31] return only numbers divisible by 4",
        "category": "pure_fn",
        "ail": (
            'pure fn div_by(xs: List[Number], d: Number) -> List[Number] {\n'
            '    out = []\n'
            '    for x in xs {\n'
            '        if x % d == 0 { out = append(out, x) }\n'
            '    }\n'
            '    return out\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return join(div_by([15, 23, 8, 42, 16, 4, 31], 4), ",")\n'
            '}'
        ),
        "expected": "8,16,4",
    },
    {
        "id": "v3_fn_count_vowels",
        "prompt": "count the vowels in 'Programming is fun'",
        "category": "pure_fn",
        "ail": (
            'pure fn count_vowels(text: Text) -> Number {\n'
            '    vowels = ["a", "e", "i", "o", "u"]\n'
            '    count = 0\n'
            '    for c in split(lower(text), "") {\n'
            '        if c in vowels { count = count + 1 }\n'
            '    }\n'
            '    return count\n'
            '}\n'
            'entry main(x: Text) { return count_vowels("Programming is fun") }'
        ),
        "expected": "5",
    },
    {
        "id": "v3_fn_longest_word",
        "prompt": "find the longest word in 'extraordinary programming capabilities'",
        "category": "pure_fn",
        "ail": (
            'pure fn longest(text: Text) -> Text {\n'
            '    best = ""\n'
            '    for w in split(text, " ") {\n'
            '        if length(w) > length(best) { best = w }\n'
            '    }\n'
            '    return best\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return longest("extraordinary programming capabilities")\n'
            '}'
        ),
        "expected": "extraordinary",
    },
    {
        "id": "v3_fn_stopword_removal",
        "prompt": "remove stop words [the, a, is, on, at] from 'the cat is on the mat'",
        "category": "pure_fn",
        "ail": (
            'pure fn remove_stops(text: Text, stops: List[Text]) -> Text {\n'
            '    out = []\n'
            '    for w in split(text, " ") {\n'
            '        if w not in stops { out = append(out, w) }\n'
            '    }\n'
            '    return join(out, " ")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return remove_stops("the cat is on the mat", ["the", "a", "is", "on", "at"])\n'
            '}'
        ),
        "expected": "cat mat",
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
            print(f"  {sid}: {why[:160]}", file=sys.stderr)
    return 0 if not broken else 1


if __name__ == "__main__":
    sys.exit(main())
