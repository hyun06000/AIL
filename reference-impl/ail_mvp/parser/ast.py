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


Expr = (
    Literal | Identifier | FieldAccess | Call | BinaryOp | UnaryOp
    | ListLiteral | PerformExpr | MembershipOp
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


Statement = (
    Assignment | ReturnStmt | PerformStmt | BranchStmt | WithContextStmt | ExprStmt
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

    Per spec/04 §4, only a small fixed set of actions is permitted. The
    MVP supports `retune` (numeric-parameter adjustment); other actions
    (`rewrite constraints`, `rewrite examples`, `rewrite goal`,
    `promote strategy`, `escalate`) are reserved for future work.
    """
    kind: str                        # 'retune' | 'rewrite_constraints' | ... (MVP: 'retune')
    target: str                      # e.g. 'confidence_threshold'
    range_lo: float | None = None    # for retune: the allowed range
    range_hi: float | None = None


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


TopLevel = ContextDecl | IntentDecl | EffectDecl | EntryDecl | ImportDecl | EvolveDecl


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
