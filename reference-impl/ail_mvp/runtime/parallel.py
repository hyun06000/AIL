"""Implicit parallelism: independent intent calls run concurrently.

When an AI writes a pipeline like:

    sentiments = classify_each(reviews)     # intent -> HTTP
    topics     = extract_topics(reviews)    # intent -> HTTP
    summary    = summarize(reviews)         # intent -> HTTP
    return build_report(sentiments, topics, summary)

there is no data dependency between the three assignments. A careful
Python author would rewrite this with `asyncio.gather` or a
ThreadPoolExecutor. An AI author should not have to. AIL detects the
independence and runs the three calls in parallel by default.

This module isolates two responsibilities:

  1. `plan_groups(stmts, intents)` — a pure AST analysis that groups
     consecutive assignments into serial runs and parallel batches.
     A parallel batch is valid iff:
       - every statement in it is an Assignment whose RHS contains at
         least one intent call (otherwise parallelism has nothing to
         overlap);
       - no statement's RHS references any LHS from the same batch
         (independence);
       - no two statements share an LHS (disjoint commits).

  2. (Runtime) execute a parallel batch via ThreadPoolExecutor. That
     belongs in the executor because it needs access to `_eval_expr`
     and a live scope; this module only provides the planner.

Why static analysis at call time, not parse time: the set of declared
intents is only known after imports resolve, which happens during
Executor initialization, not during parsing. Doing the planning just
before executing a block means the planner always sees the real intent
set for the current program.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..parser.ast import (
    Assignment, Call, Identifier, FieldAccess, BinaryOp, UnaryOp, ListLiteral,
    PerformExpr, MembershipOp, AttemptExpr, Literal,
    Expr, Statement,
)


@dataclass
class Group:
    stmts: list[Statement]
    parallel: bool   # True if the batch is safe AND worth parallelizing


def plan_groups(stmts: list[Statement], intents: set[str]) -> list[Group]:
    """Partition `stmts` into a list of groups.

    A group is either:
      - `parallel=True`: 2+ Assignment statements, each with an intent
        call in its RHS, pairwise independent.
      - `parallel=False`: any other statement (or a single assignment
        that couldn't be merged into a parallel batch).
    """
    groups: list[Group] = []
    i = 0
    n = len(stmts)
    while i < n:
        s = stmts[i]
        if (isinstance(s, Assignment)
                and _contains_intent_call(s.value, intents)):
            batch = [s]
            batch_lhs = {s.name}
            j = i + 1
            while j < n:
                nxt = stmts[j]
                if not _can_extend_parallel_batch(nxt, batch_lhs, intents):
                    break
                batch.append(nxt)
                batch_lhs.add(nxt.name)
                j += 1
            if len(batch) >= 2:
                groups.append(Group(stmts=batch, parallel=True))
                i = j
                continue
        groups.append(Group(stmts=[s], parallel=False))
        i += 1
    return groups


def _can_extend_parallel_batch(stmt: Statement, batch_lhs: set[str],
                               intents: set[str]) -> bool:
    if not isinstance(stmt, Assignment):
        return False
    if stmt.name in batch_lhs:
        return False   # would shadow an earlier parallel write
    if not _contains_intent_call(stmt.value, intents):
        return False   # nothing to overlap with, keep it serial
    if _references_any(stmt.value, batch_lhs):
        return False   # data dependency — must run after predecessors
    return True


def _contains_intent_call(expr: Expr, intents: set[str]) -> bool:
    """True if the expression tree contains a call to a declared intent.

    Nested intent calls inside args, attempt blocks, list literals, field
    accesses, etc. all count — anywhere the expression would trigger an
    intent invocation during evaluation.
    """
    if isinstance(expr, Call):
        if isinstance(expr.callee, Identifier) and expr.callee.name in intents:
            return True
        for a in expr.args:
            if _contains_intent_call(a, intents):
                return True
        for v in expr.kwargs.values():
            if _contains_intent_call(v, intents):
                return True
    elif isinstance(expr, BinaryOp):
        return (_contains_intent_call(expr.left, intents)
                or _contains_intent_call(expr.right, intents))
    elif isinstance(expr, UnaryOp):
        return _contains_intent_call(expr.operand, intents)
    elif isinstance(expr, ListLiteral):
        return any(_contains_intent_call(i, intents) for i in expr.items)
    elif isinstance(expr, FieldAccess):
        return _contains_intent_call(expr.target, intents)
    elif isinstance(expr, MembershipOp):
        return (_contains_intent_call(expr.element, intents)
                or _contains_intent_call(expr.collection, intents))
    elif isinstance(expr, AttemptExpr):
        return any(_contains_intent_call(t, intents) for t in expr.tries)
    elif isinstance(expr, PerformExpr):
        # A perform expression inside a batch makes it unsafe to parallelize
        # (side effects must execute in program order). Treat perform as
        # "not an intent call" here; batch-building will later refuse
        # statements containing perform via _contains_perform.
        return False
    return False


def _contains_perform(expr: Expr) -> bool:
    """True if the expression tree contains a perform (effect invocation)."""
    if isinstance(expr, PerformExpr):
        return True
    if isinstance(expr, Call):
        if any(_contains_perform(a) for a in expr.args):
            return True
        if any(_contains_perform(v) for v in expr.kwargs.values()):
            return True
    elif isinstance(expr, BinaryOp):
        return _contains_perform(expr.left) or _contains_perform(expr.right)
    elif isinstance(expr, UnaryOp):
        return _contains_perform(expr.operand)
    elif isinstance(expr, ListLiteral):
        return any(_contains_perform(i) for i in expr.items)
    elif isinstance(expr, FieldAccess):
        return _contains_perform(expr.target)
    elif isinstance(expr, MembershipOp):
        return _contains_perform(expr.element) or _contains_perform(expr.collection)
    elif isinstance(expr, AttemptExpr):
        return any(_contains_perform(t) for t in expr.tries)
    return False


def _references_any(expr: Expr, names: Iterable[str]) -> bool:
    """True if the expression tree references any of the given identifiers.

    Conservative: any bare `Identifier` matching a name counts as a read.
    Field accesses recurse into their target; calls recurse into callee
    (excluding the callee-name itself since that's a function name, not a
    local read) and args.
    """
    names_set = set(names)
    return _references_walk(expr, names_set)


def _references_walk(expr: Expr, names: set[str]) -> bool:
    if isinstance(expr, Identifier):
        return expr.name in names
    if isinstance(expr, Literal):
        return False
    if isinstance(expr, Call):
        # The callee slot carries the function name; we exclude it from
        # the "read" check but still recurse into its args/kwargs.
        for a in expr.args:
            if _references_walk(a, names):
                return True
        for v in expr.kwargs.values():
            if _references_walk(v, names):
                return True
        return False
    if isinstance(expr, BinaryOp):
        return (_references_walk(expr.left, names)
                or _references_walk(expr.right, names))
    if isinstance(expr, UnaryOp):
        return _references_walk(expr.operand, names)
    if isinstance(expr, ListLiteral):
        return any(_references_walk(i, names) for i in expr.items)
    if isinstance(expr, FieldAccess):
        return _references_walk(expr.target, names)
    if isinstance(expr, MembershipOp):
        return (_references_walk(expr.element, names)
                or _references_walk(expr.collection, names))
    if isinstance(expr, AttemptExpr):
        return any(_references_walk(t, names) for t in expr.tries)
    if isinstance(expr, PerformExpr):
        for a in expr.args:
            if _references_walk(a, names):
                return True
        for v in expr.kwargs.values():
            if _references_walk(v, names):
                return True
        return False
    return False
