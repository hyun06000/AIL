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


# Depth limits for perform ail.run recursive execution.
# Warning is logged to trace; hard stop returns a Result-error.
_AIL_RUN_DEPTH_WARN = 3
_AIL_RUN_DEPTH_LIMIT = 8


class Executor:
    def __init__(self, program: Program, adapter: ModelAdapter,
                 ask_human=None, metric_fn=None, approve_review=None,
                 calibrator: Optional[Calibrator] = None,
                 _ail_run_depth: int = 0,
                 log_callback=None):
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
        self._ail_run_depth = _ail_run_depth
        self.log_callback = log_callback

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
            if self.log_callback is not None:
                try:
                    self.log_callback(str(msg))
                except Exception:
                    pass
            return ConfidentValue(None, 1.0, origin=origin)
        if name == "http.get":
            return self._http_effect("GET", args, kwargs, origin)
        if name == "http.post":
            return self._http_effect("POST", args, kwargs, origin)
        if name == "http.post_json":
            return self._http_post_json(args, kwargs, origin)
        if name == "http.graphql":
            return self._http_graphql(args, kwargs, origin)
        if name == "file.read":
            return self._file_read(args, kwargs, origin)
        if name == "file.write":
            return self._file_write(args, kwargs, origin)
        if name == "clock.now":
            return self._clock_now(args, kwargs, origin)
        if name == "state.read":
            return self._state_read(args, kwargs, origin)
        if name == "state.write":
            return self._state_write(args, kwargs, origin)
        if name == "state.has":
            return self._state_has(args, kwargs, origin)
        if name == "state.delete":
            return self._state_delete(args, kwargs, origin)
        if name == "schedule.every":
            return self._schedule_every(args, kwargs, origin)
        if name == "env.read":
            return self._env_read(args, kwargs, origin)
        if name == "human.approve":
            return self._human_approve(args, kwargs, origin)
        if name == "search.web":
            return self._search_web(args, kwargs, origin)
        if name == "ail.run":
            return self._ail_run(args, kwargs, origin)
        raise RuntimeError(
            f"unknown effect: {name} "
            f"(supported: human_ask, log, http.get, http.post, "
            f"http.post_json, http.graphql, file.read, file.write, "
            f"clock.now, state.read, state.write, state.has, "
            f"state.delete, schedule.every, env.read, human.approve, "
            f"search.web, ail.run, or a declared effect)"
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

    # --- state effect (L2 v2 case study Gap #4 — cross-request memory).
    # State is process-restart-safe key/value persistence. Each key maps
    # to a JSON file under the directory pointed at by AIL_STATE_DIR
    # (set by the agentic server to .ail/state/keyval/). Outside an
    # agentic project the env var is unset and every state effect
    # returns an explanatory error rather than crashing — a raw
    # `ail run` doesn't get a state dir for free.
    def _state_dir(self):
        import os, pathlib
        path = os.environ.get("AIL_STATE_DIR")
        if not path:
            return None
        d = pathlib.Path(path)
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        return d

    def _state_key_path(self, key: str):
        # Restrict keys to a conservative character set so a stray
        # "../" can't escape the state dir. Everything outside maps
        # to None which becomes a clean error to the caller.
        import re
        if not isinstance(key, str) or not key:
            return None
        if not re.match(r"^[A-Za-z0-9_\-.]+$", key):
            return None
        d = self._state_dir()
        if d is None:
            return None
        return d / f"{key}.json"

    def _result_ok(self, value, origin):
        return ConfidentValue(
            {"_result": True, "ok": True, "value": value},
            1.0, origin=origin,
        )

    def _result_err(self, message: str, origin):
        return ConfidentValue(
            {"_result": True, "ok": False, "error": message},
            1.0, origin=origin,
        )

    def _state_read(self, args, kwargs, origin):
        """state.read(key) -> Result[Any]"""
        import json as _json
        key = args[0].value if args else ""
        path = self._state_key_path(key)
        if path is None:
            if not self._state_dir():
                return self._result_err(
                    "state directory not configured (set AIL_STATE_DIR or "
                    "run inside an agentic project via `ail up`)", origin)
            return self._result_err(
                f"invalid state key: {key!r} "
                "(letters, digits, _ - . only)", origin)
        if not path.is_file():
            return self._result_err(
                f"state key {key!r} not set", origin)
        try:
            text = path.read_text(encoding="utf-8")
            value = _json.loads(text)
        except Exception as e:
            return self._result_err(
                f"could not read state {key!r}: "
                f"{type(e).__name__}: {e}", origin)
        return self._result_ok(value, origin)

    def _state_write(self, args, kwargs, origin):
        """state.write(key, value) -> Result[Boolean]

        Atomic via write-temp-then-rename. Value must JSON-serialize;
        AIL Text/Number/Boolean/List of those is fine."""
        import json as _json
        import os
        if len(args) < 2:
            return self._result_err(
                "state.write needs (key, value)", origin)
        key = args[0].value
        value = args[1].value
        path = self._state_key_path(key)
        if path is None:
            if not self._state_dir():
                return self._result_err(
                    "state directory not configured (set AIL_STATE_DIR or "
                    "run inside an agentic project via `ail up`)", origin)
            return self._result_err(
                f"invalid state key: {key!r} "
                "(letters, digits, _ - . only)", origin)
        try:
            payload = _json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            return self._result_err(
                f"value for {key!r} is not serializable: "
                f"{type(e).__name__}: {e}", origin)
        try:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, path)
        except OSError as e:
            return self._result_err(
                f"could not write state {key!r}: "
                f"{type(e).__name__}: {e}", origin)
        return self._result_ok(True, origin)

    def _state_has(self, args, kwargs, origin):
        """state.has(key) -> Boolean"""
        key = args[0].value if args else ""
        path = self._state_key_path(key)
        if path is None:
            return ConfidentValue(False, 1.0, origin=origin)
        return ConfidentValue(path.is_file(), 1.0, origin=origin)

    def _state_delete(self, args, kwargs, origin):
        """state.delete(key) -> Result[Boolean]
        Returns ok(true) if the key existed and was removed,
        ok(false) if it did not exist, error(...) on permission /
        I/O problems or invalid key."""
        key = args[0].value if args else ""
        path = self._state_key_path(key)
        if path is None:
            if not self._state_dir():
                return self._result_err(
                    "state directory not configured", origin)
            return self._result_err(
                f"invalid state key: {key!r}", origin)
        if not path.is_file():
            return self._result_ok(False, origin)
        try:
            path.unlink()
        except OSError as e:
            return self._result_err(
                f"could not delete state {key!r}: "
                f"{type(e).__name__}: {e}", origin)
        return self._result_ok(True, origin)

    # --- env effect — read OS environment variables as Result[Text].
    # Gives AIL programs a way to pick up credentials (Mastodon token,
    # webhook URL, API key) without hardcoding them in source. The
    # authoring prompt already forbids placeholder keys; env.read is
    # the safe alternative.
    def _env_read(self, args, kwargs, origin):
        """env.read(name: Text) -> Result[Text]

        Returns ok(<value>) when the named env var is set (even to the
        empty string — that's a valid value, not a missing key),
        error(...) when it's unset or when the argument is not a
        non-empty string.

        No allow-listing of names in this release: the trust boundary
        is whoever launched `ail up` / `ail run`. A future `effect env`
        declaration can add per-project restrictions.
        """
        import os
        if not args:
            return self._result_err(
                "env.read needs a name argument", origin)
        name = args[0].value
        if not isinstance(name, str) or not name:
            return self._result_err(
                f"env.read: name must be a non-empty string "
                f"(got {name!r})", origin)
        if name not in os.environ:
            return self._result_err(
                f"env var {name!r} is not set", origin)
        return self._result_ok(os.environ[name], origin)

    # --- human.approve effect (L2 v3 — plan-validate-execute)
    # Pauses the run on a structured plan review. The agentic server's
    # UI polls .ail/approvals/pending.json, renders the plan text, and
    # offers Approve / Decline. Outside an agentic project (no
    # AIL_APPROVAL_DIR) the effect returns a clean error so `ail run`
    # doesn't hang waiting for a UI that isn't there.
    #
    # Shape: perform human.approve(plan: Text) -> Result[Boolean]
    #   - ok(true)   = user approved, program should continue with
    #                  the side effect
    #   - error(...) = user declined, timed out, or not in a UI
    #                  context. Caller handles the Result normally.
    #
    # The file dance (as opposed to in-memory Event) is intentional:
    # it makes the pending approval visible to any external observer,
    # auditable in the ledger, and survives a refresh of the UI tab.
    def _human_approve(self, args, kwargs, origin):
        """human.approve(plan: Text) -> Result[Boolean]"""
        import os
        import json as _json
        import pathlib
        import uuid
        import time as _time

        if not args:
            return self._result_err(
                "human.approve needs a plan argument", origin)
        plan = args[0].value
        if not isinstance(plan, str) or not plan.strip():
            return self._result_err(
                "human.approve: plan must be a non-empty string "
                "describing what's about to happen", origin)

        dir_str = os.environ.get("AIL_APPROVAL_DIR")
        if not dir_str:
            return self._result_err(
                "human.approve: no UI context "
                "(AIL_APPROVAL_DIR unset — run inside `ail up`)",
                origin)
        approval_dir = pathlib.Path(dir_str)
        try:
            approval_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return self._result_err(
                f"human.approve: could not create approval dir: {e}",
                origin)

        approval_id = uuid.uuid4().hex
        pending_path = approval_dir / "pending.json"
        record = {
            "id": approval_id,
            "plan": plan,
            "created_at": _time.time(),
            "status": "pending",
        }
        try:
            tmp = pending_path.with_suffix(".tmp")
            tmp.write_text(
                _json.dumps(record, ensure_ascii=False),
                encoding="utf-8")
            os.replace(tmp, pending_path)
        except OSError as e:
            return self._result_err(
                f"human.approve: could not write approval record: {e}",
                origin)

        self.trace.record(
            "human_approve_pending",
            id=approval_id,
            plan_preview=plan[:200],
        )

        # Poll for a decision. 10 minutes cap — a user who walks away
        # gets a clean `error("timed out")` and the program returns
        # instead of hanging the server forever. Polling interval is
        # 250ms: fast enough to feel instant after the click, slow
        # enough to be negligible overhead.
        deadline = _time.monotonic() + 600.0
        while _time.monotonic() < deadline:
            try:
                raw = pending_path.read_text(encoding="utf-8")
                current = _json.loads(raw)
            except (OSError, ValueError):
                current = None
            # Defend against the file being replaced by a different
            # approval (shouldn't happen in single-run flow, but a
            # racing second run would stomp us and we'd rather bail
            # than silently read someone else's decision).
            if current is None or current.get("id") != approval_id:
                return self._result_err(
                    "human.approve: pending record lost or replaced",
                    origin)
            status = current.get("status")
            if status == "approved":
                try:
                    pending_path.unlink()
                except OSError:
                    pass
                self.trace.record(
                    "human_approve_decided",
                    id=approval_id, decision="approved")
                return self._result_ok(True, origin)
            if status == "declined":
                reason = current.get("reason") or "user declined"
                try:
                    pending_path.unlink()
                except OSError:
                    pass
                self.trace.record(
                    "human_approve_decided",
                    id=approval_id, decision="declined",
                    reason=reason)
                return self._result_err(
                    f"user declined: {reason}", origin)
            _time.sleep(0.25)

        # Timed out — remove the record so the next run starts clean.
        try:
            pending_path.unlink()
        except OSError:
            pass
        self.trace.record(
            "human_approve_decided",
            id=approval_id, decision="timeout")
        return self._result_err(
            "human.approve: timed out waiting for decision "
            "(10 minutes)", origin)

    # --- schedule effect (L2 v2 case study Gap #3 — recurring work).
    # The effect only *registers* the cadence; the actual re-invocation
    # loop lives in `agentic/server.py`, which polls the schedule file
    # and owns the background thread. Outside an agentic project the
    # env var is unset and the effect returns a clean error.
    def _schedule_every(self, args, kwargs, origin):
        """schedule.every(seconds: Number) -> Result[Boolean]

        Registers "this endpoint should be re-invoked every N seconds".
        The agentic server notices the registration (via a JSON file
        pointed at by AIL_SCHEDULE_FILE) and runs the recurring
        invocation in a background thread. Calling twice updates the
        cadence; latest call wins. Outside `ail up` the effect returns
        an error — there's nothing to drive the recurrence.

        Seconds must be a positive number; hard-capped at 86400 (1 day)
        to keep an author from accidentally scheduling something that
        never fires during a debug session.
        """
        import json as _json
        import os
        if not args:
            return self._result_err(
                "schedule.every needs a seconds argument", origin)
        raw = args[0].value
        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            return self._result_err(
                f"schedule.every: seconds must be a number (got {raw!r})",
                origin)
        if seconds <= 0:
            return self._result_err(
                "schedule.every: seconds must be > 0", origin)
        if seconds > 86400:
            return self._result_err(
                "schedule.every: seconds capped at 86400 (1 day)", origin)

        path_str = os.environ.get("AIL_SCHEDULE_FILE")
        if not path_str:
            return self._result_err(
                "schedule.every: no scheduler running "
                "(set AIL_SCHEDULE_FILE or run inside `ail up`)", origin)

        import pathlib
        path = pathlib.Path(path_str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = _json.dumps({"seconds": seconds}, ensure_ascii=False)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, path)
        except OSError as e:
            return self._result_err(
                f"schedule.every: could not write schedule file: "
                f"{type(e).__name__}: {e}", origin)
        return self._result_ok(True, origin)

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

        Every call records an `http_call` trace event with method, URL,
        status, and ok. The agentic server uses those entries to turn
        opaque "fetch failed" errors into actionable diagnostics
        (status code, URL, body preview) for non-programmer users.
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

        # Optional headers: kwarg OR positional.
        # GET:  perform http.get(url)  OR  perform http.get(url, headers)
        # POST: perform http.post(url, body)  OR  perform http.post(url, body, headers)
        # Two accepted shapes for the headers value:
        #   - a record (dict at runtime)
        #   - a list of 2-element [key, value] lists
        # A User-Agent is always set unless the caller overrides it.
        custom_headers: dict[str, str] = {}
        _headers_cv = kwargs.get("headers")
        if _headers_cv is None:
            # positional: GET→args[1], POST→args[2]
            pos = 1 if method == "GET" else 2
            if len(args) > pos:
                _headers_cv = args[pos]
        if _headers_cv is not None:
            raw_headers = _headers_cv.value
            if isinstance(raw_headers, dict):
                for hk, hv in raw_headers.items():
                    if hv is None:
                        continue
                    custom_headers[str(hk)] = str(hv)
            elif isinstance(raw_headers, list):
                for pair in raw_headers:
                    if isinstance(pair, (list, tuple)) and len(pair) == 2:
                        if pair[1] is None:
                            continue
                        custom_headers[str(pair[0])] = str(pair[1])

        merged_headers = {"User-Agent": "ail-http-effect/1.0"}
        merged_headers.update(custom_headers)
        try:
            req = urllib.request.Request(
                url, method=method,
                data=(str(body).encode("utf-8") if body is not None else None),
                headers=merged_headers,
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
            self.trace.record(
                "http_call", method=method, url=url,
                status=status, ok=result["ok"],
                body_preview=content[:200] if not result["ok"] else None,
            )
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
            self.trace.record(
                "http_call", method=method, url=url,
                status=status, ok=False,
                reason=getattr(e, "reason", ""),
                body_preview=content[:200],
            )
            return ConfidentValue(result, 1.0, origin=origin)
        except urllib.error.URLError as e:
            self.trace.record(
                "http_call", method=method, url=url,
                status=None, ok=False,
                network_error=str(e),
            )
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": f"http {method} {url}: {e}"},
                0.0, origin=origin,
            )

    def _http_post_json(self, args: list[ConfidentValue],
                        kwargs: dict[str, ConfidentValue],
                        origin: Origin) -> ConfidentValue:
        """HTTP POST with structural JSON body.

        HEAAL gap closer (2026-04-23 promo-bot field test): agents
        producing API calls kept hand-rolling JSON via `join(["\\"k\\":
        \\"", v, "\\""])` and silently emitting malformed bodies — the
        archetypal injection-class bug AIL exists to make impossible.
        This effect refuses a Text body and requires a structured value
        (pair-list / record / list), forwards it to encode_json, and
        auto-sets Content-Type. Authors can still fall back to raw
        `http.post` for non-JSON payloads.
        """
        import urllib.request
        import urllib.error
        url = str(args[0].value) if args else str(
            kwargs.get("url", ConfidentValue("", 1.0)).value)
        if len(args) >= 2:
            body_raw = args[1].value
        elif "body" in kwargs:
            body_raw = kwargs["body"].value
        else:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": "http.post_json: needs a body argument"},
                1.0, origin=origin)

        if isinstance(body_raw, str):
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": ("http.post_json: body must be structured "
                           "(record or list of [key, value] pairs), not a "
                           "pre-formatted JSON string. Build the body as "
                           "an AIL value and the runtime will serialize "
                           "it. For a raw string body, use http.post.")},
                1.0, origin=origin)

        try:
            normalized = _json_normalize(body_raw)
            import json as _json
            body_text = _json.dumps(normalized, ensure_ascii=False)
        except Exception as e:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": ("http.post_json: could not encode body: "
                           f"{type(e).__name__}: {e}")},
                1.0, origin=origin)

        custom_headers: dict[str, str] = {}
        if "headers" in kwargs:
            raw_headers = kwargs["headers"].value
            if isinstance(raw_headers, dict):
                for hk, hv in raw_headers.items():
                    if hv is None:
                        continue
                    custom_headers[str(hk)] = str(hv)
            elif isinstance(raw_headers, list):
                for pair in raw_headers:
                    if isinstance(pair, (list, tuple)) and len(pair) == 2:
                        if pair[1] is None:
                            continue
                        custom_headers[str(pair[0])] = str(pair[1])

        merged_headers = {
            "User-Agent": "ail-http-effect/1.0",
            "Content-Type": "application/json",
        }
        # Caller's Content-Type wins only if they explicitly set one —
        # unusual but possible (e.g. application/vnd.github+json).
        merged_headers.update(custom_headers)

        try:
            req = urllib.request.Request(
                url, method="POST",
                data=body_text.encode("utf-8"),
                headers=merged_headers,
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                status = float(resp.status)
            result = {
                "status": status,
                "body": content,
                "ok": 200 <= status < 300,
            }
            self.trace.record(
                "http_call", method="POST_JSON", url=url,
                status=status, ok=result["ok"],
                body_preview=content[:200] if not result["ok"] else None,
            )
            return ConfidentValue(result, 1.0, origin=origin)
        except urllib.error.HTTPError as e:
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
            self.trace.record(
                "http_call", method="POST_JSON", url=url,
                status=status, ok=False,
                reason=getattr(e, "reason", ""),
                body_preview=content[:200],
            )
            return ConfidentValue(result, 1.0, origin=origin)
        except urllib.error.URLError as e:
            self.trace.record(
                "http_call", method="POST_JSON", url=url,
                status=None, ok=False,
                network_error=str(e),
            )
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": f"http.post_json {url}: {e}"},
                0.0, origin=origin,
            )

    def _http_graphql(self, args: list[ConfidentValue],
                      kwargs: dict[str, ConfidentValue],
                      origin: Origin) -> ConfidentValue:
        """HTTP POST a GraphQL query and return the `data` payload.

        HEAAL gap closer (2026-04-24 promo-bot field test): agents
        trying GitHub GraphQL kept mis-diagnosing failure because
        `200 OK` + `{"errors": [...]}` + no `data` all look like
        "it worked" from the HTTP layer. After three turns of
        "GraphQL errors: None" the agent had no idea whether the
        mutation had fired. This effect collapses the full decision
        tree — HTTP status, JSON parse, `errors` array, `data`
        present-and-not-null — into one `Result[Any]` so the author
        cannot mis-classify.

        Shape:
            perform http.graphql(url, query, variables?, headers?)
                -> Result[Any]

          - ok(data)  = response.data (the unwrapped payload;
                        inner fields accessed via `get()`)
          - error(msg)= any of: HTTP 4xx/5xx, unparseable JSON,
                        `errors` array non-empty (messages joined),
                        `data` absent or null

        Returning `ok(data)` (not `ok(response)`) intentionally hides
        the raw JSON shape — authors do `get(get(unwrap(r), "createDiscussion"),
        "discussion")` to reach into the mutation result, never
        `get(resp_body, "data")` which in the old pattern was the
        source of the silent-failure bug.
        """
        import urllib.request
        import urllib.error
        import json as _json

        url = str(args[0].value) if args else str(
            kwargs.get("url", ConfidentValue("", 1.0)).value)
        if len(args) < 2 and "query" not in kwargs:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": "http.graphql: needs a query argument"},
                1.0, origin=origin)
        query = args[1].value if len(args) >= 2 else kwargs["query"].value
        if not isinstance(query, str) or not query.strip():
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": "http.graphql: query must be a non-empty string"},
                1.0, origin=origin)

        # Variables optional. Accepts the same pair-list / record
        # shapes as encode_json does, so `[["a", 1], ["b", "x"]]`
        # works directly as a `variables` argument.
        variables = None
        if len(args) >= 3:
            variables = args[2].value
        elif "variables" in kwargs:
            variables = kwargs["variables"].value

        try:
            body_dict = {"query": query}
            if variables is not None:
                body_dict["variables"] = _json_normalize(variables)
            body_text = _json.dumps(body_dict, ensure_ascii=False)
        except Exception as e:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": ("http.graphql: could not encode body: "
                           f"{type(e).__name__}: {e}")},
                1.0, origin=origin)

        custom_headers: dict[str, str] = {}
        _raw_headers_cv = args[3] if len(args) >= 4 else kwargs.get("headers")
        if _raw_headers_cv is not None:
            raw_headers = _raw_headers_cv.value
            if isinstance(raw_headers, dict):
                for hk, hv in raw_headers.items():
                    if hv is None:
                        continue
                    custom_headers[str(hk)] = str(hv)
            elif isinstance(raw_headers, list):
                for pair in raw_headers:
                    if isinstance(pair, (list, tuple)) and len(pair) == 2:
                        if pair[1] is None:
                            continue
                        custom_headers[str(pair[0])] = str(pair[1])

        merged_headers = {
            "User-Agent": "ail-http-effect/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        merged_headers.update(custom_headers)

        try:
            req = urllib.request.Request(
                url, method="POST",
                data=body_text.encode("utf-8"),
                headers=merged_headers,
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                status = int(resp.status)
            self.trace.record(
                "http_call", method="GRAPHQL", url=url,
                status=float(status), ok=(200 <= status < 300),
                body_preview=content[:200] if not (200 <= status < 300) else None,
            )
        except urllib.error.HTTPError as e:
            status = int(e.code)
            try:
                content = e.read().decode("utf-8", errors="replace")
            except Exception:
                content = ""
            self.trace.record(
                "http_call", method="GRAPHQL", url=url,
                status=float(status), ok=False,
                reason=getattr(e, "reason", ""),
                body_preview=content[:200],
            )
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": (f"http.graphql: HTTP {status}: "
                           f"{content[:500]}")},
                1.0, origin=origin)
        except urllib.error.URLError as e:
            self.trace.record(
                "http_call", method="GRAPHQL", url=url,
                status=None, ok=False,
                network_error=str(e),
            )
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": f"http.graphql {url}: {e}"},
                0.0, origin=origin)

        if not (200 <= status < 300):
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": (f"http.graphql: HTTP {status}: "
                           f"{content[:500]}")},
                1.0, origin=origin)

        # Parse body as JSON.
        try:
            parsed = _json.loads(content)
        except ValueError as e:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": ("http.graphql: response was not JSON: "
                           f"{content[:300]}")},
                1.0, origin=origin)

        if not isinstance(parsed, dict):
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": (f"http.graphql: expected JSON object, "
                           f"got {type(parsed).__name__}: "
                           f"{content[:300]}")},
                1.0, origin=origin)

        # GraphQL spec: `errors` is an array of {message, path?, ...}.
        # Any non-empty `errors` is a hard failure — even if `data`
        # is partially populated. Authors who need partial-success
        # semantics can fall back to http.post_json and hand-parse;
        # this effect is opinionated on "did it fully succeed?".
        errors = parsed.get("errors")
        if isinstance(errors, list) and errors:
            messages = []
            for i, err in enumerate(errors):
                if isinstance(err, dict):
                    msg = err.get("message", "")
                    path = err.get("path")
                    type_ = err.get("type")
                    parts = [msg]
                    if type_:
                        parts.append(f"[{type_}]")
                    if path:
                        parts.append(f"at {path}")
                    messages.append(" ".join(str(p) for p in parts if p))
                else:
                    messages.append(str(err))
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": ("http.graphql: "
                           + "; ".join(messages))},
                1.0, origin=origin)

        # `data` must be present and not null. GraphQL semantics:
        # `data: null` means the top-level operation failed, and
        # any response without a `data` key means the server
        # couldn't even start evaluating.
        if "data" not in parsed:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": ("http.graphql: response has no `data` "
                           f"field: {content[:300]}")},
                1.0, origin=origin)
        data = parsed["data"]
        if data is None:
            return ConfidentValue(
                {"_result": True, "ok": False,
                 "error": ("http.graphql: response.data is null "
                           "(operation failed without an errors "
                           f"entry): {content[:300]}")},
                1.0, origin=origin)

        return ConfidentValue(
            {"_result": True, "ok": True, "value": data},
            1.0, origin=origin)

    def _ail_run(self, args: list[ConfidentValue],
                 kwargs: dict[str, ConfidentValue],
                 origin: Origin) -> ConfidentValue:
        """Run a block of AIL source code and return its result.

        Shape:
            perform ail.run(code: Text, input?: Text) -> Result[Text]

        This is the meta-programming primitive: an AIL program can write
        another AIL program (via intent) and execute it. The returned
        value is the sub-program's entry return value as Text.

        Safety: sub-programs run in the same executor type with the same
        harness constraints (pure fn purity, Result wrapping, human.approve
        gate on irreversible effects). They inherit this executor's adapter
        and ask_human so the same model and approval UI are used.

        Recursion limits:
          depth >= {warn}  → trace warning, execution continues
          depth >= {limit} → Result-error, execution stops
        """.format(warn=_AIL_RUN_DEPTH_WARN, limit=_AIL_RUN_DEPTH_LIMIT)

        next_depth = self._ail_run_depth + 1

        if next_depth >= _AIL_RUN_DEPTH_LIMIT:
            self.trace.record(
                "ail_run_depth_exceeded",
                depth=next_depth, limit=_AIL_RUN_DEPTH_LIMIT)
            return self._result_err(
                f"ail.run: recursion depth {next_depth} exceeds limit "
                f"({_AIL_RUN_DEPTH_LIMIT}). Autonomous agent loop too deep — "
                f"add a base case or reduce nesting.", origin)

        if next_depth >= _AIL_RUN_DEPTH_WARN:
            self.trace.record(
                "ail_run_depth_warning",
                depth=next_depth, warn=_AIL_RUN_DEPTH_WARN,
                limit=_AIL_RUN_DEPTH_LIMIT)

        if not args and "code" not in kwargs:
            return self._result_err(
                "ail.run needs a code argument", origin)
        code = str(args[0].value if args else kwargs["code"].value)
        if not code.strip():
            return self._result_err(
                "ail.run: code must be a non-empty string", origin)

        run_input = ""
        if len(args) >= 2:
            run_input = str(args[1].value)
        elif "input" in kwargs:
            run_input = str(kwargs["input"].value)

        try:
            from .. import compile_source
            program = compile_source(code)
        except Exception as e:
            return self._result_err(
                f"ail.run: parse error in generated program: "
                f"{type(e).__name__}: {e}", origin)

        try:
            sub = Executor(
                program,
                adapter=self.adapter,
                ask_human=self.ask_human,
                metric_fn=self.metric_fn,
                approve_review=self.approve_review,
                calibrator=self.calibrator,
                _ail_run_depth=next_depth,
                log_callback=self.log_callback,
            )
            result = sub.run_entry({"input": run_input})
            self.trace.record(
                "ail_run", depth=next_depth,
                code_len=len(code), ok=True)
            return self._result_ok(str(result.value), origin)
        except Exception as e:
            self.trace.record(
                "ail_run", depth=next_depth,
                code_len=len(code), ok=False,
                error=str(e)[:200])
            return self._result_err(
                f"ail.run: runtime error: {type(e).__name__}: {e}", origin)

    def _search_web(self, args: list[ConfidentValue],
                    kwargs: dict[str, ConfidentValue],
                    origin: Origin) -> ConfidentValue:
        """Web search with a three-backend fallback chain.

        Shape:
            perform search.web(query, count?) -> Result[List[Record]]

        Each Record: { title: Text, url: Text, snippet: Text }

        Backend priority:
          1. Google Custom Search API (confidence 0.9)
             — requires GOOGLE_SEARCH_API_KEY + GOOGLE_SEARCH_CX env vars.
             Skipped if keys absent; skipped on quota/auth errors.
          2. SearXNG (confidence 0.8)
             — requires SEARXNG_BASE_URL env var (e.g. http://localhost:8888).
             Skipped if var absent.
          3. DuckDuckGo HTML scrape (confidence 0.7)
             — always tried; no key needed.

        Returns Result-error only when ALL backends fail.
        """
        import urllib.request
        import urllib.parse
        import urllib.error
        import json as _json
        import os

        if not args and "query" not in kwargs:
            return self._result_err(
                "search.web needs a query argument", origin)
        query = str(args[0].value if args else kwargs["query"].value).strip()
        if not query:
            return self._result_err(
                "search.web: query must be a non-empty string", origin)

        count = 10
        if len(args) >= 2:
            try:
                count = max(1, min(int(args[1].value), 20))
            except (TypeError, ValueError):
                pass
        elif "count" in kwargs:
            try:
                count = max(1, min(int(kwargs["count"].value), 20))
            except (TypeError, ValueError):
                pass

        last_err = "no backend attempted"

        # --- Backend 1: Google Custom Search API ---
        api_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
        cx = os.environ.get("GOOGLE_SEARCH_CX", "")
        if api_key and cx:
            try:
                params = urllib.parse.urlencode({
                    "q": query, "key": api_key, "cx": cx, "num": count,
                })
                req = urllib.request.Request(
                    f"https://www.googleapis.com/customsearch/v1?{params}",
                    headers={"User-Agent": "ail-search/1.0"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = _json.loads(
                        resp.read().decode("utf-8", errors="replace"))
                items = data.get("items") or []
                results = [
                    {"title": item.get("title", ""),
                     "url": item.get("link", ""),
                     "snippet": item.get("snippet", "")}
                    for item in items
                ]
                if results:
                    self.trace.record(
                        "search_web", backend="google",
                        query=query[:100], count=len(results))
                    return ConfidentValue(
                        {"_result": True, "ok": True, "value": results},
                        0.9, origin=origin)
                last_err = "Google: no results"
            except urllib.error.HTTPError as e:
                last_err = f"Google: HTTP {e.code}"
            except Exception as e:
                last_err = f"Google: {type(e).__name__}: {e}"

        # --- Backend 2: SearXNG ---
        searxng_base = os.environ.get("SEARXNG_BASE_URL", "").rstrip("/")
        if searxng_base:
            try:
                params = urllib.parse.urlencode({
                    "q": query, "format": "json", "categories": "general",
                })
                req = urllib.request.Request(
                    f"{searxng_base}/search?{params}",
                    headers={
                        "User-Agent": "ail-search/1.0",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = _json.loads(
                        resp.read().decode("utf-8", errors="replace"))
                items = (data.get("results") or [])[:count]
                results = [
                    {"title": item.get("title", ""),
                     "url": item.get("url", ""),
                     "snippet": item.get("content", "")}
                    for item in items
                ]
                if results:
                    self.trace.record(
                        "search_web", backend="searxng",
                        query=query[:100], count=len(results))
                    return ConfidentValue(
                        {"_result": True, "ok": True, "value": results},
                        0.8, origin=origin)
                last_err = "SearXNG: no results"
            except Exception as e:
                last_err = f"SearXNG: {type(e).__name__}: {e}"

        # --- Backend 3: DuckDuckGo HTML scrape ---
        try:
            import html as _html_mod
            from html.parser import HTMLParser

            params = urllib.parse.urlencode({"q": query, "kl": "us-en"})
            req = urllib.request.Request(
                f"https://html.duckduckgo.com/html/?{params}",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                html_body = resp.read().decode("utf-8", errors="replace")

            class _DDGParser(HTMLParser):
                def __init__(self_p):
                    super().__init__()
                    self_p.results: list[dict] = []
                    self_p._cur: dict | None = None
                    self_p._capture_title = False
                    self_p._capture_snippet = False
                    self_p._buf: list[str] = []

                def handle_starttag(self_p, tag, attrs):
                    amap = dict(attrs)
                    cls = amap.get("class", "")
                    if tag == "div" and "result__body" in cls:
                        self_p._cur = {"title": "", "url": "", "snippet": ""}
                    elif self_p._cur is not None:
                        if tag == "a" and "result__a" in cls:
                            self_p._cur["url"] = amap.get("href", "")
                            self_p._capture_title = True
                            self_p._buf = []
                        elif tag in ("a", "div") and "result__snippet" in cls:
                            self_p._capture_snippet = True
                            self_p._buf = []

                def handle_endtag(self_p, tag):
                    if self_p._capture_title and tag == "a":
                        self_p._cur["title"] = _html_mod.unescape(
                            "".join(self_p._buf)).strip()
                        self_p._capture_title = False
                        self_p._buf = []
                    elif self_p._capture_snippet and tag in ("a", "div"):
                        self_p._cur["snippet"] = _html_mod.unescape(
                            "".join(self_p._buf)).strip()
                        self_p._capture_snippet = False
                        self_p._buf = []
                        if self_p._cur.get("url"):
                            self_p.results.append(self_p._cur)
                        self_p._cur = None

                def handle_data(self_p, data):
                    if self_p._capture_title or self_p._capture_snippet:
                        self_p._buf.append(data)

            parser = _DDGParser()
            parser.feed(html_body)
            results = parser.results[:count]
            if results:
                self.trace.record(
                    "search_web", backend="duckduckgo",
                    query=query[:100], count=len(results))
                return ConfidentValue(
                    {"_result": True, "ok": True, "value": results},
                    0.7, origin=origin)
            last_err = "DuckDuckGo: no results (CAPTCHA or empty response)"
        except Exception as e:
            last_err = f"DuckDuckGo: {type(e).__name__}: {e}"

        google_key_set = bool(os.environ.get("GOOGLE_SEARCH_API_KEY", "")
                              and os.environ.get("GOOGLE_SEARCH_CX", ""))
        if google_key_set:
            hint = (
                "Google API 키가 설정되어 있지만 검색에 실패했어요 "
                f"({last_err}). 키가 유효한지 확인해주세요."
            )
        else:
            hint = (
                "검색 결과를 가져오지 못했어요. "
                "Google 검색 API 키를 설정하면 더 안정적으로 검색할 수 있어요. "
                "(⚙ 설정에서 GOOGLE_SEARCH_API_KEY와 GOOGLE_SEARCH_CX를 추가하세요)"
            )
        return self._result_err(hint, origin)

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
            if len(raw) == 1:
                return ConfidentValue(list(range(int(raw[0]))), conf)
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

        if name == "strip_html":
            # strip_html(source: Text) -> Text
            # Pure. Returns the visible text content of an HTML
            # document — tags removed, <script>/<style> bodies
            # discarded, common entities decoded, whitespace
            # collapsed. Closes the HEAAL gap where agents scraping
            # web pages had no tooling between `perform http.get`
            # (which returns a huge HTML string) and an `intent`
            # that then wastes context on markup tokens. Pair:
            # `text = strip_html(resp.body)` then pass `text` to
            # an intent for semantic extraction.
            if len(raw) >= 1 and isinstance(raw[0], str):
                return ConfidentValue(_strip_html(raw[0]), conf)

        if name == "encode_json":
            # encode_json(value: Any) -> Result[Text]
            # Pure. Companion to parse_json. Closes the HEAAL gap where
            # agents hand-rolled JSON bodies via `join(["\"key\": \"", val,
            # "\""])` and broke on embedded quotes/newlines/backslashes.
            # Accepts records, lists, lists-of-pairs (same convention as
            # http headers — two-element [key, value] lists form an
            # object), primitives, and null. Escaping is the runtime's
            # responsibility, not the author's.
            if len(raw) >= 1:
                try:
                    normalized = _json_normalize(raw[0])
                    import json as _json
                    text = _json.dumps(normalized, ensure_ascii=False)
                    return ConfidentValue(
                        {"_result": True, "ok": True, "value": text}, conf)
                except Exception as e:
                    return ConfidentValue(
                        {"_result": True, "ok": False,
                         "error": f"{type(e).__name__}: {e}"}, conf)

        if name == "base64_encode":
            # base64_encode(value: Text) -> Text
            # Pure. Encodes a text string to base64. Required for GitHub
            # Contents API (PUT /repos/.../contents/...) which mandates
            # base64-encoded `content` fields. Also covers any API that
            # accepts binary/encoded payloads. Returns plain Text, not
            # a Result — encoding never fails on valid input.
            if len(raw) >= 1:
                import base64 as _b64
                text = raw[0] if isinstance(raw[0], str) else str(raw[0])
                encoded = _b64.b64encode(text.encode("utf-8")).decode("ascii")
                return ConfidentValue(encoded, conf)

        if name == "base64_decode":
            # base64_decode(value: Text) -> Result[Text]
            # Pure. Decodes a base64 string back to UTF-8 text. Returns
            # ok(text) on success, error(msg) if the input is not valid
            # base64 or the bytes are not valid UTF-8.
            if len(raw) >= 1 and isinstance(raw[0], str):
                import base64 as _b64
                try:
                    decoded = _b64.b64decode(raw[0]).decode("utf-8")
                    return ConfidentValue(
                        {"_result": True, "ok": True, "value": decoded}, conf)
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

    def _invoke_with_validation(
        self, *, intent: IntentDecl, goal_str: str,
        constraints_str: list[str], context_dict: dict,
        inputs: dict, examples,
    ) -> tuple[ModelResponse, Any, Optional[str]]:
        """Invoke the adapter and validate the response against the
        declared return type. Retry once with a sharpened prompt on
        mismatch. Returns (final_response, coerced_value, error).

        On success the third element is None. On retries-exhausted
        the caller is expected to lower confidence / record the
        failure in the trace.
        """
        from .intent_validation import validate_and_coerce

        response = self.adapter.invoke(
            goal=goal_str,
            constraints=constraints_str,
            context=context_dict,
            inputs=inputs,
            expected_type=intent.return_type,
            examples=examples,
        )
        coerced, err = validate_and_coerce(
            response.value, intent.return_type)
        if err is None:
            return response, coerced, None

        # First attempt didn't match the declared type. Record the
        # mismatch, then retry once with the error fed back as a
        # sharper constraint. The author's declared constraints are
        # preserved so the retry is strictly stricter, not looser.
        self.trace.record("intent_validation_retry",
                          intent=intent.name,
                          declared_type=intent.return_type,
                          error=err)
        sharpened = list(constraints_str) + [
            f"Your previous response was rejected because it did not "
            f"match the declared return type `{intent.return_type}`. "
            f"Reason: {err}. Return ONLY a value of type "
            f"`{intent.return_type}` — no JSON wrapping, no code "
            f"fences, no explanatory prose, no nested records.",
        ]
        retry_response = self.adapter.invoke(
            goal=goal_str,
            constraints=sharpened,
            context=context_dict,
            inputs=inputs,
            expected_type=intent.return_type,
            examples=examples,
        )
        coerced2, err2 = validate_and_coerce(
            retry_response.value, intent.return_type)
        if err2 is None:
            return retry_response, coerced2, None
        return retry_response, coerced2, err2

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

            try:
                response, coerced_value, validation_error = self._invoke_with_validation(
                    intent=intent,
                    goal_str=goal_str,
                    constraints_str=constraints_str,
                    context_dict=context_dict,
                    inputs={pname: local[pname].value for (pname, _) in intent.params if pname in local},
                    examples=example_pairs or None,
                )
            except Exception as adapter_exc:
                # Model adapter failure (network error, API 500, context too
                # large, etc.) — surface as a low-confidence error string so
                # the AIL program can observe and adapt rather than crashing.
                err_msg = f"INTENT_ERROR: {type(adapter_exc).__name__}: {adapter_exc}"
                self.trace.record("intent_adapter_error",
                                  intent=intent.name, error=err_msg)
                return ConfidentValue(err_msg, 0.0, origin=origin)

            raw = response.raw or {}
            self.trace.record("model_response",
                              model=response.model_id,
                              value=_truncate(response.value),
                              confidence=response.confidence,
                              prompt_tokens=raw.get("prompt_tokens") or raw.get("input_tokens") or 0,
                              completion_tokens=raw.get("completion_tokens") or raw.get("output_tokens") or 0)

            # Validation outcome is recorded even on success so the
            # trace shows the harness is live (not silently skipped).
            if validation_error is None:
                response = ModelResponse(
                    value=coerced_value,
                    confidence=response.confidence,
                    model_id=response.model_id,
                    raw=response.raw,
                )
            else:
                self.trace.record("intent_validation_failed",
                                  intent=intent.name,
                                  declared_type=intent.return_type,
                                  error=validation_error)
                # Retries exhausted. Pass through the raw value but
                # drop confidence to zero so downstream `attempt` /
                # confidence guards route around this result.
                response = ModelResponse(
                    value=coerced_value,
                    confidence=0.0,
                    model_id=response.model_id,
                    raw=response.raw,
                )

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


def _json_normalize(value):
    """Convert an AIL runtime value into something json.dumps can serialize.

    AIL has no dict literal syntax, so the canonical way to build an
    object inline is a list of two-element [key, value] lists — same
    convention `http.post` uses for `headers`. This helper recognises
    that shape recursively: a list whose every element is a 2-list with
    a string-ish first element becomes a JSON object; any other list
    becomes a JSON array. Python dicts pass through (from intents or
    earlier parse_json calls). Primitives pass through after Result-
    error detection (errors shouldn't silently encode to {"_result":
    true, ...} — they should propagate).

    Raises ValueError if given an ok-Result or error-Result by
    mistake; the caller should unwrap() first so the encoding is of
    the payload, not the wrapper.
    """
    # Reject Result wrappers — the author almost certainly meant the
    # unwrapped value, not the provenance container. Surfacing an
    # explicit error beats silently emitting {"_result": true, "ok":
    # true, "value": ...} which no real API accepts.
    if isinstance(value, dict) and value.get("_result") is True:
        if value.get("ok"):
            raise ValueError(
                "encode_json: got an ok-Result; call unwrap() first")
        raise ValueError(
            "encode_json: got an error-Result; cannot serialize an error")
    if isinstance(value, list):
        # Pair-list shape: every element is a [k, v] with k a string.
        if value and all(
            isinstance(e, list) and len(e) == 2 and isinstance(e[0], str)
            for e in value
        ):
            # Duplicate keys resolve last-wins (same as JSON parsers).
            return {e[0]: _json_normalize(e[1]) for e in value}
        return [_json_normalize(e) for e in value]
    if isinstance(value, dict):
        return {str(k): _json_normalize(v) for k, v in value.items()}
    # Primitives — let json.dumps decide.
    return value


def _strip_html(source: str) -> str:
    """Extract visible text content from an HTML document.

    Uses stdlib html.parser. Drops everything inside <script> and
    <style> tags (so a minified page doesn't flood the result with
    JS source). Decodes common named entities (&amp; &lt; &gt;
    &quot; &#39; &nbsp;) so downstream intents read clean text.
    Normalises run-together whitespace so what reaches the next
    stage is comparable to what a human would see in the browser.

    Not a sanitizer — callers should not trust the output to be
    safe for re-embedding in HTML; this is a "reduce noise for
    LLM consumption" helper, not a security tool.
    """
    from html.parser import HTMLParser
    import re as _re

    class _Collector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.skip = 0  # depth of open <script>/<style> tags

        def handle_starttag(self, tag, attrs):
            if tag.lower() in ("script", "style"):
                self.skip += 1

        def handle_endtag(self, tag):
            if tag.lower() in ("script", "style") and self.skip > 0:
                self.skip -= 1

        def handle_data(self, data):
            if self.skip == 0:
                self.parts.append(data)

    c = _Collector()
    try:
        c.feed(source)
        c.close()
    except Exception:
        # Malformed HTML shouldn't take the program down. Return
        # whatever we collected so far; worst case, empty string.
        pass
    joined = "".join(c.parts)
    # Collapse runs of whitespace to a single space, but keep line
    # breaks so paragraph structure is still readable.
    joined = _re.sub(r"[ \t\f\v]+", " ", joined)
    joined = _re.sub(r"\n[ \t]+", "\n", joined)
    joined = _re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()


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
