# Understanding AIL Self-Modification (`evolve`)

🇰🇷 한국어: [ko/evolve-guide.ko.md](ko/evolve-guide.ko.md) · 🤖 AI/LLM: [evolve-guide.ai.md](evolve-guide.ai.md)

**Target audience:** Anyone who wants to understand how the `evolve` block works in the AIL reference implementation, and why it was designed this way.

**Prerequisites:** It helps to have read the project's general philosophy first.

---

## Why Self-Modification

An intent written once is a reasonable promise in itself. But the world changes:

- User preferences shift.
- Downstream services update.
- Models get better or worse.
- Input data distributions drift.

A static intent ends up in one of two places: **accidentally staying right**, or **quietly breaking**. Neither is desirable.

But "the program should just fix itself" is a dangerous answer, because:

- A program that **modifies itself without bound** cannot be trusted.
- **Untraceable changes** make recovery after failures impossible.
- **Unvalidated changes** can make things worse.
- **Irreversible changes** leave no escape route.

AIL's `evolve` **structurally blocks all four of these**. Self-modification is permitted, but boundaries, validation, observability, and rollback are all made mandatory at the language level.

---

## Five Required Fields

An `evolve` block **must** include all five of the following. Omitting any one is a compile error (spec/04 §2).

| Field | Meaning |
|---|---|
| `metric` | An observable value that defines success |
| `when` | The condition under which to consider modification |
| **action** (inside the when block) | What to change |
| `rollback_on` | The condition that reverts the most recent change |
| `history` | How many prior versions to retain |

Optional additions:

| Field | Meaning |
|---|---|
| `bounded_by` | Numeric boundaries the action cannot exceed |
| `require review_by` | Whether human approval is required |

---

## Minimal Example

```ail
intent classify_sentiment(text: Text) -> Text {
    goal: sentiment_label
    constraints {
        output in ["positive", "negative", "mixed", "unclear"]
    }
}

evolve classify_sentiment {
    metric: user_feedback_score(sampled: 1.0)

    when user_feedback_score < 0.7 {
        retune confidence_threshold: within [0.5, 0.95]
        bounded_by {
            confidence_threshold: [0.4, 1.0]
        }
    }

    rollback_on: user_feedback_score < 0.3

    history: keep_last 10
}
```

How to read this:

- User feedback score is the metric. It is sampled on every call and accumulated in a rolling window.
- If the window average falls **below 0.7**, modification is considered.
- The modification action **retunes** `confidence_threshold` to the midpoint of `[0.5, 0.95]`.
- But `bounded_by` ensures it never goes outside `[0.4, 1.0]`.
- If feedback falls **below 0.3** after a modification, an immediate rollback to the previous version occurs.
- Up to 10 prior versions are retained.

---

## Seeing It in Action

Run `reference-impl/tools/evolve_demo.py`:

```bash
cd reference-impl
python tools/evolve_demo.py
```

Output:

```
── PHASE 1 — healthy feedback: 10 calls with feedback score = 0.9
   -> active version: v0, parameters: (none)

── PHASE 2 — feedback drops: 15 calls with feedback score = 0.5
   -> active version: v1, parameters: {'confidence_threshold': 0.725}

── PHASE 3 — feedback collapses: 5 calls with feedback score = 0.1
   -> active version: v0, parameters: (none)

── event log ──
  [version_applied] {'version_id': 1, 'parameters': {'confidence_threshold': 0.725}, 'reason': 'metric user_feedback_score fell below threshold; retune to midpoint'}
  [rollback] {'from_version': 1, 'to_version': 0, 'trigger_value': 0.1, 'threshold': 0.3}
```

Interpretation:

- **Phase 1** — When feedback is healthy (0.9), no evolution occurs. It isn't needed.
- **Phase 2** — When feedback drops to 0.5, after 15 calls v1 is applied. The threshold is exactly **0.725**, the midpoint of `[0.5, 0.95]`.
- **Phase 3** — But feedback drops further to 0.1. `rollback_on: score < 0.3` fires, immediately reverting to v0.

---

## What the Reference Implementation Supports

