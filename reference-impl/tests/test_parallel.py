"""Tests for implicit parallelism.

Consecutive Assignments whose RHS contain intent calls and are pairwise
independent are grouped into parallel batches and evaluated
concurrently via a ThreadPoolExecutor. The AI author writes sequential
code; the runtime parallelizes the expensive (intent) parts by default.

These tests cover:
  - Static planning: the plan_groups() analysis correctly identifies
    which assignment sequences are safe to batch.
  - Dynamic execution: parallel batches produce the same results as
    sequential execution, with values committed to scope in source order.
  - Wall-clock speedup: when intent calls have measurable latency, a
    parallel batch finishes in ~1x the time of a single call rather than
    Nx sequentially.
"""
from __future__ import annotations

import time
import threading

from ail import run, compile_source
from ail.runtime import MockAdapter
from ail.runtime.parallel import plan_groups
from ail.parser.ast import (
    Assignment, Call, Identifier, Literal, BinaryOp,
)


# ---------- static planning ----------


def test_plan_groups_empty():
    assert plan_groups([], intents=set()) == []


def test_plan_groups_no_intent_calls_all_serial():
    # a = foo(); b = bar();  —  neither calls an intent → all serial
    stmts = [
        Assignment("a", Call(Identifier("foo"), [], {})),
        Assignment("b", Call(Identifier("bar"), [], {})),
    ]
    groups = plan_groups(stmts, intents=set())
    assert all(not g.parallel for g in groups)


def test_plan_groups_independent_intent_calls_batched():
    # a = classify(x); b = extract(x);  —  both intents, independent
    stmts = [
        Assignment("a", Call(Identifier("classify"), [Identifier("x")], {})),
        Assignment("b", Call(Identifier("extract"), [Identifier("x")], {})),
    ]
    groups = plan_groups(stmts, intents={"classify", "extract"})
    assert len(groups) == 1
    assert groups[0].parallel is True
    assert len(groups[0].stmts) == 2


def test_plan_groups_dependent_intent_calls_NOT_batched():
    # a = classify(x); b = extract(a);  —  b reads a's LHS → serial
    stmts = [
        Assignment("a", Call(Identifier("classify"), [Identifier("x")], {})),
        Assignment("b", Call(Identifier("extract"), [Identifier("a")], {})),
    ]
    groups = plan_groups(stmts, intents={"classify", "extract"})
    # Both end up in their own single-stmt serial groups.
    assert all(not g.parallel for g in groups)
    assert len(groups) == 2


def test_plan_groups_mixed_assignment_breaks_batch():
    # a = classify(x); b = pure_fn(x); c = extract(x);
    # The middle statement has no intent call — it's not worth batching.
    # a and c are independent but b splits them.
    stmts = [
        Assignment("a", Call(Identifier("classify"), [Identifier("x")], {})),
        Assignment("b", Call(Identifier("pure_fn"), [Identifier("x")], {})),
        Assignment("c", Call(Identifier("extract"), [Identifier("x")], {})),
    ]
    groups = plan_groups(stmts, intents={"classify", "extract"})
    assert len(groups) == 3
    assert all(not g.parallel for g in groups)


def test_plan_groups_three_independent_intents_batched():
    stmts = [
        Assignment("a", Call(Identifier("ia"), [Identifier("x")], {})),
        Assignment("b", Call(Identifier("ib"), [Identifier("x")], {})),
        Assignment("c", Call(Identifier("ic"), [Identifier("x")], {})),
    ]
    groups = plan_groups(stmts, intents={"ia", "ib", "ic"})
    assert len(groups) == 1
    assert groups[0].parallel is True
    assert len(groups[0].stmts) == 3


def test_plan_groups_same_lhs_not_batched():
    # Two assignments to the same name cannot parallelize; the second
    # would depend on the ordering of the first.
    stmts = [
        Assignment("x", Call(Identifier("ia"), [], {})),
        Assignment("x", Call(Identifier("ib"), [], {})),
    ]
    groups = plan_groups(stmts, intents={"ia", "ib"})
    assert all(not g.parallel for g in groups)
    assert len(groups) == 2


# ---------- dynamic execution: correctness ----------


def test_parallel_batch_produces_same_values_as_serial():
    src = """
    intent ia(x: Text) -> Text { goal: label a }
    intent ib(x: Text) -> Text { goal: label b }
    intent ic(x: Text) -> Text { goal: label c }
    fn combine(a: Text, b: Text, c: Text) -> Text {
        return join([a, b, c], ",")
    }
    entry main(x: Text) {
        a = ia(x)
        b = ib(x)
        c = ic(x)
        return combine(a, b, c)
    }
    """
    adapter = MockAdapter(responses={"ia": "A", "ib": "B", "ic": "C"})
    result, trace = run(src, input="hello", adapter=adapter)
    assert result.value == "A,B,C"
    # Confirm parallel batch actually ran — trace has the marker.
    kinds = [e.kind for e in trace.entries]
    assert "parallel_batch_start" in kinds
    assert "parallel_batch_end" in kinds


