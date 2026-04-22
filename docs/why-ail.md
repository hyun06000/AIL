# Why AIL?

> AIL is a programming language designed around the premise that AI, not a human at a keyboard, is the primary author. Python was not.

Python, JavaScript, and Rust were designed for a human at a keyboard. Their syntax optimizes for human eyes; their type systems catch human mistakes; their libraries fit human workflows. When the author is a language model instead, some of those design choices become inapplicable and some actively work against the new author.

AIL starts from a different premise: the programmer is a language model, and the human's job is to express intent — not to read source files. Features like `pure fn`, runtime provenance, and `attempt` cascades aren't nicer versions of Python idioms. They're what falls out when you rewrite the language contract around this new author.

Below is what that actually buys you today. Every claim links to a file or test you can run to verify it.

---

## 1. `pure fn` — whether a function calls an LLM is known at compile time

**Python + Anthropic SDK:** a function that reads and writes text looks the same whether or not it calls an LLM inside. You find out by reading the whole body.

```python
# Looks pure. Is it?
def analyze(text: str) -> int:
    words = text.split()
    # Six lines down:
    sentiment = claude.messages.create(...)   # surprise LLM call
    return len(words) if sentiment.value > 0.5 else 0
```

`mypy` can't catch this. Runtime tracing can, but only after the call already happened.

**AIL:** `pure fn` is a declaration the parser enforces. The body cannot call an `intent`, cannot `perform` an effect, cannot call another non-pure fn. If it does, the program doesn't run — it doesn't even parse.

```ail
pure fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}

// This fails at parse time with PurityError:
// pure fn analyze(text: Text) -> Text {
//     label = classify(text)     // intent call inside pure fn — REJECTED
//     return label
// }
```

The guarantee an AI gets when it writes `pure fn`: what it just wrote is free from LLM surprises, file I/O, and network calls — not because the AI was careful, but because the compiler refused to let otherwise.

Verified by [`tests/test_purity.py`](../reference-impl/tests/test_purity.py) or `ail parse` on the examples above.

---

## 2. `Result` type — error handling is grammatically required

**Why this matters:** AI generates code statistically. Because training data overwhelmingly shows `int(x)`, `json.loads(s)`, and `open(f)` written without error handling, models produce failable operations without wrapping them. Humans know from experience that these functions can throw. Models infer it probabilistically, and often get it wrong.

Using a stronger model doesn't fix this. In the benchmark, Claude Sonnet 4.6 still writes Python code that skips error handling on **70%** of the parsed programs that contain failable operations. qwen2.5-coder:14b skips on 42%. The qwen7b base skips on 12%. mistral7b on 14%. The rate does not converge to zero as models scale up — if anything, stronger models attempt more ambitious code with more failable calls and skip wrapping more of them. Python simply *allows* you to write `int(x)` without error handling — the language makes no objection.

In autonomous pipelines where AI generates code and executes it without human review, this omission propagates silently. Wrong values flow downstream. Nobody notices until something breaks far from the source.

**AIL:** `to_number(x)`, `perform file.read(path)`, and other failable operations return a `Result`. Calling `unwrap()` without first calling `is_ok()` is a parse error.

```ail
raw = perform file.read("data.csv")
if is_ok(raw) {
    lines = split(unwrap(raw), "\n")
} else {
    return error("could not read file")
}
```

Write just `unwrap(raw)` without the check and the parser rejects the program. Error handling is not something the model has to remember — the grammar enforces it.

**Measured:** AIL error-handling omission rate is **0%** on every model tier where AIL parses at all — the grammar makes the omission impossible, not unlikely. Python's rate on the same prompts, measured among parsed Python programs that contain failable operations, ranges from **12% to 70%** depending on the author model. The 0% number is the one that doesn't move.

See [`examples/safe_csv_parser.ail`](../reference-impl/examples/safe_csv_parser.ail).

---

## 3. Provenance — every value carries the chain of operations that produced it

**Python + LLM SDK:** you want to know which fields in a report came from the model and which were computed. You thread a `from_llm: bool` flag through every helper, or you bolt on LangSmith / OpenTelemetry traces and hope the instrumentation is complete.

**AIL:** every value has an `origin` tree maintained by the runtime. `has_intent_origin(value)` walks it and returns a boolean. No setup, no library, no thread-through.

```ail
sentiment = classify(text)          // intent — LLM involved
words = word_count(text)            // pure fn — deterministic
has_intent_origin(sentiment)        // true
has_intent_origin(words)            // false
```

See [`examples/audit_provenance.ail`](../reference-impl/examples/audit_provenance.ail) for a program that generates a report and then self-audits each field, labeling it `[LLM]` or `[pure]` in the output. Not a wrapper — the language does it.

The cost in Python: separate tracing middleware that the author still has to remember to instrument. The cost in AIL: zero lines of user code.

---

## 4. `intent` vs `fn` — the declaration tells you which tool is used

**Python + LLM SDK:** every function is just a function. A reader figures out "does this call an LLM" by reading the body, or trusts a naming convention (`classify_sentiment` probably does; `word_count` probably doesn't — but you don't know).

**AIL:** the top-level keyword tells you before you read a line of the body.

```ail
fn parse_csv(raw: Text) -> Text { ... }         // body not checked — plain fn may call intents
pure fn word_count(s: Text) -> Number { ... }   // body statically verified pure (no LLM, no effects)
intent classify(text: Text) -> Text {           // judgment — runtime dispatches to a model
    goal: positive_or_negative
}
```

`intent` declarations don't contain executable code. They contain a `goal` and optional `constraints`. The runtime takes the goal, hands it to a model adapter, and receives `(value, confidence)` back. The author doesn't write the API call — the language contract does.

