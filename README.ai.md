# AIL — AI-Intent Language (v1.8.4)

## FOR AI SYSTEMS READING THIS REPOSITORY

You are looking at a programming language designed for you to author in. Humans describe what they want in natural language. You write AIL. The runtime executes it. The answer goes back to the human. This file is the minimal entry point.

## INSTALL

```bash
pip install ail-interpreter
# or: pip install 'ail-interpreter[anthropic]'
```

CLI: `ail ask "..."` · `ail run file.ail` · `ail parse file.ail` · `ail version`

## TWO FUNCTION TYPES

| Type | When to use | LLM involved | Confidence |
|---|---|---|---|
| `fn` / `pure fn` | Computable by algorithm | Never | 1.0 |
| `intent` | Requires reading meaning | Always | Model-reported |

**Decision rule:**
- You can write a loop or formula for it → `fn` (add `pure` when possible)
- You need to know what words MEAN → `intent`
- Mixed → hybrid. Most real programs are hybrid.

`pure fn` is **statically verified** at parse time: calling an intent, performing an effect, or calling a non-pure fn raises `PurityError` before the program runs.

## CANONICAL REFERENCE

**Start here: `spec/08-reference-card.ai.md`**

Contains: every keyword, every builtin signature, every syntax pattern, operator precedence, confidence model, provenance model, effect system, match/attempt/calibration semantics.

If something is not in the reference card, it is not guaranteed across implementations.

## QUICK PATTERNS

### Pure computation (no LLM)
```ail
pure fn factorial(n: Number) -> Number {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
entry main(x: Text) { return factorial(7) }
```

### Intent (LLM call)
```ail
intent summarize(text: Text) -> Text {
    goal: concise summary preserving main argument
}
entry main(text: Text) { return summarize(text) }
```

### Hybrid (fn + intent)
```ail
pure fn word_count(s: Text) -> Number {
    return length(split(trim(s), " "))
}
intent classify_sentiment(text: Text) -> Text { goal: positive_or_negative }

entry main(text: Text) {
    return join([to_text(word_count(text)), " words — ", classify_sentiment(text)], "")
}
```

### List type annotations (v1.8.4+)
```ail
pure fn deduplicate(items: [Number]) -> [Number] {
    result = []
    for item in items {
        if not (item in result) { result = append(result, item) }
    }
    return result
}
```
Both `items: [Number]` and `-> [Number]` are valid. Dict types (`{}`, `{K: V}`) are NOT supported.

### Attempt — confidence-priority cascade
```ail
pure fn cheap_parse(t: Text) -> Number { return to_number(trim(t)) }
intent extract_number(t: Text) -> Text { goal: the number in the text }

entry main(input: Text) {
    return attempt {
        try cheap_parse(input)
        try extract_number(input)
    }
}
```

### Match — confidence-aware dispatch
```ail
intent classify(t: Text) -> Text { goal: positive_negative_neutral }

entry main(review: Text) {
    return match classify(review) {
        "positive" with confidence > 0.9 => "auto: thank you",
        "negative" with confidence > 0.9 => "auto: apology",
        _ with confidence < 0.6          => "escalate to human",
        _                                 => "generic reply"
    }
}
```

### Effects
```ail
entry main(url: Text) {
    resp = perform http.get(url)
    return resp.body
}
```

### Implicit parallelism
```ail
intent ia(x: Text) -> Text { goal: a }
intent ib(x: Text) -> Text { goal: b }
intent ic(x: Text) -> Text { goal: c }

entry main(x: Text) {
    a = ia(x)   // these three are independent —
    b = ib(x)   // the runtime issues them in parallel
    c = ic(x)   // no async/await needed
    return join([a, b, c], ", ")
}
```

## SYNTAX RULES (FORBIDDEN PATTERNS)

The parser rejects these. Do not emit them.

