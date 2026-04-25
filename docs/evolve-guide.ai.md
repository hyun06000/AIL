# AIL `evolve` — for AI systems

Dense reference. Human/English: [`evolve-guide.md`](evolve-guide.md) · Korean: [`ko/evolve-guide.ko.md`](ko/evolve-guide.ko.md)

---

## What evolve is

`evolve` is AIL's bounded self-modification block. It attaches to an `intent` and specifies when and how that intent's parameters or constraints may change at runtime, subject to hard structural constraints that cannot be bypassed.

**Core guarantee:** every change is metric-justified, range-bounded, rollback-gated, and recorded. No silent unbounded mutation.

---

## Required 5 fields (all mandatory — omitting any is a compile error)

| Field | Type | Semantics |
|---|---|---|
| `metric` | metric name + sampling | Observable value defining success. Accumulated in rolling window. |
| `when <expr> { ... }` | condition + action block | Fires when window average crosses threshold AND min samples met. |
| action (inside `when`) | `retune` or `rewrite constraints` | What to change when condition fires. |
| `rollback_on: <expr>` | condition | Atomically reverts to previous version when this fires. |
| `history: keep_last N` | integer | Max versions retained. v0 **always** preserved regardless. |

Optional fields:

| Field | Semantics |
|---|---|
| `bounded_by { param: [lo, hi] }` | Hard range; proposed change outside bounds is rejected. |
| `require review_by: human` | Blocks application until human approves. **Automatically forced for `rewrite constraints`.** |

---

## Minimal structure

```ail
evolve <intent_name> {
    metric: <metric_name>(sampled: <fraction>)

    when <metric_name> < <threshold> {
        retune <param>: within [<lo>, <hi>]
        bounded_by {
            <param>: [<absolute_lo>, <absolute_hi>]
        }
    }

    rollback_on: <metric_name> < <rollback_threshold>

    history: keep_last <N>
}
```

---

## Actions

### `retune` — numeric parameter adjustment

```ail
retune confidence_threshold: within [0.5, 0.95]
```

Adjusts the named parameter to the **midpoint** of the declared range. Silent application (no human review required unless `require review_by` is declared). Parameters are implementation details — safe to change quietly.

### `rewrite constraints` — tighten numeric thresholds

```ail
rewrite constraints tighten_numeric_thresholds_by 0.05
```

Tightens all numeric comparisons in the attached intent's `constraints` block by the given delta:
- `fidelity > 0.7` becomes `fidelity > 0.75`
- `latency < 2000` becomes `latency < 1999.95`

**Safety rule: always requires human review, even without explicit `require review_by` declaration.** Constraints are the program's rules — changing them is fundamentally different from tuning parameters.

---

## rollback_on semantics

When `rollback_on` condition is true after an observation:
1. Runtime atomically reverts to the previous version (follows `parent_id` chain).
2. Metric window resets for the reverted version.
3. `[rollback]` event written to trace with `from_version`, `to_version`, `trigger_value`, `threshold`.

Rollback chain always terminates at v0 (v0 is unconditionally preserved — `keep_last` limit does not apply to v0).

---

## Calibration relationship

`evolve` and `calibration` (v1.8+) share the same `metric_fn` but operate at different layers:

| | `evolve` | calibration |
|---|---|---|
| Changes | Intent version (params, constraints) | Reported confidence value |
| Trigger | Metric below threshold + min samples | Ongoing as observations accumulate |
| Rollback | Explicit `rollback_on` condition | Automatic recalculation |

Single `metric_fn` feeds both:
```python
def metric_fn(intent_name, value, confidence) -> tuple[float, float]:
    return (metric_score, rollback_signal)
    # metric_score → evolve window + calibration ground truth
    # rollback_signal → evolve rollback_on only
```

Without `metric_fn`: `confidence` is the default metric.

---

## Safety properties — key invariants

1. **Minimum samples guard:** MVP hardcodes 10 samples before any modification triggers. Prevents premature evolution from 1-2 bad results. (Future: configurable via `metric` options.)

2. **v0 always preserved:** `history: keep_last N` applies only to versions v1+. v0 is the unconditional baseline for worst-case full rollback.

3. **Window resets on version change:** After applying a new version, the metric window empties. Previous version's performance data is irrelevant to the new version. Neither next modification nor rollback fires until new version accumulates minimum samples.

4. **`bounded_by` is a hard veto:** If `retune` proposes a value outside `bounded_by` range, the proposal is rejected. No partial application.

---

## Not yet supported (spec/04 §4)

- `rewrite examples` — rewrite the examples block
- `rewrite goal` — rewrite the goal itself (would require human review)
- `promote strategy` — lock an empirically superior strategy as preferred
- `escalate` — delegate judgment to higher authority
- Cross-session persistence (evolve state lives only for `Executor` instance lifetime)
- Shadow mode (parallel observation period before promoting new version)

---

## Trace events

All evolution events are written to the trace:

```
[version_applied] {version_id, parameters, reason}
[rollback] {from_version, to_version, trigger_value, threshold}
[bounded_by_veto] {proposed_value, bound, reason}
[review_pending] {version_id, parameters}
[review_approved] {version_id, reviewer}
```

---

## Related

- `spec/04-evolution.md` — formal specification
- `reference-impl/ail/runtime/evolution.py` — implementation
- `reference-impl/ail/runtime/calibration.py` — calibration (v1.8)
- `reference-impl/tools/evolve_demo.py` — runnable 3-phase demo
- `reference-impl/tests/test_evolution.py` — unit tests
