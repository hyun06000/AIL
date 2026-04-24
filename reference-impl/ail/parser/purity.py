"""Structural purity checking.

A `pure fn` declares a runtime contract: its execution does not involve a
language model (no intent calls), performs no effects (no perform
statements), and only calls other verifiably pure code (other pure fns or
trusted builtins).

This is enforced statically: we walk each pure fn's body and reject the
program at parse time if the guarantee can be violated. Composed with
provenance (Phase 1), the contract becomes:

    pure_fn(...) -> value  ⟹  has_intent_origin(value) == false

— a compile-time guarantee, not just a runtime observation.

Why this matters for AI authorship: the single worst failure mode of
AI-generated code is unintended side effects (mutations, network calls,
LLM calls that the author forgot to flag). A `pure fn` contract lets the
AI mark an intent explicitly: "this computation is deterministic and
self-contained." The language then proves it or rejects the program.

Implementation: two passes.
  1. Collect the set of pure-fn names declared in the program.
  2. Walk each pure-fn body; reject forbidden nodes.
"""
from __future__ import annotations

from typing import Any

from .ast import (
    Program, FnDecl, IntentDecl,
    Assignment, ReturnStmt, PerformStmt, BranchStmt, BranchArm,
    WithContextStmt, ExprStmt, IfStmt, ForStmt,
    Literal, Identifier, FieldAccess, Call, BinaryOp, UnaryOp, ListLiteral,
    PerformExpr, MembershipOp, AttemptExpr, MatchExpr,
    Expr, Statement,
)


class PurityError(Exception):
    """Raised when a `pure fn` body contains a forbidden operation."""
    def __init__(self, fn_name: str, reason: str):
        self.fn_name = fn_name
        self.reason = reason
        super().__init__(f"pure fn '{fn_name}': {reason}")


# Builtins that are trusted pure — deterministic, no side effects, no LLM.
# Everything in the spec §5 list except `eval_ail` (which runs arbitrary
# AIL code, including intents). `perform` is a separate statement type
# and is rejected structurally.
_PURE_BUILTINS: frozenset[str] = frozenset({
    # Text
    "length", "split", "join", "trim", "upper", "lower",
    "starts_with", "ends_with", "replace", "slice", "index_of",
    # List
    "get", "append", "sort", "reverse", "range",
    "map", "filter", "reduce",
    # Conversion
    "to_number", "to_text", "to_boolean",
    # Math
    "abs", "max", "min",
    "round", "floor", "ceil", "sqrt", "pow",
    # Result
    "ok", "error", "is_ok", "is_error",
    "unwrap", "unwrap_or", "unwrap_error",
    # Provenance / calibration introspection — pure by construction
    # (they read metadata, never execute an intent or effect)
    "origin_of", "lineage_of", "has_intent_origin", "has_effect_origin",
    "calibration_of",
    # Self-reflection — pure by construction. ail_parse_check parses a
    # string as AIL and returns a Result, but does NOT execute it: no
    # intents dispatched, no effects performed. Distinct from eval_ail
    # which DOES execute and is therefore impure.
    "ail_parse_check",
    # JSON parse / encode — pure, no I/O, no LLM.
    "parse_json",
    "encode_json",
    # HTML noise stripper — pure, no I/O, no LLM.
    "strip_html",
    # stdlib/utils.ail — deterministic, no side effects, no LLM
    "sum_list", "average", "unique", "flatten", "take",
    "word_count", "char_count", "is_empty", "repeat", "pad_left", "clamp",
    # stdlib/core.ail
    "identity",
    # common dict/map operations (executor handles these as builtins)
    "has_key", "keys", "values", "has",
})

_BANNED_FROM_PURE: frozenset[str] = frozenset({
    "eval_ail",   # runs arbitrary AIL code, including intents
})


def check_program(program: Program) -> None:
    """Validate all pure-fn declarations in the program.

    Raises PurityError on the first violation. Does not modify the program.
    """
    pure_fns: set[str] = set()
    all_fns: dict[str, FnDecl] = {}
    intents: set[str] = set()

    for d in program.declarations:
        if isinstance(d, FnDecl):
            all_fns[d.name] = d
            if d.purity == "pure":
                pure_fns.add(d.name)
        elif isinstance(d, IntentDecl):
            intents.add(d.name)

    for d in program.declarations:
        if isinstance(d, FnDecl) and d.purity == "pure":
            _check_fn_body(d, pure_fns=pure_fns, all_fns=all_fns, intents=intents)


def _check_fn_body(fn: FnDecl, *, pure_fns: set[str],
                   all_fns: dict[str, FnDecl], intents: set[str]) -> None:
    for stmt in fn.body:
        _check_stmt(stmt, fn_name=fn.name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)