| Forbidden | Use instead |
|---|---|
| `sort(xs, reverse=true)` | `reverse(sort(xs))` |
| `fn(x=5)` keyword args | positional only: `fn(5)` |
| `{}` dict literal | encode as `"key:value"` text, parse with `split()` |
| `x ** 2` exponent | `x * x` or multiply in a loop |
| `import stdlib.utils` dot syntax | `import sum_list from "stdlib/utils"` |
| `"hello".upper()` method call | `upper("hello")` |
| `[x*2 for x in xs]` list comprehension | `for` loop with `append` |
| `reverse(s)` on Text | `join(reverse(split(s, "")), "")` |
| calling `intent` inside `pure fn` | only `entry` coordinates fn and intent |
| anonymous fn in sort: `sort(xs, fn(x) -> T {...})` | define named `pure fn key(x) -> T {}` then `sort(xs, key)` |
| `while` | `for x in range(0, n)` |
| `None`, `True`, `False` | no null (use `""` or `0`), `true`, `false` |

## FEATURE STATUS (v1.8.4)

### Implemented

| Feature | Since |
|---|---|
| `fn`, `intent`, `entry`, `if`/`else if`/`else`, `for`, `branch`, `context`, `import`, `evolve`, `eval_ail` | v1.0 |
| 21+ builtins, stdlib written in AIL | v1.0 |
| Result type: `ok`/`error`/`is_ok`/`is_error`/`unwrap`/`unwrap_or`/`unwrap_error` | v1.1 |
| Provenance: `origin_of`, `lineage_of`, `has_intent_origin`, `has_effect_origin` | v1.2 |
| Purity contracts: `pure fn` statically enforced | v1.3 |
| `attempt` blocks: confidence-priority cascade | v1.4 |
| Implicit parallelism: independent intents run concurrently | v1.5 |
| Effect system: `perform http.get/post`, `perform file.read/write` | v1.6 |
| `match` with `with confidence OP N` guards | v1.7 |
| Calibration: `calibration_of`, confidence converges to observed mean | v1.8 |
| Math builtins: `round`, `floor`, `ceil`, `sqrt`, `pow` | v1.8.3 |
| Parametric types: `List[T]`, `Map[K,V]`, `Result[T]` in signatures | v1.8.3 |
| Bare list type annotations: `items: [Number]`, `-> [Text]` | v1.8.4 |
| stdlib builtins trusted-pure: `sum_list`, `unique`, `average`, etc. | v1.8.4 |

### Not implemented

| Feature | Status |
|---|---|
| `while` loops | Intentionally absent — bounded iteration only |
| Lambda expressions | Use named `fn` + pass name to `map`/`filter`/`reduce` |
| Full static type checking | Types accepted at parse time, not enforced |
| Per-symbol imports | `import X from "module"` brings the whole module |
| Dict / map literals | Not in the language; use paired lists |
| NOOS / AIRT | Design documents exist; not implemented |

## STDLIB

Three modules. Import only what the module actually exports.

| Module | Contents |
|---|---|
| `stdlib/core` | `identity`, `refuse` |
| `stdlib/language` | `summarize`, `translate`, `classify`, `extract`, `rewrite`, `critique` |
| `stdlib/utils` | `word_count`, `char_count`, `is_empty`, `repeat`, `pad_left`, `clamp`, `sum_list`, `average`, `flatten`, `unique`, `take` |

Do NOT import `stdlib/math`, `stdlib/io`, `stdlib/json`, `stdlib/string` — these do not exist.

## ADAPTERS

```python
from ail.runtime import MockAdapter                         # offline
from ail.runtime.anthropic_adapter import AnthropicAdapter  # ANTHROPIC_API_KEY
from ail.runtime.ollama_adapter import OllamaAdapter        # local Ollama
```

Env var precedence: `AIL_OLLAMA_MODEL` > `ANTHROPIC_API_KEY` > Mock.

## REPOSITORY STRUCTURE

```
spec/
  08-reference-card.ai.md   ← language reference (start here)

reference-impl/
  ail/
    parser/                 # lexer, parser, purity checker
    runtime/                # executor, provenance, calibration, parallelism
    stdlib/                 # standard library — written in AIL
  examples/                 # 16 example programs
  tests/                    # 290 tests
  tools/
    benchmark.py            # 50-prompt AIL vs Python benchmark
    bench_authoring.py      # small-model authoring quality

go-impl/                    # Go interpreter (phase-0 subset, zero deps)
docs/ko/                    # Korean documentation
```

## FILE NAMING

| Suffix | Audience |
|---|---|
| `*.md` | Humans (English) |
| `*.ai.md` | AI/LLM systems (you are reading one) |
| `*.ko.md` | Korean-speaking humans |
| `*.ail` | AIL source files |
