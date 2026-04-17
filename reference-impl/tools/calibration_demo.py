"""Demonstrate confidence calibration converging from reported to true.

Runs a tiny AIL program 30 times against a MockAdapter that always
reports 0.9 confidence. A metric_fn lies about ground truth to
illustrate the mechanism: we claim the model is only 40% right when
it says 0.9. After enough samples (5 by default) accumulate in the
0.9 band, subsequent calls see applied confidence settle around 0.4.

Output shows, per call:
  call #    reported    applied    delta
  ----------------------------------------
  1         0.900       0.900       0.000  (pre-calibration)
  ...
  6         0.900       0.400      -0.500  (calibration kicked in)
  ...

Demonstrates what `calibration_of()` looks like when accessed from
the program itself.
"""
from __future__ import annotations

import sys

from ail import run
from ail.runtime import MockAdapter
from ail.runtime.calibration import Calibrator


SRC = """
intent classify(t: Text) -> Text {
    goal: label
}
entry main(x: Text) {
    label = classify(x)
    return label
}
"""


def main() -> int:
    adapter = MockAdapter(responses={"classify": "positive"},
                          default_confidence=0.9)
    calibrator = Calibrator(min_samples=5)
    # metric_fn says "the model is actually right only 40% of the time
    # when it says 0.9". The calibrator should settle around 0.4.
    def metric_fn(intent_name, value, confidence):
        return (0.4, 0.4)

    print(f"{'call':>4}  {'reported':>10}  {'applied':>10}  {'delta':>10}")
    print("-" * 44)
    for i in range(1, 21):
        result, _ = run(SRC, input="hi", adapter=adapter,
                        metric_fn=metric_fn, calibrator=calibrator)
        applied = result.confidence
        reported = 0.9
        delta = applied - reported
        print(f"{i:>4}  {reported:>10.3f}  {applied:>10.3f}  {delta:>+10.3f}")

    print()
    print("calibration_of('classify'):")
    stats = calibrator.stats_for("classify")
    for bucket, s in stats.items():
        marker = " ← active" if s["calibrated"] else ""
        print(f"  {bucket}  count={s['count']:>3}  "
              f"mean_observed={s['mean_observed']:.3f}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
