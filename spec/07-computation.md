# AIL Specification — 07: Computation

**Version:** 0.2 draft

This document extends AIL from a language that delegates everything to
a language model into a language where AI can write actual algorithms.

---

## 1. Why this matters

AIL v0.1 had one computational primitive: `intent`, which delegates to
an LLM. Every AIL program was, at its core, a structured prompt.

This is useful for orchestration, but it is not programming. An AI that
wants to sort a list, parse a CSV, compute a hash, or implement a search
algorithm cannot do any of those things in AIL v0.1 without calling out
to a language model — which is absurd. You do not need a language model
to sort a list.

AIL v0.2 adds **deterministic computation**. Programs can now contain
real functions with real logic. The language model becomes one tool
among many, not the only one.

The guiding question for every decision in this document:

> What would a programming language look like if an AI — not a human —
> were the one writing every line?

## 2. The `fn` declaration

A `fn` is a pure, deterministic function. It takes typed inputs,
performs computation, and returns a typed output. No LLM is involved.

```ail
fn add(a: Number, b: Number) -> Number {
    return a + b
}

fn factorial(n: Number) -> Number {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

fn contains(haystack: [Text], needle: Text) -> Boolean {
    for item in haystack {
        if item == needle {
            return true
        }
    }
    return false
}
```

### 2.1 fn vs intent

| Property | `fn` | `intent` |
|---|---|---|
| Deterministic | Yes | No |
| Requires LLM | No | Yes (or may) |
| Has confidence | Always 1.0 | Variable |
| Can be `evolve`d | No | Yes |
| Can `perform` effects | No | Via `intent` only |
| Speed | Fast (native execution) | Slow (model call) |
| Use case | Algorithms, data transforms, logic | Natural language tasks, judgment |

A program that mixes both is the normal case:

```ail
import translate from "stdlib/language"

fn word_count(text: Text) -> Number {
    words = split(text, " ")
    return length(words)
}

entry main(document: Text) {
    translated = translate(document, "Korean")
    count = word_count(translated)
    return count
}
```

The AI chooses `fn` when the task is algorithmic and `intent` when the
task requires judgment. This is the same distinction a human programmer
makes between "write code" and "ask the AI" — except in AIL, both live
in the same language.

### 2.2 Why not just use `intent` for everything?

Three reasons:

1. **Speed.** A function that adds two numbers should not round-trip
   through an API. `fn` executes in microseconds; `intent` in seconds.

2. **Determinism.** `fn` always returns the same output for the same
   input. Tests can assert exact equality. `intent` returns a
   distribution.

3. **Cost.** Every `intent` call costs tokens. A `fn` costs nothing.

An AI writing AIL should prefer `fn` whenever the task does not require
natural language understanding or generation. The language makes this
choice explicit rather than implicit.

## 3. Control flow

### 3.1 `if` / `else`

Deterministic branching. Unlike `branch` (which dispatches by
confidence-weighted probability), `if` collapses to a boolean.

```ail
fn classify_age(age: Number) -> Text {
    if age < 13 {
        return "child"
    } else if age < 20 {
        return "teenager"
    } else {
        return "adult"
    }
}
```

`if` exists alongside `branch`. They serve different purposes:

- `if` — the condition is known with certainty. Use for data logic.
- `branch` — the condition is probabilistic. Use for model outputs.

### 3.2 `for` loops

```ail
fn sum_list(numbers: [Number]) -> Number {
    total = 0
    for n in numbers {
        total = total + n
    }
    return total
}

fn first_match(items: [Text], predicate: fn(Text) -> Boolean) -> Text {
    for item in items {
        if predicate(item) {
            return item
        }
    }
    return ""
}
```

`for` iterates over lists. There is no `while` in v0.2 — unbounded
loops are a footgun that AI code generators produce too easily.
`for` with a finite collection is always bounded.

### 3.3 Why no `while`

An AI generating code in a loop can easily produce `while true` with
a subtle exit-condition bug. The resulting program runs forever. In a
language designed for AI authorship, making infinite loops impossible
by construction is worth the expressiveness cost.

If a future version adds `while`, it will require a declared upper
bound: `while condition, max_iterations: 1000 { ... }`.

## 4. Types

AIL v0.2 has a concrete type system that the runtime enforces.

### 4.1 Primitive types

- `Number` — 64-bit float (all numbers are floats; no int/float split)
- `Text` — UTF-8 string
- `Boolean` — `true` or `false`
- `Confidence` — number in [0, 1] (from v0.1)

### 4.2 Composite types

