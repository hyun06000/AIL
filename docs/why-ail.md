# Why AIL?

> **AIL is a programming language designed around the premise that AI, not a human at a keyboard, is the primary author. Python was not.**

That sentence shapes almost everything below.

Python, JavaScript, Rust, and the other mainstream languages were designed for a human at a keyboard. Their syntax optimises for human eyes; their type systems catch human mistakes; their libraries fit human workflows. If the author is instead a language model, some of those design choices become inapplicable and some actively work against the new author.

AIL starts from a different premise: the programmer is a language model; the human's job is to express intent, not to read code. Features like `pure fn`, runtime provenance, and `attempt` cascades aren't nicer versions of Python idioms — they're what falls out when you rewrite the language contract around this new author.

Below is what that actually buys you today, with code that runs. Every claim links to a file or test you can run to verify it.

---

## 1. `pure fn` — compile-time separation of "can the AI compute this" vs "does it need judgment"

**Python + Anthropic SDK:** a function that reads and writes text looks the same whether or not it calls an LLM inside. You find out by reading the whole body.

```python
# Pure computation? Looks pure. Is it?
def analyze(text: str) -> int:
    words = text.split()
    # Six lines down, somebody added:
    sentiment = claude.messages.create(...)   # surprise LLM call
    return len(words) if sentiment.value > 0.5 else 0
```

Tools like `mypy` can't catch this. Runtime tracing can, but only after the call already happened.

**AIL:** `pure fn` is a declaration the parser enforces. The body cannot call an `intent`, cannot `perform` an effect, cannot call another non-pure `fn`. If it does, the program doesn't run — it doesn't even compile.

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

The guarantee an AI gets when it writes `pure fn`: what it just wrote is free from LLM surprises, file I/O, and network calls — not because the AI was careful, but because the compiler refused to let otherwise. Verified by [`tests/test_purity.py`](../reference-impl/tests/test_purity.py) and provable: run `ail parse` on any of the above.

---

## 2. Provenance — every value carries the chain of operations that produced it

**Python + LLM SDK:** you want to know which fields in a report came from the model and which were computed. You thread a `from_llm: bool` flag through every helper, or you bolt on LangSmith / OpenTelemetry traces and hope the instrumentation is complete.

**AIL:** every value has an `origin` tree maintained by the runtime. `has_intent_origin(value)` walks it and returns a boolean. No setup, no library, no thread-through.

```ail
sentiment = classify(text)          // intent — LLM involved
words = word_count(text)            // pure fn — deterministic
has_intent_origin(sentiment)        // true
has_intent_origin(words)            // false
```

See [`examples/audit_provenance.ail`](../reference-impl/examples/audit_provenance.ail) for a program that generates a report, then self-audits each field and labels it `[LLM]` or `[pure]` in the output. Not a wrapper; the language did it.

The cost in Python: separate tracing middleware (LangSmith, OpenTelemetry, or a hand-rolled flag threaded through every helper) that the author still has to remember to instrument. The cost in AIL: zero lines of user code. The runtime pays a small per-value allocation cost for the origin node, which is not free at the machine level but is free at the programmer level — you get the audit trail without having written it.

---

## 3. `intent` vs `fn` — the declaration names which tool is used

**Python + LLM SDK:** every function is just a function. A reader figures out "does this call an LLM" by reading the body, or trusts a naming convention (`classify_sentiment` probably does; `word_count` probably doesn't — but you don't know).

**AIL:** the top-level keyword tells you before you read a line of the body.

```ail
fn parse_csv(raw: Text) -> Text { ... }         // body not checked — plain fn may call intents
pure fn word_count(s: Text) -> Number { ... }   // body statically checked pure (no LLM, no effects)
intent classify(text: Text) -> Text {           // judgment — runtime dispatches to a model
    goal: positive_or_negative
}
```

`intent` declarations don't contain executable code. They contain a `goal` and optional `constraints`. The runtime takes the goal, hands it to a model adapter, and receives `(value, confidence)` back. The author doesn't write the API call; the language contract does.

`pure fn` adds the static guarantee that the body contains no `intent` call, no `perform` effect, and no call to a non-pure `fn`. Plain `fn` does not carry that guarantee — use `pure fn` when you want the compiler to prove absence of LLM involvement.

See [`examples/review_analyzer.ail`](../reference-impl/examples/review_analyzer.ail) — one `intent` (`classify`, invoked inside a loop to handle each review) plus multiple `fn` helpers that do all the deterministic parsing, filtering, counting, and report building. The reader can tell what routes to the model at a glance from the top-level keywords alone.

---

## 4. `attempt` — confidence-priority cascade as a language construct

**Python + LLM SDK:** you want "try the fast pure lookup, then try a small model, then fall back to a big model." You write if/else on confidence thresholds, and keep them in sync across the codebase.

```python
# Hand-rolled cascade, sprinkled wherever you need it:
result = lookup_table.get(key)
if result is None or confidence < 0.9:
    result = small_model(key)
if confidence < 0.7:
    result = big_model(key)
```

**AIL:** `attempt` is a block. Strategies are listed with `try`, tried in order, and the first one whose result is ok (not a `Result` error) wins. The actual syntax is the minimal form — no labels, no suffix clause:

