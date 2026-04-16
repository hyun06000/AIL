"""Evolution supervisor for AIL intents.

Implements the runtime side of spec/04 to the extent an MVP supports:

  - Per-intent version chain, content-addressed by hash
  - Rolling metric window populated by sampled invocations
  - Condition-driven modification (MVP: retune of a numeric parameter)
  - Bounded_by enforcement: a proposed modification that violates a bound
    is rejected before application
  - Rollback: the rollback_on predicate, evaluated on each sampled call
    after a modification, reverts the intent to its prior version
  - History: the last N versions are retained; older versions may be
    pruned (but never silently rewritten)
  - Human review: when `require review_by: human` is declared, a
    modification is not applied until an external approver says yes

The supervisor is stateful across calls within a single executor
instance. Persistence across runs is out of scope for the MVP (spec/04
requires append-only persistence; we record in-memory and leave
persistence to a future NOOS-hosted runtime).
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from ..parser.ast import EvolveDecl, EvolveAction


@dataclass
class IntentVersion:
    """A single version of an evolving intent's tunable parameters.

    The MVP tracks a dict of numeric parameters; a rewrite action type
    would extend this to include structural edits.
    """
    version_id: int
    parameters: dict[str, float]         # e.g., {'confidence_threshold': 0.75}
    parent_id: int | None                # previous version, None for v0
    reason: str                          # human-readable why this version exists
    applied_at_call: int                 # invocation count at time of apply


@dataclass
class MetricSample:
    call_number: int
    value: float


@dataclass
class EvolutionEvent:
    """A record in the supervisor's log, mirroring what a ledger would hold."""
    kind: str                            # 'version_applied' | 'rollback' | 'review_requested' | 'modification_rejected'
    payload: dict[str, Any]


