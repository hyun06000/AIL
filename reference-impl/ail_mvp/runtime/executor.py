"""AIL MVP executor.

Executes an AIL program against a model adapter. Implements:
- Intent dispatch (MVP: single strategy — delegate to the model)
- Context activation and nested `with` scopes
- Confidence propagation and `on_low_confidence` handlers
- Branch dispatch by predicate satisfaction
- `perform` for a limited, built-in effect set
- Trace recording of every decision

Scope limits: no evolution, no calibration, no parallelism, no Authority
beyond a simple yes/no prompt for `human_confirmation`.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

from ..parser.ast import (
    Program, IntentDecl, ContextDecl, EntryDecl, EffectDecl,
    Assignment, ReturnStmt, PerformStmt, BranchStmt, WithContextStmt, ExprStmt,
    Literal, Identifier, FieldAccess, Call, BinaryOp, UnaryOp, ListLiteral,
    PerformExpr, MembershipOp,
    Expr, Statement,
)
from .context import ContextStack, ContextResolver, ResolvedContext
from .trace import Trace
from .model import ModelAdapter, ModelResponse


@dataclass
class ConfidentValue:
    value: Any
    confidence: float

    def __repr__(self):
        return f"{self.value!r} @ {self.confidence:.3f}"


class ReturnSignal(Exception):
    def __init__(self, value: ConfidentValue):
        self.value = value


class ConstraintViolation(Exception):
    def __init__(self, constraint: str, value: Any):
        self.constraint = constraint
        self.value = value
        super().__init__(f"constraint violated: {constraint}")


class Executor:
    def __init__(self, program: Program, adapter: ModelAdapter,
                 ask_human=None):
        self.program = program
        self.adapter = adapter
        self.ctx_stack = ContextStack()
        self.trace = Trace()
        self.ask_human = ask_human or _default_ask_human

        # index declarations
        self.intents: dict[str, IntentDecl] = {}
        self.contexts: dict[str, ContextDecl] = {}
        self.effects: dict[str, EffectDecl] = {}
        for d in program.declarations:
            if isinstance(d, IntentDecl):
                self.intents[d.name] = d
            elif isinstance(d, ContextDecl):
                self.contexts[d.name] = d
            elif isinstance(d, EffectDecl):
                self.effects[d.name] = d

        self.resolver = ContextResolver(self)
        self._resolved_cache: dict[str, ResolvedContext] = {}

        # Ensure 'default' exists
        if "default" not in self.contexts:
            self.contexts["default"] = _default_context()

    # --- constants for context field exprs ---

    def eval_const(self, expr: Expr) -> Any:
        """Evaluate a constant expression (context field values)."""
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, Identifier):
            # field values in context blocks reference named values; for MVP,
            # we treat bare identifiers as symbolic strings (e.g. "formal")
            if expr.name in ("true", "false"):
                return expr.name == "true"
            return expr.name                    # symbolic
        if isinstance(expr, ListLiteral):
            return [self.eval_const(i) for i in expr.items]
        if isinstance(expr, BinaryOp):
            if expr.op in (">>", ">>>", ">", "<", "==", "!="):
                # weight expressions — stored symbolically as a string
                left = self._expr_as_str(expr.left)
                right = self._expr_as_str(expr.right)
                return f"{left} {expr.op} {right}"
            left = self.eval_const(expr.left)
            right = self.eval_const(expr.right)
            return _apply_binop(expr.op, left, right)
        # Fall back to stringified form
        return self._expr_as_str(expr)

    def _expr_as_str(self, expr: Expr) -> str:
        if isinstance(expr, Literal):
            return repr(expr.value)
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, FieldAccess):
            return f"{self._expr_as_str(expr.target)}.{expr.field}"
        if isinstance(expr, ListLiteral):
            return "[" + ", ".join(self._expr_as_str(i) for i in expr.items) + "]"
        if isinstance(expr, BinaryOp):
            return f"{self._expr_as_str(expr.left)} {expr.op} {self._expr_as_str(expr.right)}"
        return str(expr)

    # --- context management ---

    def resolve_context(self, name: str) -> ResolvedContext:
        if name in self._resolved_cache:
            return self._resolved_cache[name]
        if name not in self.contexts:
            raise NameError(f"unknown context: {name}")
        ctx = self.resolver.resolve(self.contexts[name], self.contexts)
        self._resolved_cache[name] = ctx
        return ctx

    # --- program entry ---

    def run_entry(self, inputs: dict[str, Any]) -> ConfidentValue:
        entry = self.program.entry()
        if entry is None:
            raise RuntimeError("program has no entry declaration")

        # push default context first
        self.ctx_stack.push(self.resolve_context("default"))
        self.trace.record("context_push", name="default")

        local_scope: dict[str, ConfidentValue] = {}
        for param_name, _ in entry.params:
            if param_name in inputs:
                local_scope[param_name] = ConfidentValue(inputs[param_name], 1.0)
            else:
                local_scope[param_name] = ConfidentValue(None, 1.0)

        try:
            for stmt in entry.body:
                self._exec_stmt(stmt, local_scope)
        except ReturnSignal as r:
            return r.value

        return ConfidentValue(None, 1.0)

    # --- statement execution ---

    def _exec_stmt(self, stmt: Statement, scope: dict[str, ConfidentValue]) -> None:
        if isinstance(stmt, Assignment):
            val = self._eval_expr(stmt.value, scope)
            scope[stmt.name] = val
            self.trace.record("assignment", name=stmt.name, value=val.value, confidence=val.confidence)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is None:
                raise ReturnSignal(ConfidentValue(None, 1.0))
            raise ReturnSignal(self._eval_expr(stmt.value, scope))
        elif isinstance(stmt, PerformStmt):
            self._exec_perform(stmt, scope)
        elif isinstance(stmt, BranchStmt):
            self._exec_branch(stmt, scope)
        elif isinstance(stmt, WithContextStmt):
            self._exec_with(stmt, scope)
        elif isinstance(stmt, ExprStmt):
            self._eval_expr(stmt.expr, scope)
        else:
            raise RuntimeError(f"unknown statement type: {type(stmt).__name__}")

    def _exec_with(self, stmt: WithContextStmt, scope: dict[str, ConfidentValue]) -> None:
        ctx = self.resolve_context(stmt.context_name)
        self.ctx_stack.push(ctx)
        self.trace.record("context_push", name=ctx.name, chain=ctx.chain)
        try:
            for s in stmt.body:
                self._exec_stmt(s, scope)
        finally:
            self.ctx_stack.pop()
            self.trace.record("context_pop", name=ctx.name)

    def _exec_branch(self, stmt: BranchStmt, scope: dict[str, ConfidentValue]) -> None:
        subject_val = self._eval_expr(stmt.subject, scope)
        self.trace.record("branch_enter", subject=subject_val.value, confidence=subject_val.confidence)
        # MVP branching: evaluate each arm's predicate against subject
        for arm in stmt.arms:
            if isinstance(arm.condition, Identifier) and arm.condition.name == "otherwise":
                self.trace.record("branch_arm_selected", reason="otherwise")
                self._exec_stmt(arm.action, scope)
                return
            # Evaluate the arm condition with subject in scope under name '_subject'
            arm_scope = dict(scope)
            arm_scope["_subject"] = subject_val
            try:
                cond_val = self._eval_expr(arm.condition, arm_scope)
            except Exception as e:
                self.trace.record("branch_arm_error", error=str(e))
                continue
            if _truthy(cond_val):
                self.trace.record("branch_arm_selected",
                                  condition=str(arm.condition), confidence=cond_val.confidence)
                self._exec_stmt(arm.action, scope)
                return
        self.trace.record("branch_no_arm_matched")

    def _exec_perform(self, stmt: PerformStmt, scope: dict[str, ConfidentValue]) -> ConfidentValue:
        # Evaluate args
        args = [self._eval_expr(a, scope) for a in stmt.args]
        kwargs = {k: self._eval_expr(v, scope) for k, v in stmt.kwargs.items()}

        effect = self.effects.get(stmt.effect)
        if effect is None:
            # MVP: allow a small set of built-in effects without declaration
            result = self._builtin_effect(stmt.effect, args, kwargs)
            self.trace.record("perform", effect=stmt.effect, builtin=True,
                              result_confidence=result.confidence)
            return result

        self.trace.record("perform_start", effect=effect.name, authorization=effect.authorization)

        # Authorization
        if effect.authorization == "human_confirmation":
            summary = f"Effect '{effect.name}' with args {[a.value for a in args]} kwargs " \
                      f"{ {k: v.value for k, v in kwargs.items()} }"
            approved = self.ask_human(f"Authorize effect? {summary}", expect="yes/no")
            if not approved:
                self.trace.record("perform_denied", effect=effect.name)
                raise RuntimeError(f"effect {effect.name} denied by human")

        # MVP: builtin dispatch
        result = self._builtin_effect(effect.name, args, kwargs)
        self.trace.record("perform_done", effect=effect.name,
                          result_confidence=result.confidence)
        return result

    def _builtin_effect(self, name: str, args: list[ConfidentValue],
                        kwargs: dict[str, ConfidentValue]) -> ConfidentValue:
        if name in ("human_ask", "ask_human"):
            question = (args[0].value if args else kwargs.get("question", ConfidentValue("?", 1.0)).value)
            answer = self.ask_human(str(question), expect="text")
            return ConfidentValue(answer, 1.0)
        if name == "log":
            msg = (args[0].value if args else "")
            print(f"[log] {msg}")
            return ConfidentValue(None, 1.0)
        raise RuntimeError(f"unknown effect: {name} (MVP supports human_ask, log, or declared effects)")

    # --- expression evaluation ---

    def _eval_expr(self, expr: Expr, scope: dict[str, ConfidentValue]) -> ConfidentValue:
        if isinstance(expr, Literal):
            return ConfidentValue(expr.value, 1.0)
        if isinstance(expr, Identifier):
            if expr.name in scope:
                return scope[expr.name]
            # special: 'context' resolves to active context fields via FieldAccess
            if expr.name == "context":
                return ConfidentValue("<context>", 1.0)
            # Bare identifiers otherwise are symbols (used in constraints, e.g. "positive")
            return ConfidentValue(expr.name, 1.0)
        if isinstance(expr, FieldAccess):
            if isinstance(expr.target, Identifier) and expr.target.name == "context":
                val = self.ctx_stack.get(expr.field)
                return ConfidentValue(val, 1.0)
            target = self._eval_expr(expr.target, scope)
            if isinstance(target.value, dict):
                return ConfidentValue(target.value.get(expr.field), target.confidence)
            return ConfidentValue(getattr(target.value, expr.field, None), target.confidence)
        if isinstance(expr, ListLiteral):
            vals = [self._eval_expr(i, scope) for i in expr.items]
            items = [v.value for v in vals]
            conf = min((v.confidence for v in vals), default=1.0)
            return ConfidentValue(items, conf)
        if isinstance(expr, BinaryOp):
            left = self._eval_expr(expr.left, scope)
            right = self._eval_expr(expr.right, scope)
            if expr.op == "and":
                return ConfidentValue(_truthy(left) and _truthy(right),
                                      min(left.confidence, right.confidence))
            if expr.op == "or":
                return ConfidentValue(_truthy(left) or _truthy(right),
                                      max(left.confidence, right.confidence))
            try:
                out = _apply_binop(expr.op, left.value, right.value)
            except Exception:
                out = None
            return ConfidentValue(out, min(left.confidence, right.confidence))
        if isinstance(expr, UnaryOp):
            operand = self._eval_expr(expr.operand, scope)
            if expr.op == "not":
                return ConfidentValue(not _truthy(operand), operand.confidence)
            if expr.op == "-":
                return ConfidentValue(-operand.value, operand.confidence)
            return operand
        if isinstance(expr, Call):
            return self._eval_call(expr, scope)
        if isinstance(expr, MembershipOp):
            elem = self._eval_expr(expr.element, scope)
            coll = self._eval_expr(expr.collection, scope)
            # Collection may be a Python list, tuple, set, string, or dict keys
            try:
                contained = elem.value in coll.value
            except TypeError:
                # Non-iterable collection: treat as not contained
                contained = False
            result = (not contained) if expr.negated else contained
            # Confidence: min of element and collection (conservative, per spec/03 §3.1)
            return ConfidentValue(result, min(elem.confidence, coll.confidence))
        if isinstance(expr, PerformExpr):
            # perform-as-expression: build a transient PerformStmt and execute
            return self._exec_perform(
                PerformStmt(effect=expr.effect, args=expr.args, kwargs=expr.kwargs),
                scope,
            )
        raise RuntimeError(f"unknown expr type: {type(expr).__name__}")

    def _eval_call(self, call: Call, scope: dict[str, ConfidentValue]) -> ConfidentValue:
        # Resolve callee name
        if isinstance(call.callee, Identifier):
            name = call.callee.name
        elif isinstance(call.callee, FieldAccess):
            # e.g., confidence.and(...) — for MVP, flatten to name
            name = self._expr_as_str(call.callee)
        else:
            raise RuntimeError(f"cannot call non-identifier: {call.callee}")

        # Evaluate arguments
        args = [self._eval_expr(a, scope) for a in call.args]
        kwargs = {k: self._eval_expr(v, scope) for k, v in call.kwargs.items()}

        # Is it a declared intent?
        if name in self.intents:
            return self._invoke_intent(self.intents[name], args, kwargs)

        # Built-in pseudo-calls used inside constraints/branches
        return self._builtin_call(name, args, kwargs)

    def _builtin_call(self, name: str, args: list[ConfidentValue],
                      kwargs: dict[str, ConfidentValue]) -> ConfidentValue:
        # Used mainly for symbolic constraint checks in MVP.
        # Returns True (confidence from args) — real AIRT would actually check.
        conf = min((a.confidence for a in args), default=1.0)
        return ConfidentValue(True, conf)

    def _invoke_intent(
        self, intent: IntentDecl,
        args: list[ConfidentValue],
        kwargs: dict[str, ConfidentValue],
    ) -> ConfidentValue:
        self.trace.record("intent_call", name=intent.name,
                          args=[a.value for a in args])
        self.trace.enter()
        try:
            # Bind params to local scope
            local: dict[str, ConfidentValue] = {}
            for (pname, _), argval in zip(intent.params, args):
                local[pname] = argval
            for k, v in kwargs.items():
                local[k] = v

            # MVP dispatch: delegate to the model adapter
            context_dict = {}
            active = self.ctx_stack.active()
            if active is not None:
                context_dict = dict(active.fields)
            context_dict["_intent_name"] = intent.name

            goal_str = self._expr_as_str(intent.goal)
            constraints_str = [self._expr_as_str(c) for c in intent.constraints]
            example_pairs = []
            for inputs, out in intent.examples:
                example_pairs.append((
                    [self.eval_const(i) for i in inputs],
                    self.eval_const(out),
                ))

            self.trace.record("model_invoke", intent=intent.name, goal=goal_str,
                              constraints=constraints_str)

            response = self.adapter.invoke(
                goal=goal_str,
                constraints=constraints_str,
                context=context_dict,
                inputs={pname: local[pname].value for (pname, _) in intent.params if pname in local},
                expected_type=intent.return_type,
                examples=example_pairs or None,
            )

            self.trace.record("model_response",
                              model=response.model_id,
                              value=_truncate(response.value),
                              confidence=response.confidence)

            # Low-confidence handler
            if intent.low_confidence_handler is not None:
                threshold, handler_body = intent.low_confidence_handler
                if response.confidence < threshold:
                    self.trace.record("low_confidence_handler",
                                      threshold=threshold,
                                      actual=response.confidence)
                    handler_scope = dict(local)
                    try:
                        for s in handler_body:
                            self._exec_stmt(s, handler_scope)
                    except ReturnSignal as r:
                        return r.value

            return ConfidentValue(response.value, response.confidence)
        finally:
            self.trace.exit()


# --- utilities ---


def _default_context() -> ContextDecl:
    """Construct the minimum 'default' context when not declared."""
    return ContextDecl(
        name="default",
        extends=None,
        fields={
            "register": Literal(value="neutral"),
            "latency_budget": Literal(value=5000),
            "audience": Literal(value="general"),
        },
        overrides=set(),
    )


def _truthy(cv: ConfidentValue | Any) -> bool:
    v = cv.value if isinstance(cv, ConfidentValue) else cv
    return bool(v)


def _apply_binop(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    raise ValueError(f"unsupported binop: {op}")


def _truncate(v: Any, n: int = 200) -> Any:
    s = str(v)
    if len(s) <= n:
        return v
    return s[:n] + "…"


def _default_ask_human(question: str, *, expect: str = "text") -> Any:
    """Default human prompt via stdin."""
    print(f"\n[ASK HUMAN] {question}")
    answer = input(f"  ({expect}) > ").strip()
    if expect == "yes/no":
        return answer.lower() in ("y", "yes", "true", "1")
    return answer
