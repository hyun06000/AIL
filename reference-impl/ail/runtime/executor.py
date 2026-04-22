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
import math
from dataclasses import dataclass
from typing import Any, Optional

from ..parser.ast import (
    Program, IntentDecl, ContextDecl, EntryDecl, EffectDecl, EvolveDecl,
    ImportDecl, FnDecl,
    Assignment, ReturnStmt, PerformStmt, BranchStmt, WithContextStmt,
    ExprStmt, IfStmt, ForStmt,
    Literal, Identifier, FieldAccess, Call, BinaryOp, UnaryOp, ListLiteral,
    PerformExpr, MembershipOp, AttemptExpr, MatchExpr, MatchArm,
    Expr, Statement,
)
from .context import ContextStack, ContextResolver, ResolvedContext
from .trace import Trace
from .model import ModelAdapter, ModelResponse
from .evolution import EvolutionSupervisor
from .provenance import (
    Origin, LITERAL_ORIGIN,
    input_origin, fn_origin, intent_origin, builtin_origin, attempt_origin,
    effect_origin,
    parents_of,
)
from .parallel import plan_groups
from .calibration import Calibrator, default_calibrator
from ..stdlib import resolve as resolve_import, ImportResolutionError


@dataclass
class ConfidentValue:
    value: Any
    confidence: float
    origin: Origin = LITERAL_ORIGIN

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
                 ask_human=None, metric_fn=None, approve_review=None,
                 calibrator: Optional[Calibrator] = None):
        """
        Parameters:
          program       — compiled AIL program
          adapter       — language model adapter
          ask_human     — callable(question, expect=...) -> answer, for
                          perform human_ask and human_confirmation
          metric_fn     — optional callable(intent_name, result_value,
                          confidence) -> (metric, rollback_value). Returning
                          (None, None) suppresses evolution observation for
                          a given call. Used by evolve blocks to get
                          real-world feedback signals AND to feed the
                          calibrator.
          approve_review — callable(review_info) -> bool, for
                          `require review_by: human` gates
          calibrator    — optional Calibrator. When None, builds a
                          default one (in-memory, respects
                          AIL_CALIBRATION_PATH env var for persistence).
        """
        self.program = program
        self.adapter = adapter
        self.ctx_stack = ContextStack()
        self.trace = Trace()
        self.ask_human = ask_human or _default_ask_human
        self.metric_fn = metric_fn   # may be None; evolution then idles
        self.approve_review = approve_review or (lambda _info: False)
        self.calibrator = calibrator if calibrator is not None else default_calibrator()

        # index declarations
        self.intents: dict[str, IntentDecl] = {}
        self.contexts: dict[str, ContextDecl] = {}
        self.effects: dict[str, EffectDecl] = {}
        self.evolves: dict[str, EvolveDecl] = {}
        self.fns: dict[str, FnDecl] = {}
        self.imported_sources: list[str] = []  # for trace & debugging
        self._index_declarations(program.declarations)

        # Construct an EvolutionSupervisor per evolving intent, lazily on
        # first use. Per spec/04 they are stateful across calls within
        # this executor's lifetime.
        self.supervisors: dict[str, EvolutionSupervisor] = {}

        self.resolver = ContextResolver(self)
        self._resolved_cache: dict[str, ResolvedContext] = {}

        # Ensure 'default' exists
        if "default" not in self.contexts:
            self.contexts["default"] = _default_context()

    def _index_declarations(self, decls, _visiting: set[str] | None = None) -> None:
        """Index declarations, resolving imports recursively.

        A local declaration shadows any imported one of the same name —
        the program's own code is authoritative. Imports are processed
        in order; an import cycle raises ImportResolutionError rather
        than silently dropping later imports.
        """
        _visiting = _visiting or set()

        for d in decls:
            if isinstance(d, ImportDecl):
                if d.source in _visiting:
                    raise ImportResolutionError(
                        f"import cycle detected at '{d.source}'"
                    )
                _visiting.add(d.source)
                try:
                    imported_program = resolve_import(d.source)
                except ImportResolutionError:
                    raise
                self.imported_sources.append(d.source)
                # Recursively index the imported program's declarations
                # so its own imports also resolve. Imports merge under
                # the imported program's own names; only symbols whose
                # name matches `d.symbol` are kept from that import.
                self._index_declarations(
                    imported_program.declarations, _visiting,
                )
                # After recursion, narrow to the requested symbol if
                # the import named a single one. For the MVP we import
                # the whole module — `d.symbol` is recorded but not
                # used to filter, because fine-grained filtering is a
                # separate feature and the bundled stdlib is curated.
                _visiting.discard(d.source)
                continue

            if isinstance(d, IntentDecl):
                # Local declarations win over imported ones
                self.intents[d.name] = d
            elif isinstance(d, ContextDecl):
                self.contexts[d.name] = d
            elif isinstance(d, EffectDecl):
                self.effects[d.name] = d
            elif isinstance(d, EvolveDecl):
                self.evolves[d.intent_name] = d
            elif isinstance(d, FnDecl):
                self.fns[d.name] = d

    # --- evolution helpers ---

    def _get_supervisor(self, intent_name: str) -> EvolutionSupervisor | None:
        """Return the supervisor for an intent, creating it if needed.

        Returns None if the intent has no evolve declaration.
        """
        if intent_name not in self.evolves:
            return None
        sup = self.supervisors.get(intent_name)
        if sup is None:
            sup = EvolutionSupervisor(
                self.evolves[intent_name],
                approve_review=self.approve_review,
                intent_decl=self.intents.get(intent_name),
            )
            self.supervisors[intent_name] = sup
        return sup

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
                local_scope[param_name] = ConfidentValue(
                    inputs[param_name], 1.0, origin=input_origin(param_name))
            else:
                local_scope[param_name] = ConfidentValue(
                    None, 1.0, origin=input_origin(param_name))

        try:
            self._exec_block(entry.body, local_scope)
        except ReturnSignal as r:
            return r.value

        return ConfidentValue(None, 1.0)

    # --- statement-block execution (with implicit parallelism) ---

    def _exec_block(self, stmts: list[Statement],
                    scope: dict[str, ConfidentValue]) -> None:
        """Execute a sequence of statements.

        Consecutive Assignments whose RHS contain intent calls and are
        pairwise independent are grouped into a parallel batch and issued
        concurrently via a ThreadPoolExecutor. All other statements run
        in source order. See runtime/parallel.py for the analysis rules.
        """
        groups = plan_groups(stmts, set(self.intents.keys()))
        for group in groups:
            if group.parallel:
                self._exec_parallel_batch(group.stmts, scope)
            else:
                for s in group.stmts:
                    self._exec_stmt(s, scope)

    def _exec_parallel_batch(self, assignments: list[Statement],
                             scope: dict[str, ConfidentValue]) -> None:
        """Evaluate a batch of independent Assignments concurrently.

        Each RHS is evaluated against a snapshot of the scope taken at
        batch start; this means no sibling's result is visible during
        evaluation. Results are committed back to the real scope in
        source order after all evaluations complete. Source order
        preserves determinism of any side channels a user might rely on
        (though by construction there are none — parallel candidates
        have no perform statements).
        """
        from concurrent.futures import ThreadPoolExecutor

        scope_snapshot = dict(scope)
        names = [a.name for a in assignments]
        self.trace.record("parallel_batch_start", size=len(assignments),
                          names=names)

        def eval_one(assign):
            return self._eval_expr(assign.value, scope_snapshot)

        with ThreadPoolExecutor(max_workers=len(assignments)) as ex:
            results = list(ex.map(eval_one, assignments))

        for assign, val in zip(assignments, results):
            scope[assign.name] = val
            self.trace.record("assignment", name=assign.name,
                              value=val.value, confidence=val.confidence,
                              parallel=True)
        self.trace.record("parallel_batch_end", size=len(assignments))

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
        elif isinstance(stmt, IfStmt):
            self._exec_if(stmt, scope)
        elif isinstance(stmt, ForStmt):
            self._exec_for(stmt, scope)
        elif isinstance(stmt, ExprStmt):
            self._eval_expr(stmt.expr, scope)
        else:
            raise RuntimeError(f"unknown statement type: {type(stmt).__name__}")

    def _exec_with(self, stmt: WithContextStmt, scope: dict[str, ConfidentValue]) -> None:
        ctx = self.resolve_context(stmt.context_name)
        self.ctx_stack.push(ctx)
        self.trace.record("context_push", name=ctx.name, chain=ctx.chain)
        try:
            self._exec_block(stmt.body, scope)
        finally:
            self.ctx_stack.pop()
            self.trace.record("context_pop", name=ctx.name)

    def _exec_if(self, stmt: IfStmt, scope: dict[str, ConfidentValue]) -> None:
        cond = self._eval_expr(stmt.condition, scope)
        if _truthy(cond):
            self._exec_block(stmt.then_body, scope)
        else:
            self._exec_block(stmt.else_body, scope)

    def _exec_for(self, stmt: ForStmt, scope: dict[str, ConfidentValue]) -> None:
        collection = self._eval_expr(stmt.collection, scope)
        items = collection.value
        if not hasattr(items, '__iter__') or isinstance(items, str):
            items = [items]
        for item in items:
            scope[stmt.var_name] = ConfidentValue(
                item, collection.confidence, origin=collection.origin)
            self._exec_block(stmt.body, scope)

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
        """Dispatch a perform call to the right effect implementation.

        Every effect wraps its result with `effect_origin(name, parents)`
        so programs can query via `has_effect_origin(value)` whether a
        given value's history involved a side-effecting operation.
        Parents are the arg origins — an effect consuming an LLM result
        (via intent) correctly shows `intent` upstream of `effect`.
        """
        origin = effect_origin(name, parents_of(args))

        if name in ("human_ask", "ask_human"):
            question = (args[0].value if args else kwargs.get("question", ConfidentValue("?", 1.0)).value)
            answer = self.ask_human(str(question), expect="text")
            return ConfidentValue(answer, 1.0, origin=origin)
        if name == "log":
            msg = (args[0].value if args else "")
            print(f"[log] {msg}")
            return ConfidentValue(None, 1.0, origin=origin)
        if name == "http.get":
            return self._http_effect("GET", args, kwargs, origin)
        if name == "http.post":
            return self._http_effect("POST", args, kwargs, origin)
        if name == "file.read":
            return self._file_read(args, kwargs, origin)
        if name == "file.write":
            return self._file_write(args, kwargs, origin)
        if name == "clock.now":
            return self._clock_now(args, kwargs, origin)
        raise RuntimeError(
            f"unknown effect: {name} "
            f"(supported: human_ask, log, http.get, http.post, "
            f"file.read, file.write, clock.now, or a declared effect)"
        )

    # --- clock effect (L2 case study 2026-04-23 — fills the "hardcoded
    # timestamp" gap authors hit when INTENT.md mentions "현재 시각").
    def _clock_now(self, args: list[ConfidentValue],
                   kwargs: dict[str, ConfidentValue],
                   origin: Origin) -> ConfidentValue:
        """Return the current wall-clock time as an ISO-8601 UTC string.

        Shape:
            perform clock.now()            -> "2026-04-23T15:02:34Z"
            perform clock.now("iso")       -> same as above
            perform clock.now("unix")      -> "1776879154" (seconds since epoch)

        Returning a plain Text (not a Result) because clock access does
        not fail on any platform we support. The value carries an
        effect-origin node so provenance queries can tell that a
        timestamp came from clock.now rather than being hardcoded.

        Deliberately no `tz` argument in v0 — non-developers won't
        know to pass one, and UTC is the right default. A pure fn
        library can format for a locale later.
        """
        import time
        fmt = (args[0].value if args else "iso")
        if isinstance(fmt, str):
            fmt = fmt.lower()
        if fmt in ("unix", "epoch", "seconds"):
            value = str(int(time.time()))
        else:
            # iso / default
            value = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return ConfidentValue(value, 1.0, origin=origin)

    # --- effect implementations ---

    def _http_effect(self, method: str, args: list[ConfidentValue],
                     kwargs: dict[str, ConfidentValue],
                     origin: Origin) -> ConfidentValue:
        """HTTP GET/POST using urllib.

        Returns a Record (dict) with `status` (Number), `body` (Text),
        and `ok` (Boolean for status in 200..299). Confidence is 1.0 on
        a successful round trip, 0.0 on network error — the caller can
        thread through an `attempt` block to fall back. Non-2xx is NOT
        confidence 0 by itself; an API returning 404 is a real response,
        not a broken pipe.
        """
        import urllib.request
        import urllib.error
        url = str(args[0].value) if args else str(kwargs.get("url", ConfidentValue("", 1.0)).value)
        body = None
        if method == "POST":
            if len(args) >= 2:
                body = args[1].value
            elif "body" in kwargs:
                body = kwargs["body"].value
        try:
            req = urllib.request.Request(
                url, method=method,
                data=(str(body).encode("utf-8") if body is not None else None),
                headers={"User-Agent": "ail-http-effect/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                status = float(resp.status)
            # Record shape: raw values (not ConfidentValue). FieldAccess
            # will wrap each in a ConfidentValue carrying the target's
            # confidence/origin, so the response fields inherit the
            # effect origin automatically.
            result = {
                "status": status,
                "body": content,
                "ok": 200 <= status < 300,
            }
            return ConfidentValue(result, 1.0, origin=origin)
        except urllib.error.HTTPError as e:
            # HTTPError carries a status — still a real response.
            status = float(e.code)
            try:
                content = e.read().decode("utf-8", errors="replace")
            except Exception:
                content = ""
            result = {
                "status": status,
                "body": content,
                "ok": False,
            }
            return ConfidentValue(result, 1.0, origin=origin)
        except urllib.error.URLError as e:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": f"http {method} {url}: {e}"},
                0.0, origin=origin,
            )

    def _file_read(self, args: list[ConfidentValue],
                   kwargs: dict[str, ConfidentValue],
                   origin: Origin) -> ConfidentValue:
        """Read a text file. Returns Text on success, Result-error on failure."""
        path = str(args[0].value) if args else str(kwargs.get("path", ConfidentValue("", 1.0)).value)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return ConfidentValue(f.read(), 1.0, origin=origin)
        except OSError as e:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": f"file.read {path}: {e}"},
                0.0, origin=origin,
            )

    def _file_write(self, args: list[ConfidentValue],
                    kwargs: dict[str, ConfidentValue],
                    origin: Origin) -> ConfidentValue:
        """Write text to a file. Returns Result-ok on success, Result-error on failure."""
        path = str(args[0].value) if args else str(kwargs.get("path", ConfidentValue("", 1.0)).value)
        content = args[1].value if len(args) >= 2 else kwargs.get("content", ConfidentValue("", 1.0)).value
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(content))
            return ConfidentValue(
                {"_result": True, "ok": True, "value": path},
                1.0, origin=origin,
            )
        except OSError as e:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": f"file.write {path}: {e}"},
                0.0, origin=origin,
            )

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
                return ConfidentValue(target.value.get(expr.field), target.confidence,
                                      origin=target.origin)
            return ConfidentValue(getattr(target.value, expr.field, None),
                                  target.confidence, origin=target.origin)
        if isinstance(expr, ListLiteral):
            vals = [self._eval_expr(i, scope) for i in expr.items]
            items = [v.value for v in vals]
            conf = min((v.confidence for v in vals), default=1.0)
            return ConfidentValue(items, conf, origin=_dominant_origin(*vals))
        if isinstance(expr, BinaryOp):
            left = self._eval_expr(expr.left, scope)
            right = self._eval_expr(expr.right, scope)
            merged_origin = _dominant_origin(left, right)
            if expr.op == "and":
                return ConfidentValue(_truthy(left) and _truthy(right),
                                      min(left.confidence, right.confidence),
                                      origin=merged_origin)
            if expr.op == "or":
                return ConfidentValue(_truthy(left) or _truthy(right),
                                      max(left.confidence, right.confidence),
                                      origin=merged_origin)
            try:
                out = _apply_binop(expr.op, left.value, right.value)
            except Exception:
                out = None
            return ConfidentValue(out, min(left.confidence, right.confidence),
                                  origin=merged_origin)
        if isinstance(expr, UnaryOp):
            operand = self._eval_expr(expr.operand, scope)
            if expr.op == "not":
                return ConfidentValue(not _truthy(operand), operand.confidence,
                                      origin=operand.origin)
            if expr.op == "-":
                return ConfidentValue(-operand.value, operand.confidence,
                                      origin=operand.origin)
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
            return ConfidentValue(result, min(elem.confidence, coll.confidence),
                                  origin=_dominant_origin(elem, coll))
        if isinstance(expr, PerformExpr):
            # perform-as-expression: build a transient PerformStmt and execute
            return self._exec_perform(
                PerformStmt(effect=expr.effect, args=expr.args, kwargs=expr.kwargs),
                scope,
            )
        if isinstance(expr, AttemptExpr):
            return self._eval_attempt(expr, scope)
        if isinstance(expr, MatchExpr):
            return self._eval_match(expr, scope)
        raise RuntimeError(f"unknown expr type: {type(expr).__name__}")

    def _eval_match(self, expr: MatchExpr,
                    scope: dict[str, ConfidentValue]) -> ConfidentValue:
        """Evaluate a match expression.

        Semantics:
          1. Evaluate the subject ONCE.
          2. For each arm in source order:
             - Check the pattern against the subject's value.
             - If pattern matches and (optional) confidence guard
               holds, evaluate the arm's body in a scope extended
               with any binding from the pattern, and return its value.
          3. If no arm matches, return a Result-error — the match was
             non-exhaustive at runtime. Programs concerned about this
             should end with a `_ =>` arm.

        The body's origin is preserved unchanged (no new match-origin
        node is introduced) — the match itself is a selection, not a
        new operation, and wrapping would clutter lineage queries.
        """
        subject = self._eval_expr(expr.subject, scope)
        self.trace.record("match_enter",
                          value=_truncate(subject.value),
                          confidence=subject.confidence,
                          arms=len(expr.arms))
        for idx, arm in enumerate(expr.arms):
            match_ok, binding = _pattern_matches(arm.pattern, subject)
            if not match_ok:
                continue
            if not _confidence_guard_passes(arm, subject.confidence):
                self.trace.record("match_arm_skipped",
                                  index=idx,
                                  reason="confidence_guard",
                                  confidence=subject.confidence,
                                  required_op=arm.confidence_op,
                                  required_threshold=arm.confidence_threshold)
                continue
            self.trace.record("match_arm_selected", index=idx)
            arm_scope = dict(scope)
            if binding is not None:
                arm_scope[binding] = subject
            return self._eval_expr(arm.body, arm_scope)
        # No arm matched — surface as a Result error for the caller.
        self.trace.record("match_no_arm")
        return ConfidentValue(
            {"_result": True, "ok": False,
             "error": f"match: no arm matched value {subject.value!r} "
                      f"(confidence {subject.confidence:.3f})"},
            0.0,
            origin=subject.origin,
        )

    def _eval_attempt(self, expr: AttemptExpr,
                      scope: dict[str, ConfidentValue]) -> ConfidentValue:
        """Evaluate an attempt block: confidence-priority cascade.

        Evaluate each try in order. A try qualifies when:
          - its value is not a Result-typed error, AND
          - its confidence is >= the block's threshold.
        First qualifying try wins. If none qualify, return the last try's
        result as-is (low confidence propagates to the caller). The final
        value is wrapped with an attempt_origin so the selected index and
        upstream lineage are queryable at runtime.
        """
        self.trace.record("attempt_enter", threshold=expr.threshold,
                          tries=len(expr.tries))
        last: ConfidentValue | None = None
        for idx, try_expr in enumerate(expr.tries):
            candidate = self._eval_expr(try_expr, scope)
            last = candidate
            if _is_result_error(candidate.value):
                self.trace.record("attempt_try_skipped",
                                  index=idx, reason="result_error")
                continue
            if candidate.confidence < expr.threshold:
                self.trace.record("attempt_try_skipped",
                                  index=idx, reason="low_confidence",
                                  confidence=candidate.confidence)
                continue
            self.trace.record("attempt_selected", index=idx,
                              confidence=candidate.confidence)
            return ConfidentValue(
                candidate.value, candidate.confidence,
                origin=attempt_origin(idx, candidate.origin),
            )
        # Fall-through: no try qualified.
        self.trace.record("attempt_exhausted",
                          fallback_index=len(expr.tries) - 1)
        if last is None:   # unreachable given parser guarantees >=1 try
            return ConfidentValue(None, 0.0)
        return ConfidentValue(
            last.value, last.confidence,
            origin=attempt_origin(len(expr.tries) - 1, last.origin),
        )

    def _eval_call(self, call: Call, scope: dict[str, ConfidentValue]) -> ConfidentValue:
        # Resolve callee name
        if isinstance(call.callee, Identifier):
            name = call.callee.name
        elif isinstance(call.callee, FieldAccess):
            name = self._expr_as_str(call.callee)
        else:
            raise RuntimeError(f"cannot call non-identifier: {call.callee}")

        # Evaluate arguments
        args = [self._eval_expr(a, scope) for a in call.args]
        kwargs = {k: self._eval_expr(v, scope) for k, v in call.kwargs.items()}

        # Provenance-introspection builtins — resolved before normal dispatch
        # so a user cannot shadow them with a fn or intent of the same name.
        if name == "origin_of":
            return self._provenance_origin_of(args)
        if name == "lineage_of":
            return self._provenance_lineage_of(args)
        if name == "has_intent_origin":
            return self._provenance_has_intent(args)
        if name == "has_effect_origin":
            return self._provenance_has_effect(args)
        if name == "calibration_of":
            return self._calibration_of(args)

        # Is it a declared fn (pure deterministic)?
        if name in self.fns:
            return self._invoke_fn(self.fns[name], args, kwargs)

        # Is it a declared intent (LLM-backed)?
        if name in self.intents:
            return self._invoke_intent(self.intents[name], args, kwargs)

        # Built-in functions (spec/07 §5)
        builtin_result = self._try_builtin_fn(name, args)
        if builtin_result is not None:
            # Wrap with provenance so we can trace that this value
            # originated from a builtin call; parents are the arg origins.
            return ConfidentValue(
                builtin_result.value,
                builtin_result.confidence,
                origin=builtin_origin(name, parents_of(args)),
            )

        # Symbolic fallback (constraint checks etc.)
        return self._builtin_call(name, args, kwargs)

    def _invoke_fn(self, fn_decl: FnDecl,
                   args: list[ConfidentValue],
                   kwargs: dict[str, ConfidentValue]) -> ConfidentValue:
        """Execute a pure fn. No LLM, confidence always 1.0."""
        self.trace.record("fn_call", name=fn_decl.name,
                          args=[a.value for a in args])
        # Bind params
        local: dict[str, ConfidentValue] = {}
        for (pname, _), argval in zip(fn_decl.params, args):
            local[pname] = argval
        for k, v in kwargs.items():
            local[k] = v
        # Provenance: the fn-call origin wraps whatever the body returns.
        # Parents are the origins of the arguments (literal args filtered out).
        call_origin = fn_origin(fn_decl.name, parents_of(args))
        # Make other fns and intents callable from within this fn
        # by sharing the executor scope lookup
        try:
            self._exec_block(fn_decl.body, local)
        except ReturnSignal as r:
            return ConfidentValue(r.value.value, r.value.confidence,
                                  origin=call_origin)
        return ConfidentValue(None, 1.0, origin=call_origin)

    def _try_builtin_fn(self, name: str,
                        args: list[ConfidentValue]) -> ConfidentValue | None:
        """Built-in functions from spec/07 §5. Returns None if not a builtin."""
        raw = [a.value for a in args]
        conf = min((a.confidence for a in args), default=1.0)

        # --- Text operations ---
        if name == "length":
            if raw and hasattr(raw[0], '__len__'):
                return ConfidentValue(len(raw[0]), conf)
        if name == "split":
            if len(raw) >= 2 and isinstance(raw[0], str):
                delim = str(raw[1])
                if delim == "":
                    # Character-level split
                    return ConfidentValue(list(raw[0]), conf)
                return ConfidentValue(raw[0].split(delim), conf)
        if name == "join":
            if len(raw) >= 2 and isinstance(raw[0], list):
                return ConfidentValue(str(raw[1]).join(str(x) for x in raw[0]), conf)
        if name == "trim":
            if raw and isinstance(raw[0], str):
                return ConfidentValue(raw[0].strip(), conf)
        if name == "upper":
            if raw and isinstance(raw[0], str):
                return ConfidentValue(raw[0].upper(), conf)
        if name == "lower":
            if raw and isinstance(raw[0], str):
                return ConfidentValue(raw[0].lower(), conf)
        if name == "starts_with":
            if len(raw) >= 2:
                return ConfidentValue(str(raw[0]).startswith(str(raw[1])), conf)
        if name == "ends_with":
            if len(raw) >= 2:
                return ConfidentValue(str(raw[0]).endswith(str(raw[1])), conf)
        if name == "replace":
            if len(raw) >= 3 and isinstance(raw[0], str):
                return ConfidentValue(raw[0].replace(str(raw[1]), str(raw[2])), conf)
        if name == "slice":
            if len(raw) >= 3:
                return ConfidentValue(raw[0][int(raw[1]):int(raw[2])], conf)

        # --- List operations ---
        if name == "get":
            # get(list_or_record, index_or_key) -> single element
            if len(raw) >= 2:
                coll = raw[0]
                key = raw[1]
                if isinstance(coll, list):
                    idx = int(key)
                    if 0 <= idx < len(coll):
                        return ConfidentValue(coll[idx], conf)
                    return ConfidentValue(None, conf)
                if isinstance(coll, dict):
                    return ConfidentValue(coll.get(str(key)), conf)
        if name == "append":
            if len(raw) >= 2 and isinstance(raw[0], list):
                return ConfidentValue(raw[0] + [raw[1]], conf)
        if name == "sort":
            if raw and isinstance(raw[0], list):
                return ConfidentValue(sorted(raw[0]), conf)
        if name == "reverse":
            if raw and isinstance(raw[0], list):
                return ConfidentValue(list(reversed(raw[0])), conf)
        if name == "range":
            if len(raw) >= 2:
                return ConfidentValue(list(range(int(raw[0]), int(raw[1]))), conf)
        if name == "map" and len(raw) >= 2 and isinstance(raw[0], list):
            # map(list, fn_name) — fn_name must be a ConfidentValue wrapping a string
            fn_name = args[1].value
            if isinstance(fn_name, str) and fn_name in self.fns:
                results = []
                for item in raw[0]:
                    r = self._invoke_fn(self.fns[fn_name], [ConfidentValue(item, conf)], {})
                    results.append(r.value)
                return ConfidentValue(results, conf)
        if name == "filter" and len(raw) >= 2 and isinstance(raw[0], list):
            fn_name = args[1].value
            if isinstance(fn_name, str) and fn_name in self.fns:
                results = []
                for item in raw[0]:
                    r = self._invoke_fn(self.fns[fn_name], [ConfidentValue(item, conf)], {})
                    if _truthy(r):
                        results.append(item)
                return ConfidentValue(results, conf)
        if name == "reduce" and len(raw) >= 3 and isinstance(raw[0], list):
            fn_name = args[1].value
            if isinstance(fn_name, str) and fn_name in self.fns:
                acc = raw[2]
                for item in raw[0]:
                    r = self._invoke_fn(
                        self.fns[fn_name],
                        [ConfidentValue(acc, conf), ConfidentValue(item, conf)], {},
                    )
                    acc = r.value
                return ConfidentValue(acc, conf)

        # --- Conversion ---
        if name == "to_number":
            try:
                return ConfidentValue(float(raw[0]), conf)
            except (ValueError, TypeError):
                return ConfidentValue(
                    {"_result": True, "ok": False, "error": f"cannot convert to number: {raw[0]}"},
                    conf)
        if name == "to_text":
            if not raw:
                return ConfidentValue("", conf)
            v = raw[0]
            # AIL boolean literals are lowercase `true` / `false` per
            # spec/08 line 160. Python's `str(True)` renders "True",
            # diverging from the Go runtime and from the grammar's own
            # literal form. Force lowercase.
            if isinstance(v, bool):
                return ConfidentValue("true" if v else "false", conf)
            # Number in AIL is backed by float in Python, so `to_text(5)`
            # of a whole number naturally prints as "5.0". That makes
            # output ugly and — more importantly — breaks conformance
            # with the Go runtime, which prints integer-valued numbers
            # without the trailing `.0`. Match Go's shape here.
            if isinstance(v, float) and v.is_integer():
                return ConfidentValue(str(int(v)), conf)
            return ConfidentValue(str(v), conf)
        if name == "to_boolean":
            return ConfidentValue(bool(raw[0]) if raw else False, conf)

        # --- Math ---
        if name == "abs":
            if raw:
                return ConfidentValue(abs(raw[0]), conf)
        if name == "max":
            if raw and isinstance(raw[0], list):
                return ConfidentValue(max(raw[0]), conf)
        if name == "min":
            if raw and isinstance(raw[0], list):
                return ConfidentValue(min(raw[0]), conf)
        if name == "round":
            if len(raw) >= 2:
                return ConfidentValue(round(raw[0], int(raw[1])), conf)
            if raw:
                return ConfidentValue(round(raw[0]), conf)
        if name == "floor":
            if raw:
                return ConfidentValue(math.floor(raw[0]), conf)
        if name == "ceil":
            if raw:
                return ConfidentValue(math.ceil(raw[0]), conf)
        if name == "sqrt":
            if raw:
                v = raw[0]
                if v < 0:
                    return ConfidentValue(
                        {"_result": True, "ok": False,
                         "error": f"sqrt: negative argument {v}"}, conf)
                return ConfidentValue(math.sqrt(v), conf)
        if name == "pow":
            if len(raw) >= 2:
                return ConfidentValue(raw[0] ** raw[1], conf)

        # --- Meta ---
        if name == "eval_ail":
            # eval_ail(source: Text, input: Text) -> Any
            # Parses an AIL source string and executes its entry with the given input.
            # This is the primitive that makes AIL self-generating.
            if len(raw) >= 1 and isinstance(raw[0], str):
                source_text = raw[0]
                eval_input = raw[1] if len(raw) >= 2 else ""
                return self._eval_ail_source(source_text, eval_input, conf)

        if name == "parse_json":
            # parse_json(source: Text) -> Result[Any]
            # Pure. Parses a JSON string using stdlib json.loads. Returns
            # ok(parsed) on success (dict / list / str / number / bool / null
            # mapped to AIL Record / List / Text / Number / Boolean / 0).
            # error(msg) on any JSONDecodeError. Added for HEAAL E2 because
            # manual line-by-line JSON extraction failed on compact API
            # responses (GitHub API returns everything on one line).
            if len(raw) >= 1 and isinstance(raw[0], str):
                import json as _json
                try:
                    parsed = _json.loads(raw[0])
                    return ConfidentValue(
                        {"_result": True, "ok": True, "value": parsed}, conf)
                except Exception as e:
                    return ConfidentValue(
                        {"_result": True, "ok": False,
                         "error": f"{type(e).__name__}: {e}"}, conf)

        if name == "ail_parse_check":
            # ail_parse_check(source: Text) -> Result[Text]
            # Returns ok(source) if the given source parses as a valid AIL
            # program; error(message) otherwise. Pure: does NOT execute, does
            # NOT dispatch intents, has no side effects. Exists so that AIL
            # programs can evaluate other AIL programs' syntactic validity —
            # the primitive that HEAAL's self-hosting evaluator needs.
            if len(raw) >= 1 and isinstance(raw[0], str):
                src = raw[0]
                try:
                    from .. import compile_source
                    compile_source(src)
                    return ConfidentValue(
                        {"_result": True, "ok": True, "value": src}, conf)
                except Exception as e:
                    return ConfidentValue(
                        {"_result": True, "ok": False,
                         "error": f"{type(e).__name__}: {e}"}, conf)

        # --- Result type (v1.1) ---
        # ok(value) -> {"_result": True, "ok": True, "value": V}
        # error(msg) -> {"_result": True, "ok": False, "error": E}
        if name == "ok":
            if raw:
                return ConfidentValue(
                    {"_result": True, "ok": True, "value": raw[0]}, conf)
        if name == "error":
            if raw:
                return ConfidentValue(
                    {"_result": True, "ok": False, "error": raw[0]}, conf)
        if name == "is_ok":
            if raw and isinstance(raw[0], dict) and raw[0].get("_result"):
                return ConfidentValue(raw[0].get("ok", False), conf)
            return ConfidentValue(True, conf)
        if name == "is_error":
            if raw and isinstance(raw[0], dict) and raw[0].get("_result"):
                return ConfidentValue(not raw[0].get("ok", True), conf)
            return ConfidentValue(False, conf)
        if name == "unwrap":
            if raw and isinstance(raw[0], dict) and raw[0].get("_result"):
                if raw[0].get("ok"):
                    return ConfidentValue(raw[0]["value"], conf)
                else:
                    return ConfidentValue(
                        f"UNWRAP_ERROR: {raw[0].get('error', 'unknown')}", 0.0)
            return ConfidentValue(raw[0] if raw else None, conf)
        if name == "unwrap_error":
            if raw and isinstance(raw[0], dict) and raw[0].get("_result"):
                if not raw[0].get("ok"):
                    return ConfidentValue(raw[0].get("error", "unknown"), conf)
                else:
                    return ConfidentValue("NOT_AN_ERROR", 0.0)
            return ConfidentValue("NOT_A_RESULT", 0.0)
        if name == "unwrap_or":
            if len(raw) >= 2 and isinstance(raw[0], dict) and raw[0].get("_result"):
                if raw[0].get("ok"):
                    return ConfidentValue(raw[0]["value"], conf)
                else:
                    return ConfidentValue(raw[1], conf)
            return ConfidentValue(raw[0] if raw else None, conf)

        return None  # not a builtin

    def _eval_ail_source(self, source: str, input_val: Any,
                         parent_confidence: float) -> ConfidentValue:
        """Parse and execute an AIL source string. Used by eval_ail builtin."""
        from ..parser import parse, ParseError
        try:
            program = parse(source)
        except ParseError as e:
            self.trace.record("eval_ail_parse_error", error=str(e))
            return ConfidentValue(f"PARSE_ERROR: {e}", 0.0)
        entry = program.entry()
        if entry is None:
            return ConfidentValue("PARSE_ERROR: no entry declaration", 0.0)
        # Create a child executor sharing our adapter but with fresh state
        child = Executor(program, self.adapter, ask_human=self.ask_human,
                         metric_fn=self.metric_fn, approve_review=self.approve_review)
        try:
            first_param = entry.params[0][0] if entry.params else "input"
            result = child.run_entry({first_param: input_val})
            self.trace.record("eval_ail_success",
                              value=_truncate(result.value),
                              confidence=result.confidence)
            return result
        except Exception as e:
            self.trace.record("eval_ail_runtime_error", error=str(e))
            return ConfidentValue(f"RUNTIME_ERROR: {e}", 0.0)

    def _builtin_call(self, name: str, args: list[ConfidentValue],
                      kwargs: dict[str, ConfidentValue]) -> ConfidentValue:
        # Used mainly for symbolic constraint checks in MVP.
        # Returns True (confidence from args) — real AIRT would actually check.
        conf = min((a.confidence for a in args), default=1.0)
        return ConfidentValue(True, conf,
                              origin=builtin_origin(name, parents_of(args)))

    # --- provenance-introspection builtins ---

    def _provenance_origin_of(self, args: list[ConfidentValue]) -> ConfidentValue:
        """origin_of(value) -> Record describing the immediate origin node.

        Returns a dict with fields kind, name, model_id, at, parents (nested
        dicts). A literal's origin has kind="literal" and no parents.
        """
        if not args:
            return ConfidentValue(None, 1.0)
        o = args[0].origin
        return ConfidentValue(
            o.to_dict(), 1.0,
            origin=builtin_origin("origin_of", parents_of(args)),
        )

    def _provenance_lineage_of(self, args: list[ConfidentValue]) -> ConfidentValue:
        """lineage_of(value) -> [Record]

        Flattens the origin tree to a list of origin records (post-order).
        Useful for audit: iterate and check which operations produced the
        value.
        """
        if not args:
            return ConfidentValue([], 1.0)
        events = [o.to_dict() for o in args[0].origin.lineage()]
        return ConfidentValue(
            events, 1.0,
            origin=builtin_origin("lineage_of", parents_of(args)),
        )

    def _provenance_has_intent(self, args: list[ConfidentValue]) -> ConfidentValue:
        """has_intent_origin(value) -> Boolean

        True iff any node in the value's origin tree has kind="intent" —
        i.e., an LLM was involved somewhere in this value's history.
        """
        if not args:
            return ConfidentValue(False, 1.0)
        result = args[0].origin.has_kind("intent")
        return ConfidentValue(
            result, 1.0,
            origin=builtin_origin("has_intent_origin", parents_of(args)),
        )

    def _provenance_has_effect(self, args: list[ConfidentValue]) -> ConfidentValue:
        """has_effect_origin(value) -> Boolean

        True iff any node in the value's origin tree has kind="effect" —
        i.e., a `perform` (http, file, log, etc.) was involved in
        producing this value.
        """
        if not args:
            return ConfidentValue(False, 1.0)
        result = args[0].origin.has_kind("effect")
        return ConfidentValue(
            result, 1.0,
            origin=builtin_origin("has_effect_origin", parents_of(args)),
        )

    def _calibration_of(self, args: list[ConfidentValue]) -> ConfidentValue:
        """calibration_of(intent_name: Text) -> Record

        Returns the calibrator's per-bucket statistics for the named
        intent, shaped like:
            {
                "0.8-0.9": {"count": 12, "mean_observed": 0.71,
                            "calibrated": true},
                ...
            }
        Empty record if the intent has not been observed yet.

        Exposing this to AIL programs lets a program introspect its
        own belief quality at runtime — "if my classifier has no
        calibration data, fall back to a cheaper heuristic" is a
        real pattern this enables.
        """
        if not args:
            return ConfidentValue({}, 1.0,
                origin=builtin_origin("calibration_of", ()))
        intent_name = str(args[0].value)
        stats = self.calibrator.stats_for(intent_name)
        return ConfidentValue(
            stats, 1.0,
            origin=builtin_origin("calibration_of", parents_of(args)),
        )

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

            # Evolution: if this intent is evolving, inject the current
            # tuned parameters into the context. This is how the model
            # (and downstream logic) sees the effect of a retune.
            supervisor = self._get_supervisor(intent.name)
            if supervisor is not None:
                tuned = supervisor.active_parameters()
                if tuned:
                    context_dict["_evolved_parameters"] = dict(tuned)
                    context_dict["_evolve_version"] = supervisor.active_version_id
                    self.trace.record(
                        "evolution_version_active",
                        intent=intent.name,
                        version=supervisor.active_version_id,
                        parameters=tuned,
                    )

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

            raw = response.raw or {}
            self.trace.record("model_response",
                              model=response.model_id,
                              value=_truncate(response.value),
                              confidence=response.confidence,
                              prompt_tokens=raw.get("prompt_tokens") or raw.get("input_tokens") or 0,
                              completion_tokens=raw.get("completion_tokens") or raw.get("output_tokens") or 0)

            # Apply calibration: replace the model-reported confidence
            # with whatever past observations of this intent say the
            # true success rate is in this confidence band. If the
            # calibrator has not seen enough samples yet, the reported
            # value passes through unchanged.
            reported_conf = response.confidence
            applied_conf, was_calibrated = self.calibrator.apply(
                intent.name, reported_conf,
            )
            if was_calibrated:
                self.trace.record("calibration_applied",
                                  intent=intent.name,
                                  reported=reported_conf,
                                  calibrated=applied_conf)

            # Low-confidence handler runs against the CALIBRATED value —
            # a user asking "if confidence < 0.6 bail out" wants that to
            # fire when the *calibrated* belief is below 0.6, which is
            # the closer-to-truth number.
            if intent.low_confidence_handler is not None:
                threshold, handler_body = intent.low_confidence_handler
                if applied_conf < threshold:
                    self.trace.record("low_confidence_handler",
                                      threshold=threshold,
                                      actual=applied_conf,
                                      reported=reported_conf)
                    handler_scope = dict(local)
                    try:
                        self._exec_block(handler_body, handler_scope)
                    except ReturnSignal as r:
                        # Observation still uses the REPORTED confidence
                        # for calibration bucket assignment — we want to
                        # learn from what the model claimed, not from
                        # what we already post-processed it to.
                        self._observe_evolution(intent.name, r.value.value,
                                                r.value.confidence,
                                                reported_confidence=reported_conf)
                        return r.value

            result = ConfidentValue(
                response.value,
                applied_conf,
                origin=intent_origin(intent.name, parents_of(args),
                                     model_id=response.model_id),
            )

            # Feed supervisor AND calibrator. The reported_confidence
            # parameter preserves the pre-calibration number so buckets
            # remain indexed by what the model claimed (calibration's
            # learning signal would collapse otherwise).
            self._observe_evolution(intent.name, result.value,
                                    result.confidence,
                                    reported_confidence=reported_conf)

            return result
        finally:
            self.trace.exit()

    def _observe_evolution(self, intent_name: str,
                           value: Any, confidence: float,
                           reported_confidence: Optional[float] = None) -> None:
        """Feed the supervisor a metric sample AND the calibrator.

        `confidence` is the post-calibration value (what the program
        saw). `reported_confidence` is the pre-calibration model
        output; when None it defaults to `confidence`. The calibrator
        needs the REPORTED number to bucket observations correctly —
        learning a mapping from "what the model claimed" to "what
        actually happened."

        metric_fn is the primary source of the "what actually happened"
        signal. Its metric is [0, 1]-ish (we clamp inside the
        calibrator). If metric_fn is None, no calibration update
        occurs — we have no ground-truth signal to learn from, and
        stuffing `confidence` back in as its own metric would teach the
        calibrator nothing useful.
        """
        raw_reported = (reported_confidence
                        if reported_confidence is not None else confidence)
        sup = self._get_supervisor(intent_name)

        if self.metric_fn is not None:
            metric, rollback = self.metric_fn(intent_name, value, confidence)
            if metric is not None:
                self.calibrator.observe(intent_name, raw_reported, metric)
            if sup is not None:
                events = sup.observe(metric_value=metric, rollback_value=rollback)
                for ev in events:
                    payload = dict(ev.payload)
                    payload.setdefault("intent", intent_name)
                    self.trace.record(f"evolution_{ev.kind}", **payload)
            return

        # No metric_fn: evolution uses confidence as a self-signal for
        # backward compatibility; calibration stays silent (no
        # ground truth to learn from).
        if sup is None:
            return
        metric = confidence
        rollback = confidence
        events = sup.observe(metric_value=metric, rollback_value=rollback)
        for ev in events:
            # Avoid collision if the payload already carries 'intent'
            payload = dict(ev.payload)
            payload.setdefault("intent", intent_name)
            self.trace.record(f"evolution_{ev.kind}", **payload)


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
    if op == "%":
        return left % right
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


