"""Tests for EvolutionSupervisor in isolation.

These tests do not involve the parser or executor. They construct
EvolveDecl objects directly and drive the supervisor to verify:

  - sampled metric window fills correctly
  - modification triggers only after sufficient samples
  - bounded_by rejects out-of-range proposals
  - human-review gate holds modifications until approved
  - rollback reverts the active version
  - history pruning respects keep_last
"""
from __future__ import annotations

import pytest

from ail.parser.ast import (
    EvolveDecl, EvolveAction, BinaryOp, Literal, Identifier,
)
from ail.runtime.evolution import EvolutionSupervisor


def _make_decl(
    *, threshold: float = 0.7, rollback_threshold: float = 0.5,
    action_lo: float = 0.4, action_hi: float = 0.9,
    bounded: dict | None = None, review: str | None = None,
    history_keep: int = 10, sample_rate: float = 1.0,
) -> EvolveDecl:
    """Build an EvolveDecl for tests. Metric: `m < threshold`."""
    return EvolveDecl(
        intent_name="test_intent",
        metric=Identifier(name="m"),
        metric_sample_rate=sample_rate,
        when_condition=BinaryOp(op="<", left=Identifier(name="m"),
                                right=Literal(value=threshold)),
        action=EvolveAction(
            kind="retune", target="confidence_threshold",
            range_lo=action_lo, range_hi=action_hi,
        ),
        rollback_on=BinaryOp(op="<", left=Identifier(name="m"),
                             right=Literal(value=rollback_threshold)),
        history_keep=history_keep,
        bounded_by=bounded or {},
        review_by=review,
        raw={},
    )


def test_initial_state():
    sup = EvolutionSupervisor(_make_decl())
    assert sup.active_version_id == 0
    assert sup.active_parameters() == {}
    assert sup.events == []


def test_modification_requires_minimum_samples():
    """Fewer than 10 samples below threshold should not trigger a modification."""
    sup = EvolutionSupervisor(_make_decl(), rng_seed=0)
    for _ in range(9):
        sup.observe(metric_value=0.3, rollback_value=None)
    assert sup.active_version_id == 0
    assert not any(e.kind == "version_applied" for e in sup.events)


def test_modification_applies_when_average_below_threshold():
    sup = EvolutionSupervisor(_make_decl(), rng_seed=0)
    # Feed many samples below threshold 0.7
    for _ in range(15):
        sup.observe(metric_value=0.3, rollback_value=None)
    assert sup.active_version_id != 0
    applied = [e for e in sup.events if e.kind == "version_applied"]
    assert len(applied) == 1
    # Midpoint of [0.4, 0.9] = 0.65
    assert sup.active_parameters()["confidence_threshold"] == 0.65


def test_no_modification_when_metric_above_threshold():
    sup = EvolutionSupervisor(_make_decl(), rng_seed=0)
    for _ in range(20):
        sup.observe(metric_value=0.9, rollback_value=None)
    assert sup.active_version_id == 0


def test_bounded_by_rejects_out_of_range():
    """Proposed midpoint 0.65 is outside bound [0.8, 1.0] -> rejected."""
    sup = EvolutionSupervisor(_make_decl(
        action_lo=0.4, action_hi=0.9,
        bounded={"confidence_threshold": (0.8, 1.0)},
    ), rng_seed=0)
    for _ in range(15):
        sup.observe(metric_value=0.3, rollback_value=None)
    rejections = [e for e in sup.events if e.kind == "modification_rejected"]
    assert len(rejections) >= 1
    assert rejections[0].payload["reason"] == "bounded_by violated"
    assert sup.active_version_id == 0  # unchanged


def test_human_review_holds_modification_until_approved():
    approvals: list[dict] = []

    def approver(info):
        approvals.append(info)
        return True  # approve

    sup = EvolutionSupervisor(
        _make_decl(review="human"), approve_review=approver, rng_seed=0,
    )
    for _ in range(15):
        sup.observe(metric_value=0.3, rollback_value=None)

    # Approval was called synchronously -> version applied
    assert len(approvals) == 1
    assert sup.active_version_id != 0
    kinds = [e.kind for e in sup.events]
    assert "review_requested" in kinds
    assert "version_applied" in kinds


def test_human_review_denied_means_no_change():
    sup = EvolutionSupervisor(
        _make_decl(review="human"),
        approve_review=lambda _: False,   # deny
        rng_seed=0,
    )
    for _ in range(15):
        sup.observe(metric_value=0.3, rollback_value=None)
    assert sup.active_version_id == 0
    assert any(e.kind == "review_requested" for e in sup.events)
    assert not any(e.kind == "version_applied" for e in sup.events)


def test_rollback_reverts_active_version():
    sup = EvolutionSupervisor(
        _make_decl(rollback_threshold=0.5),
        rng_seed=0,
    )
    # Apply a version first
    for _ in range(15):
        sup.observe(metric_value=0.3, rollback_value=None)
    assert sup.active_version_id == 1

    # Now feed rollback signals (m < 0.5 triggers rollback)
    sup.observe(metric_value=None, rollback_value=0.2)
    assert sup.active_version_id == 0
    assert any(e.kind == "rollback" for e in sup.events)


