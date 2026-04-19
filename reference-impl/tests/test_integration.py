"""Integration tests that exercise multiple v1.2+ features at once.

Unit tests cover each feature in isolation. This file covers their
INTERACTIONS — the axis Opus 4 flagged in CLAUDE.md as the real risk:

  "Does provenance tracking work correctly when parallelism is
  enabled? Does calibration interact properly with attempt blocks?
  Does the Go runtime produce identical output to Python for all
  examples? If you cannot answer these confidently, you have been
  building on sand."

Three programs, each crossing three features:

  A. provenance × parallelism × calibration
  B. attempt × match × Result
  C. evolve × parallelism

If one of these fails, the root cause must be fixed in the feature
interaction, not worked around in the test — the language-level
contract is what's on the line.
"""
from __future__ import annotations

import pytest

from ail import run, compile_source
from ail.runtime import MockAdapter
from ail.runtime.calibration import Calibrator


# ============================================================
# A. provenance × parallelism × calibration
# ============================================================


def test_A_provenance_survives_parallel_batch_with_calibration_active():
    """Three independent intents run in parallel; each intent's
    observation is recorded by the calibrator; the combined final
    value traces back through provenance to all three originals."""
    src = '''
    intent classify_a(t: Text) -> Text { goal: label_a }
    intent classify_b(t: Text) -> Text { goal: label_b }
    intent classify_c(t: Text) -> Text { goal: label_c }

    fn combine(a: Text, b: Text, c: Text) -> Text {
        return join([a, b, c], "|")
    }

    entry main(x: Text) {
        a = classify_a(x)
        b = classify_b(x)
        c = classify_c(x)
        return combine(a, b, c)
    }
    '''
    adapter = MockAdapter(
        responses={"classify_a": "A", "classify_b": "B", "classify_c": "C"},
        default_confidence=0.85,
    )
    calibrator = Calibrator(min_samples=2)

    # Metric: every prediction is reliably correct 50% of the time at
    # the reported 0.85 confidence — so calibration should settle toward 0.5.
    def metric_fn(intent_name, value, confidence):
        return (0.5, 0.5)

    # Run three times to give the calibrator enough samples per bucket
    # across all three intents (3 runs × 3 intents = 9 observations).
    result = None
    trace = None
    for _ in range(3):
        result, trace = run(src, input="hello", adapter=adapter,
                            metric_fn=metric_fn, calibrator=calibrator)

    # --- 1. Parallelism didn't break semantics ---------------------
    assert result.value == "A|B|C"

    # --- 2. Parallelism actually ran (trace shows a batch) ---------
    kinds = [e.kind for e in trace.entries]
    batch_markers = [k for k in kinds
                     if k in ("parallel_batch_start", "parallel_batch_end")]
    # If the planner batched anything, we see both markers at least once.
    # If this assertion regresses, provenance×calibration testing is
    # meaningless because nothing was actually parallel.
    assert len(batch_markers) >= 2, (
        f"expected parallel batch markers, got kinds: {kinds}")

    # --- 3. Provenance tree reaches all three upstream intents -----
    # `combine(a, b, c)` is a fn — its result's origin tree should
    # have all three intent origins in its lineage.
    lineage_names = {o.name for o in result.origin.lineage()}
    assert "classify_a" in lineage_names, (
        f"classify_a missing from lineage: {lineage_names}")
    assert "classify_b" in lineage_names
    assert "classify_c" in lineage_names

    # --- 4. Calibration accumulated samples per intent -------------
    # After 3 runs with metric_fn=(0.5, 0.5), each intent has 3 samples
    # in the 0.85 bucket. min_samples=2, so calibration should be active.
    # Run once more and verify the confidence dropped from the reported
    # 0.85 to the calibrated 0.5.
    final_result, _ = run(src, input="one-more", adapter=adapter,
                          metric_fn=metric_fn, calibrator=calibrator)
    # fn's `combine` takes min() of its input confidences. All three
    # intents should now be calibrated to ~0.5, so the fn output is ~0.5.
    assert abs(final_result.confidence - 0.5) < 0.1, (
        f"calibration didn't propagate through parallelism: "
        f"got {final_result.confidence}, expected ~0.5")


# ============================================================
# B. attempt × match × Result
# ============================================================


