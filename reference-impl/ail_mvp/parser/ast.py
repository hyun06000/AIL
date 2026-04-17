"""AST node definitions for the AIL MVP.

The MVP covers a subset of the full AIL grammar sufficient to express the
example programs. Nodes not implemented are parsed and retained (for round-
tripping) but ignored by the executor.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ---------- Expressions ----------


@dataclass
class Literal:
    value: Any  # str, int, float, bool, or list


@dataclass
class Identifier:
    name: str


@dataclass
class FieldAccess:
    target: "Expr"
    field: str


@dataclass
class Call:
    callee: "Expr"
    args: list["Expr"]
    kwargs: dict[str, "Expr"] = field(default_factory=dict)


@dataclass
class BinaryOp:
    op: str  # '>', '<', '>=', '<=', '==', '!=', 'and', 'or', '+', '-', '*', '/'
    left: "Expr"
    right: "Expr"


@dataclass
class UnaryOp:
    op: str  # 'not'
    operand: "Expr"


@dataclass
class ListLiteral:
    items: list["Expr"]


@dataclass
class PerformExpr:
    """`perform` used as an expression (e.g. `x = perform effect(...)`)."""
    effect: str
    args: list["Expr"]
    kwargs: dict[str, "Expr"]


@dataclass
class MembershipOp:
    """`x in [a, b, c]` — tests whether `element` is contained in `collection`.

    The collection may be a list literal, an identifier bound to a list, or
    any expression that evaluates to a sequence.
    """
    element: "Expr"
    collection: "Expr"
    negated: bool = False     # `x not in [...]`


@dataclass
class AttemptExpr:
    """`attempt { try EXPR; try EXPR; ... }` — confidence-priority cascade.

    Evaluates each `try` expression in order. The first result that
    qualifies (not an error(), confidence >= threshold) is returned. If
    none qualify, the last try's result is returned. This is AIL's
    native idiom for "prefer the cheap deterministic strategy; fall back
    to the expensive LLM call only when the earlier strategies don't
    produce a confident answer."

    threshold: minimum confidence for a try to qualify (default 0.7).
    """
    tries: list["Expr"]
    threshold: float = 0.7


Expr = (
    Literal | Identifier | FieldAccess | Call | BinaryOp | UnaryOp
    | ListLiteral | PerformExpr | MembershipOp | AttemptExpr
)


# ---------- Statements / Blocks ----------


@dataclass
class Assignment:
    name: str
    value: Expr


@dataclass
class ReturnStmt:
    value: Expr | None


@dataclass
class PerformStmt:
    effect: str
    args: list[Expr]
    kwargs: dict[str, Expr]


@dataclass
class BranchArm:
    condition: Expr
    action: "Statement"


@dataclass
class BranchStmt:
    subject: Expr
    arms: list[BranchArm]
    calibrate_on: str | None


@dataclass
class WithContextStmt:
    context_name: str
    body: list["Statement"]


@dataclass
class ExprStmt:
    expr: Expr


@dataclass
class IfStmt:
    """Deterministic if/else — boolean condition, not probabilistic."""
    condition: Expr
    then_body: list["Statement"]
    else_body: list["Statement"]    # may be empty, or contain a single IfStmt (else if)


@dataclass
class ForStmt:
    """Bounded iteration: `for VAR in COLLECTION { ... }`."""
    var_name: str
    collection: Expr
    body: list["Statement"]


Statement = (
    Assignment | ReturnStmt | PerformStmt | BranchStmt | WithContextStmt
    | ExprStmt | IfStmt | ForStmt
)


# ---------- Top-level declarations ----------


@dataclass
class ContextDecl:
    name: str
    extends: str | None
    fields: dict[str, Expr]
    overrides: set[str]  # names of fields marked `override`


@dataclass
class IntentDecl:
    name: str
    params: list[tuple[str, str | None]]  # (name, optional type)
    return_type: str | None
    goal: Expr
    constraints: list[Expr]
    examples: list[tuple[list[Expr], Expr]]  # (inputs, expected)
    low_confidence_handler: tuple[float, list[Statement]] | None  # (threshold, body)
    trace_level: str  # 'none' | 'partial' | 'full'
    body_hint: list[Statement]  # optional explicit body (MVP)


@dataclass
class EffectDecl:
    name: str
    signature_params: list[tuple[str, str | None]]
    signature_return: str | None
    authorization: str  # 'none' | 'required' | 'human_confirmation'
    observable_by: list[str]


@dataclass
class EntryDecl:
    name: str
    params: list[tuple[str, str | None]]
    body: list[Statement]


@dataclass
class ImportDecl:
    symbol: str
    source: str
    kind: str  # 'intent' | 'context' | 'effect' (default 'intent')


@dataclass
class EvolveAction:
    """A single permitted action inside an evolve block's `when` clause.

    Per spec/04 §4, only a small fixed set of actions is permitted.
    The MVP supports:
      - 'retune'             : adjust a numeric parameter to the
                               midpoint of a declared range
      - 'rewrite_constraints': tighten numeric thresholds in the
                               intent's constraints block by a fixed
                               delta; requires human review

    Other actions (`rewrite examples`, `rewrite goal`, `promote
    strategy`, `escalate`) are reserved for future work.
    """
    kind: str                        # 'retune' | 'rewrite_constraints'
    # For 'retune':
    target: str = ""                 # e.g. 'confidence_threshold'
    range_lo: float | None = None    # the allowed range
    range_hi: float | None = None
    # For 'rewrite_constraints':
    tighten_delta: float | None = None  # e.g. 0.05 -> tighter by 5%


@dataclass
class EvolveDecl:
    """A declaration attaching evolution rules to an intent.

    Spec/04 §2 requires `metric`, `when`, an action, `rollback_on`, and
    `history`. An EvolveDecl missing any of these is a compile error,
    enforced by the parser/validator (see parser.py).
    """
    intent_name: str
    metric: Expr                                    # scalar expression
    metric_sample_rate: float                       # 0.0–1.0
    when_condition: Expr                            # triggers action
    action: EvolveAction                            # the change to apply
    rollback_on: Expr                               # reverts most recent change
    history_keep: int                               # versions retained
    bounded_by: dict[str, tuple[float, float]]      # field name -> (min, max)
    review_by: str | None                           # None | 'human' | role name
    # Raw form preserved for round-tripping; parser stores a best-effort
    # normalization and keeps the rest of the block here for forward compat.
    raw: dict[str, Any]


@dataclass
class FnDecl:
    """A deterministic function — no LLM involvement at the fn boundary.

    This is where AI writes actual algorithms: sorting, parsing,
    transforming data. The body contains real control flow (if, for,
    assignments, returns) rather than goals and constraints.

    The `purity` field declares a structural contract:
    - "default": no contract; the fn may call intents (LLM) or use
      `perform` statements if its body does so. No static guarantee.
    - "pure": guaranteed no intent calls, no `perform` statements, and
      no calls to other non-pure fns. The purity checker rejects the
      program at parse time if this guarantee can be violated. Values
      produced by a `pure fn` are guaranteed to have no intent anywhere
      in their origin tree.
    """
    name: str
    params: list[tuple[str, str | None]]   # (name, optional type)
    return_type: str | None
    body: list[Statement]
    purity: str = "default"   # "default" | "pure"


TopLevel = ContextDecl | IntentDecl | EffectDecl | EntryDecl | ImportDecl | EvolveDecl | FnDecl


@dataclass
class Program:
    declarations: list[TopLevel]

    def context_by_name(self, name: str) -> ContextDecl | None:
        for d in self.declarations:
            if isinstance(d, ContextDecl) and d.name == name:
                return d
        return None

    def intent_by_name(self, name: str) -> IntentDecl | None:
        for d in self.declarations:
            if isinstance(d, IntentDecl) and d.name == name:
                return d
        return None

    def effect_by_name(self, name: str) -> EffectDecl | None:
        for d in self.declarations:
            if isinstance(d, EffectDecl) and d.name == name:
                return d
        return None

    def entry(self) -> EntryDecl | None:
        for d in self.declarations:
            if isinstance(d, EntryDecl):
                return d
        return None