def test_history_keep_last_prunes_old_versions():
    """With history_keep=2, after many modifications only the most recent
    2 (plus the initial v0) should remain in self.versions."""
    sup = EvolutionSupervisor(_make_decl(history_keep=2), rng_seed=0)
    # Drive 5 modifications by repeatedly provoking the trigger
    # (each modification clears the window, so we need to refill each time)
    for cycle in range(5):
        for _ in range(12):
            sup.observe(metric_value=0.2, rollback_value=None)
    applied = [e for e in sup.events if e.kind == "version_applied"]
    assert len(applied) >= 3  # at least 3 modifications happened
    # Verify retention: v0 always kept + at most keep_last newest
    assert len(sup.versions) <= 2 + 1
    assert sup.versions[0].version_id == 0  # initial preserved


# ---------- rewrite_constraints action ----------


def test_rewrite_constraints_tightens_greater_than():
    """A '>' threshold tightens UP by the declared delta."""
    from ail import compile_source
    from ail.runtime.executor import Executor
    from ail.runtime import MockAdapter
    from ail.runtime.model import ModelResponse

    class Low(MockAdapter):
        def invoke(self, **kw):
            return ModelResponse(value="x", confidence=0.3, model_id="m", raw={})

    src = """
    intent i(x: Text) -> Text {
        goal: label
        constraints {
            fidelity > 0.7
        }
    }
    evolve i {
        metric: score
        when score < 0.7 {
            rewrite constraints tighten_numeric_thresholds_by 0.05
        }
        rollback_on: score < 0.1
        history: keep_last 5
        require review_by: human
    }
    entry main(x: Text) { return i(x) }
    """
    program = compile_source(src)
    executor = Executor(program, Low(), approve_review=lambda _: True)
    for _ in range(15):
        executor.run_entry({"x": "test"})

    sup = executor.supervisors["i"]
    assert sup.active_version_id >= 1
    overrides = sup.versions[-1].constraint_overrides
    # fidelity > 0.7  ->  fidelity > 0.75
    assert overrides[0] == "fidelity > 0.75"


def test_rewrite_constraints_tightens_less_than():
    """A '<' threshold tightens DOWN by the declared delta."""
    from ail import compile_source
    from ail.runtime.executor import Executor
    from ail.runtime import MockAdapter
    from ail.runtime.model import ModelResponse

    class Low(MockAdapter):
        def invoke(self, **kw):
            return ModelResponse(value="x", confidence=0.3, model_id="m", raw={})

    src = """
    intent i(x: Text) -> Text {
        goal: label
        constraints {
            latency < 2000
        }
    }
    evolve i {
        metric: score
        when score < 0.7 {
            rewrite constraints tighten_numeric_thresholds_by 0.05
        }
        rollback_on: score < 0.1
        history: keep_last 5
    }
    entry main(x: Text) { return i(x) }
    """
    program = compile_source(src)
    executor = Executor(program, Low(), approve_review=lambda _: True)
    for _ in range(15):
        executor.run_entry({"x": "test"})

    sup = executor.supervisors["i"]
    overrides = sup.versions[-1].constraint_overrides
    assert overrides[0] == "latency < 1999.95"


def test_rewrite_constraints_always_forces_human_review():
    """Even without 'require review_by: human', rewrite_constraints
    must go through a reviewer. Denial blocks the change."""
    from ail import compile_source
    from ail.runtime.executor import Executor
    from ail.runtime import MockAdapter
    from ail.runtime.model import ModelResponse

    class Low(MockAdapter):
        def invoke(self, **kw):
            return ModelResponse(value="x", confidence=0.3, model_id="m", raw={})

    # NOTE: No `require review_by: human` clause in this program.
    src = """
    intent i(x: Text) -> Text {
        goal: label
        constraints {
            fidelity > 0.7
        }
    }
    evolve i {
        metric: score
        when score < 0.7 {
            rewrite constraints tighten_numeric_thresholds_by 0.05
        }
        rollback_on: score < 0.1
        history: keep_last 5
    }
    entry main(x: Text) { return i(x) }
    """
    program = compile_source(src)
    # Deny all approvals
    executor = Executor(program, Low(), approve_review=lambda _: False)
    for _ in range(15):
        executor.run_entry({"x": "test"})

    sup = executor.supervisors["i"]
    # Review was requested (forced)
    assert any(e.kind == "review_requested" for e in sup.events)
    # The review event's payload should mark it as forced
    rr = next(e for e in sup.events if e.kind == "review_requested")
    assert rr.payload.get("forced_review") is True
    # Denied -> no version change
    assert sup.active_version_id == 0


def test_rewrite_constraints_rejected_when_no_numeric_constraints():
    """If the intent has only symbolic constraints, there's nothing to
    tighten — emit modification_rejected."""
    from ail import compile_source
    from ail.runtime.executor import Executor
    from ail.runtime import MockAdapter
    from ail.runtime.model import ModelResponse

    class Low(MockAdapter):
        def invoke(self, **kw):
            return ModelResponse(value="x", confidence=0.3, model_id="m", raw={})

    src = """
    intent i(x: Text) -> Text {
        goal: label
        constraints {
            output_is_valid
        }
    }
    evolve i {
        metric: score
        when score < 0.7 {
            rewrite constraints tighten_numeric_thresholds_by 0.05
        }
        rollback_on: score < 0.1
        history: keep_last 5
        require review_by: human
    }
    entry main(x: Text) { return i(x) }
    """
    program = compile_source(src)
    executor = Executor(program, Low(), approve_review=lambda _: True)
    for _ in range(15):
        executor.run_entry({"x": "test"})

    sup = executor.supervisors["i"]
    assert sup.active_version_id == 0
    rejections = [e for e in sup.events if e.kind == "modification_rejected"]
    assert len(rejections) >= 1
    assert "no numeric constraints" in rejections[0].payload["reason"]