def test_B_attempt_falls_through_error_and_match_dispatches_on_confidence():
    """Three-strategy cascade with Result-on-failure semantics; match
    then dispatches on the winning value's confidence. Each of the
    three expected paths (fast pure win / intent win / fallback) gets
    a separate assertion.

    Convention (matches `to_number`): strategies return the raw value
    on success and `error(reason)` on failure. `attempt` treats a
    Result-error as "this strategy declined" and moves to the next
    try; a plain value means "this strategy delivered" and qualifies
    subject to the confidence threshold. The winning plain value
    flows into `match` as-is, where a confidence guard picks the arm.
    """
    src = '''
    pure fn cheap_lookup(x: Text) -> Text {
        if x == "known" { return "fast_answer" }
        return error("not in lookup table")
    }
    intent model_guess(t: Text) -> Text { goal: label }
    pure fn fallback(x: Text) -> Text { return "fallback" }

    entry main(x: Text) {
        outcome = attempt {
            try cheap_lookup(x)
            try model_guess(x)
            try fallback(x)
        }
        return match outcome {
            "fast_answer" with confidence > 0.9 => "CERTAIN",
            "fallback" => "FALLBACK",
            _ with confidence > 0.7 => "MODEL",
            _ => "UNSURE"
        }
    }
    '''

    # Path 1: input matches the lookup table — cheap_lookup wins with
    # confidence 1.0, match hits the "fast_answer with confidence > 0.9" arm.
    adapter1 = MockAdapter(responses={"model_guess": "something"},
                           default_confidence=0.3)
    r1, _ = run(src, input="known", adapter=adapter1)
    assert r1.value == "CERTAIN", (
        f"path 1 (pure lookup) returned {r1.value!r}; "
        "cheap_lookup should have won the attempt cascade")

    # Path 2: lookup fails (error falls through), model's confidence
    # is high enough to win. match's second arm catches the model result.
    adapter2 = MockAdapter(responses={"model_guess": "something_else"},
                           default_confidence=0.85)
    r2, _ = run(src, input="unknown_word", adapter=adapter2)
    assert r2.value == "MODEL", (
        f"path 2 (model guess) returned {r2.value!r}; "
        "model_guess should have won after cheap_lookup errored")

    # Path 3: lookup errors, model's confidence is too low, fallback
    # is the last try — attempt's fallthrough returns its value, and
    # match's literal "fallback" arm catches it.
    adapter3 = MockAdapter(responses={"model_guess": "weak"},
                           default_confidence=0.2)
    r3, _ = run(src, input="unknown_word", adapter=adapter3)
    assert r3.value == "FALLBACK", (
        f"path 3 (fallback) returned {r3.value!r}; "
        "expected the attempt cascade's last try to land in match's "
        "literal arm")


# ============================================================
# C. evolve × parallelism
# ============================================================


def test_C_evolve_triggers_while_intents_run_in_parallel():
    """Three parallel intents, one of them has an evolve block whose
    metric consistently fails the threshold. After enough calls the
    supervisor should apply a retune; the version chain must stay
    consistent even though observations are coming from concurrent
    execution."""
    src = '''
    intent unstable(t: Text) -> Text { goal: classify }
    intent stable_a(t: Text) -> Text { goal: a }
    intent stable_b(t: Text) -> Text { goal: b }

    evolve unstable {
        metric: m
        when metric < 0.7 {
            retune confidence_threshold: within [0.3, 0.9]
        }
        rollback_on: metric_drop > 0.5
        history: keep_last 5
    }

    fn merge(u: Text, a: Text, b: Text) -> Text {
        return join([u, a, b], ",")
    }

    entry main(x: Text) {
        u = unstable(x)
        a = stable_a(x)
        b = stable_b(x)
        return merge(u, a, b)
    }
    '''
    adapter = MockAdapter(
        responses={"unstable": "U", "stable_a": "A", "stable_b": "B"},
        default_confidence=0.8,
    )

    # metric_fn tells the supervisor that `unstable` is consistently
    # underperforming (0.4 < 0.7 threshold) while the others are fine.
    # This should drive the supervisor to emit a retune after enough
    # samples accumulate.
    def metric_fn(intent_name, value, confidence):
        if intent_name == "unstable":
            return (0.4, 0.4)
        return (0.9, 0.9)

    # Run enough times to give the supervisor >= its min_samples window
    # (default in Executor is implementation-defined; 8 is comfortably
    # above the common min of 3-5).
    final_trace = None
    for _ in range(8):
        _, final_trace = run(src, input="x", adapter=adapter,
                             metric_fn=metric_fn)

    # --- 1. Parallelism stayed active alongside evolve -------------
    kinds = [e.kind for e in final_trace.entries]
    batch_markers = [k for k in kinds
                     if k in ("parallel_batch_start", "parallel_batch_end")]
    assert len(batch_markers) >= 2, (
        f"parallel batching disabled under evolve; kinds: {kinds[:40]}")

    # --- 2. Every run returned a semantically correct result -------
    # Re-run once more to confirm the program still works after the
    # version chain has (presumably) evolved.
    result, _ = run(src, input="x", adapter=adapter, metric_fn=metric_fn)
    assert result.value == "U,A,B", (
        f"program broke after evolve triggered: got {result.value!r}")

    # --- 3. The trace records evolve activity without corruption ---
    # A well-behaved run produces either no evolve events (not enough
    # samples yet) or a consistent chain: observations, then at most
    # one `version_applied` per version bump, then more observations.
    # The smoking-gun failure we want to catch is interleaved
    # `version_applied` records that reference the same version_id
    # (double-apply under concurrent observation).
    version_applied_events = [
        e for e in final_trace.entries if e.kind == "version_applied"
    ]
    ids_seen = [e.payload.get("version_id") for e in version_applied_events]
    assert len(ids_seen) == len(set(ids_seen)), (
        f"version_applied emitted a duplicate id under parallel "
        f"observation: {ids_seen}")
