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


Expr = Literal | Identifier | FieldAccess | Call | BinaryOp | UnaryOp | ListLiteral | PerformExpr


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
class EvolveDecl:
    """Parsed but not executed in MVP."""

    intent_name: str
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