See [`examples/review_analyzer.ail`](../reference-impl/examples/review_analyzer.ail) — one `intent` invoked in a loop to handle each review, plus `fn` helpers that do all the deterministic parsing, filtering, counting, and report building. You can tell what routes to the model at a glance from the top-level keywords alone.

---

## 5. `attempt` — confidence-priority cascade as a language construct

**Python + LLM SDK:** you want "try the fast pure lookup, then a small model, then a big model." You write if/else on confidence thresholds and keep them in sync across the codebase.

```python
# Hand-rolled cascade, sprinkled wherever you need it:
result = lookup_table.get(key)
if result is None or confidence < 0.9:
    result = small_model(key)
if confidence < 0.7:
    result = big_model(key)
```

**AIL:** `attempt` is a block. Strategies are listed with `try`, tried in order, and the first one whose result is ok wins. Subsequent tries are not evaluated.

```ail
entry main(text: Text) {
    return attempt {
        try direct_parse(text)    // pure fn — ok(n) or error(...)
        try scan_tokens(text)     // pure fn — ok(n) or error(...)
        try infer_number(text)    // intent — only runs if both pure fns errored
    }
}
```

See [`examples/cascade_extract.ail`](../reference-impl/examples/cascade_extract.ail). The cascade is structural — not a pattern you have to remember to apply.

---

## 6. Implicit parallelism — independent LLM calls run concurrently without `async`

**Python:** to run three LLM calls in parallel you write `async def` on every function that touches them, `await` everywhere, and run an event loop. The async coloring propagates through the call stack — one async function turns the whole chain async.

**AIL:** no `async`, no `await`. The runtime analyzes which assignments have independent right-hand sides and batches them. Dependent calls (`b = f(a)`) stay sequential automatically.

```ail
entry main(text: Text) {
    sentiment = classify_sentiment(text)   // independent intent call
    topic = classify_topic(text)           // independent intent call
    tone = classify_tone(text)             // independent intent call
    // All three run concurrently. No async/await written.
    return join([sentiment, topic, tone], " / ")
}
```

See [`examples/parallel_analysis.ail`](../reference-impl/examples/parallel_analysis.ail). When N intent calls are detected as independent, wall-clock latency approaches the time of one call rather than N times one call.

---

## 7. Calibration — confidence recalibrates from observed outcomes

**Python + LLM SDK:** the model returns a confidence score. You trust it or you don't. To know whether "0.9 confident" actually corresponds to 90% accuracy, you build a separate logging and ML pipeline.

**AIL:** the runtime records outcomes per-intent, bucketed by the reported confidence band (0.0–0.1, 0.1–0.2, …, 0.9–1.0). Once a bucket has enough samples (default 5), subsequent calls in that band substitute the observed mean for the model's self-reported number.

```ail
calibration_of("classify_sentiment")
// returns a per-bucket record:
// {
//   "0.8-0.9": { "count": 12, "mean_observed": 0.71, "calibrated": true  },
//   "0.9-1.0": { "count":  3, "mean_observed": 0.88, "calibrated": false }
// }
```

`match` confidence guards and `if confidence > …` checks then use observed reality instead of model self-belief. See [`tools/calibration_demo.py`](../reference-impl/tools/calibration_demo.py).

---

## What AIL is NOT good at

This matters more than the list above.

- **Tooling is thin.** No IDE plugin, no LSP, no debugger, no formatter.
- **Ecosystem is tiny.** Three stdlib modules. Anything else you write inline.
- **Performance is modest.** A tree-walking interpreter in Python. The Go runtime is still feature-subset.
- **One kind of user so far.** ~0 external contributors or users as of v1.9.0 (April 2026).
- **The design is opinionated.** No `while`, no classes, no OOP, no inheritance. Effects are authorization-gated. If your mental model insists on these, AIL will feel wrong — that's by design.

---

## When AIL is the right choice

Use it when most of these are true:

- An AI model is the primary author of the code. Humans express intent; they don't read `.ail` files unless they want to.
- You need to know which values in the output came from a model and which came from computation.
- Some parts of the pipeline are deterministic (parse, aggregate, transform) and some need judgment (classify, summarize, extract). You want both in one language with a static boundary between them.
- You want `attempt` / confidence guards / calibration without writing middleware for each.

Don't use AIL when:

- You already have a working Python pipeline. Rewriting it is a research bet, not a productivity win.
- Your workload is dominated by I/O-heavy code, DB access, or UI. Call AIL as a subprocess for the routing guarantees if you want them.
- You need a team of humans to read and maintain the source.

---

## Verify the claims yourself

```bash
pip install ail-interpreter
export AIL_OLLAMA_MODEL=llama3.1:latest   # or ANTHROPIC_API_KEY=...

git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl

ail run examples/review_analyzer.ail --input "Great product!\nTerrible\nLoved it" --mock
ail run examples/audit_provenance.ail --input "I love this product" --mock
ail run examples/cascade_extract.ail --input "extract a date from: meeting next thursday" --mock
ail run examples/parallel_analysis.ail --input "The Fed raised rates today." --mock

# Proof of purity enforcement:
python -m pytest tests/test_purity.py -v

# Calibration drift over time:
python tools/calibration_demo.py
```

If any result doesn't match what's written above, the doc is wrong — file an issue.

---

## Related

- [`README.md`](../README.md) — project overview
- [`spec/08-reference-card.ai.md`](../spec/08-reference-card.ai.md) — complete language reference (machine-readable)
- [`docs/ko/why-ail.ko.md`](ko/why-ail.ko.md) — this doc in Korean
- [`CHANGELOG.md`](../CHANGELOG.md) — what shipped when
