"""Tests for confidence calibration — making `confidence` mean something.

Until Phase 7 the confidence a program saw was whatever the model
reported. Now the calibrator tracks how often each reported-confidence
band actually corresponds to a correct answer, and replaces the
reported value with the observed mean once enough samples accumulate.

Coverage:
  - Bucket arithmetic in isolation (deterministic, no Executor needed)
  - Apply is a no-op before min_samples, then active after
  - Integration: run() with a metric_fn trains the calibrator and
    applied_confidence drops accordingly on subsequent calls
  - Persistence roundtrip (JSON file)
  - calibration_of() builtin exposes bucket stats to AIL code
"""
from __future__ import annotations

import json
from pathlib import Path

from ail import run, compile_source
from ail.runtime import MockAdapter
from ail.runtime.calibration import Calibrator


# ---------- Calibrator as a standalone class ----------


def test_calibrator_no_data_returns_reported_confidence():
    c = Calibrator(min_samples=3)
    applied, was_cal = c.apply("classify", 0.8)
    assert applied == 0.8
    assert was_cal is False


def test_calibrator_applies_once_enough_samples():
    c = Calibrator(min_samples=3)
    # Three observations in the 0.8-0.9 band, all with metric 0.4.
    for _ in range(3):
        c.observe("classify", reported_confidence=0.85, metric=0.4)
    applied, was_cal = c.apply("classify", 0.87)   # same bucket
    assert was_cal is True
    assert abs(applied - 0.4) < 1e-9


def test_calibrator_buckets_are_independent():
    # A noisy 0.9 band should not affect a clean 0.5 band.
    c = Calibrator(min_samples=2)
    c.observe("classify", 0.95, metric=0.3)
    c.observe("classify", 0.95, metric=0.3)
    c.observe("classify", 0.55, metric=0.9)
    c.observe("classify", 0.55, metric=0.9)
    a1, _ = c.apply("classify", 0.9)
    a2, _ = c.apply("classify", 0.5)
    assert abs(a1 - 0.3) < 1e-9
    assert abs(a2 - 0.9) < 1e-9


def test_calibrator_intent_scoped():
    # Different intent names get different calibration tables.
    c = Calibrator(min_samples=2)
    c.observe("strict", 0.9, metric=0.9)
    c.observe("strict", 0.9, metric=0.9)
    c.observe("loose", 0.9, metric=0.2)
    c.observe("loose", 0.9, metric=0.2)
    strict_applied, _ = c.apply("strict", 0.9)
    loose_applied, _ = c.apply("loose", 0.9)
    assert abs(strict_applied - 0.9) < 1e-9
    assert abs(loose_applied - 0.2) < 1e-9


def test_calibrator_clamps_metric_out_of_range():
    c = Calibrator(min_samples=1)
    c.observe("classify", 0.5, metric=2.5)
    applied, _ = c.apply("classify", 0.5)
    assert applied == 1.0   # clamped to max
    c.observe("classify", 0.5, metric=-0.5)  # clamped to 0.0
    # Mean of 1.0 + 0.0 = 0.5 over 2 samples
    applied, _ = c.apply("classify", 0.5)
    assert abs(applied - 0.5) < 1e-9


def test_calibrator_stats_for_report():
    c = Calibrator(min_samples=2)
    c.observe("classify", 0.85, metric=0.6)
    c.observe("classify", 0.85, metric=0.4)
    c.observe("classify", 0.15, metric=0.1)   # different bucket, one sample
    stats = c.stats_for("classify")
    assert "0.8-0.9" in stats
    assert stats["0.8-0.9"]["count"] == 2
    assert abs(stats["0.8-0.9"]["mean_observed"] - 0.5) < 1e-9
    assert stats["0.8-0.9"]["calibrated"] is True
    assert stats["0.1-0.2"]["count"] == 1
    assert stats["0.1-0.2"]["calibrated"] is False   # below min_samples


# ---------- persistence ----------


def test_calibrator_persistence_roundtrip(tmp_path):
    path = tmp_path / "cal.json"
    c1 = Calibrator(min_samples=2, path=path)
    c1.observe("classify", 0.85, metric=0.5)
    c1.observe("classify", 0.85, metric=0.7)
    assert path.exists()
    # Load into a fresh instance — state should restore.
    c2 = Calibrator(min_samples=2, path=path)
    stats = c2.stats_for("classify")
    assert stats["0.8-0.9"]["count"] == 2
    assert abs(stats["0.8-0.9"]["mean_observed"] - 0.6) < 1e-9


def test_calibrator_ignores_corrupt_persistence_file(tmp_path):
    # A malformed JSON file should not crash calibrator init.
    path = tmp_path / "bad.json"
    path.write_text("not json{{{")
    c = Calibrator(path=path)
    # New instance, empty state — shouldn't have thrown.
    assert c.stats_for("whatever") == {}


# ---------- integration with Executor ----------


