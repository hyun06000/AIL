# Understanding the Standard Library (`stdlib`)

🇰🇷 한국어: [ko/stdlib-guide.ko.md](ko/stdlib-guide.ko.md) · 🤖 AI/LLM: [stdlib-guide.ai.md](stdlib-guide.ai.md)

**Target audience:** Anyone who finds it strange to define `intent summarize` or `intent translate` from scratch every time they write an AIL program.

**Prerequisites:** It helps to have read the project's general philosophy first.

---

## Why a Standard Library

For AIL to truly be a "language," programs need to share a common foundation. If every program defines `intent summarize` and `intent classify` from scratch every time, that's closer to **a quirky syntactic convention in a host language than an actual language**.

Part of what makes Python Python is that `import os` and `import json` just work. Part of what makes SQL SQL is that `SELECT` and `JOIN` mean the same thing everywhere. AIL needs this too.

---

## An Important Design Decision: stdlib is Written in AIL

Look at the `reference-impl/ail/stdlib/` directory and you'll find three files:

- `core.ail` — `identity`, `refuse` (common intents)
- `language.ail` — 6 primary NLP intents
- `utils.ail` — 12 `pure fn` utilities (all statically verified since v1.3)

**These are AIL files, not Python files.** When the runtime receives a request to import `stdlib/language`, it just reads and parses the `language.ail` file. It is processed in exactly the same way as any `.ail` file a user writes.

Why? Two reasons:

1. **To avoid privileged intents.** If stdlib were hardcoded in Python, stdlib intents would be "special entities where real AIL rules don't apply." Users wouldn't be able to imitate or improve stdlib.

2. **Proof that the language can express itself.** If AIL can't write its own stdlib, that means the language can't express something important. In practice, writing stdlib revealed two parser limitations — and they were documented (see commit `69ec236`).

---

## What's Currently Provided

### `stdlib/core`

The most fundamental utilities:

```ail
intent identity(x: Text) -> Text {
    goal: return the input value unchanged
}

intent refuse(reason: Text) -> Text {
    goal: a structured refusal carrying the declared reason
}
```

### `stdlib/language`

Six primary natural language processing intents:

| Intent | What it does |
|---|---|
| `summarize(source, max_tokens)` | Summarize within a given token limit |
| `translate(source, target_language)` | Translate to another language |
| `classify(text, labels)` | Classify into one of the given labels |
| `extract(source, schema_description)` | Extract structured data (JSON) |
| `rewrite(source, instruction)` | Rewrite according to an instruction |
| `critique(artifact, rubric)` | Critique according to an evaluation rubric |

`classify` and `extract` have their own `on_low_confidence` handlers — when confidence is low, they fall back to safe defaults. **From v1.8, this threshold is judged against calibrated confidence** — if the model claims "0.9" but past observations say "actually 0.3," the handler fires.

### `stdlib/utils` (all `pure fn` since v1.3)

12 numeric, string, and list processing utilities:

| Fn | Signature |
|---|---|
| `word_count(text)` | Space-delimited word count |
| `char_count(text)` | Character count |
| `is_empty(text)` | True even if only whitespace |
| `repeat(text, n)` | Repeat text n times |
| `pad_left(text, len, pad)` | Left-pad to length |
| `clamp(value, lo, hi)` | Clamp to range |
| `sum_list(nums)` | Sum of a list |
| `average(nums)` | Average of a list |
| `flatten(nested)` | Flatten a nested list |
| `unique(items)` | Remove duplicates |
| `take(items, n)` | First n items |
| `zip_lists(a, b)` | Zip two lists together |

**The fact that all of these are `pure fn` is significant.** Values computed via these utilities are guaranteed to have `has_intent_origin == false` **at compile time**. In other words: the runtime doesn't need to be queried at runtime to know whether the result of `sum_list([...])` has passed through an LLM. The language already knows.

---

## Usage

```ail
import summarize from "stdlib/language"
import classify from "stdlib/language"

context editorial_review extends default {
    register: "neutral"
    audience: "general_reader"
    preserve: [names, dates, numbers]
}

entry main(article: Text) {
    with context editorial_review:
        brief = summarize(article, 80)
        mood = classify(brief, "positive_negative_mixed_unclear")
    return mood
}
```

This program is at `reference-impl/examples/summarize_and_classify.ail`. Run it yourself:

```bash
cd reference-impl
ail run examples/summarize_and_classify.ail --input "article content..." --mock
```

---

## Current Limitations (v1.8)

Imports currently have the simple meaning of "bring in the whole module":

```ail
import summarize from "stdlib/language"
```

Writing this brings the **entire `language` module** into scope — not just `summarize`, but `classify`, `translate`, and so on. **Symbol-level import** is not yet implemented.

Other limitations:

- **Relative path import** (`./helpers.ail`): rejected. Sharing files within the same project is planned for future addition.
- **URL import** (`org://company/lib@v1`): rejected. External registries are an OS-level (NOOS) feature.
- **stdlib extension room**: `stdlib/data` (CSV/JSON processing), `stdlib/math` (statistics/linear algebra), `stdlib/text` (regex/templates) are on the roadmap but don't exist yet.

---

## Local Definitions Win

Defining a local intent with the same name shadows the imported one:

```ail
import summarize from "stdlib/language"

// My custom summarize
intent summarize(source: Text, max_tokens: Number) -> Text {
    goal: my_special_summary_logic
}

entry main(text: Text) {
    return summarize(text, 50)  // local version is used here
}
```

This is not a bug — it's intentional behavior. User code has authority over stdlib.

---

## Related

- `reference-impl/ail/stdlib/` — the actual implementation
- `reference-impl/ail/stdlib/__init__.py` — import resolver
- [`../../spec/06-stdlib.md`](../../spec/06-stdlib.md) — standard library specification
- [`../../reference-impl/examples/summarize_and_classify.ail`](../../reference-impl/examples/summarize_and_classify.ail) — example using stdlib

---

## Summary

Having a standard library means:

- ✅ AIL programs can **share a common foundation**
- ✅ AIL can **express itself** (stdlib is written in AIL)
- ✅ User code can **redefine stdlib via local definition**
- ✅ Contributing new intents or pure fns to stdlib = **editing a `.ail` file**
- ✅ All fns in `utils.ail` are **statically verified `pure fn`** — values passing through these utilities are guaranteed not to touch an LLM at compile time (v1.3)