def _pattern_matches(pattern: Expr,
                     subject: "ConfidentValue") -> tuple[bool, str | None]:
    """Check whether a pattern matches the subject's value.

    Returns (matched, binding_name) where `binding_name` is non-None if
    the pattern introduces a variable binding (identifier other than `_`).

    v1 patterns:
      - Literal: exact equality with subject.value.
      - Identifier("_"): wildcard — always matches, no binding.
      - Identifier(other): variable binding — always matches, binds.

    Other expression types are rejected as invalid patterns. Restricting
    now keeps match semantics crisp; richer patterns (list, record) can
    be layered on without changing this base.
    """
    if isinstance(pattern, Literal):
        return (pattern.value == subject.value, None)
    if isinstance(pattern, Identifier):
        if pattern.name == "_":
            return (True, None)
        # Treat bools as literals even though they lex as identifiers.
        if pattern.name == "true":
            return (subject.value is True, None)
        if pattern.name == "false":
            return (subject.value is False, None)
        # Any other identifier is a variable binding.
        return (True, pattern.name)
    # Anything else is not a valid pattern shape in v1.
    raise RuntimeError(
        f"match pattern must be a literal, '_', or identifier; "
        f"got {type(pattern).__name__}"
    )


def _confidence_guard_passes(arm: MatchArm, subject_conf: float) -> bool:
    """Check the optional `with confidence OP N` guard on a match arm."""
    if arm.confidence_op is None or arm.confidence_threshold is None:
        return True
    op = arm.confidence_op
    t = arm.confidence_threshold
    if op == ">":
        return subject_conf > t
    if op == "<":
        return subject_conf < t
    if op == ">=":
        return subject_conf >= t
    if op == "<=":
        return subject_conf <= t
    if op == "==":
        return subject_conf == t
    return False


def _is_result_error(value: Any) -> bool:
    """True if `value` is a Result wrapping an error (i.e. error(...))."""
    return (isinstance(value, dict)
            and value.get("_result") is True
            and value.get("ok") is False)


def _dominant_origin(*values) -> Origin:
    """Return the first non-literal origin among the given ConfidentValues.

    If every argument is a literal, returns LITERAL_ORIGIN. Used by
    binary/unary/field operations that don't themselves create a new origin
    node but inherit from their operand's history. This keeps origin trees
    bounded in hot loops (a + b + c + ...) while preserving the essential
    lineage: the tracked operation that produced each value still carries
    its own origin node.
    """
    for v in values:
        o = v.origin if hasattr(v, "origin") else LITERAL_ORIGIN
        if o is not LITERAL_ORIGIN:
            return o
    return LITERAL_ORIGIN


def _default_ask_human(question: str, *, expect: str = "text") -> Any:
    """Default human prompt via stdin."""
    print(f"\n[ASK HUMAN] {question}")
    answer = input(f"  ({expect}) > ").strip()
    if expect == "yes/no":
        return answer.lower() in ("y", "yes", "true", "1")
    return answer
