"""Generate dataset/09_r3_fixes.jsonl — canonical programs for R3 failure patterns.

Round 3 benchmark analysis (2026-04-21) identified recurring failure modes:

  1. Dedup/unique — model uses dict {}; teach `in` operator pattern
  2. Character frequency — model uses dict; teach pair-list pattern
  3. Fibonacci with join — model returns True due to map+join issue; teach to_text per element
  4. Sort with named key fn — model writes anonymous fn; teach named fn pattern
  5. Hybrid: parse list then call intent per item — model puts intent inside pure fn

Each entry is validated before writing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ail import compile_source, run, MockAdapter  # noqa: E402

OUT_PATH = Path(__file__).parent / "dataset" / "09_r3_fixes.jsonl"

SAMPLES: list[dict] = [
    # ── Dedup / unique without dict ──────────────────────────────────
    {
        "prompt": "remove duplicate values from [1, 3, 2, 3, 1, 4, 2, 5]",
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
        "category": "pure_fn",
        "expected": "[1, 3, 2, 4, 5]",
        "input_text": "",
    },
    {
        "prompt": "deduplicate the list ['apple', 'banana', 'apple', 'cherry', 'banana']",
        "ail": (
            'pure fn deduplicate(items: [Text]) -> [Text] {\n'
            '    result = []\n'
            '    for item in items {\n'
            '        if not (item in result) { result = append(result, item) }\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    return deduplicate(["apple", "banana", "apple", "cherry", "banana"])\n'
            '}'
        ),
        "category": "pure_fn",
        "expected": "['apple', 'banana', 'cherry']",
        "input_text": "",
    },
    # ── Character / item frequency without dict ───────────────────────
    {
        "prompt": "count the frequency of each character in 'hello'",
        "ail": (
            'pure fn count_char(s: Text, ch: Text) -> Number {\n'
            '    count = 0\n'
            '    for c in split(s, "") {\n'
            '        if c == ch { count = count + 1 }\n'
            '    }\n'
            '    return count\n'
            '}\n'
            'pure fn unique_sorted(s: Text) -> [Text] {\n'
            '    result = []\n'
            '    for c in split(s, "") {\n'
            '        if not (c in result) { result = append(result, c) }\n'
            '    }\n'
            '    return sort(result)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    s = "hello"\n'
            '    chars = unique_sorted(s)\n'
            '    pairs = []\n'
            '    for c in chars {\n'
            '        pairs = append(pairs, join([c, ":", to_text(count_char(s, c))], ""))\n'
            '    }\n'
            '    return join(pairs, ", ")\n'
            '}'
        ),
        "category": "pure_fn",
        "expected": "e:1, h:1, l:2, o:1",
        "input_text": "",
    },
    # ── Fibonacci — to_text each element before join ──────────────────
    {
        "prompt": "generate the first 8 fibonacci numbers as a comma-separated string",
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
        "category": "pure_fn",
        "expected": "0, 1, 1, 2, 3, 5, 8, 13",
        "input_text": "",
    },
    {
        "prompt": "list the first 5 fibonacci numbers",
        "ail": (
            'pure fn fib(n: Number) -> Number {\n'
            '    if n <= 1 { return n }\n'
            '    return fib(n - 1) + fib(n - 2)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    nums = []\n'
            '    for i in range(0, 5) {\n'
            '        nums = append(nums, to_text(fib(i)))\n'
            '    }\n'
            '    return join(nums, ", ")\n'
            '}'
        ),
        "category": "pure_fn",
        "expected": "0, 1, 1, 2, 3",
        "input_text": "",
    },
    # ── Sort with named key fn (no anonymous fn in sort) ─────────────
    {
        "prompt": "sort 'Charlie:78,Alice:85,Bob:92' by name alphabetically",
        "ail": (
            'pure fn name_key(pair: Text) -> Text {\n'
            '    return get(split(pair, ":"), 0)\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    pairs = ["Charlie:78", "Alice:85", "Bob:92"]\n'
            '    return join(sort(pairs, name_key), ", ")\n'
            '}'
        ),
        "category": "pure_fn",
        "expected": "Alice:85, Bob:92, Charlie:78",
        "input_text": "",
    },
    {
        "prompt": "sort the words 'banana cherry apple date' by length (shortest first)",
        "ail": (
            'pure fn word_len(w: Text) -> Number { return length(w) }\n'
            'entry main(x: Text) {\n'
            '    words = split("banana cherry apple date", " ")\n'
            '    return join(sort(words, word_len), " ")\n'
            '}'
        ),
        "category": "pure_fn",
        "expected": "date apple banana cherry",
        "input_text": "",
    },
    # ── Hybrid: parse list, call intent PER ITEM in entry (not pure fn) ──
    {
        "prompt": "parse 'Alice:85,Bob:62,Carol:91' and label each score as pass (>=70) or fail",
        "ail": (
            'intent label_score(name: Text, score: Text) -> Text {\n'
            '    goal: pass_or_fail\n'
            '}\n'
            'pure fn parse_pair(pair: Text) -> [Text] {\n'
            '    return split(trim(pair), ":")\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    pairs = split("Alice:85,Bob:62,Carol:91", ",")\n'
            '    results = []\n'
            '    for pair in pairs {\n'
            '        parts = parse_pair(pair)\n'
            '        name = get(parts, 0)\n'
            '        score = get(parts, 1)\n'
            '        results = append(results, join([name, ": ", label_score(name, score)], ""))\n'
            '    }\n'
            '    return join(results, ", ")\n'
            '}'
        ),
        "category": "hybrid",
        "input_text": "",
    },
    {
        "prompt": "for each item in 'apple,car,ocean' classify it as food, vehicle, or nature",
        "ail": (
            'intent classify_item(item: Text) -> Text {\n'
            '    goal: food_vehicle_or_nature\n'
            '}\n'
            'pure fn parse_items(s: Text) -> [Text] {\n'
            '    result = []\n'
            '    for item in split(s, ",") {\n'
            '        result = append(result, trim(item))\n'
            '    }\n'
            '    return result\n'
            '}\n'
            'entry main(x: Text) {\n'
            '    items = parse_items("apple,car,ocean")\n'
            '    results = []\n'
            '    for item in items {\n'
            '        results = append(results, join([item, ": ", classify_item(item)], ""))\n'
            '    }\n'
            '    return join(results, "\\n")\n'
            '}'
        ),
        "category": "hybrid",
        "input_text": "",
    },
    # ── Intent must always have { goal: ... } body ───────────────────
    {
        "prompt": "translate 'good morning' to Spanish",
        "ail": (
            'intent translate(text: Text) -> Text {\n'
            '    goal: spanish translation\n'
            '}\n'
            'entry main(x: Text) { return translate("good morning") }'
        ),
        "category": "pure_intent",
        "input_text": "",
    },
    {
        "prompt": "is 'running late for a meeting' urgent or not urgent?",
        "ail": (
            'intent detect_urgency(text: Text) -> Text {\n'
            '    goal: urgent_or_not_urgent\n'
            '}\n'
            'entry main(x: Text) { return detect_urgency("running late for a meeting") }'
        ),
        "category": "pure_intent",
        "input_text": "",
    },
    # ── Descending sort: reverse(sort(x)) ────────────────────────────
    {
        "prompt": "sort [42, 17, 8, 93, 55] in descending order",
        "ail": (
            'entry main(x: Text) {\n'
            '    nums = [42, 17, 8, 93, 55]\n'
            '    return reverse(sort(nums))\n'
            '}'
        ),
        "category": "pure_fn",
        "expected": "[93, 55, 42, 17, 8]",
        "input_text": "",
    },
]


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0

    with OUT_PATH.open("w") as f:
        for sample in SAMPLES:
            src = sample["ail"]
            input_text = sample.get("input_text", "")
            try:
                compile_source(src)
                result, _ = run(src, input=input_text, adapter=MockAdapter())
            except Exception as e:
                print(f"SKIP {sample['prompt'][:50]!r}: {e}", file=sys.stderr)
                skipped += 1
                continue

            if sample["category"] == "pure_fn":
                expected = sample.get("expected")
                if expected:
                    actual = str(result.value).strip()
                    if actual != expected:
                        print(
                            f"SKIP {sample['prompt'][:50]!r}: "
                            f"got={actual!r} expected={expected!r}",
                            file=sys.stderr,
                        )
                        skipped += 1
                        continue

            entry = {
                "id": f"r3fix_{written:03d}",
                "prompt": sample["prompt"],
                "ail_source": src,
                "category": sample["category"],
                "input_text": input_text,
                "source_of_sample": "r3_fixes",
            }
            if "expected" in sample:
                entry["expected"] = sample["expected"]
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += 1

    print(f"wrote {written} samples ({skipped} skipped) → {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
