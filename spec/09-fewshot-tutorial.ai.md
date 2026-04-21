# AIL Few-Shot Tutorial

**Audience:** an AI model that has never seen AIL.
**Goal:** read this once, then write valid AIL.
**Grammar:** v1.8 (frozen — see [09-stability.md](09-stability.md)).
**Reference:** [08-reference-card.ai.md](08-reference-card.ai.md). This file is the path through; that file is the dictionary.

---

## 30-second mental model

AIL has **two kinds of functions** and you must pick one for every operation:

- **`fn`** (or `pure fn`) — deterministic computation. Runs locally. No LLM. Free, instant, reproducible. Use for: arithmetic, parsing, sorting, comparison, transformation.
- **`intent`** — declares a goal that requires judgment. The runtime calls a language model. Costs tokens, returns `(value, confidence)`. Use for: sentiment, classification, translation, summarisation, opinion.

A program is a sequence of declarations plus exactly **one `entry main(...)`** which returns the result.

```ail
// Smallest valid program.
entry main(x: Text) {
    return "hello"
}
```

Run it:

```
ail run prog.ail --input "ignored" --mock
# → hello
```

`--mock` makes any `intent` call return a placeholder string instead of hitting a real model — useful for testing structure.

---

## Step 1 — Hello, with input

```ail
entry main(name: Text) {
    return join(["hello, ", name], "")
}
```

```
ail run prog.ail --input "AIL" --mock
# → hello, AIL
```

Three things to internalise:

- The `entry main` parameter is bound to whatever `--input` is. The first parameter takes the input string; it must be `Text`.
- `return` exits the function with a value. The runtime emits that value to the caller. **There is no `print`.** Anything you don't `return` is invisible.
- String concatenation uses `join(LIST, SEPARATOR)`. There is no `+` for strings.

---

## Step 2 — Numbers and `to_text` / `to_number`

All numbers are 64-bit float. `42` and `42.0` are the same value. To embed a number in a return string, convert with `to_text`. To parse a string as a number, use `to_number` (which returns a `Result` — see step 10).

```ail
entry main(x: Text) {
    a = 7
    b = 5
    return join(["sum=", to_text(a + b)], "")
}
```

```
ail run prog.ail --input "" --mock
# → "sum=12"
```

Operators: `+ - * / %` with standard precedence. Comparison: `== != < > <= >=`. Boolean: `and or not` (short-circuit).

---

## Step 3 — fn vs intent — DECISION TABLE

This is the single most important table in the language.

| Task | Use | Why |
|---|---|---|
| Add 7 and 5 | `pure fn` | Computable. No meaning needed. |
| Sort `[3, 1, 2]` | `pure fn` | Algorithm. |
| Count vowels in "hello" | `pure fn` | Iterate and compare characters. |
| Parse "Alice:85,Bob:92" | `pure fn` | Split, structured. |
| Classify "I love this" as positive/negative | **`intent`** | Requires understanding meaning. |
| Translate "hello" to Korean | **`intent`** | Meaning across languages. |
| Summarise a paragraph | **`intent`** | Judgment. |
| Decide if an email is spam | **`intent`** | Subjective. |
| Generate a creative title | **`intent`** | New language. |

**Rule of thumb:** *If you can write the algorithm, use `pure fn`. If you need to know what words MEAN, use `intent`. When unsure, default to `pure fn`.*

A hybrid program declares both:

```ail
intent classify_sentiment(text: Text) -> Text {
    goal: positive_or_negative_or_neutral
}
pure fn word_count(text: Text) -> Number {
    return length(split(trim(text), " "))
}
entry main(text: Text) {
    return join([
        to_text(word_count(text)),
        " words, sentiment=",
        classify_sentiment(text)
    ], "")
}
```

`join`'s argument is a `[Text]` list literal. AIL list literals **do not allow a trailing comma** — the last item has no comma after it.

```
ail run prog.ail --input "I absolutely love this product" --mock
# → 5 words, sentiment=[mock response for classify_sentiment]
```