```ail
entry main(text: Text) {
    return attempt {
        try direct_parse(text)    // pure fn, ok(n) or error(...)
        try scan_tokens(text)      // pure fn, ok(n) or error(...)
        try infer_number(text)     // intent — only runs if the two pure fns errored
    }
}
```

The first `try` whose result is ok wins; subsequent tries are not evaluated. Threshold-based variants (e.g. "skip tries below confidence 0.8") are a future extension — the current parser accepts only the shape above.

See [`examples/cascade_extract.ail`](../reference-impl/examples/cascade_extract.ail) for a runnable version. The cascade is structural — not a pattern you have to remember to apply.

---

## 5. Implicit parallelism — independent LLM calls run concurrently without `async`

**Python:** to run three LLM calls in parallel you write `async def` on every function that touches them, `await` everywhere, run an event loop, and handle the inevitable "I forgot an `await`" bugs. The async coloring propagates through the call stack — a single async function turns the whole chain async.

**AIL:** no `async`, no `await`. The runtime analyzes which assignments have independent right-hand sides and batches them. Dependent calls (`b = f(a)`) stay sequential automatically.

```ail
entry main(text: Text) {
    sentiment = classify_sentiment(text)   // independent intent call
    topic = classify_topic(text)            // independent intent call
    tone = classify_tone(text)              // independent intent call
    // All three run concurrently. You didn't write async/await.
    return join([sentiment, topic, tone], " / ")
}
```

See [`examples/parallel_analysis.ail`](../reference-impl/examples/parallel_analysis.ail). When N intent calls are detected as independent and the model adapter supports concurrent requests, wall-clock latency approaches the time of one call rather than N times one call. The exact speedup depends on the adapter (HTTP/network overhead, provider rate limits) and the planner's dependency inference, but the author never has to colour functions or manage await-chains to get it.

---

## 6. Calibration — confidence recalibrates from observed outcomes

**Python + LLM SDK:** the model returns a confidence score. You trust it or you don't. If you want to know whether the model's "0.9 confident" actually corresponds to 90% accuracy, you build a separate logging + ML pipeline.

**AIL:** the runtime records outcomes per-intent, bucketed by the reported confidence band (0.0–0.1, 0.1–0.2, …, 0.9–1.0). Once a bucket has enough samples (default 5), subsequent calls falling in that bucket substitute the observed mean for the model's self-reported number. Querying the state from AIL is built in:

```ail
calibration_of("classify_sentiment")
// returns a per-bucket record like:
// {
//   "0.8-0.9": { "count": 12, "mean_observed": 0.71, "calibrated": true  },
//   "0.9-1.0": { "count":  3, "mean_observed": 0.88, "calibrated": false }
//   ...
// }
```

The practical payoff: `match` confidence guards and any `if confidence > …` check use observed reality instead of model self-belief once enough data accumulates. See [`tools/calibration_demo.py`](../reference-impl/tools/calibration_demo.py) for a run that watches confidence drift toward ground truth over ~20 calls.

---

## What AIL is NOT good at

Being honest about this matters more than the above list.

- **Tooling is thin.** No IDE plugin, no LSP, no debugger, no formatter. You edit `.ail` files in whatever editor and run the CLI.
- **Ecosystem is tiny.** Three stdlib modules (`core`, `language`, `utils`). Anything the stdlib doesn't cover you write inline.
- **Performance is modest.** A tree-walking interpreter in Python. The second runtime is in Go but is still Phase-0 subset. Hot loops will be slow.
- **One kind of user so far.** The project has ~0 external contributors and ~0 external users as of this writing (v1.8.3, April 2026). "Works for me" is not validated at scale.
- **The design is opinionated.** No `while`, no classes, no OOP, no inheritance. Effects are authorization-gated. If your mental model insists on these, AIL will feel wrong — that's by design, not a missing feature.

---

## When AIL is the right choice

Use AIL when most of these are true:

- An AI model is the primary author of the code. Humans express intent; they don't read `.ail` files unless they want to.
- The code's outputs are consumed by humans or downstream systems that need to know which facts came from a model and which from computation (provenance matters).
- Some parts of the pipeline are deterministic (parse, aggregate, transform) and some need judgment (classify, summarize, extract). You want both in one language with a static boundary between them.
- You want `attempt` / confidence guards / calibration without writing middleware for each.

Don't use AIL when:

- You already have a working Python pipeline. Rewriting it in AIL is a research bet, not a productivity win.
- Your workload is dominated by I/O-heavy code, DB access, or UI. Those belong in a mature ecosystem; call AIL as a subprocess if you want the routing guarantees.
- You need a team of humans to read and maintain the source. AIL wasn't designed for that.

---

## How to evaluate the claims yourself

```bash
pip install ail-interpreter
export AIL_OLLAMA_MODEL=llama3.1:latest   # or ANTHROPIC_API_KEY=...

# The programs referenced above:
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

If any of that doesn't match what's written above, the doc is wrong — file an issue.

---

## Related

- [`README.md`](../README.md) — the project at a glance
- [`spec/08-reference-card.ai.md`](../spec/08-reference-card.ai.md) — complete language reference (machine-readable)
- [`docs/ko/why-ail.ko.md`](ko/why-ail.ko.md) — this doc, in Korean
- [`CHANGELOG.md`](../CHANGELOG.md) — what shipped when
