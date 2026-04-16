# AIL Roadmap

This document sketches where the project intends to go. Dates are
intentionally absent; this is an open-ended research project without a
fixed schedule.

---

## Milestone 0 — v0.1 (current)

The first public drop. Goal: make the ideas concrete enough that people
can read them, argue with them, and run a simple program.

**Shipped:**

- Full draft of the language specification (`spec/00` through `spec/06`)
- AIRT runtime design document (`runtime/00-airt.md`)
- NOOS OS design documents (`os/00` through `os/03`)
- Python reference implementation of a language subset
  - Parser for intents, contexts, effects, entries, branch, with,
    perform, on_low_confidence, evolve (parsed-only)
  - Executor with context stack, confidence propagation, branch dispatch,
    built-in `human_ask` effect
  - Anthropic and mock model adapters
  - CLI: `ail run`, `ail parse`, `ail version`
- Four example programs (hello, translate, classify, ask_human)
- 14 pytest tests covering parser and executor core

**Known limits acknowledged in this drop:**

- `evolve` blocks are parsed but not executed
- Constraints are extracted and logged but not evaluated
- No calibration loop; confidence pass-through only
- Single-strategy dispatch (delegate to model); no strategy catalog
- No ledger persistence; traces are in-memory per run
- No multi-file imports
- Parser error messages are terse

---

## Milestone 1 — v0.2 — Executing evolve

Focus: make `evolve` blocks execute in a constrained form. The goal is to
demonstrate one full cycle of observe → trigger → propose → approve →
promote → rollback.

**Work:**

- Persistent metric window storage (SQLite)
- `retune` action — the simplest evolution action
- `bounded_by` enforcement
- Rollback by metric-drop condition
- Human review request queue and approve/deny flow via CLI
- Trace inclusion of the evolution decision

**Stretch:**

- `promote strategy` action
- Per-intent version history browsing

---

## Milestone 2 — v0.3 — Strategy dispatch

Focus: move from "always delegate to the model" to "pick a strategy."

**Work:**

- Strategy registration API
- At least three strategy types: single-model-call, cached-result,
  deterministic-function
- Score-based dispatch as described in `runtime/00-airt.md §5.1`
- Observed-outcome updates to strategy score estimates
- `calibrate_on` wiring for branch arms and intent outputs

**Stretch:**

- Ensemble / consensus strategies (run multiple, take vote)

---

## Milestone 3 — v0.4 — The Authority and a real effect surface

Focus: make `perform` a gated operation, not just a dispatch.

**Work:**

- Authority process that mediates every `perform`
- Capability token format (signed, scoped, revocable)
- Two or three production-usable bridges: `file.write`, `http.post`,
  `message.send`
- Budget accounting
- Ledger persistence (SQLite, Merkle-chained)
- Local HTTP surface for authorization prompts

**Stretch:**

- Federated intent contracts between two local `airtd` instances

---

## Milestone 4 — v0.5 — The User Surface

Focus: non-developer interaction.

**Work:**

- Local web UI served by `airtd`
- Intent placement: describe in natural language, review AIL before placing
- Authorization card UX
- Ledger browser with search and attest

**Stretch:**

- Evolution review UI with diffs and sample-call display

---

## Milestone 5+ — research

Beyond v0.5, the project becomes a research agenda as much as an engineering
effort. Candidate directions, in no particular order:

- **Second runtime**: a Rust implementation of AIRT targeting a NOOS-native
  kernel.
- **Formal semantics**: a denotational semantics for AIL that supports
  program-equivalence checking.
- **Calibration theory**: better calibrators than isotonic regression for
  per-(intent, context) cells; transfer of calibration across contexts.
- **Adversarial robustness**: formal analysis of prompt-injection resistance
  given the input-taint model.
- **Multi-tenant NOOS**: actual kernel-level tenant isolation.
- **Bootstrapping**: writing AIL-authored tooling for AIL itself.

---

## What will *not* be done

To save future debate:

- **No `if` keyword.** The `branch` construct is the decision primitive.
- **No implicit effects.** Every effect is declared.
- **No silent evolution.** Every change has a metric, bounds, rollback, and
  often a human review.
- **No prompt-template DSL wrapped as AIL.** The dispatch discipline is
  structural, not textual.

These are not under-specified decisions; they are the shape of the project.

---

## How to propose a change to this roadmap

Open an issue. Explain the change, why it belongs before other milestones,
and what it enables that the current order does not.