- ✅ `retune` action (adjusts a numeric parameter to the declared range's midpoint)
- ✅ `rewrite constraints` action — rewrites numeric thresholds in constraint expressions by a delta
- ✅ Version chain (monotonically increasing version_id)
- ✅ `bounded_by` rejecting out-of-range proposals
- ✅ Atomic rollback when `rollback_on` fires
- ✅ Pruning old versions per `history: keep_last` (but v0 is always preserved)
- ✅ `require review_by: human` — synchronous review via `approve_review` callback
- ✅ All evolution events recorded to the trace

### `rewrite constraints` Syntax and Safety Properties

```ail
evolve classify {
    metric: score
    when score < 0.7 {
        rewrite constraints tighten_numeric_thresholds_by 0.05
    }
    rollback_on: score < 0.2
    history: keep_last 5
}
```

This action tightens all **numeric comparisons** in the intent's `constraints` block by the given delta:

- `fidelity > 0.7` → `fidelity > 0.75` (stricter lower bound)
- `latency < 2000` → `latency < 1999.95` (stricter upper bound)

**Important safety property:** `rewrite constraints` **always requires human review.** Even if the program doesn't declare `require review_by: human`, the runtime enforces it. Changing constraint expressions — even by small amounts — changes "what rules the program upholds," which is a far heavier change than retuning.

This is the decisive difference from `retune`. `retune` can be applied silently (parameters are implementation details). But `rewrite constraints` changes what the program promises to uphold, so a human must always review it.

Not yet supported (spec/04 §4):

- ❌ `rewrite examples` — rewriting the examples block
- ❌ `rewrite goal` — rewriting the goal itself (human review mandatory)
- ❌ `promote strategy` — fixing an empirically superior strategy as preferred
- ❌ `escalate` — delegating judgment to a higher authority

Runtime properties not yet supported:

- ❌ Cross-session persistence (current evolution state is only retained for the `Executor` instance's lifetime)
- ❌ Minimum sample count for `bounded_by` (MVP hardcodes 10)
- ❌ Shadow mode (the parallel observation period required by spec/04 §4.7)

---

## The Relationship Between `evolve` and Calibration (v1.8)

**Calibration** introduced in v1.8 and `evolve` **share the same `metric_fn`**, but operate at different layers. To clarify:

| | `evolve` | calibration |
|---|---|---|
| What it changes | The intent's **version** (parameters, constraints) | The intent's reported **confidence value** |
| When it operates | When metric falls below threshold and minimum samples have accumulated | Continuously, as metric observations accumulate |
| Observability | Version chain: v0, v1, v2... | Per-bucket (reported → observed) averages |
| Rollback | To previous version when `rollback_on` fires | Automatic recalculation (no separate rollback) |

A clear example of the distinction:

**evolve says:** "This intent's internal tuning is off; we need to change the parameters."
**calibration says:** "The confidence this intent reports is overconfident; adjust the numbers to match reality."

A program can use both. The `(metric, rollback)` tuple returned by `metric_fn` feeds both:
- `metric` is used as ground-truth signal for calibration, and also accumulated in evolve's sampled window.
- `rollback` is used only by evolve's rollback_on trigger.

In other words, **provide `metric_fn` once** and evolve and calibration **learn simultaneously**.

---

## Design Notes

### Metrics are injected from outside

The `evolve` block declares the metric by **name** (e.g., `metric: user_feedback_score`), but where the actual value comes from is determined by the runtime. In the reference implementation, the `metric_fn` callback plays this role:

```python
def metric_fn(intent_name, value, confidence):
    # Example: fetch score from a recent user feedback system
    return (feedback_score, rollback_signal)

executor = Executor(program, adapter, metric_fn=metric_fn)
```

Without a callback, `confidence` is used as the default metric. This is a reasonable default ("many confident answers means things are working"), but if you have an external signal correlated with real quality (A/B test results, user ratings, downstream success rates), always provide `metric_fn`.

### Minimum sample protection

The MVP does not trigger modification even when the metric average falls below threshold until **at least 10 samples** have accumulated. This is a safety guard to prevent the first one or two bad results from causing premature evolution. This value will be exposed as an option on `metric` in the future.

### Version v0 is always kept

Even if you write `history: keep_last 5`, the initial version v0 is **always** retained. The reason: in the worst case where all changes turn out badly and backtracking is needed, a baseline is required. Rollback follows the `parent_id` chain, which must eventually reach v0.

### The window resets when the version changes

When a new version is applied, the metric window resets. The reason: evaluations from the previous version are irrelevant to the new version's performance. Until the new version has been observed sufficiently, neither the next modification nor a rollback will be triggered.

---

## Related Documents

- [spec/04-evolution.md](../../spec/04-evolution.md) — formal specification
- `reference-impl/ail/runtime/evolution.py` — implementation
- `reference-impl/ail/runtime/calibration.py` — calibration implementation (v1.8)
- `reference-impl/tests/test_evolution.py` — standalone tests
- `reference-impl/tests/test_calibration.py` — calibration tests (v1.8)
- `reference-impl/tests/test_executor.py` — integration tests (evolution section)

---

## Summary

AIL's `evolve` **permits self-modification, but makes it pay a price**. Every change must be:

- **Justified by a metric**,
- **Unable to exceed declared boundaries**,
- **Paired with a revert condition**,
- **Recorded** in the history.

This is what we believe is the minimum requirement for code written by AI to be trusted in the real world.
