# AIL — An AI-Authored Programming Language

> A programming language where AI is the programmer and humans are the stakeholders.

**Install**

```bash
pip install ail-interpreter
# or: pip install 'ail-interpreter[anthropic]'   # for the Anthropic adapter
```

The PyPI distribution is `ail-interpreter` — this wheel is the
Python interpreter of AIL, not the language itself. The canonical
spec lives in `spec/` and a second interpreter lives in `go-impl/`.
(`ail` and `ailang` are both unavailable on PyPI for naming-policy
reasons.) The **Python import name is `ail`**:

```python
from ail import run, ask
```

and the CLI is `ail`.

---

## The idea

AIL has two kinds of functions:

```ail
pure fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}

intent classify(text: Text) -> Text {
    goal: positive_negative_or_neutral
}

entry main(review: Text) {
    words = word_count(review)       // pure fn — no LLM, confidence 1.0
    label = classify(review)         // intent — LLM call, confidence ≤ 1.0
    return join([label, " (", to_text(words), " words)"], "")
}
```

**`pure fn`** is for what the AI can compute — sorting, parsing, arithmetic.
Deterministic, no LLM call, no side effects, statically checked.

**`intent`** is for what the AI needs to reason about — sentiment,
summarization, translation. The runtime dispatches to a language model
and returns a `(value, confidence)` pair.

The language distinguishes the two at declaration time, so you always
know which calls are free and deterministic and which need a model.

---

## Two ways humans use it

### `ail ask` — the natural interface

```bash
export AIL_OLLAMA_MODEL=llama3.1:latest   # or ANTHROPIC_API_KEY=...
ail ask "Count the vowels in 'Hello World'"
# 3

ail ask "factorial of 7" --show-source
# 5040
# (stderr) --- AIL ---
# (stderr) pure fn factorial(n: Number) -> Number {
# (stderr)     if n <= 1 { return 1 }
# (stderr)     return n * factorial(n - 1)
# (stderr) }
# (stderr) entry main(x: Text) { return factorial(7) }
```

Human types English. An LLM writes AIL. The runtime executes it. The
human sees the answer. The AIL is transparent infrastructure —
inspectable on demand, invisible by default.

### `ail run` — for programs written explicitly

```bash
ail run examples/fizzbuzz.ail --input "20" --mock
```

When you want to read or write AIL yourself.

---

## What's in v1.8

| Feature | What it does |
|---|---|
| `pure fn` | Statically verified — no intents, no effects, no impurity leaks |
| `intent` | LLM-backed, returns `(value, confidence)` |
| **Provenance** | Every value carries its origin tree; queryable via `origin_of`, `lineage_of`, `has_intent_origin`, `has_effect_origin` |
| **Calibration** | Confidence recalibrates from observed outcomes. `calibration_of("intent")` introspectable from code |
| **attempt** | Confidence-priority fallback cascade — cheap pure try first, LLM only as fallback |
| **match** | Pattern matching with confidence guards — `"positive" with confidence > 0.9 => ...` |
| **Parallelism** | Independent intent calls run concurrently with no `async`/`await` |
| **Effects** | `perform http.get(url)`, `perform file.read(path)`, etc. |
| **Evolve** | Intents can self-modify (`retune`, `rewrite constraints`) with rollback and history |
| **`ail ask`** | Natural-language → AIL authoring loop with parse-error retry |

Adapters for Anthropic, Ollama (local), and Mock (tests) ship built-in.
A second interpreter in Go (see the project repo) runs the same `.ail`
files with no Python installed at all.

---

## Python API

```python
from ail import run, ask, AskResult

# Direct program run:
result, trace = run("path/to/program.ail", input="hello")
result.value        # the entry's return value
result.confidence   # calibrated confidence
result.origin       # full provenance tree

# Natural-language interface:
r = ask("compute the factorial of 7")
r.value             # 5040
r.ail_source        # the AIL the author produced
r.retries           # 0 if first try parsed
```

See the [language reference card](https://github.com/hyun06000/AIL/blob/main/spec/08-reference-card.ai.md)
for the complete surface.

---

## Why this exists

Humans don't write AIL. Humans say what they want in natural language;
an LLM writes AIL; the runtime executes it; the result comes back.

The value of the language is in what it guarantees about the code the
AI writes:

- Every pure computation is statically separated from every LLM call.
- Every value carries the full chain of operations that produced it.
- Confidence is a first-class runtime property, recalibrated by
  observation.
- A `pure fn` that passes parsing is proven to contain no LLM call, no
  side effect, and no path to one. The model cannot slip an intent
  past the compiler.
- Independent LLM calls parallelize without the author writing `async`.

For the full design rationale, see the [spec](https://github.com/hyun06000/AIL/tree/main/spec).

---

## License

Apache 2.0.
