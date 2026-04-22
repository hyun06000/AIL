# AIL Roadmap

No dates. This is a project with a direction, not a schedule.

---

## Current state (v1.9.0)

L1 language, L2 runtime skeleton, benchmark, fine-tune pipeline, and the first L2 layer (agentic projects) are all working.

- **Language (L1):** `fn`, `pure fn`, `intent`, `attempt`, `match`, `evolve`, `Result`, provenance, calibration, implicit parallelism, effect system, `EXPR[INDEX]` subscript sugar, `parse_json`, `ail_parse_check`. v1.8 grammar freeze in effect (see `spec/09-stability.md`).
- **Runtimes:** Python reference implementation (full feature set + agentic layer) and a Go interpreter (core feature set).
- **Fine-tune:** `ail-coder:7b-v3` (qwen2.5-coder-7b + QLoRA on 291 validated samples).
- **Benchmark:** 50-prompt corpus, AIL vs Python, HEAAL Score methodology, empirically anchored across four model families (Anthropic, Alibaba, Meta, Mistral).
- **Agentic projects (L2 v0+v1):** `ail init`, `ail up`, INTENT.md-centered project layout, file watcher + auto reload, `ail chat` (natural-language project edits), `ail up --auto-fix N` (autonomous diagnosis on test failure). 3 working example projects.
- **HEAAL claim boundary:** grammar floor lifts AIL above Python at every tier where the author model clears the AIL parse threshold (Sonnet +2.3 → qwen14b +11.3 → llama8b +30.6). Below parse threshold (mistral7b at 0% parse) the floor has nothing to lift and fine-tuning is the remedy.

Details: [`docs/benchmarks/2026-04-22_heaal_boundary_summary.md`](docs/benchmarks/2026-04-22_heaal_boundary_summary.md).

---

## Three-layer vision

- **L1 — AIL Language.** Harness is the grammar. `pure fn` / `Result` / no `while` / `evolve rollback_on`. Shipped.
- **L2 — AIRT Runtime.** Harness is the scheduler and the project structure. Intent-graph execution, agentic projects with durable ledgers, cross-session evolve state. v0+v1 shipped in v1.9.0; v2 open.
- **L3 — HEAAOS.** Harness is the kernel. Intent / context / capacity / authority as OS primitives. Reframed from the earlier "NOOS" design once the HEAAL paradigm became the north star. Design documents only; no implementation.

Design docs: [`runtime/00-airt.md`](runtime/00-airt.md), [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md), [`os/00-noos.md`](os/00-noos.md) (to be renamed to HEAAOS when L3 is started).

---

## Next steps

### 1. L2 v2 — deeper agentic capability

v0 (init/up/HTTP serve) and v1 (watcher + chat + auto-fix) close the non-developer loop. v2 sharpens what the agent can actually do — and adds the four primitives the news-dashboard case study (2026-04-23, `docs/case-studies/2026-04-23_news-dashboard.md`) showed are the binding constraint on real projects.

The first six items below come from that case study, in the priority order it implied. The remainder are pre-existing v2 ideas.

- **`perform clock.now() -> Result[Text]`** — pure-function-style time effect. Today AIL has no `now()`; authors hardcode literals like `"2024-01-15"` and the program is wrong forever. Smallest fix, highest payoff.
- **Authoring prompt surfaces `perform http.get`** — the spec already has the effect; `_authoring_examples()` doesn't demonstrate it, so models default to delegating "fetch web data" to `intent` (which hallucinates the data from training). One example pair in the few-shot set fixes this.
- **`perform schedule.every(seconds: Number) { ... }`** — declarative background polling. Unlocks the dashboard / monitor / cron-job project class. Requires a scheduler thread in the agentic runtime.
- **Cross-request state effect** on top of `.ail/state/` — `perform state.read("k")` / `perform state.write("k", v)`, process-restart-safe. Lets a long-running service accumulate references / counts / running summaries instead of recomputing from scratch every request.
- **HTML / layout output mode** — entries today must return Text; the browser UI shows it as monospace. Allow `entry main` to return rich layout (HTML, structured payload, or INTENT.md `## Layout` directives) so projects can express "left summary, right references" without leaving plain language.
- **Input-aware UI rendering** — when `entry main` does not reference its `input` parameter, the friendly UI should hide the textarea. Currently a user types "안녕" and gets back unrelated content with no signal that input was ignored.

- **Better autonomous diagnosis.** Current auto-fix hands the whole app.ail to the chat backend. v2 should isolate the failing test, propose the minimal patch, and re-run. Smaller context, faster cycle, lower cost per attempt.
- **Multi-file projects.** One `app.ail` per project today. v2 allows sub-modules / shared stdlib files for anything non-trivial.
- **`ail bundle`.** Single-binary deliverable for true double-click distribution. PyInstaller-class work.
- **Ledger viewer.** Optional web UI on a separate port showing authoring decisions, test runs, requests, evolve events. Not committed work.

### 2. HEAAL track — frontier transferability

The HEAAL claim is anchored across Sonnet (✅) and local base models (qwen14b ✅, llama8b ✅, mistral7b ✅ as boundary). Still open:

- **GPT-4o, Gemini Pro** with `anti_python`. Does the frontier-only effect reproduce across model families? ~$5 in API credits per run.
- **E1' retest** — Sonnet 4.5 with the default prompt, apples-to-apples against the anti_python score. ~$2.
- **HEAAL in a manifesto-ready form.** The paradigm, boundary, and corrected scores are in place; a public long-form pitch is not.

### 3. First external user

The project has ~0 external users. v1.9.0 makes the first-user experience meaningful (non-developer can `ail init` → edit one markdown file → `ail up`). Channels: X/Twitter demo video, GeekNews, direct outreach to AI researchers. Hyun06000's call.

---

## Future grammar candidates

Queued for the next grammar-freeze window (conditions in `spec/09-stability.md`). None are committed. Each needs a `spec/10-proposals.md` entry first.

- **Per-symbol import** — `import classify from "stdlib/language"` currently imports the whole module; should import only the named symbol.
- **Attempt + confidence threshold** — `attempt { try A with confidence > 0.8 }`. The parser reserves the syntax; the feature is not implemented.
- **Result-unwrap on error raises** — current semantics return a sentinel string and keep running; a fail-fast variant would make the agentic layer's error detection simpler.

---

## Go runtime expansion

The Go interpreter covers: `fn`, `intent`, `entry`, control flow, `Result`, and `attempt`. Features still Python-only (provenance, purity checking, parallelism, calibration, agentic projects) can be brought over once the higher priorities above are resolved.

---

## Fine-tune v4+

v3 (`ail-coder:7b-v3`) is the current serving model. v4/v5/v6 were experiments (see `docs/benchmarks/2026-04-22_r{4,5,6}_analysis.md`); v3 remains the winner. v7 has been queued twice and OOM'd twice on the 3070 — preconditions for the next attempt are documented in CLAUDE.md (`ollama stop <model>` before training + `max-seq-length=1024`).

If a future retrain happens, the primary target should be Category C (hybrid) fn/intent accuracy; v3's remaining weakness.

---

## What will NOT be done

- **No `while` loop.** Infinite loops are an AI code-generation failure mode. This decision does not change.
- **No classes / OOP / inheritance.** Outside the design scope.
- **No implicit effects.** Every effect is declared.
- **No silent evolution.** Every self-modification has a metric, bounds, and rollback.

---

## Proposing a change to this roadmap

Open an issue. Explain why the current order is wrong, what should come earlier, and what it enables that the current order does not.
