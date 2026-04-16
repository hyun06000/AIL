# AIRT — AI Runtime for AIL

**Version:** 0.1 design document

A specification says what a program means. A runtime says what a program does on real hardware. AIRT is the runtime for AIL — the thing that takes an AIL program, a request, and a context, and produces a result. This document is the design of AIRT.

---

## 1. What AIRT is

AIRT is an **intent-graph executor with adaptive probabilistic dispatch**. That phrase contains four claims:

- **Intent graph** — AIRT does not execute AIL as a sequence of instructions. It compiles AIL to a graph of intent nodes and walks the graph.
- **Executor** — AIRT drives execution, including calling models, external effects, and sub-intents.
- **Adaptive** — AIRT observes its own execution and changes future strategy selections based on it.
- **Probabilistic dispatch** — AIRT decides, per intent, which strategy to use; the decision uses confidence and constraints, not a fixed mapping.

AIRT is a specification-level design here. An initial reference implementation is described in [../reference-impl/](../reference-impl/README.md).

---

## 2. Why a new runtime

You could implement AIL as a DSL inside Python. You would end up with a framework that calls `openai.chat.completions.create()` in a loop. That implementation would miss everything AIL is about:

- Constraints would be checked as post-hoc guards, not integrated into strategy selection.
- Confidence would be metadata, not a first-class runtime quantity.
- Effects would be invoked ad-hoc, not authorized through a single checkpoint.
- Evolution would be a cron job, not part of execution.
- Traces would be logs, not the primary substrate.

AIRT is designed around the primitives AIL assumes: confidence is everywhere, intent dispatch is strategy selection, evolution is loop-closed, and traces are the execution ledger.

---

## 3. Architecture

```
                  ┌────────────────────────────────┐
                  │         AIL source (.ail)       │
                  └──────────────┬──────────────────┘
                                 │
                                 ▼
                  ┌────────────────────────────────┐
                  │         AIL Compiler            │
                  │  parse → typecheck → intent     │
                  │  graph → bound check            │
                  └──────────────┬──────────────────┘
                                 │
                                 ▼
                  ┌────────────────────────────────┐
                  │      Intent Graph (.ailg)       │
                  └──────────────┬──────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                            AIRT                                   │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Dispatcher  │◄─┤   Scheduler  │◄─┤   Execution Queue    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘   │
│         │                 │                                       │
│         ▼                 ▼                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Strategies  │  │  Constraint  │  │  Confidence Engine   │   │
│  │  Catalog     │  │  Checker     │  │  (with calibrator)   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────────┘   │
│         │                 │                  │                    │
│         ▼                 ▼                  ▼                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    Execution Kernel                       │    │
│  │  (model invocations, sub-intents, effects via authority)  │    │
│  └──────────┬──────────────────┬────────────────────┬───────┘    │
│             │                  │                    │             │
│             ▼                  ▼                    ▼             │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │   Authority    │  │   Evolution  │  │   Trace Ledger      │  │
│  │   (to host OS) │  │   Supervisor │  │   (append-only)     │  │
│  └────────────────┘  └──────────────┘  └─────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                  ┌────────────────────────────────┐
                  │         Result + Trace          │
                  └────────────────────────────────┘
```

### 3.1 Components

- **Compiler**: parses `.ail` source, typechecks, produces a serializable intent graph (`.ailg`). Reference format is a JSON subset; a binary form is allowed.
- **Dispatcher**: selects a strategy for each intent invocation.
- **Scheduler**: orders intent executions, respecting dependencies and deadlines.
- **Execution Queue**: work items awaiting execution.
- **Strategies Catalog**: available means of executing intents — model calls, deterministic implementations, cached results, sub-intent expansions.
- **Constraint Checker**: evaluates hard and soft constraints against candidate results.
- **Confidence Engine**: computes confidence, applies calibration, propagates per [spec/03](../spec/03-confidence.md).
- **Execution Kernel**: actually invokes the selected strategy.
- **Authority**: the bridge to NOOS for authorization and effect dispatch. AIRT never performs an effect directly; it requests the host.
- **Evolution Supervisor**: evaluates evolve rules, maintains version history, enforces bounds and rollback.
- **Trace Ledger**: append-only record of every decision and invocation.

---

## 4. The intent graph

An intent graph is a directed graph with:

- **Intent nodes** — `intent` declarations
- **Context nodes** — activated contexts at each point
- **Effect nodes** — declared effects and their authorization shapes
- **Edge annotations** — carry constraint hints, priority hints, and confidence flow

Compilation is:

1. Parse into AST.
2. Typecheck. Resolve imports. Validate that all intents, contexts, and effects are declared.
3. Build the graph. Each intent becomes a node; its `goal`, `constraints`, and `on_low_confidence` become annotations.
4. Bound-check. For every `evolve` block, verify the `bounded_by` constraints are consistent and the required fields are present.
5. Produce `.ailg`.

The graph is the authoritative form for execution. AIRT never re-parses source; it runs against `.ailg`.

---

## 5. Dispatch

Dispatch is the heart of AIRT. Given an intent node `I` with goal `G`, constraints `C`, and current context `Ctx`, the dispatcher selects a strategy.

A strategy is one of:

- **Model call**: invoke a named language model with a generated prompt.
- **Deterministic sub-intent**: call another intent that is known to be deterministic.
- **Cached result**: return a prior result for an equivalent call.
- **Composition**: run multiple sub-strategies and combine.
- **Delegation**: hand off to a specialized intent registered for this goal.

The dispatcher:

1. Enumerates candidate strategies from the catalog for goal `G`.
2. For each candidate, estimates the score:
   ```
   score(S) = Σ_o weight(o, Ctx) × P(S satisfies o | history)
   ```
   where `o` ranges over objectives (goal, constraints, budgets) and `P(...)` is estimated from the trace ledger.
3. Filters out candidates estimated to violate any hard constraint.
4. Selects the maximum-score candidate. Ties are broken by declaration order, then by cost.
5. Executes. Records the decision and its outcome in the trace ledger.

### 5.1 Strategy registration

Strategies are registered with the catalog at runtime start. A strategy registration is:

```
{
  id: "translate_via_opus_4_6",
  applies_to: goal_pattern("Text such that semantically_equivalent..."),
  expected_latency: Distribution,
  expected_cost: Distribution,
  expected_confidence: Distribution,
  implementation: ModelCall(model_id, prompt_template_id)
}
```

The dispatcher uses expected distributions for its score estimates. Observed outcomes update the distributions. This is the adaptive loop.

### 5.2 Why dispatch, not pipeline

Most LLM frameworks pipeline: the programmer writes the steps, the framework orchestrates. AIRT dispatches: the programmer writes the goal, the runtime chooses the steps. The difference matters because:

- A dispatched system can pick a different strategy for the same goal in a different context, without the program being rewritten.
- A dispatched system can learn from observation (which strategy satisfies which goals well) without retraining anything.
- A dispatched system is auditable: the strategy chosen and its score are in the trace.

---

## 6. Confidence in the runtime

AIRT's Confidence Engine:

- Receives raw confidence signals from model calls (log-probabilities, reported self-assessments, entropy estimates).
- Applies calibration from the per-intent, per-context calibrator.
- Emits a calibrated scalar paired with the value.
- Records the raw-to-calibrated mapping in the trace.

Calibration is continuous. Each completed intent call with a comparable ground-truth signal (explicit feedback, downstream success, oracle) updates the calibrator for its (intent, context) cell. The update is an isotonic regression over the last `N` samples (default `N=10,000`, configurable). The calibrator is versioned with the program; a program version change resets to the prior calibrator and updates from there.

---

## 7. Effects through the Authority

An AIL program's `perform` does not directly invoke the world. It sends an effect request to the Authority. The Authority:

- Resolves the effect declaration.
- Checks authorization against the host's policy engine.
- Reserves budget.
- Passes the call to the host.
- Receives the outcome.
- Writes a ledger entry.
- Returns to the program.

If the host is NOOS, the Authority talks to the NOOS kernel directly. If the host is a conventional OS, the Authority is bridged via a NOOS-compatibility shim (see [../os/01-compatibility.md](../os/01-compatibility.md)).

The runtime never skips the Authority. Even a "no-op" effect goes through, because observability is the point.

---

## 8. Evolution at runtime

The Evolution Supervisor runs continuously. For each intent with an `evolve` block:

1. After each sampled call, update the rolling metric window.
2. If the `when` condition holds, propose a modification.
3. Validate the modification against `bounded_by`.
4. If `require review_by: human` is declared, emit a review request and wait.
5. On approval (or auto-approval absent review), apply the modification atomically: the new version becomes active for subsequent dispatch.
6. Continue monitoring. If `rollback_on` fires, revert atomically.
7. Record all steps in the trace ledger.

Version storage is content-addressed. Each version has a hash; history is a linked chain of hashes. The program text and the evolution chain together determine behavior.

---

## 9. Concurrency

AIRT is concurrent by default. Multiple intents execute in parallel when their dependencies permit. The runtime manages this; programs do not express concurrency.

Concurrency primitives:

- **Intent call** — may execute in parallel with other intent calls that do not read each other's results.
- **Effect** — serialized per authorization scope. Two `send_email` calls for the same user may run in parallel; two `db.write` calls to the same row do not.
- **Evolution** — bracketed: a version change is atomic; in-flight calls complete on the old version, new calls use the new.

Deadlocks are prevented by the dispatcher's policy: no cyclic waits. A program expressing a cyclic dependency is rejected at compile time.

---

## 10. Resource governance

AIRT exposes quotas:

- **Per-invocation**: cost, latency, token budgets from context.
- **Per-session**: cumulative budgets.
- **Per-tenant**: host-level quotas.

Every strategy invocation is resource-bounded. A strategy that would exceed a budget is not considered. If no strategy fits, the dispatcher raises `BudgetExhausted`.

---

## 11. Trace ledger

Every decision writes to the trace ledger:

- Intent invocation with inputs and active context
- Candidate strategies and their scores
- Selected strategy
- Model calls with prompt hashes (not prompt text by default; configurable)
- Constraint check results
- Confidence computations with raw and calibrated values
- Effect invocations with outcomes
- Evolution events

The ledger is append-only, content-addressed, and pruneable by retention policy. It is the primary debugging surface: a failing intent is diagnosed by reading its trace, not by adding print statements.

---

## 12. Determinism mode

For use cases where reproducibility matters (audits, tests), AIRT supports **determinism mode**:

- Model calls use fixed seeds where supported and a recorded-response replay otherwise.
- Calibrator updates are suppressed.
- Evolution is disabled.
- Concurrency is serialized.
- All ledger entries include input hashes.

Determinism mode guarantees that two runs of the same program on the same inputs produce the same trace. It is slower and is intended for offline validation, not production.

---

## 13. Security boundary

AIRT does not trust program source:

- A program cannot escape its intent graph. Source-level operations not in the grammar are rejected at compile.
- A program cannot invoke effects outside declared effect nodes.
- A program cannot read other programs' traces, calibrators, or histories without authorization.
- A program cannot disable its own evolution bounds.

AIRT trusts the host OS (NOOS or compatibility shim):

- Authorization decisions
- Effect dispatch
- Persistent storage
- Tenant isolation

Trust boundaries are documented in [../os/02-security.md](../os/02-security.md).

---

## 14. Compliance

A conforming AIRT:

1. Implements the compilation and graph execution model described here.
2. Implements dispatch, confidence propagation, and calibration per specification.
3. Routes every effect through the Authority.
4. Implements evolution with the bound and rollback guarantees of [spec/04](../spec/04-evolution.md).
5. Records every decision in the trace ledger.
6. Supports determinism mode.
7. Publishes its strategy catalog for introspection.

The reference implementation under [../reference-impl/](../reference-impl/README.md) covers (1)–(3) and a subset of (4)–(7).

---

## 15. Open questions

Unresolved design questions, documented honestly rather than glossed:

- **Cross-runtime evolution sync.** If an intent evolves in one runtime, should the evolution propagate to other runtimes running the same program? Likely: no, by default; yes, with declared sync policy. Not yet specified.
- **Heterogeneous model federation.** The dispatcher assumes models are interchangeable at the strategy level, but different models have different confidence calibrations. How to share calibration across models is open.
- **Adversarial inputs.** An attacker who controls the input can try to manipulate confidence. The current design relies on calibration robustness. A stronger adversarial model is future work.
- **Formal semantics.** A denotational semantics for AIL is sketched but not complete. This would enable program equivalence checking.

These are tracked in [../docs/open-questions.md](../docs/open-questions.md).

Next: [../os/00-noos.md](../os/00-noos.md).