def test_parallel_batch_preserves_origins_per_assignment():
    src = """
    intent ia(x: Text) -> Text { goal: ga }
    intent ib(x: Text) -> Text { goal: gb }
    fn pair(a: Text, b: Text) -> Text { return join([a, b], "|") }
    entry main(x: Text) {
        a = ia(x)
        b = ib(x)
        return pair(a, b)
    }
    """
    adapter = MockAdapter(responses={"ia": "A", "ib": "B"})
    result, _ = run(src, input="hello", adapter=adapter)
    # The return flows through `pair`, which is a fn; origins of its
    # args trace back to the two intents. The merged result's origin
    # tree must contain both.
    kinds_in_lineage = {o.kind for o in result.origin.lineage()}
    assert "intent" in kinds_in_lineage
    assert "fn" in kinds_in_lineage


def test_dependent_assignments_execute_sequentially():
    # Verify the planner's dependency detection: b = ib(a) MUST see a's
    # committed value, not an uninitialized snapshot.
    src = """
    intent ia(x: Text) -> Text { goal: ga }
    intent ib(x: Text) -> Text { goal: gb }
    entry main(x: Text) {
        a = ia(x)
        b = ib(a)
        return b
    }
    """
    responses = {"ia": "from_a", "ib": "from_b"}
    adapter = MockAdapter(responses=responses)
    result, trace = run(src, input="hello", adapter=adapter)
    # Both intents invoked; ordering must be serial (a first, then b).
    intent_calls = [e for e in trace.entries if e.kind == "intent_call"]
    assert len(intent_calls) == 2
    assert intent_calls[0].payload["name"] == "ia"
    assert intent_calls[1].payload["name"] == "ib"


# ---------- wall-clock speedup (integration-style) ----------


class _SlowAdapter:
    """Adapter that sleeps per invocation. Used to detect whether
    multiple invocations overlap in wall-clock time.
    """
    name = "slow"

    def __init__(self, delay_s: float, responses: dict):
        self.delay_s = delay_s
        self.responses = responses
        self.concurrent_high_water = 0
        self._active = 0
        self._lock = threading.Lock()

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None):
        with self._lock:
            self._active += 1
            if self._active > self.concurrent_high_water:
                self.concurrent_high_water = self._active
        time.sleep(self.delay_s)
        with self._lock:
            self._active -= 1
        from ail.runtime.model import ModelResponse
        intent_name = context.get("_intent_name", "unknown")
        return ModelResponse(
            value=self.responses.get(intent_name, ""),
            confidence=0.9, model_id="slow-mock",
            raw={"goal": goal},
        )


def test_parallel_batch_actually_overlaps_in_wall_time():
    # Three independent intent calls each sleep for 100ms. Serial would
    # take ~300ms; parallel should take ~100ms. We assert high-water
    # concurrency observed by the adapter is >= 2 (i.e., calls overlapped).
    src = """
    intent ia(x: Text) -> Text { goal: ga }
    intent ib(x: Text) -> Text { goal: gb }
    intent ic(x: Text) -> Text { goal: gc }
    fn combine(a: Text, b: Text, c: Text) -> Text {
        return join([a, b, c], ",")
    }
    entry main(x: Text) {
        a = ia(x)
        b = ib(x)
        c = ic(x)
        return combine(a, b, c)
    }
    """
    adapter = _SlowAdapter(delay_s=0.1,
                           responses={"ia": "A", "ib": "B", "ic": "C"})
    t0 = time.perf_counter()
    result, _ = run(src, input="hello", adapter=adapter)
    elapsed = time.perf_counter() - t0
    assert result.value == "A,B,C"
    # Concurrency observed: adapter saw at least 2 calls overlap.
    assert adapter.concurrent_high_water >= 2, (
        f"expected overlap >= 2, got {adapter.concurrent_high_water}"
    )
    # Wall-clock loosely bounded: well under 3x serial.
    # (Use a generous margin to avoid flakiness on slow CI.)
    assert elapsed < 0.25, f"elapsed {elapsed:.3f}s too slow for parallel"


def test_serial_fallback_when_dependent():
    # With dependent assignments, concurrency should NOT occur.
    src = """
    intent ia(x: Text) -> Text { goal: ga }
    intent ib(x: Text) -> Text { goal: gb }
    entry main(x: Text) {
        a = ia(x)
        b = ib(a)
        return b
    }
    """
    adapter = _SlowAdapter(delay_s=0.05,
                           responses={"ia": "A", "ib": "B"})
    run(src, input="hello", adapter=adapter)
    # Dependent → must run serially; high-water concurrency is 1.
    assert adapter.concurrent_high_water == 1


# ---------- purity interaction ----------


def test_parallelism_works_inside_default_fn():
    # Parallelism planning runs inside fn bodies too, not just entry.
    src = """
    intent ia(x: Text) -> Text { goal: ga }
    intent ib(x: Text) -> Text { goal: gb }
    fn gather(x: Text) -> Text {
        a = ia(x)
        b = ib(x)
        return join([a, b], "+")
    }
    entry main(x: Text) { return gather(x) }
    """
    adapter = _SlowAdapter(delay_s=0.05,
                           responses={"ia": "A", "ib": "B"})
    result, _ = run(src, input="hello", adapter=adapter)
    assert result.value == "A+B"
    assert adapter.concurrent_high_water >= 2
