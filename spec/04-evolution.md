# AIL Specification — 04: Evolution

**Version:** 0.1 draft

AIL programs can modify themselves. This is not a feature that happens to exist; it is a central design commitment. It is also the feature most likely to cause harm if done wrong. This document specifies what is permitted, what is required, and what a conforming runtime must prevent.

---

## 1. Motivation

An intent captures what a program is trying to do. Over time, the environment changes: users' preferences shift, downstream services evolve, models improve, data distributions drift. A static intent either stays correct by accident or degrades silently.

A program that is written to be improved can observe its own performance and update itself. The danger is not that a program improves; the danger is that a program modifies itself in ways that are **unbounded**, **untraceable**, **unchecked**, or **irreversible**.

AIL's evolution subsystem is designed so that every self-modification is bounded, traced, checked, and reversible.

## 2. The `evolve` block

Evolution is declared alongside an intent and attaches to it. An intent without an `evolve` block never self-modifies.

```ail
evolve translate_document {
    metric: human_preference_score(sampled: 0.05)
    baseline: record after_calls 100
    when metric < 0.75 over last 200 calls {
        rewrite constraints
        bounded_by { constraints.fidelity_floor: 0.85 }
    }
    rollback_on: metric_drop > 0.15 over last 50 calls
    history: keep_last 20
    require review_by: human @ latency < 48h
}
```

Every `evolve` block MUST contain:

- **`metric`** — a scalar, observable quantity that defines success.
- **`when`** — a condition under which modification is considered.
- **An action** — one of a small enumerated set (see §4).
- **`rollback_on`** — a condition that reverts the last modification.
- **`history`** — the number of past versions retained for rollback.

An `evolve` block missing any of these fields is a compile error.

## 3. Metrics

A metric is a named expression evaluated per-call, producing a number. Metrics may be:

- **Intrinsic**: computed by the runtime — `latency`, `cost`, `token_count`, `confidence`.
- **Intent-declared**: defined in the intent's `constraints` block and surfaced as a metric.
- **External**: produced by a feedback channel — explicit user rating, downstream success signal, A/B test arm.

Metrics MUST be:

- **Sampled** at a declared rate (`sampled: 0.05` = 5% of calls). 100% sampling is permitted but discouraged for latency reasons.
- **Bounded**: metric values outside a declared range `[min, max]` are clamped and logged.
- **Stable**: a metric whose definition changes invalidates prior history.

A metric changing its definition forces a reset of baselines and history; this is intentional.

## 4. Permitted actions

An `evolve` block's `when` clause may trigger exactly one of these actions:

### 4.1 `rewrite constraints`

Modify the intent's `constraints` block. The modification MUST remain within declared `bounded_by` limits. Fields the bound does not mention are not writable by evolution.

### 4.2 `rewrite examples`

Add, remove, or replace items in the `examples` block. New examples MUST pass static consistency checks before taking effect.

### 4.3 `rewrite goal`

The most invasive action. The goal expression may be altered. Permitted only if:

- `require review_by: human` is declared.
- A human approves the new goal before it takes effect.
- The prior goal is retained in history indefinitely (not subject to `keep_last`).

### 4.4 `promote strategy`

The runtime typically chooses among candidate strategies per call. `promote strategy` marks an empirically-superior strategy as preferred. This does not change the program's source; it changes a runtime hint. Reversible by `rollback_on`.

### 4.5 `retune`

Adjust numeric parameters (thresholds, weights, timeouts) within declared ranges. The lowest-impact and most common action.

### 4.6 `escalate`

Not a self-modification. Instead, submits the current situation to a higher authority (human reviewer, admin service, etc.) with a structured report. Used when `when` fires but the evolve block does not permit acting automatically.

**No other actions are permitted.** The language does not allow arbitrary code generation to modify an intent. Anything that cannot be expressed in terms of these actions is outside the evolution subsystem and requires explicit program replacement.

## 5. Bounds

The `bounded_by` clause declares hard limits that a modification MUST respect:

```ail
bounded_by {
    constraints.fidelity: >= 0.85
    constraints.latency: <= 3000ms
    constraints.cost: <= 0.20
}
```

A proposed modification violating any bound is rejected before application. Bounds are themselves immutable by evolution; they can only be changed by a program revision committed by a human (or by a higher-level evolution subject to its own bounds).

## 6. Rollback

Every modification creates a new version. Versions are numbered and linked: `v17` supersedes `v16`. The runtime retains the last `history.keep_last` versions.

`rollback_on` is evaluated after every sampled call. If its condition holds, the runtime atomically reverts to the immediately prior version. Rollback itself is logged. Repeated rollback within a short window triggers an escalation: the intent is frozen at a stable version until human review.

Rollback is time-bounded. A modification that has been in force for longer than `max_rollback_age` (default 30 days) is considered accepted; rollback requires a program revision instead.

## 7. Human review

`require review_by: human` forces human-in-the-loop evolution. The runtime does not apply the modification until a reviewer with the appropriate authorization approves. Review requests include:

- The current version and the proposed version (full diff)
- The triggering metric value and its history
- Sample calls where the metric fell short
- A runtime-generated "why this change is expected to help" summary

Review requests have SLA declarations. `@ latency < 48h` means: if no decision is returned within 48 hours, the modification is dropped (not applied). A runtime MUST NOT apply a pending modification past its declared SLA.

Review may also be required for specific metrics even without an explicit `require` clause. The stdlib marks certain metrics as "review-required" (e.g., metrics involving user trust or safety); touching those always forces review.

## 8. Evolution across programs

An `evolve` block applies to one intent within one program. A program that imports an intent from another source may, at import time, add its own local `evolve` rules for that intent as used within this program. The imported intent's upstream evolution is unaffected; the local evolution produces a per-program fork whose changes do not propagate back.

```ail
import translate_document from "stdlib/language"

evolve translate_document {
    metric: our_users.preference_score
    when metric < 0.7 over last 100 calls {
        retune confidence_threshold: within [0.6, 0.9]
    }
    rollback_on: metric_drop > 0.1
    history: keep_last 10
}
```

## 9. Traceability

Every version of an evolving intent records:

- The source hash of the prior version
- The triggering condition that produced the new version
- The metric values that caused the trigger
- The call samples that informed the change
- The human approver, if any
- The timestamp

This history is not user-deletable. A program whose evolution log is tampered with is rejected by the runtime on next load.

## 10. What evolution is not

- **Not reinforcement learning.** The program does not "learn" in a weights-update sense. It replaces declarative fields with other declarative fields. The reasoning about what to change *may* use a learned model, but the result is a concrete source-level edit that a human can read.
- **Not open-ended.** The action set is fixed and small. An AIL runtime that adds new actions breaks the specification.
- **Not silent.** Every change is visible.
- **Not mandatory.** An intent without `evolve` never changes. Evolution is opt-in per intent.

## 11. Safety assertions the runtime MUST uphold

A conforming AIL runtime MUST:

1. Reject any `evolve` block missing required fields.
2. Reject any proposed modification violating `bounded_by`.
3. Never apply a modification marked `require review_by: human` without recorded approval.
4. Retain complete, append-only evolution history per `history.keep_last`, plus indefinite retention of goal changes.
5. Revert atomically on `rollback_on` trigger.
6. Refuse to load a program with a corrupted evolution log.
7. Expose current version, prior versions, and pending modifications via runtime introspection.

A runtime failing any of these is non-conforming.

## 12. What evolution gives up

Evolution requires state — the history, the metrics, the calibrators. A program that relies on evolution cannot be treated as a pure artifact of its source code; its behavior depends on its operating history. This is a real cost. It is accepted because the alternative — code that cannot improve without full human rewrites in a world where its environment shifts weekly — is worse for the problems AIL is meant to solve.

For programs that must remain pure, omit `evolve`. The language is fully usable as a static language.

Next: [05-effects.md](05-effects.md).