- `[T]` — list of T: `[Number]`, `[Text]`, `[[Number]]`
- `{key: T, ...}` — record: `{name: Text, age: Number}`
- `T | None` — optional: `Number | None`

### 4.3 Function types

Functions are first-class values:

```ail
fn apply(f: fn(Number) -> Number, x: Number) -> Number {
    return f(x)
}

fn double(n: Number) -> Number {
    return n * 2
}

entry main(x: Number) {
    result = apply(double, x)
    return result
}
```

### 4.4 Runtime type checking

In v0.2, types are checked at runtime (not compile time). A type
mismatch raises a `TypeError` signal. This is a pragmatic choice:
a full static type checker is a large project; runtime checks are
implementable now and catch real bugs.

## 5. Built-in operations

### 5.1 Arithmetic

`+`, `-`, `*`, `/`, `%` (modulo), `**` (power)

### 5.2 Comparison

`==`, `!=`, `<`, `>`, `<=`, `>=`

### 5.3 Logic

`and`, `or`, `not`

### 5.4 Text operations

- `length(text)` → Number
- `split(text, delimiter)` → [Text]
- `join(items, delimiter)` → Text
- `trim(text)` → Text
- `upper(text)` → Text
- `lower(text)` → Text
- `starts_with(text, prefix)` → Boolean
- `ends_with(text, suffix)` → Boolean
- `replace(text, old, new)` → Text
- `slice(text, start, end)` → Text

### 5.5 List operations

- `length(list)` → Number
- `append(list, item)` → [T]
- `map(list, fn)` → [T]
- `filter(list, fn)` → [T]
- `reduce(list, fn, initial)` → T
- `sort(list)` → [T]
- `reverse(list)` → [T]
- `range(start, end)` → [Number]
- `zip(list_a, list_b)` → [{a: T, b: U}]
- `flat_map(list, fn)` → [T]

### 5.6 Record operations

- `get(record, key)` → T
- `set(record, key, value)` → Record
- `keys(record)` → [Text]
- `values(record)` → [T]

### 5.7 Conversion

- `to_number(text)` → Number | None
- `to_text(value)` → Text
- `to_boolean(value)` → Boolean

## 6. The hybrid model

The power of AIL v0.2 is that `fn` and `intent` coexist in the same
program. An AI writing an AIL program chooses the right tool for each
subtask:

```ail
import classify from "stdlib/language"
import translate from "stdlib/language"

fn count_words(text: Text) -> Number {
    return length(split(text, " "))
}

fn is_short(text: Text) -> Boolean {
    return count_words(text) < 50
}

fn build_report(original: Text, translated: Text, sentiment: Text) -> Text {
    header = join(["Original length: ", to_text(count_words(original)),
                   " words | Sentiment: ", sentiment], "")
    return join([header, "", translated], "\n")
}

entry main(document: Text) {
    sentiment = classify(document, "positive_negative_neutral")
    translated = translate(document, "Korean")

    if is_short(document) {
        return build_report(document, translated, sentiment)
    } else {
        summary = summarize(document, 100)
        return build_report(summary, translated, sentiment)
    }
}
```

The AI decides: word counting is a `fn` (no LLM needed), classification
is an `intent` (judgment required), report building is a `fn` (string
concatenation), summarization is an `intent` (language understanding).

This is what "AI-friendly" means: **the language lets the AI express
its own distinction between what it can compute and what it needs to
reason about.**

## 7. Interaction with existing features

### 7.1 `fn` and confidence

A `fn` always returns values at confidence 1.0. When a `fn` receives
a value from an `intent` (which may have lower confidence), the
confidence propagates through the function per spec/03 §3.1.

### 7.2 `fn` and context

A `fn` can read the active context (it is ambient), but context is
most useful for `intent` calls. A `fn` may use context for
configuration:

```ail
fn format_number(n: Number) -> Text {
    if context.locale == "Korean" {
        return to_text(n) + "개"
    }
    return to_text(n)
}
```

### 7.3 `fn` and evolve

A `fn` cannot be evolved. It is deterministic; its behavior is fully
specified by its source code. If you want adaptive behavior, use an
`intent`.

### 7.4 `fn` and effects

A `fn` cannot `perform` effects. It is pure. If you need side effects,
wrap the `fn` call in an `intent` or call `perform` from `entry`.

## 8. What this document does not cover

- Concurrency / async (`fn` is synchronous in v0.2)
- Pattern matching (a likely v0.3 addition)
- Error handling beyond type checks (a structured `result` type is
  likely in v0.3)
- Module system for `fn` (currently `fn` is only local; `import` works
  for `intent` only)

---

Next: implementation in the reference interpreter.
