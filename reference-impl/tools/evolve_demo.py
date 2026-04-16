"""Demo: watch an evolving intent retune itself over many calls.

Run from reference-impl/:

    python examples/evolve_retune_demo.py

What you should see:
  - 10 calls with "good" feedback -> no evolution (confidence stays high)
  - Then 15 calls with "bad" feedback -> retune triggers, a new version
    is applied with threshold = 0.725 (midpoint of [0.5, 0.95])
  - Then 5 calls with terrible feedback -> rollback reverts to v0

This is what a production runtime would do continuously, driven by
real feedback channels. Here we drive it manually to make the mechanism
observable.
"""
from pathlib import Path

from ail_mvp import compile_source
from ail_mvp.runtime import MockAdapter
from ail_mvp.runtime.executor import Executor
from ail_mvp.runtime.model import ModelResponse


class ScriptedAdapter(MockAdapter):
    def __init__(self, value: str, confidence: float):
        super().__init__()
        self._value = value
        self._confidence = confidence

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None):
        return ModelResponse(
            value=self._value, confidence=self._confidence,
            model_id="demo", raw={},
        )


def main():
    source = (Path(__file__).parent.parent / "examples" / "evolve_retune.ail").read_text()
    program = compile_source(source)
    adapter = ScriptedAdapter(value="positive", confidence=0.92)

    # We'll vary the feedback signal across phases to drive evolution.
    feedback = {"score": 0.9}

    def metric_fn(intent_name, value, confidence):
        return (feedback["score"], feedback["score"])

    executor = Executor(program, adapter, metric_fn=metric_fn)
    sup = None  # will exist after the first call

    def phase(label, score, n):
        nonlocal sup
        feedback["score"] = score
        print(f"\n── {label}: {n} calls with feedback score = {score}")
        for _ in range(n):
            executor.run_entry({"message": "I loved it"})
        sup = executor.supervisors["classify_sentiment"]
        v = sup.active_version_id
        params = sup.active_parameters()
        print(f"   -> active version: v{v}, parameters: {params or '(none)'}")

    phase("PHASE 1 — healthy feedback", score=0.9, n=10)
    phase("PHASE 2 — feedback drops",    score=0.5, n=15)
    phase("PHASE 3 — feedback collapses", score=0.1, n=5)

    print("\n── event log ──")
    for ev in sup.events:
        print(f"  [{ev.kind}] {ev.payload}")


if __name__ == "__main__":
    main()
