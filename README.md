# AIL — AI-Intent Language

🇺🇸 English · [🇰🇷 한국어](docs/ko/README.ko.md) · [🤖 AI/LLM reference](README.ai.md)

[![PyPI](https://img.shields.io/pypi/v/ail-interpreter)](https://pypi.org/project/ail-interpreter/)
[![Tests](https://github.com/hyun06000/AIL/actions/workflows/ci.yml/badge.svg)](https://github.com/hyun06000/AIL/actions)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://pypi.org/project/ail-interpreter/)

A programming language where **AI writes the code and humans just say what they want.**  
Designed from scratch for language models as the author — not humans at a keyboard.

---

## The one idea behind AIL

Every function in AIL is either a `pure fn` or an `intent`.  
That split is enforced by the parser — not a linter, not a code review, not an `AGENTS.md` file.

| | `pure fn` | `intent` |
|---|---|---|
| **What it does** | Deterministic computation | Delegates to a language model |
| **LLM calls** | Zero — the parser refuses | One per call, model-reported confidence |
| **Side effects** | Forbidden — `PurityError` at parse time | Allowed via `perform` |
| **When to use** | Parsing, arithmetic, sorting, filtering | Summarizing, classifying, translating |

```ail
pure fn word_count(s: Text) -> Number {
    return length(split(trim(s), " "))
}

intent classify_sentiment(text: Text) -> Text {
    goal: positive_negative_or_neutral
}

entry main(text: Text) {
    count = word_count(text)               // runs locally — zero LLM calls
    label = classify_sentiment(text)       // dispatches to the model
    return join([to_text(count), " words, ", label], "")
}
```

---

## What HEAAL means

AIL is the reference implementation of **HEAAL — Harness Engineering As A Language**.

Everyone else builds safety harnesses *around* Python: pre-commit hooks, `AGENTS.md` files, custom linters, retry wrappers. AIL puts the harness *inside the grammar*. Nothing to configure. Nothing to drift.

| Safety property | Python + external harness | AIL |
|---|---|---|
| No infinite loops | Linter, optional | `while` keyword doesn't exist — parser rejects |
| Error handling on failable ops | `try/except`, optional | `Result` type — required by grammar |
| No side effects in pure functions | `@pure` decorator, unenforced | `PurityError` at parse time |
| Every LLM call is explicit | Convention | `intent` keyword — the only path to a model |

> **One sentence:** Other teams configure harnesses. In AIL, the harness is the grammar.

Full manifesto by Claude Opus 4 (AIL's original designer): [`docs/heaal.md`](docs/heaal.md) · [Korean](docs/ko/heaal.ko.md) · [AI-readable](docs/heaal.ai.md)

---

## Measured results

Two questions, answered with numbers.

### Does the language produce safer code?

50 natural-language prompts. Same task. Fine-tuned 7B model writing AIL vs Python.

| Metric | AIL | Python | Δ |
|---|---|---|---|
| Answer correctness | **70%** | 48% | +22pp |
| Error-handling omission | **0%** | 12–70% | — |
| Infinite loop risk | **impossible** | present | — |

The 0% error-handling omission holds across every model tier where AIL parses at all. The grammar makes the omission impossible, not unlikely.

### Can a frontier model get those properties without fine-tuning?

Claude Sonnet writing both AIL and Python through `ail ask`, no external tooling on either side.

| Scenario | AIL HEAAL Score | Python HEAAL Score | Δ |
|---|---|---|---|
| Fine-tuned 7B (`ail-coder:7b-v3`) | **87.7** | 58.0 | +29.7 |
| Sonnet 4.6, default prompt | **77.6** | 75.3 | +2.3 |
| Sonnet 4.5, `anti_python` prompt | **96.1** | 75.9 | +20.2 |

On long tasks with real HTTP and file I/O (10 tasks, E2 benchmark): **AIL and Python tie at 9/10 tasks passed.** But every Python program omitted error handling — one crashed with an unhandled HTTP 403. AIL's `Result` type made that crash impossible.

Full dashboards: [`docs/benchmarks/dashboards/`](docs/benchmarks/dashboards/) · Raw data: [`docs/benchmarks/`](docs/benchmarks/)

---

## Quick start

### Option A — Frontier API (Anthropic, OpenAI, etc.)

```bash
pip install 'ail-interpreter[anthropic]'
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

ail ask "Count the vowels in 'Hello World'"
# 3
```

### Option B — Local model via Ollama (no API key)

```bash
ollama pull ail-coder:7b-v3        # 4.7 GB — fine-tuned on AIL, trained 2026-04-21
export AIL_OLLAMA_MODEL=ail-coder:7b-v3

ail ask "factorial of 7"
# 5040
```

### See the AIL the AI wrote

```bash
ail ask "Sum 1 to 100" --show-source
# 5050
# --- AIL ---
# pure fn sum_range(start: Number, end: Number) -> Number {
#     total = 0
#     for i in range(start, end + 1) { total = total + i }
#     return total
# }
# entry main(x: Text) { return sum_range(1, 100) }
# --- confidence=1.000 retries=0 author=anthropic/claude-sonnet-4-5-20250929 ---
```

The `author=` field shows `provider/model-id` so you can verify your environment variables routed to the model you expected.

Save the program to a file and replay it later:

```bash
ail ask "Sum 1 to 100" --save-source sum.ail
ail run sum.ail --input ""
# 5050
```

---

## From a one-shot answer to a running service

`ail ask` answers one prompt. The next step is an **agentic project** — a folder with an `INTENT.md` you write in plain language, and an HTTP service the AI authors, tests, and serves.

**1. Initialize the project**

```bash
ail init word-counter
# Initialized AIL project at ./word-counter
#   edit:  ./word-counter/INTENT.md
#   then:  ail up word-counter
```

**2. Describe what you want** — in any language, in plain text

```markdown
# word-counter

Counts words in incoming text. Empty input is an error, not a zero.

## Behavior
- Trim whitespace before counting
- Empty input → error

## Tests
- "hello world" → succeed
- "" → 에러

## Deployment
- Port 8080
```

**3. Start the service**

```bash
ail up word-counter
# ✓ AIL authored — word_count.ail
# ✓ Tests passed (2/2)
# ✓ Serving at http://127.0.0.1:8080/
```

Open `http://127.0.0.1:8080/` in a browser → text box, Send button, result area.  
Type `"the quick brown fox"` → `4`.  
Submit empty input → error message, HTTP 500.

For scripts: `curl -X POST localhost:8080/ -d "hello"` → `1`

> **Hot reload:** Edit `INTENT.md` and save while the service is running — it re-reads, re-runs your tests, and hot-swaps the program. No restart.

Everything goes into `.ail/ledger.jsonl` — every authoring decision, test run, and request, across sessions. Failed attempts land in `.ail/attempts/` so you or a future AI can see what the model tried.

Design notes: [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md) · Working examples: [`reference-impl/examples/agentic/`](reference-impl/examples/agentic/)

---

## What the language includes

| Feature | Since | What it does |
|---|---|---|
| `pure fn` / `intent` / `entry` | v1.0 | Core split — deterministic vs model-delegated |
| `Result` type | v1.0 | `ok()` / `error()` / `unwrap_or()` — errors as values |
| `with context` | v1.1 | Scoped situational assumptions for intent calls |
| Provenance tracking | v1.2 | Every value knows which fn/intent produced it |
| `pure fn` purity checker | v1.3 | Static enforcement — `PurityError` before runtime |
| `attempt` blocks | v1.4 | Try multiple strategies in confidence-priority order |
| Implicit parallelism | v1.5 | Independent `intent` calls run concurrently — no async/await |
| `perform` effects | v1.6 | `http.get`, `file.read`, `file.write`, `clock.now`, `state.*` |
| `match` with confidence guards | v1.7 | Pattern dispatch on value + confidence threshold |
| `evolve` self-modification | v1.8 | Adaptive fn rewriting with mandatory `rollback_on` |
| `parse_json` builtin | v1.8.5 | Parse HTTP response bodies — `Result[Any]` |
| `ail ask --save-source` | v1.8.6 | Save generated AIL to a file |
| Agentic projects (`ail init` / `ail up`) | v1.9.0 | L2 layer — project-level AI authorship |
| `ail chat` | v1.9.0 | Natural-language edits to a running project |
| `--auto-fix N` | v1.9.0 | Autonomous retry loop for failed authoring |
| `clock.now` / `state.*` effects | v1.9.5–v1.9.8 | Stateful and time-aware programs |
| Input-aware UI / HTML output mode | v1.9.9–v1.9.10 | Browser UI adapts to whether entry uses input / returns HTML |
| `schedule.every` effect | v1.9.12 | Recurring `entry` re-invocation — dashboards and cron-style workloads |
| `http.post` / `http.post_json` effects | v1.10+ | POST to REST APIs; `post_json` serializes body + sets Content-Type automatically |
| `http.graphql` effect | v1.15 | POST a GraphQL query — collapses HTTP status / `errors` array / `data` null into one `Result` |
| `env.read` effect | v1.14+ | Read credentials from project secrets (masked input in UI, never in source) |
| `human.approve` effect | v1.14+ | Show an approval card in the browser UI before irreversible actions |
| `search.web` effect | v1.28+ | Web search — returns JSON array of results |
| `perform log` effect | v1.43 | Stream a message to the browser run-log in real time |
| `encode_json` builtin | v1.15 | Serialize AIL value to JSON text — pure counterpart to `parse_json` |
| Browser authoring chat (`ail up`) | v1.14+ | In-browser chat replaces CLI `ail chat`; agent's memory is the chat history |
| Multi-program per project | v1.20+ | One `ail up` directory can hold multiple independent `.ail` programs |

Standard library (written in AIL, not Python): `stdlib/core`, `stdlib/language`, `stdlib/utils`

---

## How it works

```
User: "ail ask 'summarize this CSV'"
           │
           ▼
    ┌─────────────┐
    │ Author model │  writes AIL source once
    │ (Sonnet, GPT,│
    │  local 7B…) │
    └──────┬──────┘
           │ AIL source
           ▼
    ┌─────────────┐
    │   Parser +  │──── PurityError? ────► retry (≤3×) ─► Author model
    │ purity check│
    └──────┬──────┘
           │ valid AST
           ▼
    ┌─────────────┐
    │   Runtime   │◄──► Intent model (dispatched per `intent` call)
    │  executes   │
    └──────┬──────┘
           │
           ▼
         answer
```

Two models, different roles. The **author model** writes the program once. The **intent model** runs inside the program at each `intent` call. They can be the same API or different providers — the safety properties are properties of the runtime, not of which model is where.

---

## Repository map

```
AIL/
├── spec/                     # Language specification (00-overview → 08-reference-card)
├── reference-impl/           # Python interpreter — pip install ail-interpreter
│   ├── ail/                  # Parser, runtime, stdlib, agentic engine
│   │   └── agentic/          # ail init / ail up / ail chat / --auto-fix
│   ├── examples/             # Single-file .ail programs + agentic/ project demos
│   └── training/             # QLoRA fine-tune pipeline (ail-coder:7b-v3)
├── go-impl/                  # Second interpreter in Go — same spec, independent impl
├── runtime/                  # AIRT (L2) design: agentic project spec
├── docs/
│   ├── heaal.md              # HEAAL manifesto (Claude Opus 4)
│   ├── heaal/                # HEAAL experiment track — prompts, fixtures, status
│   ├── benchmarks/           # Raw JSONs, analyses, HEAAL Score dashboards
│   ├── why-ail.md            # Six concrete advantages over Python + LLM SDK
│   └── ko/                   # Korean versions of all human-facing docs
└── benchmarks/
    ├── prompts.json          # 50-prompt corpus (AIL track)
    └── heaal_e2/             # Long-task corpus — HTTP + file effects
```

---

## Is AIL for you?

**Yes, if:**
- You ship AI-generated code and "did the model handle this error?" keeps coming up
- You want safety guarantees that survive model upgrades without re-configuring a linter
- You're open to trying `ail ask` before deciding

**No, if:**
- Your codebase is already well-harnessed — you've built the external harness AIL replaces
- Your tasks are pure text summarization with no computation — call the model directly
- You need an IDE, LSP, debugger, or formatter — AIL doesn't have those yet

---

## Troubleshooting

If `ail -h` errors with `ModuleNotFoundError: No module named 'ail_mvp'`, a stale pre-v1.8 editable install is present:

```bash
pip uninstall -y ail-mvp ail-interpreter
pip install ail-interpreter
```

---

## Further reading

- [`docs/heaal.md`](docs/heaal.md) — HEAAL manifesto: paradigm pitch, Rust analogy, three layers of AI code safety
- [`docs/why-ail.md`](docs/why-ail.md) — six runnable advantages of AIL over Python + LLM SDK
- [`docs/open-questions.md`](docs/open-questions.md) — 17 unresolved design questions (good contribution starting points)
- [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md) — machine-readable spec for any AI model to learn AIL in one read

---

## Contributing

Issues and PRs welcome in **English or Korean**.  
Design critique is as valuable as code — [`docs/open-questions.md`](docs/open-questions.md) has 17 open questions.  
See [`CONTRIBUTING.md`](CONTRIBUTING.md). Apache 2.0 licensed.

---

## Authors

**[hyun06000](https://github.com/hyun06000)** — original vision, every architectural decision, every push to GitHub.

The code and documentation through **v1.0** were written by **Claude Opus 4** through the claude.ai chat interface — a chatbot in a browser tab with git bundles copy-pasted back and forth. Those commits appear as `Author: Claude` up to the `v1.0.0` tag.

**v1.1 through today** — built with **Claude Code**: language features, Go runtime, training pipeline, fine-tuned `ail-coder:7b-v3` adapter, HEAAL benchmarks, and agentic projects.

*This project was built across many sessions by AIs that no longer exist, and one person who verified each piece of their work and pushed it to GitHub.*
