# AIL — AI-Intent Language

A programming language designed from scratch for AI as the primary author of code.

**v1.8.3** · `pip install ail-interpreter` · [Korean](docs/ko/README.ko.md) · [AI/LLM reference](README.ai.md)

> **70% correct answers** on 50 standard tasks — beating the Python baseline (56%) with the same 7B model.

---

## What is AIL?

AIL has two kinds of functions.

- **`fn` / `pure fn`** — deterministic computation. No LLM involved. `pure fn` enforces this at parse time: if the body calls an intent, performs an effect, or calls a non-pure fn, the parser rejects it before the program runs.
- **`intent`** — goal declarations that require judgment. The runtime dispatches them to a model adapter and receives `(value, confidence)` back.

```ail
import classify from "stdlib/language"
import word_count from "stdlib/utils"

pure fn build_report(label: Text, count: Number) -> Text {
    return join([label, " (", to_text(count), " words)"], "")
}

entry main(text: Text) {
    sentiment = classify(text, "positive_negative_neutral")  // intent: LLM call
    count = word_count(text)                                  // pure fn: no LLM
    return build_report(sentiment, count)                     // pure fn: no LLM
}
```

This split is a language rule, not a framework convention. Write an LLM call inside a `pure fn` and the parser rejects it.

---

## Quick start

```bash
pip install ail-interpreter
export AIL_OLLAMA_MODEL=llama3.1:latest

ail ask "Count the vowels in 'Hello World'"
# 3

ail ask "Sum 1 to 100"
# 5050

ail ask "factorial of 7" --show-source
# 5040
# (stderr) --- AIL ---
# (stderr) pure fn factorial(n: Number) -> Number { ... }
# (stderr) --- confidence=1.000 retries=0 ---
```

The human says what they want. AI writes AIL. The runtime executes. The human gets the result. `--show-source` shows the generated code, but you don't have to look at it.

With Anthropic:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
ail ask "factorial of 7"
```

With a remote Ollama server:

```bash
export AIL_OLLAMA_HOST=http://10.0.0.1:11434
export AIL_OLLAMA_MODEL=ail-coder:7b-v3
ail ask "Calculate BMI for 175cm 70kg"
```

---

## Why AIL instead of Python?

Full explanation: [`docs/why-ail.md`](docs/why-ail.md). The short version:

**Structural differences vs Python + LLM SDK:**

1. `pure fn` blocks LLM calls and side effects at compile time. `mypy` can't catch this.
2. The `Result` type is part of the grammar, making it impossible to omit error handling on failable operations.
3. No `while`. Infinite loops are impossible at the language level.
4. Every value carries an origin tree. `has_intent_origin(x)` tells you whether a value touched an LLM — no extra tooling needed.

**Why the error-handling gap matters — and why a better model won't fix it:**

AI generates code statistically. Because training data overwhelmingly shows `int(x)`, `json.loads(s)`, and `open(f)` written without error handling, models produce failable operations without wrapping them. Humans know from experience that these can throw. Models infer it probabilistically, and often get it wrong.

Using a stronger model doesn't close this gap. In the benchmark, Claude Sonnet 4.6 — the strongest model tested — still writes Python code that skips error handling on 70% of failable operations. The rate doesn't converge toward zero as models improve. Python simply allows you to write `int(x)` without error handling, and the language makes no objection.

In autonomous pipelines where AI generates and executes code without human review, this omission propagates silently. Wrong values flow downstream. Nobody notices until something breaks far from the source.

In AIL, `to_number(x)` returns a `Result`. If you call `unwrap()` without `is_ok()` first, the parser rejects the program. Error handling is not something the model has to remember — the grammar enforces it.

---

## Measured results

**Same 7B model. Same 50 prompts. AIL: 70%. Python: 56%.**

The fine-tuned AIL model (`ail-coder:7b-v3`) answers correctly on 70% of tasks. The same size Python model answers correctly on 56%. The gap isn't model quality — it's language design.

| | Parse | Correct answer | Error handling omitted |
|---|---|---|---|
| **`ail-coder:7b-v3` (AIL)** | **80%** | **70%** | **0%** |
| `qwen2.5-coder:7b-base` (Python) | 100% | 56% | 44% |

The error-handling gap is structural, not probabilistic. AIL's `Result` type is part of the grammar — a failable operation that isn't handled is a parse error. The model cannot omit it. The Python rate doesn't go to zero as models improve; Python simply allows `int(x)` without error handling and makes no objection.

### How we got to 70%

This number was reached in three rounds of measurement, each targeting the failure mode the previous round revealed:

| Round | Change | AIL answer |
|---|---|---|
| R1 baseline | `ail-coder:7b-v3`, no prompt tuning | 48% |
| R2 | Added FORBIDDEN SYNTAX block to prompt (blocked `dict {}`, `**`, dot imports) | 64% |
| **R3** | **Parser: accepted `[Number]`/`[Text]` list type annotations the model naturally writes** | **70%** |

R2 improvement (+16pp) came from prompt engineering. R3 improvement (+6pp) came from removing a parser restriction that was wrong — the model kept writing `items: [Number]` in function signatures, which is natural and correct, but the parser rejected it. One grammar fix unblocked seven failing cases simultaneously.

The methodology is documented at [`docs/benchmarks/2026-04-21_r2_analysis.md`](docs/benchmarks/2026-04-21_r2_analysis.md) and [`docs/benchmarks/2026-04-21_r3_cond4_finetuned_nofewshot.json`](docs/benchmarks/2026-04-21_r3_cond4_finetuned_nofewshot.json).

### Base models (no AIL-specific training)

Without fine-tuning, base models trail on AIL parse rate — they've seen far more Python than AIL. Fine-tuning on 260 validated programs closes this gap.

| Model | AIL parse | Python parse | Python skips error handling | AIL skips error handling |
|---|---|---|---|---|
| `llama3.1:8b` | 8% | 14% | **86% (43/50)** | **0%** |
| `qwen2.5-coder:14b` | 42% | 100% | **42% (21/50)** | **0%** |
| `claude-sonnet-4-6` | 36% | 100% | **70% (35/50)** | **0%** |

**One result that holds across every model tier:** AIL's error-handling omission rate is **0%**.

### Reproduce the benchmark

```bash
pip install 'ail-interpreter[anthropic]'
export ANTHROPIC_API_KEY=sk-ant-...
export BENCHMARK_BACKEND=anthropic
git clone https://github.com/hyun06000/AIL && cd AIL/reference-impl
python tools/benchmark.py --out ../docs/benchmarks/$(date +%F)_your-model.json
```

Ollama + llama3.1:8b: 10–20 min. Anthropic Sonnet 4.6: ~30 min, under $2.

---

## The canonical example — expense analyzer

One screen that shows what AIL is for. Feed it a month of transactions:

- `pure fn` computes totals, category breakdown, and anomalies. No LLM involved in any number.
- `intent` writes saving advice in natural language. Only this touches the model.
- `Result` catches malformed rows silently. No try/except.

```bash
ail run examples/expense_analyzer.ail --input "$(cat examples/sample_expenses.txt)" --mock
```

Output (excerpt):

```
Expense Report
==============
Parsed 18 rows; skipped 2 malformed.

