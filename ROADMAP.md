# AIL Roadmap

No dates. This is a project with a direction, not a schedule.

---

## Current state (v1.46.5)

L1 language, L2 runtime (v2 complete), benchmark, fine-tune pipeline all working. Field-tested in production by hyun06000.

- **Language (L1):** `fn`, `pure fn`, `intent`, `attempt`, `match`, `evolve`, `Result`, provenance, calibration, implicit parallelism, effect system, `EXPR[INDEX]` subscript sugar, `parse_json`, `encode_json`, `ail_parse_check`. v1.8 grammar freeze in effect.
- **Effect system:** `http.get`, `http.post`, `http.post_json`, `http.graphql`, `file.read`, `file.write`, `clock.now`, `state.*`, `schedule.every`, `env.read`, `human.approve`, `search.web`, `log`, `ail.run`.
- **Runtimes:** Python reference implementation (full feature set + agentic layer) and a Go interpreter (core feature set).
- **Fine-tune:** `ail-coder:7b-v3` (qwen2.5-coder-7b + QLoRA on 291 validated samples). Serving via Ollama.
- **Benchmark:** 50-prompt corpus, AIL vs Python, HEAAL Score methodology. Fine-tuned 7B: AIL 87.7 vs Python 58.0. Frontier (Sonnet anti_python): AIL 96.1 vs Python 75.9.
- **Agentic projects (L2 v2 complete):** `ail init`, `ail up`, browser-based authoring chat (agent memory = chat history), `human.approve` gates, `env.read` credential UI, live log streaming, multi-program per project, abort/reset controls. 7 working example projects.
- **Authoring architecture:** plan+execute pattern — `make_plan` intent reads service guide, `decide_step` intent returns structured HTTP call spec, main entry executes directly. Intent models never receive the authoring system prompt.
- **HEAAL claim boundary:** grammar floor lifts AIL above Python at every tier where the author model clears the AIL parse threshold (Sonnet +2.3 → qwen14b +11.3 → llama8b +30.6). Below parse threshold (mistral7b at 0% parse) the floor has nothing to lift.

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

- ✅ **`perform clock.now() -> Text`** — shipped in v1.9.5. No more hardcoded `"2024-01-15"` literals.
- ✅ **Authoring prompt surfaces `perform http.get`** — shipped in v1.9.5; verified by hyun06000's usd-now project where Sonnet picked the effect on the real exchangerate-api URL.
- **`perform schedule.every(seconds: Number) { ... }`** — declarative background polling. Unlocks the dashboard / monitor / cron-job project class. Requires a scheduler thread in the agentic runtime.
- ✅ **Cross-request state effect** — `perform state.read/write/has/delete` shipped in v1.9.8. Process-restart-safe under `.ail/state/keyval/`. Live-verified with the visit-counter example.
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

## Effect signature enforcement (runtime hardening backlog)

These are known HEAAL gaps in the effect system — places where passing a wrong argument silently fails instead of raising a clear error. Not urgent (current field failures are fixed), but each one is a hole in the harness. Open until effect signatures are formally validated at runtime.

| Gap | Observed failure | Proposed fix |
|---|---|---|
| `perform http.get(url, wrong_type)` — non-list/dict second arg silently ignored, auth header not sent | 401 on authenticated GET endpoints | Validate arg type at dispatch; raise `EffectArgError` if arg 2 is not a pair-list or dict |
| `perform http.post_json(url, text_body)` — text body refused with error message but no parse-time check | Runtime error only, not grammar error | Future: declare body type in effect signature so `pure fn` purity checker can also catch it |
| `perform http.graphql(url, q, vars, headers)` — 4th positional arg was silently ignored (fixed v1.46.4) | 403 on authenticated GraphQL | Fixed. Documented here as prior art for the pattern. |
| `perform env.read(name)` — trailing newline in stored value passes silently, causes 401 on write APIs | Auth works for GET (public), fails for POST/PUT | `trim()` in authoring prompt (v1.47.1). Ideal fix: runtime trims automatically. |

**When to close:** When the effect dispatcher validates arg count + type against a formal signature table and raises a structured error on mismatch. Not before — prompt-level guidance is a workaround, not a harness.

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
