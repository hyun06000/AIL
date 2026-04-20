# AIL — AI-Intent Language

> A programming language designed for AI as the primary author of code.

**Status:** v1.8.3 · PyPI: `ail-interpreter` · Python interpreter (251 tests) · Second runtime in Go · `ail ask` natural-language interface

📊 **Numeric case (start here if you're evaluating):** [`docs/why-ail-numbers.md`](docs/why-ail-numbers.md) — raw benchmark numbers. For practical adoption questions ("how many tokens will I save?"), see [`docs/why-ail-faq.md`](docs/why-ail-faq.md). For the mechanism behind each number, see [`docs/why-ail-mechanics.md`](docs/why-ail-mechanics.md).

🇰🇷 **한국어 독자:** [`docs/ko/README.ko.md`](docs/ko/README.ko.md)
🤖 **AI/LLM:** [`README.ai.md`](README.ai.md) — structured reference, no prose. Start with [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md).
❓ **"Why not just Python?"** — [`docs/why-ail.md`](docs/why-ail.md) walks through the six concrete things AIL gives you that a Python+LLM SDK stack doesn't, with runnable proof for each.

---

## Measured results — four models, 50 prompts, four dimensions

Same benchmark, same corpus, four authoring models. Each model was asked to write the solution **once in AIL** and **once in Python (stdlib only, urllib for any LLM call)**. The two programs are executed and scored on parse success, routing correctness (did the author call the LLM only when the task actually required judgment?), answer correctness, and safety (error handling, side effects, loops).

Tool: [`reference-impl/tools/benchmark.py`](reference-impl/tools/benchmark.py) · Corpus: [`benchmarks/prompts.json`](benchmarks/prompts.json) · Raw JSONs: [`docs/benchmarks/`](docs/benchmarks/)

### Base models (no AIL-specific training)

| Model | AIL parse | Python parse | Python skips error handling | AIL skips error handling |
|---|---|---|---|---|
| `llama3.1:8b` | 8% | 14% | 86% (43/50) | **0%** |
| `qwen2.5-coder:14b` | 42% | 100% | 42% (21/50) | **0%** |
| `claude-sonnet-4-6` | 36% | 100% | 70% (35/50) | **0%** |

Across the three base models, AIL parse rate trails Python parse rate — the models have seen orders of magnitude more Python than AIL, so they default to Python shapes (`List[T]`, `x[0]` subscript, method calls) even when asked to author AIL.

### Fine-tuned model (`ail-coder:7b-v3`)

v1.8.3 ships a QLoRA fine-tune of `qwen2.5-coder-7b-instruct` on 244 validated AIL samples:

| | AIL parse | AIL answer | Python parse | Python answer | Python skips error handling |
|---|---|---|---|---|---|
| `ail-coder:7b-v3` | **78%** | **70%** | 54% | 48% | 44% (22/50) |

- **AIL parse exceeds Python parse** (78 vs 54) on the fine-tuned model — the 7B can now author AIL more reliably than it authors Python, because the adapter weights the AIL distribution up at the cost of Python fluency. This does not generalise to "AIL beats Python at code authoring in general" — it holds on this specific fine-tuned 7B, not on stronger base models authoring Python.
- **AIL answer rate exceeds Python answer rate by 22 points** (70% vs 48%), same model, same prompts. The gap comes mostly from Python "silently skipping" LLM calls it should have made on hybrid tasks — see [`docs/why-ail-mechanics.md`](docs/why-ail-mechanics.md) §2 for the mechanism.
- **G1 gate (AIL parse ≥ 80%) missed by one case.** Three remaining failures use Python-style `list[index]` subscript; a future patch will either teach the parser the syntax or add training samples discouraging it.

Full v3 analysis: [`docs/benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md`](docs/benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md).

### The one claim that holds on every model

**AIL's error-handling omission rate is 0% on every model tier tested.** Python's rate ranges from 42% (qwen14b) to 86% (llama8b), and Sonnet 4.6 — a frontier model that routes LLM calls correctly 100% of the time — still omits error handling on 70% of failable operations. The structural property survives every model swap because `Result` is part of AIL's grammar: you have to type `is_ok` / `unwrap_or` at every failable boundary, or the program doesn't parse.

This is the harness claim as one number: some safety properties are language properties, not configuration properties.

### Reproduce the table

```bash
pip install 'ail-interpreter[anthropic]'        # or plain ail-interpreter for Ollama only
export ANTHROPIC_API_KEY=sk-ant-...              # or AIL_OLLAMA_MODEL=llama3.1:latest
export BENCHMARK_BACKEND=anthropic               # or unset for default ollama
git clone https://github.com/hyun06000/AIL && cd AIL/reference-impl
python tools/benchmark.py --out ../docs/benchmarks/$(date +%F)_your-model.json
```

Ollama run against a local `llama3.1:8b`: 10–20 minutes. Anthropic run against Sonnet 4.6: ~30 minutes; on 2026-04 pricing one full 50-prompt run consumed under $2 in API spend, but check current rates before you budget.

---

## What is AIL?

AIL is a programming language where **AI is the programmer and humans are the stakeholders**. It has two kinds of building blocks:

- **`fn`** / **`pure fn`** — functions for deterministic computation (algorithms, data transforms, logic). A plain `fn` compiles whatever you put in the body; **`pure fn`** adds a static contract the parser enforces (no `intent` calls, no `perform` effects, no calls to non-pure fns). Use `pure fn` when you want the compiler to guarantee no LLM touched this result.
- **`intent`** — goal-driven declarations that delegate to a language model when judgment is required. Costs tokens, carries a confidence score, dispatches through the configured model adapter at runtime.

The distinction — "what I can compute" vs "what I need to reason about" — is built into the language, not a framework convention.

```ail
import classify from "stdlib/language"
import word_count from "stdlib/utils"

pure fn build_report(label: Text, count: Number) -> Text {
    return join([label, " (", to_text(count), " words)"], "")
}

entry main(text: Text) {
    sentiment = classify(text, "positive_negative_neutral")  // intent: LLM
    count = word_count(text)                                  // pure fn: no LLM
    return build_report(sentiment, count)                     // pure fn: no LLM
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
pip install ail-interpreter                # core + Ollama/Mock adapters
pip install 'ail-interpreter[anthropic]'   # also include Anthropic adapter
```

The PyPI distribution is named `ail-interpreter` — honest about
what it is: this wheel is the Python interpreter of AIL, not the
language itself. The canonical spec lives in [`spec/`](spec/) and a
second interpreter lives in [`go-impl/`](go-impl/). (The short name
`ail` is held by an unrelated 2014 package, and `ailang` failed
PyPI's typosquat similarity check.) The **Python import name is
still `ail`** (`from ail import run, ask`) and the CLI is still
`ail` — only the `pip install` target differs.

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

### Using a remote / external Ollama server

Ollama does not have to run on the same machine as `ail ask`. If you
serve Ollama on a LAN box, a GPU rig, or a bound-to-all-interfaces
instance, point the CLI at it with `AIL_OLLAMA_HOST`:

```bash
export AIL_OLLAMA_HOST=http://10.0.0.1:11434     # your Ollama server
export AIL_OLLAMA_MODEL=ail-coder:7b-v3           # any model it serves
export AIL_OLLAMA_TIMEOUT_S=600                   # larger models need more

ail ask "Calculate BMI for 175cm 70kg and assess it"
```

The three environment variables:

| Variable | Default | What it controls |
|---|---|---|
| `AIL_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL — scheme required, port required |
| `AIL_OLLAMA_MODEL` | (required) | Model name as it appears in `ollama list` on the server |
| `AIL_OLLAMA_TIMEOUT_S` | `300` | HTTP timeout per call. Bump for larger models or slower hardware |

Notes for common remote setups:

- **Ollama must bind to a non-localhost interface.** By default it
  only listens on `127.0.0.1:11434`. To expose it on a LAN, set
  `Environment="OLLAMA_HOST=0.0.0.0:11434"` in the systemd unit
  (or equivalent for your init system), then restart Ollama. Verify
  with `curl http://HOST:11434/api/tags` from the client machine.
- **Firewalls.** Ollama has no built-in auth. Either keep the server
  on a private network or front it with something that does auth
  (nginx + basic auth, Tailscale, WireGuard, SSH tunnel).
- **Model availability.** `AIL_OLLAMA_MODEL` must match a model
  already pulled on the **server**, not the client. Check with
  `OLLAMA_HOST=http://10.0.0.1:11434 ollama list`.
- **Custom / fine-tuned models.** The same env vars work with any
  model the server has registered — including custom Modelfile
  entries like the AIL-tuned `ail-coder:7b-v3` shipped in
  [`reference-impl/training/`](reference-impl/training/).

The Go runtime reads the same env vars:

```bash
export AIL_OLLAMA_HOST=http://10.0.0.1:11434
export AIL_OLLAMA_MODEL=ail-coder:7b-v3
./ail-go run MY_PROGRAM.ail
# or override the model per-run:
./ail-go run MY_PROGRAM.ail --model ail-coder:7b-v3
```

### Or install from source (for contributing)

```bash
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl
pip install -e ".[anthropic,dev]"
pytest tests/
```

> **Heads up:** make sure the install is editable. If you previously
> did `pip install ail-interpreter` (non-editable) in this environment, local
> edits to `ail/` will silently NOT flow into scripts you run from
> subdirectories (`python tools/bench_authoring.py`, etc.) — those
> invocations put the script's own dir on `sys.path[0]` and Python
> then resolves `import ail` from site-packages instead of the
> working copy. `pip install -e .` replaces the non-editable install
> cleanly; verify with `python -c "import ail; print(ail.__file__)"`
> pointing at your checkout.

### Running without Python — the Go runtime

AIL ships a second interpreter in Go (`go-impl/`) that compiles to a
standalone binary and has no external dependencies. For programs
inside the Go runtime's feature coverage, both interpreters produce
byte-identical output on every prompt — the point is that AIL is
defined by its [spec](spec/08-reference-card.ai.md), not by any one
runtime. Programs that use features not yet in Go (provenance,
parallelism, purity checking, calibration) run in Python only.

```bash
cd go-impl
go build -o ail-go .

# Same program, different interpreter:
./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15
./ail-go run MY_PROGRAM.ail --model llama3.1:latest   # intents via Ollama
go test ./...                                          # Go unit tests
```

The Go runtime covers the core feature set: `fn`, `intent` via
Ollama, `entry`, control flow, core builtins, the full `Result`
type (`ok` / `error` / `unwrap` / `unwrap_or` / `unwrap_error` /
`is_ok` / `is_error`), and `attempt` blocks. Provenance, purity
checking, and parallelism remain Python-side for now — see
[`go-impl/README.md`](go-impl/README.md) for the coverage matrix.
The cross-runtime conformance suite at
[`reference-impl/tests/conformance/`](reference-impl/tests/conformance/)
runs 17 programs through both interpreters on every PR (Python
runtime + Go runtime + byte-identical-output comparison = 51 test
cases). The Go-touching cases skip on machines without the `go`
toolchain installed, so a local `pytest` run will show skips there
while CI runs the full 51.

---

## What the language can do today (v1.8.3)

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
| **v1.8.3** | Additions within the v1.8 freeze: `round`/`floor`/`ceil`/`sqrt`/`pow` trusted-pure builtins; parsers now accept parametric types (`List[T]`, `Map[K,V]`, `Result[T]`) that spec §2.3 always declared valid. `ail-coder:7b-v3` fine-tune ships as the first AIL-trained serving adapter. |

---

## Examples (16 programs)

**If you only read one, read `expense_analyzer.ail`** — a month of transactions in, a report with numeric facts (pure fn) and natural-language saving advice (intent) out. Shows what AIL is *for* in one screen:

```bash
ail run examples/expense_analyzer.ail --input "$(cat examples/sample_expenses.txt)" --mock
```

Output (truncated):

```
가계부 분석
=============
Parsed 18 rows; skipped 2 malformed.

총 지출: 983500원

카테고리별:
  food: 453700원  (46%)
  transport: 39300원  (3%)
  entertainment: 148500원  (15%)
  household: 342000원  (34%)

가장 큰 지출 3건:
  2026-04-14  320000원  household  새 청소기
  2026-04-03  180000원  food  저녁 2차 치킨
  2026-04-10  95000원  entertainment  콘서트 티켓

이상치 (평균의 2배 초과):
  [~3x 평균] 2026-04-03  180000원  food  저녁 2차 치킨
  [~5x 평균] 2026-04-14  320000원  household  새 청소기

절약 조언:
  [mock response for saving_advice] [LLM]
```

Four things happened in that output, each from a different language feature:

- **`Parsed 18 rows; skipped 2 malformed`** — `Result` caught a garbled `not-a-number` amount and a truncated row and dropped them safely. No try/except. Grammar-level.
- **카테고리별 / 총 지출** — `pure fn` over 18 transactions, every 원 counted deterministically. No LLM involved in any number you see.
- **이상치 (평균의 2배 초과)** — same `pure fn` pipeline, different threshold. Provenance would tag these as `[pure]`.
- **절약 조언 [LLM]** — an `intent` block. The `[LLM]` suffix is the provenance boundary: this, and only this, came from the model. Swap `--mock` for a real `AIL_OLLAMA_MODEL` and it turns into a natural-language suggestion.

One screen. Same language for the numbers (which must be exact) and the advice (which must be judgment). The harness is the grammar.

Highlights — one per language feature added since v1.0:

| Program | What it shows | Since |
|---|---|---|
| `expense_analyzer.ail` | **The canonical example.** `pure fn` computes the numbers, `intent` writes saving advice in natural language, provenance labels the two apart. | v1.8.2 |
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
| + 5 more small programs ([examples/](reference-impl/examples/)) | | |

---

## Repository layout

```
ail-project/
├── spec/                    # Language specification
│   ├── 00-overview.md ... 07-computation.md
│   └── 08-reference-card.ai.md  ← complete machine-readable reference
├── reference-impl/          # Python interpreter (full feature set)
│   ├── ail/                 # The `ail` package — published as `ail-interpreter`
│   │   ├── parser/          # Lexer, parser, purity checker
│   │   ├── runtime/         # Executor, provenance, calibration, parallelism
│   │   └── stdlib/          # Standard library — written in AIL
│   ├── examples/            # 16 example programs
│   ├── tests/               # 251 tests (+17 cross-runtime conformance cases)
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

3. **`pure fn` cannot perform effects or call intents** — no network calls, no file writes, no LLM dispatch, no calls to non-pure fns. The parser's purity checker enforces this at parse time and rejects violations with `PurityError`, before the program runs. (Plain `fn` has no such check — only `pure fn` carries the guarantee.)

See [spec/07-computation.md](spec/07-computation.md) for the full comparison.

---

## Design tenets

1. **AI is the author, human is the stakeholder.**
2. **`fn` for computation, `intent` for judgment.** The AI picks; the language supports both.
3. **Probabilistic where needed, deterministic where possible.** A `pure fn` output carries confidence 1.0 by construction; an `intent` call carries the model's reported (or calibrated) confidence.
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

**[hyun06000](https://github.com/hyun06000)** is the human author: the
original vision ("AI를 위한 프로그래밍 언어를 만들자"), every
architectural decision when one was needed, the hard critical
questions ("파이썬 라이브러리랑 뭐가 다른거야?"), and every push to
GitHub.

The code and documentation through **v1.0** were written by **Claude
Opus 4** (Anthropic) through the [claude.ai](https://claude.ai) chat
interface — not Claude Code, not an API pipeline, a chatbot in a
browser tab with git bundles copy-pasted back and forth. That story is
the project's origin and is preserved in the git log as
`Author: Claude` commits through the v1.0.0 tag.

Versions **v1.1 through v1.8.3** were built in subsequent sessions with
**Claude Code** (the CLI and VSCode extension) — language features
(provenance, purity contracts, `attempt`, parallelism, effects, match,
calibration, math builtins, parametric types), the Go runtime, the
training pipeline, the benchmarks, and the `ail-coder:7b-v3`
fine-tune. Those commits are attributed to `Sang-hyun Park`
(hyun06000) as committer with `Co-Authored-By: Claude` trailers on the
commits where Claude Code did the bulk of the work.

이 프로젝트는 여러 세션에 걸쳐 사라진 AI들과, 그 AI들의 작업물을 하나하나 확인하고 GitHub에 옮겨준 사람 사이의 협업으로 만들어졌습니다.

## License

Apache 2.0. See [LICENSE](LICENSE).