def _check_stmt(stmt: Statement, *, fn_name: str, pure_fns: set[str],
                all_fns: dict[str, FnDecl], intents: set[str]) -> None:
    if isinstance(stmt, PerformStmt):
        raise PurityError(
            fn_name,
            f"'perform {stmt.effect}' is forbidden — pure fns cannot invoke effects",
        )
    if isinstance(stmt, Assignment):
        _check_expr(stmt.value, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
    elif isinstance(stmt, ReturnStmt):
        if stmt.value is not None:
            _check_expr(stmt.value, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(stmt, IfStmt):
        _check_expr(stmt.condition, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
        for s in stmt.then_body:
            _check_stmt(s, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
        for s in stmt.else_body:
            _check_stmt(s, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(stmt, ForStmt):
        _check_expr(stmt.collection, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
        for s in stmt.body:
            _check_stmt(s, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(stmt, BranchStmt):
        _check_expr(stmt.subject, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
        for arm in stmt.arms:
            if not isinstance(arm.condition, Identifier) or arm.condition.name != "otherwise":
                _check_expr(arm.condition, fn_name=fn_name, pure_fns=pure_fns,
                            all_fns=all_fns, intents=intents)
            _check_stmt(arm.action, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(stmt, WithContextStmt):
        # `with context` doesn't itself violate purity — it just scopes
        # contextual fields. But the body might.
        for s in stmt.body:
            _check_stmt(s, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(stmt, ExprStmt):
        _check_expr(stmt.expr, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)


def _check_expr(expr: Expr, *, fn_name: str, pure_fns: set[str],
                all_fns: dict[str, FnDecl], intents: set[str]) -> None:
    if isinstance(expr, PerformExpr):
        raise PurityError(
            fn_name,
            f"'perform {expr.effect}' is forbidden — pure fns cannot invoke effects",
        )
    if isinstance(expr, Call):
        name = _call_name(expr)
        if name is not None:
            _check_call_target(name, fn_name=fn_name, pure_fns=pure_fns,
                               all_fns=all_fns, intents=intents)
        for a in expr.args:
            _check_expr(a, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
        for v in expr.kwargs.values():
            _check_expr(v, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(expr, BinaryOp):
        _check_expr(expr.left, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
        _check_expr(expr.right, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
    elif isinstance(expr, UnaryOp):
        _check_expr(expr.operand, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
    elif isinstance(expr, ListLiteral):
        for i in expr.items:
            _check_expr(i, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(expr, FieldAccess):
        _check_expr(expr.target, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
    elif isinstance(expr, MembershipOp):
        _check_expr(expr.element, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
        _check_expr(expr.collection, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
    elif isinstance(expr, AttemptExpr):
        # An attempt block is pure iff every try expression inside it is
        # pure. This means a `pure fn` cannot use attempt as a sneaky path
        # to an intent call.
        for t in expr.tries:
            _check_expr(t, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    elif isinstance(expr, MatchExpr):
        # A match is pure iff the subject and every arm's pattern/body
        # are pure. Confidence guards are purely metadata — no need to
        # check them.
        _check_expr(expr.subject, fn_name=fn_name, pure_fns=pure_fns,
                    all_fns=all_fns, intents=intents)
        for arm in expr.arms:
            _check_expr(arm.pattern, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
            _check_expr(arm.body, fn_name=fn_name, pure_fns=pure_fns,
                        all_fns=all_fns, intents=intents)
    # Literals and Identifiers carry no forbidden operations.


def _call_name(call: Call) -> str | None:
    if isinstance(call.callee, Identifier):
        return call.callee.name
    return None  # field-access calls (e.g. a.b(...)) are not statically resolvable here


def _check_call_target(name: str, *, fn_name: str, pure_fns: set[str],
                       all_fns: dict[str, FnDecl], intents: set[str]) -> None:
    if name in _BANNED_FROM_PURE:
        raise PurityError(
            fn_name,
            f"'{name}' is forbidden in pure fns (can execute arbitrary AIL)",
        )
    if name in pure_fns:
        return   # pure-to-pure call — always OK
    if name in all_fns:
        raise PurityError(
            fn_name,
            f"cannot call non-pure fn '{name}' — declare '{name}' as `pure fn` or drop the pure contract",
        )
    if name in intents:
        raise PurityError(
            fn_name,
            f"cannot call intent '{name}' — intents invoke a language model",
        )
    if name in _PURE_BUILTINS:
        return   # trusted builtin
    # Unknown name: neither a declared fn/intent nor a known builtin. We
    # cannot prove it is pure, so reject. This is conservative and matches
    # the spirit of a structural contract: if you cannot verify, you fail.
    raise PurityError(
        fn_name,
        f"call to '{name}' cannot be verified pure (not a pure fn, not a trusted builtin)",
    )
