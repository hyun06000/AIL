# AIL stdlib — for AI systems

Dense reference. Human/English: [`stdlib-guide.md`](stdlib-guide.md) · Korean: [`ko/stdlib-guide.ko.md`](ko/stdlib-guide.ko.md)

---

## What stdlib provides

Shared AIL foundation so programs don't redefine common intents from scratch. Three modules in `reference-impl/ail/stdlib/`. **All stdlib files are `.ail` files, not Python** — processed identically to user code. No privileged execution path.

Why AIL-native: (1) no privileged intents — same rules apply; (2) proof of language self-expressiveness — stdlib authoring exposed two parser limits, both fixed.

---

## Import syntax

```ail
import summarize from "stdlib/language"
import word_count from "stdlib/utils"
import identity from "stdlib/core"
```

**Important:** current import semantics bring in the **entire module**, not just the named symbol. `import summarize from "stdlib/language"` loads all 6 language intents into scope. Symbol-level selective import not yet implemented.

---

## `stdlib/core` — 2 intents

```ail
intent identity(x: Text) -> Text
// goal: return the input value unchanged

intent refuse(reason: Text) -> Text
// goal: structured refusal carrying declared reason
```

---

## `stdlib/language` — 6 intents

| Intent | Signature | Notes |
|---|---|---|
| `summarize` | `(source: Text, max_tokens: Number) -> Text` | Respects token limit |
| `translate` | `(source: Text, target_language: Text) -> Text` | |
| `classify` | `(text: Text, labels: Text) -> Text` | Has `on_low_confidence` handler |
| `extract` | `(source: Text, schema_description: Text) -> Text` | Returns JSON; has `on_low_confidence` handler |
| `rewrite` | `(source: Text, instruction: Text) -> Text` | |
| `critique` | `(artifact: Text, rubric: Text) -> Text` | |

`classify` and `extract` `on_low_confidence` behavior: falls back to safe default. Since v1.8, threshold is judged against **calibrated confidence** — model's self-reported confidence overridden by historical calibration data.

---

## `stdlib/utils` — 12 pure fns

All statically verified `pure fn` since v1.3. Values computed through these have `has_intent_origin == false` at **compile time** — no LLM contact, no runtime query needed.

| Fn | Signature | Description |
|---|---|---|
| `word_count` | `(text: Text) -> Number` | Space-delimited word count |
| `char_count` | `(text: Text) -> Number` | Character count |
| `is_empty` | `(text: Text) -> Bool` | True if text is empty or only whitespace |
| `repeat` | `(text: Text, n: Number) -> Text` | Concatenate text n times |
| `pad_left` | `(text: Text, len: Number, pad: Text) -> Text` | Left-pad to target length |
| `clamp` | `(value: Number, lo: Number, hi: Number) -> Number` | Clamp to [lo, hi] |
| `sum_list` | `(nums: [Number]) -> Number` | Sum of list |
| `average` | `(nums: [Number]) -> Number` | Arithmetic mean |
| `flatten` | `(nested: [[Any]]) -> [Any]` | Flatten one level of nesting |
| `unique` | `(items: [Any]) -> [Any]` | Remove duplicates, preserve order |
| `take` | `(items: [Any], n: Number) -> [Any]` | First n elements |
| `zip_lists` | `(a: [Any], b: [Any]) -> [[Any]]` | Zip two lists into pairs |

---

## Current limits

| Limitation | Status |
|---|---|
| Whole-module import only | Symbol-level selective import not implemented |
| No relative path import (`./helpers.ail`) | Rejected; planned for future |
| No URL import (`org://company/lib@v1`) | Rejected; OS-level (NOOS) feature |
| No `stdlib/data`, `stdlib/math`, `stdlib/text` | On roadmap, not yet present |

---

## Local definition wins over import

```ail
import summarize from "stdlib/language"

intent summarize(source: Text, max_tokens: Number) -> Text {
    goal: my_custom_logic
}

entry main(text: Text) {
    return summarize(text, 50)  // local version, not stdlib
}
```

Intentional behavior. User code has authority over stdlib. Not a bug.

---

## Tool promotion path

```
community-tools/*.ail
    ↓ (used in 2+ projects)
stdlib candidate review
    ↓ (language-level decision)
reference-impl/ail/stdlib/
    ↓ (if used everywhere)
built-in (no import needed)
```

---

## Related

- `reference-impl/ail/stdlib/` — implementation files
- `reference-impl/ail/stdlib/__init__.py` — import resolver
- `spec/06-stdlib.md` — formal specification
- `reference-impl/examples/summarize_and_classify.ail` — usage example