def test_run_applies_calibration_after_min_samples():
    """End-to-end: run() repeatedly with a metric_fn that says the
    model is systematically wrong; applied confidence should settle
    to that observed rate.
    """
    src = '''
    intent classify(t: Text) -> Text {
        goal: label
    }
    entry main(x: Text) { return classify(x) }
    '''
    adapter = MockAdapter(responses={"classify": "positive"},
                          default_confidence=0.9)
    calibrator = Calibrator(min_samples=3)
    # metric_fn reports that the model is only right 40% of the time
    # when it says 0.9 confidence.
    def metric_fn(intent_name, value, confidence):
        return (0.4, 0.4)

    # First few calls: no calibration data yet → confidence passes through.
    last_reported_uncalibrated = []
    for _ in range(3):
        result, _ = run(src, input="x", adapter=adapter,
                        metric_fn=metric_fn, calibrator=calibrator)
        last_reported_uncalibrated.append(result.confidence)
    # All three initial results report the raw 0.9 because each call
    # contributes to the calibrator AFTER its result is returned —
    # the 3rd call also sees pre-calibration data. Only the 4th+ see
    # calibration kick in.
    assert all(abs(c - 0.9) < 1e-9 for c in last_reported_uncalibrated)

    # After 3 observations have accumulated, next call should be calibrated.
    result, _ = run(src, input="x", adapter=adapter,
                    metric_fn=metric_fn, calibrator=calibrator)
    assert abs(result.confidence - 0.4) < 1e-9


def test_run_without_metric_fn_never_calibrates():
    """With no ground-truth signal, the calibrator should stay silent."""
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    entry main(x: Text) { return classify(x) }
    '''
    adapter = MockAdapter(responses={"classify": "positive"},
                          default_confidence=0.9)
    calibrator = Calibrator(min_samples=1)
    for _ in range(5):
        result, _ = run(src, input="x", adapter=adapter,
                        calibrator=calibrator)
    # No metric_fn, no observations recorded, confidence stays 0.9.
    assert abs(result.confidence - 0.9) < 1e-9
    assert calibrator.stats_for("classify") == {}


def test_calibration_trace_records_reported_and_applied():
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    entry main(x: Text) { return classify(x) }
    '''
    adapter = MockAdapter(responses={"classify": "positive"},
                          default_confidence=0.9)
    calibrator = Calibrator(min_samples=2)
    # Train it: two observations in the 0.9 band saying metric=0.5.
    calibrator.observe("classify", 0.9, 0.5)
    calibrator.observe("classify", 0.9, 0.5)
    result, trace = run(src, input="x", adapter=adapter,
                        calibrator=calibrator)
    assert abs(result.confidence - 0.5) < 1e-9
    # Trace includes the calibration event with both numbers.
    events = [e for e in trace.entries if e.kind == "calibration_applied"]
    assert len(events) == 1
    assert events[0].payload["intent"] == "classify"
    assert abs(events[0].payload["reported"] - 0.9) < 1e-9
    assert abs(events[0].payload["calibrated"] - 0.5) < 1e-9


# ---------- calibration_of builtin ----------


def test_calibration_of_builtin_returns_stats():
    # Program queries its own calibration data.
    src = '''
    intent classify(t: Text) -> Text { goal: label }
    entry main(x: Text) {
        stats = calibration_of("classify")
        return stats
    }
    '''
    adapter = MockAdapter(responses={"classify": "positive"},
                          default_confidence=0.85)
    calibrator = Calibrator(min_samples=2)
    calibrator.observe("classify", 0.85, 0.6)
    calibrator.observe("classify", 0.85, 0.8)
    result, _ = run(src, input="x", adapter=adapter,
                    calibrator=calibrator)
    assert "0.8-0.9" in result.value
    assert result.value["0.8-0.9"]["count"] == 2
    assert abs(result.value["0.8-0.9"]["mean_observed"] - 0.7) < 1e-9
    assert result.value["0.8-0.9"]["calibrated"] is True


def test_calibration_of_unknown_intent_returns_empty():
    src = '''
    entry main(x: Text) { return calibration_of("never_seen") }
    '''
    result, _ = run(src, input="x", adapter=MockAdapter(),
                    calibrator=Calibrator())
    assert result.value == {}


# ---------- interaction with low_confidence_handler ----------


def test_low_confidence_handler_fires_on_calibrated_value():
    """The handler threshold is checked against the CALIBRATED
    confidence, not the raw reported one. This is the more useful
    semantic: the handler exists to trigger when belief is low, and
    the calibrated value is closer to truth.
    """
    src = '''
    intent classify(t: Text) -> Text {
        goal: label
        on_low_confidence(threshold: 0.5) {
            return "FALLBACK"
        }
    }
    entry main(x: Text) { return classify(x) }
    '''
    adapter = MockAdapter(responses={"classify": "positive"},
                          default_confidence=0.9)
    calibrator = Calibrator(min_samples=2)
    # Teach the calibrator: 0.9 really means 0.3.
    calibrator.observe("classify", 0.9, 0.3)
    calibrator.observe("classify", 0.9, 0.3)
    result, trace = run(src, input="x", adapter=adapter,
                        calibrator=calibrator)
    # Raw 0.9 would have skipped the handler; calibrated 0.3 fires it.
    assert result.value == "FALLBACK"
    handler_events = [e for e in trace.entries
                      if e.kind == "low_confidence_handler"]
    assert len(handler_events) == 1
    assert abs(handler_events[0].payload["actual"] - 0.3) < 1e-9
    assert abs(handler_events[0].payload["reported"] - 0.9) < 1e-9