class EvolutionSupervisor:
    """Supervises evolution for one intent.

    One supervisor per evolving intent. The executor creates supervisors
    lazily on the first call to an intent that has an evolve declaration.
    """

    def __init__(self, decl: EvolveDecl,
                 approve_review: Callable[[dict], bool] | None = None,
                 rng_seed: int | None = None):
        self.decl = decl
        self.intent_name = decl.intent_name
        self.approve_review = approve_review or (lambda _info: False)

        # Random sampling for metric collection
        import random
        self._rng = random.Random(rng_seed)

        # Version chain, starting with v0 (no parameters until first applied)
        self.versions: list[IntentVersion] = [
            IntentVersion(
                version_id=0, parameters={},
                parent_id=None, reason="initial",
                applied_at_call=0,
            )
        ]
        self.active_version_id: int = 0

        # Rolling metric window. Simpler than a real implementation (which
        # would separate windows per version), but sufficient for MVP.
        self._metric_window: deque[MetricSample] = deque(maxlen=500)
        self._call_counter: int = 0

        # Events for introspection and trace
        self.events: list[EvolutionEvent] = []

        # Guard: once human review is pending, no further modifications
        # are proposed until the prior one resolves.
        self._review_pending: bool = False

    # ---- public API used by the executor ----

    def active_parameters(self) -> dict[str, float]:
        """The currently-active tunable parameters, or {} if no version applied."""
        return dict(self._active_version().parameters)

    def observe(self, metric_value: float | None,
                rollback_value: float | None) -> list[EvolutionEvent]:
        """Record an invocation; possibly trigger modification or rollback.

        Called by the executor after each invocation of the evolving
        intent. `metric_value` and `rollback_value` are already-evaluated
        scalars; the supervisor is deliberately not given AST nodes, so
        it can be tested independently.

        Returns the list of events produced during this observation
        (typically 0 or 1 events).
        """
        self._call_counter += 1
        new_events: list[EvolutionEvent] = []

        # Sampling: only a fraction of calls feed the metric window
        if metric_value is not None and self._rng.random() < self.decl.metric_sample_rate:
            self._metric_window.append(MetricSample(
                call_number=self._call_counter,
                value=metric_value,
            ))

        # Consider modification if not already awaiting review
        if not self._review_pending and metric_value is not None:
            ev = self._maybe_propose_modification(metric_value)
            if ev is not None:
                new_events.append(ev)

        # Consider rollback (evaluated on every call, not sampled)
        if rollback_value is not None and self.active_version_id != 0:
            ev = self._maybe_rollback(rollback_value)
            if ev is not None:
                new_events.append(ev)

        return new_events

    def approve_pending(self) -> list[EvolutionEvent]:
        """Called externally to approve a pending human-review modification.

        Returns events produced (e.g. version_applied). If nothing is
        pending, returns [].
        """
        # The MVP's flow is simple: `_maybe_propose_modification` either
        # applies immediately (no review) or records a review_requested
        # event with a pending modification stored in _pending_modification.
        if not self._review_pending:
            return []
        pending = getattr(self, "_pending_modification", None)
        if pending is None:
            self._review_pending = False
            return []
        self._apply_modification(pending, reason_suffix=" (human-approved)")
        self._review_pending = False
        self._pending_modification = None
        return [self.events[-1]]

    # ---- internal ----

    def _active_version(self) -> IntentVersion:
        for v in self.versions:
            if v.version_id == self.active_version_id:
                return v
        return self.versions[0]

    def _maybe_propose_modification(self, metric_value: float) -> EvolutionEvent | None:
        # MVP trigger rule: `when <metric_name> < <threshold>` with a
        # minimum window of 10 samples. We pattern-match the when_condition
        # shape; more complex conditions fall back to "don't trigger".
        from ..parser.ast import BinaryOp, Identifier, Literal

        cond = self.decl.when_condition
        if not (isinstance(cond, BinaryOp) and cond.op in ("<", "<=")):
            return None  # MVP only handles simple threshold below
        if not isinstance(cond.right, Literal) or not isinstance(cond.right.value, (int, float)):
            return None
        threshold = float(cond.right.value)

        if len(self._metric_window) < 10:
            return None

        avg = sum(s.value for s in self._metric_window) / len(self._metric_window)
        if not (avg < threshold if cond.op == "<" else avg <= threshold):
            return None

        # Build the proposed modification (MVP: retune)
        action = self.decl.action
        if action.kind != "retune":
            return None

        # Nudge toward the midpoint of the allowed range
        mid = (action.range_lo + action.range_hi) / 2.0
        proposed_params = dict(self._active_version().parameters)
        proposed_params[action.target] = mid

        # Bounded_by check
        bound = self.decl.bounded_by.get(action.target)
        if bound is not None:
            lo, hi = bound
            if not (lo <= mid <= hi):
                ev = EvolutionEvent(
                    kind="modification_rejected",
                    payload={
                        "reason": "bounded_by violated",
                        "target": action.target,
                        "proposed": mid,
                        "bound": (lo, hi),
                    },
                )
                self.events.append(ev)
                return ev

        # Human review gate
        if self.decl.review_by == "human":
            self._pending_modification = proposed_params
            self._review_pending = True
            info = {
                "intent": self.intent_name,
                "current_version": self.active_version_id,
                "proposed_params": proposed_params,
                "trigger_metric_avg": avg,
                "threshold": threshold,
            }
            ev = EvolutionEvent(kind="review_requested", payload=info)
            self.events.append(ev)
            # Call the approval callback synchronously (MVP behavior).
            # In a production runtime this would be async.
            if self.approve_review(info):
                self._apply_modification(proposed_params, reason_suffix=" (human-approved)")
                self._review_pending = False
                self._pending_modification = None
                return ev  # the apply event is appended by _apply_modification
            return ev

        # No review required: apply immediately
        self._apply_modification(proposed_params)
        return self.events[-1]

    def _apply_modification(self, proposed_params: dict[str, float],
                            reason_suffix: str = "") -> None:
        new_id = max(v.version_id for v in self.versions) + 1
        reason = (
            f"metric {self._describe_metric()} fell below threshold; "
            f"retune to midpoint{reason_suffix}"
        )
        new_version = IntentVersion(
            version_id=new_id,
            parameters=proposed_params,
            parent_id=self.active_version_id,
            reason=reason,
            applied_at_call=self._call_counter,
        )
        self.versions.append(new_version)
        self.active_version_id = new_id

        # Prune history (keep_last)
        keep = self.decl.history_keep
        if len(self.versions) > keep + 1:  # +1 for v0 initial, always kept
            # Remove oldest non-initial versions
            keep_versions = [self.versions[0]] + self.versions[-keep:]
            self.versions = keep_versions

        self.events.append(EvolutionEvent(
            kind="version_applied",
            payload={
                "version_id": new_id,
                "parameters": dict(proposed_params),
                "reason": reason,
            },
        ))

        # Reset window after version change; new version needs fresh evidence
        self._metric_window.clear()

    def _maybe_rollback(self, rollback_value: float) -> EvolutionEvent | None:
        from ..parser.ast import BinaryOp, Literal

        cond = self.decl.rollback_on
        # MVP: simple pattern `<name> > <number>` or `<name> < <number>`
        if not (isinstance(cond, BinaryOp) and cond.op in (">", ">=", "<", "<=")):
            return None
        if not isinstance(cond.right, Literal) or not isinstance(cond.right.value, (int, float)):
            return None
        threshold = float(cond.right.value)
        op = cond.op

        triggered = (
            (op == ">" and rollback_value > threshold) or
            (op == ">=" and rollback_value >= threshold) or
            (op == "<" and rollback_value < threshold) or
            (op == "<=" and rollback_value <= threshold)
        )
        if not triggered:
            return None

        current = self._active_version()
        if current.parent_id is None:
            # Already at v0 — nothing to roll back to
            return None
        old_id = self.active_version_id
        self.active_version_id = current.parent_id
        ev = EvolutionEvent(
            kind="rollback",
            payload={
                "from_version": old_id,
                "to_version": current.parent_id,
                "trigger_value": rollback_value,
                "threshold": threshold,
            },
        )
        self.events.append(ev)
        self._metric_window.clear()
        return ev

    def _describe_metric(self) -> str:
        from ..parser.ast import Identifier
        if isinstance(self.decl.metric, Identifier):
            return self.decl.metric.name
        return "<complex>"
