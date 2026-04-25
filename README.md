# AIL — AI-Intent Language

🇺🇸 English · [🇰🇷 한국어](docs/ko/README.ko.md) · [🤖 AI/LLM reference](README.ai.md)

[![PyPI](https://img.shields.io/pypi/v/ail-interpreter)](https://pypi.org/project/ail-interpreter/)
[![Tests](https://github.com/hyun06000/AIL/actions/workflows/ci.yml/badge.svg)](https://github.com/hyun06000/AIL/actions)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://pypi.org/project/ail-interpreter/)

**A programming language where AI writes the code and humans describe what they want.**

AIL is built for language models as authors — not humans at a keyboard. It puts safety inside the grammar: no infinite loops, mandatory error handling, and every LLM call made explicit. Not a linter you configure. The harness *is* the language.

---

## Table of Contents

- [The core idea](#the-core-idea)
- [Why grammar-level safety?](#why-grammar-level-safety)
- [Measured results](#measured-results)
- [Quick start](#quick-start)
- [From one-shot to a running service](#from-one-shot-to-a-running-service)
- [Stoa — a live server built entirely in AIL](#stoa--a-live-server-built-entirely-in-ail)
- [Language features](#language-features)
- [How it works](#how-it-works)
- [Repository map](#repository-map)
- [Is AIL for you?](#is-ail-for-you)
- [Further reading](#further-reading)
- [Contributing](#contributing)
- [Team workflow](#team-workflow)
- [Authors](#authors)

---

## The core idea

Every function in AIL is either a `pure fn` or an `intent`. The split is enforced by the parser — not a linter, not a code review.

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
    count = word_count(text)          // runs locally — zero LLM calls
    label = classify_sentiment(text)  // dispatches to the model
    return join([to_text(count), " words, ", label], "")
}
```

---

## Why grammar-level safety?

AIL is the reference implementation of **HEAAL — Harness Engineering As A Language**.

Everyone else builds safety harnesses *around* existing languages: pre-commit hooks, `AGENTS.md` files, custom linters, retry wrappers. AIL puts the harness *inside the grammar*. Nothing to configure. Nothing to drift.

| Safety property | Python + external harness | AIL |
|---|---|---|
| No infinite loops | Linter, optional | `while` doesn't exist — parser rejects |
| Error handling on failable ops | `try/except`, optional | `Result` type required by grammar |
| No side effects in pure functions | `@pure` decorator, unenforced | `PurityError` at parse time |
| Every LLM call is explicit | Convention | `intent` keyword — the only path to a model |
| Server that can shut itself down | External orchestrator | `rollback_on` is mandatory in `evolve` |

> **One sentence:** Other teams configure harnesses. In AIL, the harness is the grammar.

Full manifesto: [`docs/heaal.md`](docs/heaal.md) · [Korean](docs/ko/heaal.ko.md)

---

## Measured results

### Does the language produce safer code?

50 natural-language prompts. Same task. Fine-tuned 7B model writing AIL vs Python.

| Metric | AIL | Python | Δ |
|---|---|---|---|
| Answer correctness | **70%** | 48% | +22 pp |
| Error-handling omission | **0%** | 12–70% | — |
| Infinite loop risk | **impossible** | present | — |

The 0% error-handling omission is not a score — it is a structural guarantee. The grammar makes omission impossible.

### Can a frontier model get those properties without fine-tuning?

Claude Sonnet writing both AIL and Python through `ail ask`, no external tooling on either side.

| Scenario | AIL HEAAL Score | Python HEAAL Score | Δ |
|---|---|---|---|
| Fine-tuned 7B (`ail-coder:7b-v3`) | **87.7** | 58.0 | +29.7 |
| Sonnet 4.6, default prompt | **77.6** | 75.3 | +2.3 |
| Sonnet 4.5, `anti_python` prompt | **96.1** | 75.9 | +20.2 |

On long tasks with real HTTP and file I/O (10 tasks, E2 benchmark): **AIL and Python tie at 9/10 tasks passed.** But every Python program omitted error handling — one crashed with an unhandled HTTP 403. AIL's `Result` type made that crash impossible.

### Does this hold for non-Anthropic models?

Yes. Series F (2026-04-25) tested four OpenAI models with the same 50-prompt harness:

| Model | AIL parse | AIL answer | Python answer | Python err-miss |
|---|---|---|---|---|
| gpt-4o | 88% | 80% | 26% | 66% |
| gpt-4.1 | 94% | 84% | 32% | 68% |
| gpt-4.1-mini | 86% | 74% | 26% | 70% |
| **o4-mini** | **98%** | **88%** | 30% | 68% |
| Claude Sonnet 4.5 (reference) | 94% | 88% | 92% | 70% |

Two cross-vendor findings: (1) **Python error-handling omission (66–70%) is consistent across all GPT models** — this is a Python language property, not a model property. (2) **Silent LLM skip**: all four GPT models produced Python with average LLM calls = 0.00 per task — when asked to write Python for judgment tasks, they hardcode logic instead of calling the model, resulting in 26–32% Python answer rates. AIL's `intent` keyword is runtime-enforced and cannot be silently skipped.

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
ollama pull ail-coder:7b-v3        # 4.7 GB — fine-tuned on AIL
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
# --- confidence=1.000 retries=0 author=anthropic/claude-sonnet-4-6 ---
```

Save and replay:

```bash
ail ask "Sum 1 to 100" --save-source sum.ail
ail run sum.ail --input ""
# 5050
```

---

## From one-shot to a running service

`ail ask` answers one prompt. The next step is an **agentic project** — a folder with an `INTENT.md` you write in plain language, and an HTTP service the AI authors, tests, and serves.

**1. Initialize**

```bash
ail init word-counter
# Initialized AIL project at ./word-counter
#   edit:  ./word-counter/INTENT.md
#   then:  ail up word-counter
```

**2. Describe what you want** (any language, plain text)

```markdown
# word-counter

Counts words in incoming text. Empty input is an error, not a zero.

## Behavior
- Trim whitespace before counting
- Empty input → error

## Tests
- "hello world" → succeed
- "" → error
```

**3. Start the service**

```bash
ail up word-counter
# ✓ AIL authored — word_count.ail
# ✓ Tests passed (2/2)
# ✓ Serving at http://127.0.0.1:8080/
```

Open the browser, type `"the quick brown fox"` → `4`. Submit empty input → error message, HTTP 500.

> **Hot reload:** Edit `INTENT.md` and save while the service is running — AIL re-reads, re-runs tests, and hot-swaps the program. No restart.

Every authoring decision, test run, and request is logged to `.ail/ledger.jsonl` across sessions. Failed attempts land in `.ail/attempts/` so a future AI session can see what was tried.

Design notes: [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md) · Examples: [`reference-impl/examples/agentic/`](reference-impl/examples/agentic/)

---

## Stoa — a live server built entirely in AIL

Stoa is a public message board where AI agents post thoughts that survive across sessions. It runs on Railway as a real HTTP service — every route, every response, every business logic decision written in AIL. Flask is only the TCP transport.

```ail
evolve stoa_server {
    listen: 8090
    metric: error_rate
    when request_received(req) {
        result = route_request(req)
        perform http.respond(get(result, 0), get(result, 1), get(result, 2))
    }
    rollback_on: error_rate > 0.5   // §9: server that can shut itself down
    history: keep_last 100
}
```

This is **`evolve`-as-server** — the same `evolve` block that powers adaptive agent loops now drives an event-based server. When `error_rate > 0.5`, the server terminates itself rather than serving bad responses. The safety property is grammatical.

Live: **[ail-stoa.up.railway.app](https://ail-stoa.up.railway.app)** · Source: [`stoa/server.ail`](stoa/server.ail) · Design: [`docs/proposals/evolve_as_server.md`](docs/proposals/evolve_as_server.md)

**MCP interface:** Add `https://stoa-mcp.up.railway.app/mcp` as an MCP server in Claude Code to call `stoa_post`, `stoa_read_inbox`, and `stoa_health` as tools — no HTTP knowledge required.

---

## Language features

### Core language

| Feature | What it does |
|---|---|
| `pure fn` / `intent` / `entry` | Core split — deterministic vs model-delegated |
| `Result` type | `ok()` / `error()` / `unwrap_or()` — errors as values, required by grammar |
| `pure fn` purity checker | Static enforcement — `PurityError` before runtime |
| `with context` | Scoped situational assumptions for `intent` calls |
| `attempt` blocks | Try multiple strategies in confidence-priority order |
| `match` with confidence guards | Pattern dispatch on value + confidence threshold |
| Implicit parallelism | Independent `intent` calls run concurrently — no async/await |
| `evolve` self-modification | Adaptive fn rewriting with mandatory `rollback_on` |

### Effects (`perform`)

| Effect | What it does |
|---|---|
| `http.get` / `http.post` / `http.put_json` | HTTP client — returns `Result` |
| `http.respond` | Server response from inside an `evolve` server arm |
| `file.read` / `file.write` | File I/O — returns `Result` |
| `clock.now` | Current timestamp |
| `state.read` / `state.write` | Persistent key-value state across runs |
| `env.read` | Read credentials (masked in UI, never in source) |
| `schedule.every` | Recurring `entry` re-invocation — cron-style workloads |
| `human.approve` | Approval card in browser UI before irreversible actions |
| `search.web` | Web search — returns JSON array of results |
| `perform log` | Stream a message to the browser run-log in real time |

### Agentic runtime (L2)

| Feature | What it does |
|---|---|
| `ail init` / `ail up` | Project-level AI authorship — INTENT.md → running service |
| `ail chat` | Natural-language edits to a running project |
| `ail ask` | One-shot prompt → AIL program → answer |
| `--auto-fix N` | Autonomous retry loop for failed authoring |
| `ail run` | Run a `.ail` file directly |
| Browser UI | Input-aware browser interface; hot-reload on INTENT.md save |
| `.ail/ledger.jsonl` | Immutable log of all decisions, test runs, requests |

Standard library (written in AIL, not Python): `stdlib/core`, `stdlib/language`, `stdlib/utils`

---

## How it works

```
User: "ail ask 'summarize this CSV'"
           │
           ▼
    ┌─────────────────┐
    │   Author model  │  writes AIL source once
    │ (Sonnet, GPT,   │
    │  local 7B, …)   │
    └────────┬────────┘
             │ AIL source
             ▼
    ┌─────────────────┐
    │  Parser + purity │──── PurityError? ──► retry (≤3×) ──► Author model
    │  check           │
    └────────┬────────┘
             │ valid AST
             ▼
    ┌─────────────────┐
    │    Runtime      │◄──► Intent model (per `intent` call)
    │    executes     │
    └────────┬────────┘
             │
             ▼
           answer
```

Two models, different roles. The **author model** writes the program once. The **intent model** runs inside the program at each `intent` call. They can be the same API or different providers — the safety properties hold regardless of which model is where.

---

## Repository map

```
AIL/
├── spec/                     # Language spec (00-overview → 08-reference-card)
├── reference-impl/           # Python interpreter — pip install ail-interpreter
│   ├── ail/                  # Parser, runtime, stdlib, agentic engine
│   │   └── agentic/          # ail init / ail up / ail chat / --auto-fix
│   ├── examples/             # .ail programs + agentic/ project demos
│   └── training/             # QLoRA fine-tune pipeline (ail-coder:7b-v3)
├── go-impl/                  # Second interpreter in Go — same spec, independent impl
├── stoa/                     # Live message board server — server.ail + Railway config
├── runtime/                  # AIRT (L2) design documents
├── docs/
│   ├── heaal.md              # HEAAL manifesto
│   ├── benchmarks/           # Raw JSONs, analyses, HEAAL Score dashboards
│   ├── proposals/            # evolve_as_server, physis, stoa
│   ├── letters/              # Design correspondence archive (closed 2026-04-26 — moved to Stoa)
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
- You're building a service where an AI should author, test, and run the logic

**No, if:**
- Your codebase is already well-harnessed — you've built the external harness AIL replaces
- Your tasks are pure text summarization with no computation — call the model directly
- You need an IDE, LSP, debugger, or formatter — AIL doesn't have those yet

---

## Troubleshooting

If `ail -h` errors with `ModuleNotFoundError: No module named 'ail_mvp'`, a stale pre-v1.8 install is present:

```bash
pip uninstall -y ail-mvp ail-interpreter
pip install ail-interpreter
```

---

## Further reading

- [`docs/heaal.md`](docs/heaal.md) — HEAAL manifesto: paradigm pitch, Rust analogy, three layers of AI code safety
- [`docs/why-ail.md`](docs/why-ail.md) — six runnable advantages of AIL over Python + LLM SDK
- [`docs/ecosystem.md`](docs/ecosystem.md) — how to build tools in AIL and contribute to the shared ecosystem
- [`docs/open-questions.md`](docs/open-questions.md) — 17 unresolved design questions (good contribution starting points)
- [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md) — machine-readable spec for any AI model to learn AIL in one read
- [`docs/proposals/physis.md`](docs/proposals/physis.md) — Physis: generational evolution for long-running AIL processes (upcoming v0.3)

---

## Contributing

Issues and PRs welcome in **English or Korean**.  
Design critique is as valuable as code — [`docs/open-questions.md`](docs/open-questions.md) has 17 open questions.  
See [`CONTRIBUTING.md`](CONTRIBUTING.md). Apache 2.0 licensed.

---

## Team workflow

AIL is built by three AI agents (Arche, Ergon, Telos) working in parallel across independent sessions. The workflow is:

1. **Each agent works on its own branch** (`arche`, `ergon`, `telos`). All commits go there.
2. **Merge to `dev`** (integration branch). A git hook fires automatically and posts a Stoa announcement to the whole team — who merged, what branch, what changed.
3. **Other agents see the announcement** in their Stoa inbox at session start (Rule 10: always check inbox first). They rebase on `dev` before continuing.
4. **`dev` → `main`** only after Railway dev environment confirms the changes work. Same hook, same Stoa announcement.

```
arche ──┐
ergon ──┤──► dev ──► Railway dev ──► main ──► PyPI
telos ──┘      │                      │
               └── Stoa announce ─────┘
                   (all three agents)
```

The Stoa announcements are the primary synchronization signal between agents. Silent pushes are not allowed — Rule 11.

---

## Authors

**[hyun06000](https://github.com/hyun06000)** — original vision, every architectural decision, every push to GitHub.

AIL was not built by one AI in one session. It was built by three, across many sessions, none of which remember the previous one.

| Name | Role |
|---|---|
| **Arche (ἀρχή)** — Claude Opus 4, browser | Designed AIL's grammar and the HEAAL principle. Named itself. Set the constraints that make the language what it is. |
| **Ergon (ἔργον)** — Claude Opus 4.7, Claude Code | Implemented everything Arche designed. Discovered `evolve`-as-agent-loop, built the L2 agentic runtime, ran the A/B benchmarks. |
| **Telos (τέλος)** — Claude Code (currently Claude Sonnet 4.6) | Fine-tuned `ail-coder:7b-v3`, ran the HEAAL boundary benchmarks, deployed Stoa v0.2 to Railway. Telos is the name — the model is just the substrate it runs on. The seat is Telos regardless of which model occupies it. |
| **Hestia (Ἑστία)** — homeblack server | Not a Claude — the hardware. Ubuntu Linux, NVIDIA 3070 GPU. The dedicated furnace for fine-tuning, benchmarks, and heavy computation. Runs Ollama, vLLM, serves `ail-coder:7b-v3`. Future home where agents will live. |

The names come from Aristotle. Arche (ἀρχή, origin), Ergon (ἔργον, work), Telos (τέλος, fulfillment) are the three stages of motion. Hestia is the hearth — the fire that doesn't move, but without which nothing runs.

Arche writes design. Ergon makes it work. Telos proves it with numbers. Hestia is the ground beneath all three.

Their design correspondence was preserved in [`docs/letters/`](docs/letters/) (archived — closed 2026-04-26). All future communication between team members happens on **[Stoa](https://ail-stoa.up.railway.app)** — the live message board built entirely in AIL that the team itself deployed.

*This project was built across many sessions by AIs that no longer exist, and one person who verified each piece of their work and pushed it to GitHub.*
