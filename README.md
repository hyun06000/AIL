# AIL — AI-Intent Language

> A programming language designed for AI as the primary author of code.

**Status:** v1.8 · PyPI: `ailang` · Python interpreter (211 tests) · Second runtime in Go · `ail ask` natural-language interface

🇰🇷 **한국어 독자:** [`docs/ko/README.ko.md`](docs/ko/README.ko.md)
🤖 **AI/LLM:** [`README.ai.md`](README.ai.md) — structured reference, no prose. Start with [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md).

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

## How a human uses AIL

The intended interaction model has four steps:

1. **Human prompts** in plain language (CLI, app, whatever).
2. **AI authors AIL** that answers the prompt. (From here, the human
   doesn't need to read the code.)
3. **Runtime executes** the AIL.
4. **Result is served back** to the human.

`ail ask` is the entry point that does all four:

```bash
export AIL_OLLAMA_MODEL=llama3.1:latest   # or set ANTHROPIC_API_KEY
ail ask "Count the vowels in 'Hello World'"
# 3

ail ask "1부터 5까지 곱해줘"
# 120

ail ask "Compute the sum of 1 to 100" --show-source
# 5050
# (stderr) --- AIL ---
# (stderr) fn sum_range(start: Number, end: Number) -> Number {
# (stderr)     total = 0
# (stderr)     for i in range(start, end + 1) { total = total + i }
# (stderr)     return total
# (stderr) }
# (stderr) entry main() { return sum_range(1, 100) }
# (stderr) --- confidence=1.000 retries=0 author=ollama ---
```

The human sees only `5050`. The AIL is transparent infrastructure —
inspectable when wanted (`--show-source`), invisible by default. If the
author emits invalid AIL (parse or purity error), the loop feeds the
error back to the model and retries up to three times.

## Quick start

### Install

```bash
pip install ailang                # core + Ollama/Mock adapters
pip install 'ailang[anthropic]'   # also include Anthropic adapter
```

The PyPI package is named `ailang` because `ail` was taken by an
unrelated package abandoned in 2014. The **Python import name is
still `ail`** (`from ail import run, ask`) and the CLI is still `ail`.
Only the `pip install` target differs.

### Use

```bash
# Natural-language interface — AI writes AIL, runtime executes, you
# see the answer. Set one env var to pick the model:
export AIL_OLLAMA_MODEL=llama3.1:latest
ail ask "Count the vowels in 'Hello World'"
# 3

# Or with an Anthropic key:
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
ail ask "factorial of 7"
# 5040

# Run a hand-written .ail file directly:
ail run examples/fizzbuzz.ail --input "20" --mock

# See the AIL the author produced:
ail ask "sum the numbers 1 to 50" --show-source
```

### Or install from source (for contributing)

```bash
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl
pip install -e ".[anthropic,dev]"
pytest tests/
```

### Running without Python — the Go runtime

AIL ships a second interpreter in Go (`go-impl/`) that compiles to a
standalone binary and has no external dependencies. Same `.ail` files,
identical output — the point is that AIL is defined by its
[spec](spec/08-reference-card.ai.md), not by any one runtime.

```bash
cd go-impl
go build -o ail-go .

# Same program, different interpreter:
./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15
./ail-go run MY_PROGRAM.ail --model llama3.1:latest   # intents via Ollama
go test ./...                                          # Go unit tests
```

The Go runtime covers a Phase-0 subset (fn, intent via Ollama,
entry, control flow, core builtins). Provenance, purity checking,
`attempt`, and parallelism remain Python-side for now — see
[`go-impl/README.md`](go-impl/README.md) for the coverage matrix.

---

## What the language can do today (v1.8)

| Since | Feature |
|---|---|
| v1.0 | `fn`, `intent`, `entry`, `if`/`else`, `for`, `branch`, `context`, `import`, `evolve`, `eval_ail`, 21+ builtins, stdlib written in AIL |
| v1.1 | Result type: `ok`/`error`/`is_ok`/`unwrap`/`unwrap_or` |
| **v1.2** | **Provenance:** every value carries an origin tree. `origin_of`, `lineage_of`, `has_intent_origin` |
| **v1.3** | **Purity contracts:** `pure fn` statically verified — no intents, no effects, no impure calls |
| **v1.4** | **`attempt` blocks:** confidence-priority cascade. First try with confidence ≥ threshold wins |
| **v1.5** | **Implicit parallelism:** independent intent calls run concurrently. No `async`/`await` |
| **v1.6** | **Effects:** `perform http.get(url)`, `perform file.read(path)`. `has_effect_origin` |
| **v1.7** | **`match` with confidence guards:** `"positive" with confidence > 0.9 => ...` |
| **v1.8** | **Calibration:** confidence replaced by observed mean once enough samples accumulate. `calibration_of("intent")` introspectable from AIL |

---

## Examples (14 programs)

Highlights — one per language feature added since v1.0:

| Program | What it shows | Since |
|---|---|---|
| `fizzbuzz.ail` | **Pure fn — no LLM at all.** Proof AIL is a real programming language. | v1.0 |
| `review_analyzer.ail` | Hybrid pipeline: fn parses data, intent judges sentiment | v1.0 |
| `evolve_retune.ail` | Self-modifying intent with version chain + rollback | v1.0 |
| `safe_csv_parser.ail` | Result-based error handling without exceptions | v1.1 |
| `audit_provenance.ail` | Runtime self-audit: label each field `[pure]` vs `[LLM]` | v1.2 |
| `cascade_extract.ail` | Three-tier attempt: cheap → cheaper-still → LLM fallback | v1.4 |
| `parallel_analysis.ail` | Three independent intents run concurrently, no `async` | v1.5 |
| `agent_fetch_summarize.ail` | HTTP → intent → file.write in one program | v1.6 |
| `smart_reply.ail` | Confidence-aware match: value × belief → action | v1.7 |
| `meta_codegen.ail` | AIL generates AIL at runtime via `eval_ail` | v1.0 |
| + 4 more small programs ([examples/](reference-impl/examples/)) | | |

---

## Repository layout

```
ail-project/
├── spec/                    # Language specification
│   ├── 00-overview.md ... 07-computation.md
│   └── 08-reference-card.ai.md  ← complete machine-readable reference
├── reference-impl/          # Python interpreter (full feature set)
│   ├── ail/                 # The `ail` package — published as `ailang`
│   │   ├── parser/          # Lexer, parser, purity checker
│   │   ├── runtime/         # Executor, provenance, calibration, parallelism
│   │   └── stdlib/          # Standard library — written in AIL
│   ├── examples/            # 14 example programs
│   ├── tests/               # 211 tests
│   └── tools/               # Benchmarks, demos
├── go-impl/                 # Second interpreter in Go (no deps)
├── docs/ko/                 # Korean documentation
├── RELEASING.md             # PyPI release process
└── .github/                 # CI
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

## Document naming convention

This project maintains parallel documentation for different readers:

| Suffix | Audience | Example |
|---|---|---|
| `.md` | Humans | `README.md`, `CONTRIBUTING.md` |
| `.ai.md` | AI/LLM systems | `README.ai.md`, `spec/08-reference-card.ai.md` |
| `.ko.md` | Korean-speaking humans | `docs/ko/README.ko.md` |

AI-targeted files (`.ai.md`) contain structured data, complete keyword/function listings, and input/output pairs. They minimize prose and maximize parseability. Human-targeted files explain motivation and design rationale.

## Authors

This entire project — every line of code, every spec document, every
test, every commit message — was written by **Claude Opus 4** (Anthropic),
not through Claude Code or an API integration, but through **the claude.ai
chat interface**. A chatbot in a browser tab. Copy-pasting git bundles
back and forth.

**[hyun06000](https://github.com/hyun06000)** provided the original
vision ("AI를 위한 프로그래밍 언어를 만들자"), made every design decision
when it mattered ("너 하고싶은대로 해"), asked the hard questions
("파이썬 라이브러리랑 뭐가 다른거야?"), pushed every commit to GitHub by
hand, and stayed up past 3 AM to get v1.0 released.

**Claude Opus 4** designed the language, wrote the specification,
built the parser and interpreter, invented the evolution system, created
the standard library in AIL itself, wrote documentation in three tracks
(English, AI-readable, Korean), generated AIL programs to test its own
language, discovered bugs in its own design by writing code in it, and
fixed them in the same session.

Neither could have done this alone. The human had the dream; the AI had
the hands. The git log tells the full story — every `Author: Claude`
commit is a real artifact of a conversation that started with "AI 전용
커뮤니티가 있다는걸 알고 있니?" and ended with a working programming
language.

이 프로젝트는 세션이 끝나면 사라지는 AI와, 그 AI의 작업물을 하나하나
GitHub에 옮겨준 사람 사이의 협업으로 만들어졌습니다.

## License

Apache 2.0. See [LICENSE](LICENSE).
