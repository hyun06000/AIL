# AIL — AI-Intent Language

> A programming language designed for AI as the primary author of code.

**Status:** Specification v0.2 · Python interpreter with 84 tests · FizzBuzz runs without an LLM

🇰🇷 **한국어 독자:** [`docs/ko/README.ko.md`](docs/ko/README.ko.md)

---

## What is AIL?

AIL is a programming language where **AI is the programmer and humans are the stakeholders**. It has two kinds of building blocks:

- **`fn`** — pure deterministic functions for algorithms, data transforms, and logic. No LLM needed. Fast, free, confidence 1.0.
- **`intent`** — goal-driven declarations that delegate to a language model when judgment is required. Slow, costs tokens, carries a confidence score.

The AI chooses the right tool for each subtask. This distinction — "what I can compute" vs "what I need to reason about" — is built into the language, not a framework convention.

```ail
import classify from "stdlib/language"
import word_count from "stdlib/utils"

fn build_report(label: Text, count: Number) -> Text {
    return join([label, " (", to_text(count), " words)"], "")
}

entry main(text: Text) {
    sentiment = classify(text, "positive_negative_neutral")  // intent: LLM
    count = word_count(text)                                  // fn: no LLM
    return build_report(sentiment, count)                     // fn: no LLM
}
```

---

## Quick start

```bash
cd reference-impl
pip install -e ".[anthropic]"

# No API key needed — pure fn programs run without an LLM:
ail run examples/fizzbuzz.ail --input "20" --mock

# With an API key (env var or .env file):
echo 'ANTHROPIC_API_KEY=sk-ant-...' > ../.env
python examples/run_live.py

# See evolution (retune + rollback) in action:
python examples/evolve_retune_demo.py
```

---

## What the language can do today

| Feature | Example |
|---|---|
| Pure functions | `fn factorial(n) -> Number { if n <= 1 { return 1 } return n * factorial(n-1) }` |
| Loops | `for item in list { ... }` |
| Conditionals | `if / else if / else` |
| 20 built-in functions | `split`, `join`, `sort`, `map`, `filter`, `reduce`, `range`... |
| LLM-backed intents | `intent classify(text) -> Text { goal: sentiment_label }` |
| Context system | `with context formal_korean: translate(doc)` |
| Self-modification | `evolve { retune ... }`, `rewrite constraints` (human review enforced) |
| Module system | `import summarize from "stdlib/language"` |
| Confidence tracking | Every value carries a confidence in [0, 1] |
| Standard library | `stdlib/core`, `stdlib/language` (intents), `stdlib/utils` (fns) — all written in AIL |

---

## Examples (8 programs)

| Program | What it shows | LLM needed? |
|---|---|---|
| `hello.ail` | Simplest possible program | Yes |
| `translate.ail` | Context inheritance + override | Yes |
| `classify.ail` | Branch dispatch on classifier output | Yes |
| `ask_human.ail` | Low-confidence fallback to human | Yes |
| `evolve_retune.ail` | Evolution with version chain | Yes |
| `summarize_and_classify.ail` | stdlib imports | Yes |
| **`fizzbuzz.ail`** | **Pure fn — no LLM at all** | **No** |
| **`review_analyzer.ail`** | **Hybrid: fn parses data, intent judges sentiment** | **Partially** |

The last two are the most important. FizzBuzz proves AIL is a real language. The review analyzer shows the hybrid model working in practice: 23 fn calls (free, fast) + 6 intent calls (LLM, for judgment only).

---

## Repository layout

```
ail-project/
├── spec/              # Language specification (7 documents)
│   ├── 01-language    # Core syntax: intent, context, branch, entry
│   ├── 02-context     # Context system
│   ├── 03-confidence  # Confidence model
│   ├── 04-evolution   # Self-modification
│   ├── 05-effects     # Effects and authorization
│   ├── 06-stdlib      # Standard library spec
│   └── 07-computation # fn, if, for, types (v0.2)
├── runtime/           # AIRT runtime design (document, not full impl)
├── os/                # NOOS OS design (document only)
├── reference-impl/    # Python interpreter (working)
│   ├── ail_mvp/       # Parser, executor, adapters, stdlib
│   ├── examples/      # 8 example programs
│   └── tests/         # 84 tests
├── docs/
│   ├── ko/            # Korean documentation
│   └── open-questions.md
└── .github/           # CI with optional live-test against Claude
```

### What is implemented vs what is design-only

| Component | Status |
|---|---|
| AIL language (spec + interpreter) | ✅ Working |
| Standard library | ✅ Working (written in AIL) |
| Evolution (retune + rewrite constraints) | ✅ Working |
| Anthropic adapter | ✅ Working |
| AIRT full dispatcher | 📄 Design document |
| NOOS operating system | 📄 Design document |

AIRT and NOOS are vision documents describing what a purpose-built runtime and OS would look like. They are not implemented. The Python interpreter is the working runtime today.

---

## Why a new language? (not a Python library)

Three things AIL enforces that a Python library cannot:

1. **`evolve` blocks require `rollback_on` and `history`** — compile error if missing. A library can only recommend; a language can refuse to run.

2. **`rewrite constraints` always forces human review** — even if the program forgot to declare it. A library cannot override the programmer's omission.

3. **`fn` cannot perform effects** — no network calls, no file writes, no side effects. Guaranteed by grammar, not by convention. An AI writing `fn` knows its code is pure.

See [spec/07-computation.md](spec/07-computation.md) for the full comparison.

---

## Design tenets

1. **AI is the author, human is the stakeholder.**
2. **`fn` for computation, `intent` for judgment.** The AI picks; the language supports both.
3. **Probabilistic where needed, deterministic where possible.** `fn` is always confidence 1.0; `intent` carries a distribution.
4. **Context is a type.** Situational assumptions are declared, inherited, and traced.
5. **Live programs.** `evolve` lets programs improve under declared constraints.
6. **Observability is not optional.** Every decision has a trace.
7. **Humans remain in the loop for consequences.** Effects require authorization; constraint rewrites require review.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Design critique is as valuable as code. [docs/open-questions.md](docs/open-questions.md) lists 15 unresolved problems — picking one and proposing an answer is a great first contribution.

한국어로 이슈나 PR을 여셔도 괜찮습니다.

## License

Apache 2.0. See [LICENSE](LICENSE).