`--mock` substitutes the intent output. With a real model (`AIL_OLLAMA_MODEL=llama3.1:latest` or `ANTHROPIC_API_KEY=sk-...`), it would return the actual classification.

---

## Step 4 — `pure fn` for computation

`pure fn` is `fn` plus a static contract verified at parse time:

- Body cannot call any `intent`.
- Body cannot `perform` an effect.
- Body cannot call a non-pure `fn`.

Violations raise `PurityError` *at parse time*; the program never runs. This is the language's structural way of separating "no LLM possible" from "may call LLM".

```ail
pure fn factorial(n: Number) -> Number {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
entry main(x: Text) {
    return to_text(factorial(7))
}
```

```
ail run prog.ail --input "" --mock
# → 5040
```

If you tried `pure fn ask_user() -> Text { ai_helper("...") }` where `ai_helper` is an intent, the parser would refuse the program. Use this property: when you mean "this never calls a model", say so explicitly with `pure fn`.

---

## Step 5 — Conditionals

```ail
pure fn fizzbuzz(n: Number) -> Text {
    if n % 15 == 0 { return "FizzBuzz" }
    if n % 3 == 0 { return "Fizz" }
    if n % 5 == 0 { return "Buzz" }
    return to_text(n)
}
entry main(n: Text) {
    return fizzbuzz(to_number(n))
}
```

```
ail run prog.ail --input "15" --mock
# → FizzBuzz
```

`if COND { BODY } else if COND { BODY } else { BODY }`. **`if` is a statement, not an expression.** The pattern `x = if cond { a } else { b }` is **not valid AIL** — write it as a `pure fn` returning `a` or `b`.

---

## Step 6 — Bounded iteration with `for` (and no `while`)

The only loop is `for VAR in COLLECTION { BODY }`. It iterates over a list. To iterate over numbers, use `range(start, end)` which returns the list `[start, start+1, ..., end-1]`.

```ail
pure fn sum_first_n(n: Number) -> Number {
    total = 0
    for i in range(1, n + 1) {
        total = total + i
    }
    return total
}
entry main(x: Text) {
    return to_text(sum_first_n(100))
}
```

```
ail run prog.ail --input "" --mock
# → 5050
```

**There is no `while`.** Unbounded loops are a structural failure mode AIL prevents. If you need conditional iteration, build a bounded list and `for`-iterate it.

---

## Step 7 — Lists, subscript, and the most useful list builtins

```ail
entry main(x: Text) {
    xs = [10, 20, 30, 40]
    first = xs[0]                       // subscript sugar
    same = get(xs, 0)                   // canonical form — identical
    n = length(xs)                      // 4
    bigger = append(xs, 50)             // [10, 20, 30, 40, 50]
    return join([
        to_text(first), ",", to_text(same), ",",
        to_text(n), ",", to_text(length(bigger))
    ], "")
}
```

```
ail run prog.ail --input "" --mock
# → 10,10,4,5
```

`xs[i]` is sugar for `get(xs, i)` (since v1.8.4 — both runtimes). Lists are immutable: `append` returns a new list, it does not modify in place. Other list builtins you will use constantly: `length`, `range`, `sort`, `reverse`, `slice(xs, a, b)`. Membership: `x in xs`, `x not in xs`.

Note `xs[i]` does **not** support slicing; for that, use `slice(xs, start, end)`.

---

## Step 8 — Strings: split, join, trim, the rest

Strings are values; the same `length` you used on lists works on `Text`.

```ail
pure fn count_words(text: Text) -> Number {
    return length(split(trim(text), " "))
}
entry main(text: Text) {
    return to_text(count_words(text))
}
```

```
ail run prog.ail --input "  the quick brown fox  " --mock
# → 4
```

Most-used text builtins: `length`, `split(text, sep)`, `join(list, sep)`, `trim(text)`, `upper(text)`, `lower(text)`, `starts_with(text, prefix)`, `ends_with(text, suffix)`, `replace(text, old, new)`, `slice(text, start, end)`.

Substring with `slice` returns a `Text`; subscript with `text[i]` returns... actually — subscript is for lists. Use `slice(text, i, i+1)` for a single character.

---

## Step 9 — Your first `intent`

