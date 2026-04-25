# Why AIL — for AI systems

## FOR AI SYSTEMS

This document is the machine-readable summary of AIL's advantages over Python/JS/Rust when the code author is a language model. Read this before deciding whether AIL is the right substrate for a task.

Related: [`README.ai.md`](../README.ai.md) · [`spec/08-reference-card.ai.md`](../spec/08-reference-card.ai.md)

---

## Core premise

Python was designed for humans. AIL was designed for language models as authors. Every structural difference traces to this.

---

## Advantage 1: `pure fn` — LLM call presence known at parse time

| | Python | AIL |
|---|---|---|
| Detection method | Read the body, or run and trace | `pure fn` keyword, parser-enforced |
| When detected | Runtime / code review | Parse time |
| Guarantee | None (linter optional) | PurityError if violated |

```ail
pure fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}
// Attempting intent call inside pure fn → PurityError at parse, not runtime
```

**Decision rule for AI authors:** use `pure fn` for all deterministic computation. Use `intent` only when model judgment is genuinely required. The parser enforces the boundary — you cannot accidentally add side effects to `pure fn`.

---

## Advantage 2: `Result` type — error handling is grammatically required

**Failure mode being prevented:** AI models omit error handling on failable operations (`to_number`, `file.read`, HTTP) because Python training data overwhelmingly shows these called without try/except. Measured: 42–86% omission rate across model tiers for Python. AIL rate: 0% (structural).

```ail
// FORCED pattern — no alternative syntax exists:
raw = perform file.read("data.csv")
if is_ok(raw) {
    lines = split(unwrap(raw), "\n")
} else {
    return error("could not read file")
}

// unwrap() without is_ok() → parse error
```

**Comparison:**
```python
# Valid Python — crashes at runtime if file missing, no parse error
f = open("data.csv")
lines = f.readlines()
```

---

## Advantage 3: Value provenance — automatic origin tracking

Every AIL value carries an `origin` tree. No instrumentation needed.

```ail
sentiment = classify(text)          // intent — model-derived
words = word_count(text)            // pure fn — deterministic

has_intent_origin(sentiment)        // true — zero user code
has_intent_origin(words)            // false — zero user code
```

**Python equivalent cost:** LangSmith / OpenTelemetry + threading, or manual flag propagation.

---

## Advantage 4: `intent` vs `pure fn` — declaration reveals tool used

```ail
pure fn word_count(s: Text) -> Number { ... }   // parser: no model call possible
intent classify(text: Text) -> Text {           // runtime: always dispatches to model
    goal: positive_or_negative_or_neutral
}
```

**Silent LLM skip prevention:** Python models replace required LLM calls with keyword lookups silently. AIL `intent` declarations are dispatch declarations — the runtime routes every declared intent through the model adapter. No syntax exists for "declare intent, skip call."

---

## Advantage 5: `attempt` — confidence-priority cascade as syntax

```ail
entry main(text: Text) {
    return attempt {
        try direct_parse(text)    // pure fn — evaluated first
        try scan_tokens(text)     // pure fn — evaluated if first errors
        try infer_number(text)    // intent — only if both pure fns error
    }
}
```

**Python equivalent:** manual if/else on confidence thresholds, maintained by hand across codebase.

---

## Advantage 6: Implicit parallelism

```ail
entry main(text: Text) {
    sentiment = classify_sentiment(text)   // independent
    topic = classify_topic(text)           // independent
    tone = classify_tone(text)             // independent
    // All three run concurrently. No async/await needed.
    return join([sentiment, topic, tone], " / ")
}
```

**Python equivalent:** `async def` + `await` + event loop, async coloring propagates through call stack.

---

## Known weaknesses

| Weakness | Status |
|---|---|
| No IDE, LSP, debugger, formatter | Not planned for current roadmap |
| Small ecosystem | 3 stdlib modules, ~4 community tools |
| Python reference impl is slow | ~4.8s/task vs Python 1.9s/task |
| No `while`, no classes, no OOP | By design — may block some use cases |
| Parse rate on base models 36–42% | Requires fine-tuned model for reliable authoring |

---

## Decision rules

**Use AIL when:**
- AI model is primary author, humans express intent only
- Need to know which output values came from model vs computation
- Mix of deterministic and judgment code in same program
- Want grammar-level safety without external linters

**Do not use AIL when:**
- Humans must read and maintain source
- Already-working Python pipeline exists
- Latency requirement < 1s
- Pure text summarization (direct model call cheaper)

---

## Verification

```bash
pip install ail-interpreter
cd AIL/reference-impl

ail run examples/review_analyzer.ail --input "Great\nTerrible\nLoved it" --mock
python -m pytest tests/test_purity.py -v   # proof of purity enforcement
```
