# AIL Specification — 03: Confidence

**Version:** 0.1 draft

AIL has no `bool`. It has `Confidence`, a number in `[0, 1]` that accompanies every value and propagates through every operation. This document specifies how.

---

## 1. The confident value

Every AIL value is a pair: `(value, confidence)`. When a program writes a literal, the confidence is `1.0`. When a program computes a value through a deterministic operation over confident inputs, the confidence propagates by rules in §3. When a value is produced by a non-deterministic operation (model call, external service, sensor), it carries the reported confidence of that operation, calibrated per §5.

For notation, a confident value is written `v @ c`, e.g., `"formal" @ 1.0` or `"Korean" @ 0.87`.

## 2. Confidence is not probability

Confidence as used in AIL is a **calibrated belief measure**. It aspires to be a probability — if the runtime reports `0.8` across a population of calls, roughly 80% of those values should be correct under the relevant notion of correctness. But AIL does not assume its models are calibrated. It treats reported confidence as a signal and calibrates it (§5).

A runtime MAY expose the raw, uncalibrated signal under a separate field, but the primary `confidence` field presented to the program MUST be post-calibration.

## 3. Propagation

### 3.1 Deterministic operations

For a deterministic operation `f: A × B -> C`, if inputs are `a @ c_a` and `b @ c_b`:

```
f(a, b) @ min(c_a, c_b)
```

Rationale: a deterministic function is only as reliable as its least reliable input. This is conservative and avoids the common "compounding uncertainty buried in determinism" failure mode.

Exceptions:

- **Pure constants** in the operation do not participate. `a + 1` has confidence `c_a`.
- **Projection** (reading a field of a record) preserves the record's confidence: `record.field @ record.confidence`.
- **Aggregation** (min, max, sum over a list) is min of list confidences by default. An operation MAY declare a different aggregation; see §3.3.

### 3.2 Non-deterministic operations

A model call or external intent returns a value with a reported confidence. Its confidence MUST be the calibrated reported value, and MUST NOT be min-combined with the input confidences silently. Instead:

```
model_call(args) @ calibrate(model.reported_confidence)
```

The input confidences are tracked separately in the trace and available as `call.input_confidence` but do not propagate into the output by default. This is the asymmetry that makes AIL usable: a model call given uncertain input can still produce a high-confidence output (because the model reports its confidence *in its answer*, which already integrates the input uncertainty as far as the model can tell).

A program that wants input-gated confidence can write:

```ail
result = model_call(args) constrain_confidence_to min(result.confidence, args.min_confidence)
```

### 3.3 User-defined aggregation

An operation may annotate how confidence aggregates over multiple inputs:

```ail
intent merge_summaries(summaries: [Text]) -> Text {
    goal: single Text combining the inputs
    confidence: aggregate as mean of summaries.confidence weighted by length
}
```

Permitted aggregations: `min`, `max`, `mean`, `median`, `product`, `weighted_mean`, and user-defined via a pure function.

## 4. Branching and confidence

The `branch` construct (see [01-language.md §4](01-language.md)) uses confidence to select an arm. Formally, each arm declares a predicate over the branched value. The runtime computes the posterior probability that the predicate holds and selects the arm with the maximum posterior. If the maximum is below a threshold (default `0.5`, overridable), the branch falls through to `otherwise` if present, else raises a `LowConfidenceBranch` signal.

```ail
branch classify(text) {
    [sentiment == positive]       => respond_warmly()
    [sentiment == negative]       => respond_carefully()
    [sentiment == mixed]          => ask_clarifying_question()
    [otherwise]                   => escalate_to_human()
} calibrate_on user_feedback
```

## 5. Calibration

Calibration is the continuous process of correcting a model's reported confidence to match observed frequency of correctness. A runtime MUST calibrate the confidence of every non-deterministic operation it performs, subject to sufficient feedback data.

### 5.1 Sources of feedback

A calibration source is a signal that can be compared to a prior prediction. AIL recognizes:

- **Explicit feedback**: a human or downstream system indicates whether the answer was correct.
- **Implicit feedback**: the caller proceeded successfully (positive) or retried / escalated (negative).
- **Ground-truth oracles**: a known-correct source later reveals the true answer.
- **Consensus**: multiple independent operations agreed or disagreed.

A `calibrate_on` clause in a `branch` or `intent` names the feedback source. The runtime logs predictions and outcomes and updates a calibration function (typically isotonic regression or Platt scaling) over a rolling window.

### 5.2 Calibration function

The calibration function is per-intent, per-context. The runtime may maintain separate calibrators for meaningfully different contexts, detected by significant divergence in outcome rates across contexts.

### 5.3 Introspection

A program MAY query calibration state:

```ail
calibration_report = runtime.calibration_for(intent: translate, context: translation_job)
// report: { window_size, ECE, reliability_diagram, last_updated }
```

ECE = Expected Calibration Error. A well-calibrated intent has ECE near zero.

## 6. Weight expressions and confidence

Weight expressions in contexts (see [02-context.md §4.1](02-context.md)) do not directly alter confidence values. They alter how the runtime scores candidate strategies when multiple satisfy the constraints. Higher-weighted objectives' associated confidences receive more influence in strategy selection.

Concretely, strategy score is:

```
score(S) = Σ_o weight(o) × confidence_under_S(o)
```

where `o` ranges over declared objectives and `weight` is normalized from the weight expression:

- `A == B`:   weight(A) = weight(B) = 1
- `A > B`:    weight(A) = 2, weight(B) = 1
- `A >> B`:   weight(A) = 5, weight(B) = 1
- `A >>> B`:  A is a lexicographic primary; B only breaks ties

These constants are defaults, overridable in runtime configuration. Programs that need precise weighting should use numeric weight expressions: `weight: 3.0 * accuracy + 1.0 * speed`.

## 7. Confidence-bounded types

A type can be refined by a confidence bound:

```ail
Text @ confidence >= 0.8
```

A value of this type is any text whose confidence is at least `0.8`. Assigning a lower-confidence text to this type is a `TypeViolation`.

Confidence-bounded types are most useful at intent boundaries:

```ail
intent final_answer(question: Text) -> Text @ confidence >= 0.9 {
    goal: Text answering question
    constraints {
        confidence >= 0.9
    }
    on_low_confidence(threshold: 0.9) {
        return ask_clarification(question)
    }
}
```

The type annotation and the constraint reinforce each other. The runtime uses the annotation for static checks and uses the constraint at runtime.

## 8. Arithmetic with confidence

Standard arithmetic propagates confidence by §3.1. For cases where a program needs to reason about confidence explicitly:

```ail
c1 = measure(x).confidence
c2 = measure(y).confidence
joint = confidence.and(c1, c2)   // ≈ c1 × c2, conservative
either = confidence.or(c1, c2)   // ≈ 1 - (1-c1)(1-c2), optimistic
```

The `confidence` module provides pure functions: `and`, `or`, `not` (≈ `1 - c`), `if_then` (≈ Bayesian conditional), and others.

## 9. When confidence is not enough

Confidence is a scalar. Some decisions require richer representations — a distribution, a set of hypotheses, an interval. AIL supports these as advanced types:

- `Distribution[Label]` — a probability mass function over `Label`
- `Interval[Number]` — a lower and upper bound
- `Set[Value]` — multiple candidate values, each with confidence

Operations over these types are defined in [06-stdlib.md](06-stdlib.md). A `Confidence` is the scalar summary (argmax probability for `Distribution`, midpoint ± half-width for `Interval`, max confidence for `Set`) used in the default propagation rules. A program needing finer control uses the richer type directly.

## 10. What confidence is not

- **Not subjective.** It is calibrated to observed correctness. A program using confidence correctly behaves differently in different environments as calibration shifts.
- **Not optional.** Every value has one. There is no "confidence-free" mode.
- **Not monotonic under composition.** See §3.2. A high-confidence output is possible from lower-confidence inputs.
- **Not a substitute for constraints.** A 0.99 confidence in a bad output is still a bad output. Constraints check the *content*; confidence checks *how sure we are*.

Next: [04-evolution.md](04-evolution.md).