An `intent` declaration tells the runtime: "for this task I need a model". You declare a goal in plain words; the runtime constructs the prompt, calls the model, parses the response, and returns it as a `(value, confidence)` pair.

```ail
intent classify_topic(text: Text) -> Text {
    goal: the most salient topic word from economics politics sports science or other
}
entry main(text: Text) {
    return classify_topic(text)
}
```

The `goal:` line is parsed as an AIL expression followed by free identifier tokens, so it must be syntactically clean. Constraints:

- ASCII only — the lexer rejects unicode punctuation like `—`, `…`, `•`. Use `-`, `...`, `*`.
- **No commas** in the goal text. Commas are only valid inside list literals and argument lists.
- No colons inside the goal (the leading `goal:` already used the colon).
- Avoid AIL control-flow keywords as words: `for`, `in`, `if`, `else`, `return`, `true`, `false`, `attempt`, `try`, `match`, `branch`, `with`, `evolve`, `effect`, `entry`, `import`, `pure`, `fn`, `intent`, `perform`. The boolean operators `and` `or` `not` are tolerated (they parse, just produce noise the runtime ignores).
- Keep it terse. Existing samples are usually under 12 words: `the single most salient topic word`, `positive_or_negative_or_neutral`, `Text greeting the named person warmly`. Long prose goals are not better than short ones — the model receiving the goal at runtime gets the parameter values too.

```
ail run prog.ail --input "The central bank raised rates by 25 basis points" --mock
# → [mock response for classify_topic]
```

Replace `--mock` with `AIL_OLLAMA_MODEL=llama3.1:latest` or `ANTHROPIC_API_KEY=sk-...` and the same source returns a real classification (likely `"economics"` or `"finance"`).

The `goal` line is free-form prose. Constraints, examples, and confidence handling are optional fields documented in the reference card. For the simple case, `goal:` alone is enough.

---

## Step 10 — `Result` for failable operations (no exceptions)

`to_number(text)` may fail (the input might not be a number). It returns a `Result` — a value that is either `ok(VALUE)` or `error(MESSAGE)`. You **must** handle both shapes, or the parser rejects the program.

The Result API: `ok(v)`, `error(msg)`, `is_ok(r)`, `is_error(r)`, `unwrap(r)` (extracts value, panics on error), `unwrap_or(r, default)` (extracts value, returns default on error), `unwrap_error(r)`.

Idiomatic guard pattern:

```ail
pure fn safe_double(raw: Text) -> Number {
    n = to_number(raw)
    if is_error(n) { return -1 }
    return unwrap(n) * 2
}
entry main(text: Text) {
    return to_text(safe_double(text))
}
```

```
ail run prog.ail --input "21" --mock
# → 42
ail run prog.ail --input "not a number" --mock
# → -1
```

For one-line defaults, `unwrap_or` is shorter:

```ail
pure fn safe_parse(raw: Text, default: Number) -> Number {
    return unwrap_or(to_number(raw), default)
}
```

This is the language's structural answer to error handling. You cannot accidentally use a failed parse as a number — the type system disallows it. (Other languages let you write `int(x)` and crash at runtime; AIL refuses to parse the program.)

---

## Step 11 — `attempt` cascades

When you have multiple ways to compute something — cheap → expensive — express it as an `attempt` block. The runtime walks the `try` arms in order; the first one that returns a non-error result wins.

```ail
pure fn direct_parse(text: Text) -> Number {
    return to_number(trim(text))
}
pure fn scan_tokens(text: Text) -> Number {
    for t in split(text, " ") {
        parsed = to_number(t)
        if is_ok(parsed) { return parsed }
    }
    return error("no numeric token")
}
intent infer_number(text: Text) -> Number {
    goal: the single number the user is referring to
}
entry main(text: Text) {
    return to_text(unwrap(attempt {
        try direct_parse(text)
        try scan_tokens(text)
        try infer_number(text)
    }))
}
```

```
ail run prog.ail --input "42" --mock           # → 42   (direct_parse wins)
ail run prog.ail --input "order 17 ready" --mock  # → 17 (scan_tokens wins)
ail run prog.ail --input "I need three" --mock    # → [mock response for infer_number]
```

