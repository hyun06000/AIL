"""Confidence calibration — make `confidence` mean something.

Spec/03 §4 says confidence should be *calibrated*: when an intent
reports 0.9 confidence, and it turns out to be right 60% of the time,
the runtime should start reporting 0.6 when that intent says 0.9.
Until this phase confidence was model-reported pass-through; after it
confidence becomes a number that has been validated against reality.

Why no other language needs this:

Human-authored languages don't treat confidence as a runtime property.
The closest thing in a typical Python program is `score = 0.87` — just
a number the programmer wrote or a model produced. AIL's `intent`
call returns a `(value, confidence)` pair at the language level, which
is what makes recalibration from observed outcomes possible at all.
With this class, it also makes recalibration routine.

How it works:

The Calibrator buckets observations by the confidence the model
reported at the time. Once a bucket has enough samples
(`min_samples`, default 5), later invocations whose reported
confidence falls into that bucket get their confidence replaced by
the bucket's observed mean metric.

Observations arrive via the existing `metric_fn` callback — the same
one that feeds evolution. `metric_fn(intent, value, confidence)`
returns (metric, rollback). We use the metric alone here: treat it
as a success signal in [0, 1], observe it against the reported
confidence, update the bucket.

Interpretation of `metric`:
  - 1.0 = fully satisfied / correct
  - 0.0 = completely wrong
  - anything in between = partial credit

If the caller's metric is outside [0, 1], the calibrator clamps —
calibrated confidence must itself be a valid confidence.

Persistence is optional. Set `AIL_CALIBRATION_PATH` to enable
automatic load-on-init / save-on-update; otherwise the calibrator
lives in memory for the session.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


@dataclass
class BucketStats:
    """Running statistics for one reported-confidence bucket."""
    count: int = 0
    sum_metric: float = 0.0

    @property
    def mean(self) -> float:
        if self.count == 0:
            return 0.0
        return self.sum_metric / self.count

    def as_dict(self) -> dict:
        return {"count": self.count, "sum_metric": self.sum_metric}


class Calibrator:
    """Per-intent confidence calibrator.

    Thread-safe: multiple intent calls executing in parallel (v1.5)
    can observe and apply concurrently without corrupting bucket
    statistics.
    """

    def __init__(self,
                 min_samples: int = 5,
                 n_buckets: int = 10,
                 path: Optional[str | Path] = None):
        self.min_samples = min_samples
        self.n_buckets = n_buckets
        # intent_name -> bucket_index -> stats
        self._data: dict[str, dict[int, BucketStats]] = {}
        self._lock = threading.Lock()
        self.path: Optional[Path] = Path(path) if path else None
        if self.path is not None and self.path.exists():
            self._load_locked()

    # --- public API ---

    def observe(self, intent_name: str, reported_confidence: float,
                metric: float) -> None:
        """Record one observation.

        `reported_confidence` is what the model claimed at call time
        (before any calibration). `metric` is the ground-truth signal
        from metric_fn: 1.0 for fully correct, 0.0 for wrong.
        """
        m = _clamp01(metric)
        bucket = self._bucket_for(reported_confidence)
        with self._lock:
            intent_buckets = self._data.setdefault(intent_name, {})
            stats = intent_buckets.setdefault(bucket, BucketStats())
            stats.count += 1
            stats.sum_metric += m
            if self.path is not None:
                self._save_locked()

    def apply(self, intent_name: str,
              reported_confidence: float) -> tuple[float, bool]:
        """Return (calibrated_confidence, was_calibrated).

        Falls back to the reported value when the matching bucket has
        fewer than `min_samples`. `was_calibrated` lets the caller
        record the difference in the trace.
        """
        bucket = self._bucket_for(reported_confidence)
        with self._lock:
            stats = self._data.get(intent_name, {}).get(bucket)
        if stats is None or stats.count < self.min_samples:
            return reported_confidence, False
        return stats.mean, True

    def stats_for(self, intent_name: str) -> dict:
        """Introspection: current bucket table for an intent.

        Returns a dict keyed by bucket range (e.g. "0.8-0.9") whose
        values are `{count, mean_observed}`. Empty if the intent has
        not been observed yet.
        """
        with self._lock:
            buckets = dict(self._data.get(intent_name, {}))
        out: dict[str, dict] = {}
        for bucket, s in sorted(buckets.items()):
            lo = bucket / self.n_buckets
            hi = (bucket + 1) / self.n_buckets
            label = f"{lo:.1f}-{hi:.1f}"
            out[label] = {
                "count": s.count,
                "mean_observed": s.mean,
                "calibrated": s.count >= self.min_samples,
            }
        return out

    def has_data_for(self, intent_name: str) -> bool:
        with self._lock:
            return intent_name in self._data

    # --- persistence ---

    def _save_locked(self) -> None:
        """Caller holds the lock."""
        if self.path is None:
            return
        payload = {
            "min_samples": self.min_samples,
            "n_buckets": self.n_buckets,
            "intents": {
                name: {str(b): s.as_dict() for b, s in buckets.items()}
                for name, buckets in self._data.items()
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _load_locked(self) -> None:
        """Caller holds the lock. Silently tolerates malformed files —
        calibration state is advisory; corrupted data shouldn't crash
        the interpreter."""
        if self.path is None:
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        intents_raw = payload.get("intents")
        if not isinstance(intents_raw, dict):
            return
        for name, buckets in intents_raw.items():
            if not isinstance(buckets, dict):
                continue
            restored: dict[int, BucketStats] = {}
            for bstr, stats in buckets.items():
                try:
                    b = int(bstr)
                    restored[b] = BucketStats(
                        count=int(stats.get("count", 0)),
                        sum_metric=float(stats.get("sum_metric", 0.0)),
                    )
                except (TypeError, ValueError):
                    continue
            if restored:
                self._data[name] = restored

    # --- internal ---

    def _bucket_for(self, confidence: float) -> int:
        c = _clamp01(confidence)
        idx = int(c * self.n_buckets)
        if idx >= self.n_buckets:
            idx = self.n_buckets - 1
        return idx


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def default_calibrator() -> Calibrator:
    """Construct the default calibrator, honoring AIL_CALIBRATION_PATH.

    Called by the Executor when no calibrator is passed explicitly.
    """
    path = os.environ.get("AIL_CALIBRATION_PATH")
    return Calibrator(path=path)
