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

    Two kinds of per-version state:
      - parameters: numeric values used by retune actions
      - constraint_overrides: replacement constraint expressions for
        rewrite_constraints actions. Maps constraint-index (position in
        the original intent's constraints list) to the replacement
        expression in stringified form.

    The executor reads these at dispatch time: parameters are injected
    into the context; constraint_overrides replace the corresponding
    lines of the constraints block passed to the model adapter.
    """
    version_id: int
    parameters: dict[str, float]
    parent_id: int | None
    reason: str
    applied_at_call: int
    constraint_overrides: dict[int, str] = field(default_factory=dict)


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
                 rng_seed: int | None = None,
                 intent_decl=None):
        self.decl = decl
        self.intent_name = decl.intent_name
        self.approve_review = approve_review or (lambda _info: False)
        # The AST node for the intent this supervisor governs. Needed by
        # rewrite_constraints to introspect existing constraint expressions.
        self._intent_decl = intent_decl

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

        action = self.decl.action

        # Dispatch by action kind
        if action.kind == "retune":
            return self._propose_retune(action, avg, threshold)
        if action.kind == "rewrite_constraints":
            return self._propose_rewrite_constraints(action, avg, threshold)
        return None

    def _propose_retune(self, action, avg: float,
                        threshold: float) -> EvolutionEvent | None:
        """Build a retune proposal: set the target to the midpoint of the range."""
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
            return self._seek_review_or_apply(
                proposed_params=proposed_params,
                proposed_overrides={},
                avg=avg, threshold=threshold,
            )

        self._apply_modification(proposed_params, {})
        return self.events[-1]

    def _propose_rewrite_constraints(self, action, avg: float,
                                     threshold: float) -> EvolutionEvent | None:
        """Build a rewrite_constraints proposal.

        Walks the intent's constraints block, finds BinaryOp nodes of the
        form `<lhs> <op> <number>`, and proposes tighter versions:

          >  and >=   : increase threshold by tighten_delta
          <  and <=   : decrease threshold by tighten_delta

        The proposal is stored as constraint_overrides (index -> string
        form of the new constraint). The original constraints AST is
        never mutated; each version carries its own overrides.
        """
        from ..parser.ast import BinaryOp, Literal

        intent = self._intent_decl
        if intent is None:
            return None

        delta = action.tighten_delta or 0.0
        current = self._active_version()
        proposed_overrides = dict(current.constraint_overrides)

        changed_any = False
        for idx, constraint in enumerate(intent.constraints):
            if not isinstance(constraint, BinaryOp):
                continue
            if not isinstance(constraint.right, Literal):
                continue
            if not isinstance(constraint.right.value, (int, float)):
                continue

            lhs_repr = self._expr_repr(constraint.left)
            old_val = float(constraint.right.value)
            # Tightening direction depends on operator
            if constraint.op in (">", ">="):
                new_val = old_val + delta
            elif constraint.op in ("<", "<="):
                new_val = old_val - delta
            else:
                continue

            # Accumulate if this constraint was already overridden
            if idx in proposed_overrides:
                # Re-tightening: parse the prior override's number and add
                # another delta. For MVP we skip re-tightening; the
                # window is reset after each version, so the next time
                # we trigger we're starting from the prior value.
                pass

            new_text = f"{lhs_repr} {constraint.op} {new_val}"
            proposed_overrides[idx] = new_text
            changed_any = True

        if not changed_any:
            ev = EvolutionEvent(
                kind="modification_rejected",
                payload={
                    "reason": "no numeric constraints to tighten",
                },
            )
            self.events.append(ev)
            return ev

        # rewrite_constraints ALWAYS goes through human review —
        # tightening rules is a material change even if numerically
        # small. If the program did not declare review_by: human,
        # we force it for safety.
        return self._seek_review_or_apply(
            proposed_params=dict(self._active_version().parameters),
            proposed_overrides=proposed_overrides,
            avg=avg, threshold=threshold,
            force_review=True,
        )

    def _seek_review_or_apply(self, *, proposed_params: dict[str, float],
                              proposed_overrides: dict[int, str],
                              avg: float, threshold: float,
                              force_review: bool = False,
                              ) -> EvolutionEvent | None:
        """Common path: if review required, request it; else apply."""
        if self.decl.review_by == "human" or force_review:
            self._pending_modification = (proposed_params, proposed_overrides)
            self._review_pending = True
            info = {
                "intent": self.intent_name,
                "current_version": self.active_version_id,
                "proposed_params": proposed_params,
                "proposed_constraint_overrides": proposed_overrides,
                "trigger_metric_avg": avg,
                "threshold": threshold,
                "forced_review": force_review,
            }
            ev = EvolutionEvent(kind="review_requested", payload=info)
            self.events.append(ev)
            if self.approve_review(info):
                self._apply_modification(proposed_params, proposed_overrides,
                                         reason_suffix=" (human-approved)")
                self._review_pending = False
                self._pending_modification = None
            return ev

        self._apply_modification(proposed_params, proposed_overrides)
        return self.events[-1]

    @staticmethod
    def _expr_repr(expr) -> str:
        """Best-effort string representation of an expression for override text."""
        from ..parser.ast import Identifier, FieldAccess, Literal
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, FieldAccess):
            return f"{EvolutionSupervisor._expr_repr(expr.target)}.{expr.field}"
        if isinstance(expr, Literal):
            return repr(expr.value)
        return str(expr)

    def _apply_modification(self, proposed_params: dict[str, float],
                            proposed_overrides: dict[int, str] | None = None,
                            reason_suffix: str = "") -> None:
        new_id = max(v.version_id for v in self.versions) + 1
        action = self.decl.action
        if action.kind == "rewrite_constraints":
            action_desc = f"tighten constraints by {action.tighten_delta}"
        else:
            action_desc = "retune to midpoint"
        reason = (
            f"metric {self._describe_metric()} fell below threshold; "
            f"{action_desc}{reason_suffix}"
        )
        new_version = IntentVersion(
            version_id=new_id,
            parameters=proposed_params,
            parent_id=self.active_version_id,
            reason=reason,
            applied_at_call=self._call_counter,
            constraint_overrides=proposed_overrides or {},
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