The pure paths run free; the model is called only when both deterministic strategies fail. This is the canonical way to implement "use the cheapest tool that gives a confident answer".

---

## Step 12 — Putting it together: a hybrid program

A realistic program threads `pure fn` (computation), `Result` (failable parsing), and `intent` (judgment) through one pipeline.

```ail
pure fn parse_row(line: Text) -> Text {
    parts = split(line, ":")
    if length(parts) < 2 { return error("malformed") }
    amount = to_number(get(parts, 1))
    if is_error(amount) { return error("bad amount") }
    return ok([get(parts, 0), unwrap(amount)])
}
pure fn category_total(rows: Text, category: Text) -> Number {
    total = 0
    for row in rows {
        if get(row, 0) == category { total = total + get(row, 1) }
    }
    return total
}
intent saving_advice(food_won: Number) -> Text {
    goal: one short Korean line on whether this weekly food spend is reasonable
}
entry main(text: Text) {
    raw_lines = split(text, "\n")
    parsed = []
    for line in raw_lines {
        r = parse_row(line)
        if is_ok(r) { parsed = append(parsed, unwrap(r)) }
    }
    food = category_total(parsed, "food")
    advice = saving_advice(food)
    return join([to_text(food), " won food / ", advice], "")
}
```

```
ail run prog.ail --input "food:8000
transit:3500
food:12000
malformed_line
cafe:4500" --mock
# → 20000 won food / [mock response for saving_advice]
```

What this program demonstrates, in one screen:

- `Result` quietly drops the malformed row — no `try/except`, no crash.
- `pure fn category_total` computes a number with confidence 1.0 — every won is counted deterministically.
- `intent saving_advice` is the only place the model is consulted — exactly the part that requires judgment.
- The output mixes a hard number (`20000`) with model-authored text. The boundary is visible in the source.

---

## Forbidden patterns (Python prior leaks the parser rejects)

| You might write | Use this instead |
|---|---|
| `xs[a:b]` (slice) | `slice(xs, a, b)` |
| `xs[i]` for text | `slice(text, i, i+1)` |
| `result = if cond { a } else { b }` | `pure fn pick() { if cond { return a } return b }` |
| `{key: value}` (dict literal) | not in v1.8; use parallel lists or wait for a future version |
| `for x of y` | `for x in y` |
| `while ...` | bounded `for x in range(...)` |
| `&` `|` `^` (bitwise) | not in v1.8 |
| `f"text {var}"` (f-string) | `join(["text ", to_text(var)], "")` |
| `xs.append(item)` (method call) | `xs = append(xs, item)` (returns new list) |
| `List[Number]` as a working generic | parametric type annotations parse but are no-op; runtime is dynamically typed |
| `List(map(fn, xs))` | `map(xs, "fn_name")` — fn name as a STRING |
| `[x*2 for x in xs]` (comprehension) | `for` loop building a list with `append` |

When in doubt, look at the [reference card](08-reference-card.ai.md) for the exact builtin signature.

---

## Twelve-line cheat sheet

```
.ail file = declarations + exactly one entry main
two function kinds: pure fn (deterministic, no LLM) and intent (LLM-backed)
default to pure fn; use intent only when you need to know what words MEAN
no while; no print; no if-as-expression; no slice subscript; no f-strings
return EXPR exits a function. assignments inside fn bodies are local.
text builtins: length / split / join / trim / upper / lower / slice
list builtins:  length / get / range / append / sort / reverse / slice
math builtins:  abs / max / min / round / floor / ceil / sqrt / pow
conversion:     to_number (returns Result) / to_text / to_boolean
Result API:     ok / error / is_ok / is_error / unwrap / unwrap_or / unwrap_error
attempt block:  walk try arms in order; first non-error wins
xs[i] is sugar for get(xs, i); both forms accepted (v1.8.4+)
```

That is enough to write working AIL today. Read the [reference card](08-reference-card.ai.md) for every builtin's exact signature, and `spec/01-language.md` for the full grammar.