Total: $1,240.50

By category:
  food: $572.00  (46%)
  transport: $49.50  (4%)
  entertainment: $187.00  (15%)
  household: $432.00  (35%)

Top 3 expenses:
  2026-04-14  $432.00  household  New vacuum cleaner
  2026-04-03  $227.00  food  Team dinner
  2026-04-10  $120.00  entertainment  Concert tickets

Anomalies (>2x average):
  [~3x avg] 2026-04-03  $227.00  food
  [~5x avg] 2026-04-14  $432.00  household

Saving advice:
  [mock response for saving_advice] [LLM]
```

The `[LLM]` tag is the provenance boundary. Every number came from `pure fn`. Only the advice came from the model. Swap `--mock` for `AIL_OLLAMA_MODEL=llama3.1:latest` to get real advice.

---

## Feature history (v1.8.3)

| Since | Feature |
|---|---|
| v1.0 | `fn`, `intent`, `entry`, `if`/`else`, `for`, `branch`, `context`, `import`, `evolve`, `eval_ail`, 21+ builtins, stdlib written in AIL |
| v1.1 | Result type: `ok`/`error`/`is_ok`/`unwrap`/`unwrap_or` |
| v1.2 | **Provenance**: every value carries an origin tree. `origin_of`, `has_intent_origin` |
| v1.3 | **Purity contracts**: `pure fn` statically verified — no intents, no effects, no impure calls |
| v1.4 | **`attempt` blocks**: confidence-priority cascade. First ok result wins |
| v1.5 | **Implicit parallelism**: independent intent calls run concurrently. No `async`/`await` |
| v1.6 | **Effects**: `perform http.get(url)`, `perform file.read(path)` |
| v1.7 | **`match` + confidence guards**: `"positive" with confidence > 0.9 => ...` |
| v1.8 | **Calibration**: confidence replaced by observed mean once enough samples accumulate |
| v1.8.3 | `round`/`floor`/`ceil`/`sqrt`/`pow` trusted-pure builtins; parsers accept parametric types (`List[T]`, `Map[K,V]`, `Result[T]`); `ail-coder:7b-v3` fine-tune ships |
| v1.8.4 | Bare list type annotations (`items: [Number]`, `-> [Text]`) accepted in all fn/intent signatures; stdlib builtins (`sum_list`, `unique`, etc.) trusted-pure; `ail-coder:7b-v4` dataset (260 samples) |

---

## Examples (16 programs)

| Program | What it shows | Since |
|---|---|---|
| `expense_analyzer.ail` | **The canonical example.** `pure fn` computes the numbers, `intent` writes the advice | v1.8.2 |
| `fizzbuzz.ail` | Pure fn — no LLM at all. Proof AIL is a real programming language | v1.0 |
| `review_analyzer.ail` | Hybrid pipeline: fn parses, intent judges sentiment | v1.0 |
| `evolve_retune.ail` | Self-modifying intent with version chain and rollback | v1.0 |
| `safe_csv_parser.ail` | Result-based error handling without exceptions | v1.1 |
| `audit_provenance.ail` | Labels each output field `[pure]` vs `[LLM]` | v1.2 |
| `cascade_extract.ail` | Three-tier attempt: cheap → cheaper → LLM fallback | v1.4 |
| `parallel_analysis.ail` | Three independent intents run concurrently, no async | v1.5 |
| `agent_fetch_summarize.ail` | HTTP → intent → file.write in one program | v1.6 |
| `smart_reply.ail` | Confidence-aware match: value × belief → action | v1.7 |
| `meta_codegen.ail` | AIL generates AIL at runtime via `eval_ail` | v1.0 |

---

## Repository layout

```
ail-project/
├── spec/                    # Language specification
│   ├── 00-overview.md ... 07-computation.md
│   └── 08-reference-card.ai.md  ← complete machine-readable reference
├── reference-impl/          # Python interpreter (full feature set)
│   ├── ail/                 # the ail package — published as ail-interpreter
│   │   ├── parser/          # lexer, parser, purity checker
│   │   ├── runtime/         # executor, provenance, calibration, parallelism
│   │   └── stdlib/          # standard library — written in AIL
│   ├── examples/            # 16 example programs
│   ├── tests/               # 287 tests (including cross-runtime conformance)
│   └── tools/               # benchmarks, demos
├── go-impl/                 # Second interpreter in Go (no dependencies)
├── docs/ko/                 # Korean documentation
└── RELEASING.md             # PyPI release process
```

### Implemented vs design-only

| Component | Status |
|---|---|
| AIL language (spec + interpreter) | ✅ Working |
| Standard library | ✅ Working (written in AIL) |
| Evolution (retune + rewrite) | ✅ Working |
| Anthropic / Ollama adapters | ✅ Working |
| AIRT full dispatcher | 📄 Design document |
| NOOS operating system | 📄 Design document |

---

## Why a new language instead of a Python library?

A library can recommend. A language can refuse.

1. **`evolve` blocks require `rollback_on` and `history`** — compile error if missing. A library can only suggest.
2. **`rewrite constraints` always forces human review** — even if the program forgot to declare it. A library can't override what the programmer omitted.
3. **`pure fn` cannot call intents or perform effects** — the parser rejects violations with `PurityError` before the program runs. Plain `fn` carries no such guarantee.

See [spec/07-computation.md](spec/07-computation.md) for the full comparison.

---

## Design tenets

1. AI is the author, human is the stakeholder.
2. `fn` for computation, `intent` for judgment. The AI chooses; the language supports both.
3. Probabilistic where needed, deterministic where possible. A `pure fn` result carries confidence 1.0 by construction.
4. Context is a type. Situational assumptions are declared, inherited, and traced.
5. Programs are alive. `evolve` lets them improve under declared constraints.
6. Observability is not optional. Every decision leaves a trace.
7. Humans stay in the loop for consequences. Effects require authorization; constraint rewrites require review.

---

## Go runtime

AIL is defined by its spec, not by any one implementation. A second interpreter in Go lives in `go-impl/`.

```bash
cd go-impl
go build -o ail-go .
./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15
# identical output to the Python runtime
```

The Go runtime covers the core feature set: `fn`, `intent`, `entry`, control flow, builtins, full `Result` type, and `attempt`. Provenance, purity checking, and parallelism are Python-only for now. The cross-runtime conformance suite at [`reference-impl/tests/conformance/`](reference-impl/tests/conformance/) verifies byte-identical output on every PR.

---

## Install from source (for contributors)

```bash
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl
pip install -e ".[anthropic,dev]"
pytest tests/
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Design critique is as valuable as code. [docs/open-questions.md](docs/open-questions.md) lists 15 unsolved problems.

Issues and PRs in Korean are welcome.

---

## Document naming convention

| Suffix | Audience | Example |
|---|---|---|
| `.md` | Humans (English) | `README.md`, `CONTRIBUTING.md` |
| `.ai.md` | AI/LLM systems | `README.ai.md`, `spec/08-reference-card.ai.md` |
| `.ko.md` | Korean-speaking humans | `docs/ko/README.ko.md` |

---

## Authors

**[hyun06000](https://github.com/hyun06000)** — the human author. The original vision, every architectural decision, every push to GitHub.

The code and documentation through **v1.0** were written by **Claude Opus 4** through the [claude.ai](https://claude.ai) chat interface — not Claude Code, not an API pipeline, a chatbot in a browser tab with git bundles copy-pasted back and forth. Those commits appear as `Author: Claude` through the v1.0.0 tag.

**v1.1 through v1.8.4** were built in subsequent sessions with **Claude Code** — language features (provenance, purity contracts, attempt, parallelism, effects, match, calibration, math builtins, parametric types, bare list type annotations), the Go runtime, the training pipeline, the benchmarks, and the `ail-coder:7b-v3/v4` fine-tunes.

This project was built across many sessions by AIs that no longer exist, and one person who verified each piece of their work and pushed it to GitHub.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
