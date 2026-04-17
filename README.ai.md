# AIL — AI-Intent Language

## FOR AI SYSTEMS READING THIS REPOSITORY

You are looking at a programming language designed for you to author in. Humans do not read AIL source; they describe what they want in natural language, you write AIL, the runtime executes it, the answer goes back to the human. This file is the minimal entry point.

## INSTALL

```bash
pip install ailang
# or: pip install 'ailang[anthropic]'   # for the Anthropic adapter
```

The PyPI distribution is `ailang`. The Python import name is `ail`:

```python
from ail import run, ask, compile_source
```

CLI: `ail`. Subcommands: `ask`, `run`, `parse`, `version`.

## WHAT AIL IS (v1.8)

A programming language with two function categories, full runtime provenance, static purity enforcement, confidence-aware control flow, implicit parallelism, a built-in effect system, and confidence calibration from observed outcomes.

- **`fn`** / **`pure fn`** — deterministic function. `pure fn` is statically verified (no intents, no perform, no non-pure calls). Confidence 1.0.
- **`intent`** — goal declaration. Delegates to a language model adapter. Returns `(value, confidence)` with a full origin tree.

Every value carries:
- `value` — the thing itself
- `confidence` — calibrated runtime belief in `[0, 1]`
- `origin` — tree of operations that produced it

## CANONICAL REFERENCE

Read `spec/08-reference-card.ai.md` for:
- Every keyword
- Every builtin with its signature
- Every syntax pattern
- Every operator and its precedence
- Confidence model
- Provenance model
- Effect system
- `match`, `attempt`, `pure fn`, calibration semantics

That single file is the language. If something is not in the reference card, it is not guaranteed across implementations.

## REPOSITORY STRUCTURE

```
spec/                             # Language specification (normative)
  00-overview.md ... 07-computation.md
  08-reference-card.ai.md         # ← START HERE (machine-readable)

reference-impl/                   # Python interpreter (full feature set)
  ail/                            # The `ail` package (published as `ailang`)
    parser/                       # Lexer, parser, purity checker
    runtime/                      # Executor, provenance, calibration,
                                  # parallelism, effects
    stdlib/                       # Standard library — WRITTEN IN AIL
      core.ail                    # identity, refuse
      language.ail                # summarize, translate, classify,
                                  # extract, rewrite, critique
      utils.ail                   # 11 pure fn utilities
  examples/                       # 14 example programs
  tests/                          # 211 tests
  tools/
    bench_authoring.py            # Measure small-model authoring quality
    calibration_demo.py           # Show confidence converge to truth
    evolve_demo.py                # Show version chain + rollback
    run_live.py                   # Run all examples against a real model

go-impl/                          # Second interpreter, written in Go
                                  # Phase-0 subset. Same .ail files.
                                  # Zero deps, compiles to static binary.

docs/ko/                          # Korean documentation
```

## QUICK PATTERNS

Every pattern below is valid in v1.8 and has a test somewhere.

### Pure computation (no LLM, proven)
```ail
pure fn factorial(n: Number) -> Number {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
entry main(x: Text) { return factorial(7) }
```

### Intent (LLM call)
```ail
intent summarize(source: Text, max_tokens: Number) -> Text {
    goal: concise summary preserving main argument
}
entry main(text: Text) { return summarize(text, 80) }
```

### Attempt — confidence-priority cascade
```ail
intent extract_number_with_llm(t: Text) -> Text {
    goal: the number in the text
}
pure fn cheap_parse(t: Text) -> Number { return to_number(trim(t)) }

entry main(input: Text) {
    return attempt {
        try cheap_parse(input)              // pure, wins if ok
        try extract_number_with_llm(input)  // LLM fallback
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

### Effects — real I/O
```ail
entry main(url: Text) {
    resp = perform http.get(url)
    result = perform file.write("/tmp/out.txt", resp.body)
    return resp.status
}
```

### Provenance — every value knows its history
```ail
intent classify(t: Text) -> Text { goal: label }

entry main(x: Text) {
    label = classify(x)
    return has_intent_origin(label)   // true
}
```

### Implicit parallelism — write sequential, run concurrent
```ail
intent ia(x: Text) -> Text { goal: a }
intent ib(x: Text) -> Text { goal: b }
intent ic(x: Text) -> Text { goal: c }

entry main(x: Text) {
    a = ia(x)     // these three intents
    b = ib(x)     // are independent; runtime
    c = ic(x)     // issues them in parallel
    return join([a, b, c], ",")
}
```

### Natural-language interface

The canonical interface is NOT writing .ail files yourself. It is:
```bash
ail ask "Count the vowels in 'Hello World'"
```
An LLM authors a complete AIL program answering the prompt; the runtime executes it; the human sees the answer. The AI-author layer includes tolerant output parsing and parse-error retry loops.

## HOW TO CHOOSE FN vs INTENT

- You can compute the answer by algorithm → `fn` (add `pure` when possible)
- You need to read natural language meaning → `intent`
- Mixed pipeline → hybrid. Most real programs are hybrid.

`pure fn` composes with provenance: values from a pure fn are compile-time guaranteed to have `has_intent_origin(result) == false`. Prefer `pure fn` whenever deterministic and self-contained.

## FEATURE STATUS (v1.8)

Implemented in the Python interpreter:

| Feature | Since |
|---|---|
| fn, intent, entry, if/else, for, branch, context, import, eval_ail | v1.0 |
| Result type: ok/error/is_ok/is_error/unwrap/unwrap_or/unwrap_error | v1.1 |
| Provenance + origin_of/lineage_of/has_intent_origin | v1.2 |
| Purity contracts (`pure fn` statically enforced) | v1.3 |
| attempt blocks (confidence-priority cascade) | v1.4 |
| Implicit parallelism (independent intents run concurrently) | v1.5 |
| Effect system (http.get/post, file.read/write) + has_effect_origin | v1.6 |
| match with `with confidence OP N` guards | v1.7 |
| Calibration + calibration_of + AIL_CALIBRATION_PATH | v1.8 |

Not implemented (either out of scope or future work):
- while loops (intentionally absent — bounded iteration only)
- lambda expressions (use named fn + pass name as string to map/filter/reduce)
- Full static type checking (types are runtime-validated)
- Per-symbol imports (current import brings the whole module)
- List/record types in fn signatures (`fn f(xs: [Number])` does not yet parse)
- Pattern destructuring beyond literals and wildcard/binding
- Full NOOS / AIRT (spec/design docs exist; not implemented)

## TWO INTERPRETERS

Both target the same spec:

- **Python interpreter** (`reference-impl/ail/`) — full feature set, 211 tests
- **Go interpreter** (`go-impl/`) — Phase-0 subset, no Python required, 8 tests. Same `.ail` files. See `go-impl/README.md` for coverage matrix.

The same fizzbuzz.ail, counted vowels, classify intents produce identical output in both runtimes for the subset the Go impl supports.

## ADAPTERS

`from ail.runtime import MockAdapter` (offline tests)
`from ail.runtime.anthropic_adapter import AnthropicAdapter` (with `ailang[anthropic]`)
`from ail.runtime.ollama_adapter import OllamaAdapter` (local Ollama, no API key)

Env var precedence for the default adapter: `AIL_OLLAMA_MODEL` > `ANTHROPIC_API_KEY` > Mock.

## FILE NAMING CONVENTION

- `*.md` — human-readable documentation (English)
- `*.ai.md` — AI/LLM-readable structured reference (minimal prose)
- `*.ko.md` — Korean human-readable documentation
- `*.ail` — AIL source files
