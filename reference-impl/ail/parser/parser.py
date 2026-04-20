"""Recursive-descent parser for AIL (MVP subset).

Covers: context, intent, effect, entry, import, evolve (parsed only).
Statement forms: assignment, return, perform, branch, with, expression.
Expression forms: literals, identifiers, field access, calls, binary/unary ops, lists.

The MVP grammar is deliberately a subset of the full spec. Features parsed
but not executed (like `evolve`) are preserved for round-trip visibility.
"""
from __future__ import annotations
from typing import Any

from .lexer import Token, Tok, tokenize
from .ast import (
    Program, ContextDecl, IntentDecl, EffectDecl, EntryDecl, ImportDecl, EvolveDecl,
    Assignment, ReturnStmt, PerformStmt, BranchStmt, BranchArm, WithContextStmt, ExprStmt,
    Literal, Identifier, FieldAccess, Call, BinaryOp, UnaryOp, ListLiteral,
    Expr, Statement,
)


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    # --- helpers ---

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[self.i + offset]

    def advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def check(self, kind: Tok, value: str | None = None) -> bool:
        t = self.peek()
        if t.kind != kind:
            return False
        if value is not None and t.value != value:
            return False
        return True

    def match(self, kind: Tok, value: str | None = None) -> bool:
        if self.check(kind, value):
            self.advance()
            return True
        return False

    def expect(self, kind: Tok, value: str | None = None) -> Token:
        if not self.check(kind, value):
            t = self.peek()
            want = value if value else kind.name
            raise ParseError(f"expected {want} at {t.line}:{t.col}, got {t.kind.name}({t.value!r})")
        return self.advance()

    def expect_keyword(self, kw: str) -> Token:
        return self.expect(Tok.IDENT, kw)

    def is_keyword(self, kw: str) -> bool:
        return self.check(Tok.IDENT, kw)

    # --- top level ---

    def parse_program(self) -> Program:
        decls: list[Any] = []
        while not self.check(Tok.EOF):
            decls.append(self.parse_top_level())
        return Program(declarations=decls)

    def parse_top_level(self) -> Any:
        t = self.peek()
        if t.kind == Tok.IDENT:
            if t.value == "context":
                return self.parse_context()
            if t.value == "intent":
                return self.parse_intent()
            if t.value == "effect":
                return self.parse_effect()
            if t.value == "entry":
                return self.parse_entry()
            if t.value == "import":
                return self.parse_import()
            if t.value == "evolve":
                return self.parse_evolve()
            if t.value == "fn":
                return self.parse_fn()
            if t.value == "pure" and self.peek(1).kind == Tok.IDENT and self.peek(1).value == "fn":
                return self.parse_fn(purity="pure")
        raise ParseError(f"unexpected top-level token {t!r}")

    # --- context ---

    def parse_context(self) -> ContextDecl:
        self.expect_keyword("context")
        name = self.expect(Tok.IDENT).value
        extends = None
        if self.match(Tok.IDENT, "extends"):
            extends = self.expect(Tok.IDENT).value
        self.expect(Tok.LBRACE)
        fields: dict[str, Expr] = {}
        overrides: set[str] = set()
        while not self.check(Tok.RBRACE):
            is_override = False
            if self.match(Tok.IDENT, "override"):
                is_override = True
            field_name = self.expect(Tok.IDENT).value
            self.expect(Tok.COLON)
            value = self.parse_expr()
            fields[field_name] = value
            if is_override:
                overrides.add(field_name)
        self.expect(Tok.RBRACE)
        return ContextDecl(name=name, extends=extends, fields=fields, overrides=overrides)

    # --- intent ---

    def parse_intent(self) -> IntentDecl:
        self.expect_keyword("intent")
        name = self.expect(Tok.IDENT).value
        params = self.parse_params()
        return_type = None
        if self.match(Tok.ARROW):
            return_type = self.parse_type_name()
        self.expect(Tok.LBRACE)

        goal: Expr = Literal(value=None)
        constraints: list[Expr] = []
        examples: list[tuple[list[Expr], Expr]] = []
        low_conf: tuple[float, list[Statement]] | None = None
        trace_level = "partial"
        body_hint: list[Statement] = []

        while not self.check(Tok.RBRACE):
            if self.is_keyword("goal"):
                self.advance()
                self.expect(Tok.COLON)
                goal = self.parse_expr()
            elif self.is_keyword("constraints"):
                self.advance()
                self.expect(Tok.LBRACE)
                while not self.check(Tok.RBRACE):
                    constraints.append(self.parse_expr())
                self.expect(Tok.RBRACE)
            elif self.is_keyword("examples"):
                self.advance()
                self.expect(Tok.LBRACE)
                while not self.check(Tok.RBRACE):
                    inputs, out = self.parse_example()
                    examples.append((inputs, out))
                self.expect(Tok.RBRACE)
            elif self.is_keyword("on_low_confidence"):
                self.advance()
                self.expect(Tok.LPAREN)
                self.expect_keyword("threshold")
                self.expect(Tok.COLON)
                thresh_tok = self.expect(Tok.NUMBER)
                self.expect(Tok.RPAREN)
                self.expect(Tok.LBRACE)
                handler_body = []
                while not self.check(Tok.RBRACE):
                    handler_body.append(self.parse_statement())
                self.expect(Tok.RBRACE)
                low_conf = (float(thresh_tok.value), handler_body)
            elif self.is_keyword("trace"):
                self.advance()
                self.expect(Tok.COLON)
                trace_level = self.expect(Tok.IDENT).value
            else:
                # body statement hint
                body_hint.append(self.parse_statement())

        self.expect(Tok.RBRACE)
        return IntentDecl(
            name=name, params=params, return_type=return_type,
            goal=goal, constraints=constraints, examples=examples,
            low_confidence_handler=low_conf, trace_level=trace_level,
            body_hint=body_hint,
        )

    def parse_example(self) -> tuple[list[Expr], Expr]:
        # Simplified: ( expr, expr, ... ) => expr
        self.expect(Tok.LPAREN)
        inputs: list[Expr] = []
        if not self.check(Tok.RPAREN):
            inputs.append(self.parse_expr())
            while self.match(Tok.COMMA):
                # Skip named kwargs like "register: ..." in examples (MVP)
                if self.peek().kind == Tok.IDENT and self.tokens[self.i + 1].kind == Tok.COLON:
                    self.advance(); self.advance()  # name and colon
                    self.parse_expr()  # discard for MVP
                else:
                    inputs.append(self.parse_expr())
        self.expect(Tok.RPAREN)
        self.expect(Tok.FATARROW)
        # Output may be wrapped in parens
        if self.match(Tok.LPAREN):
            out = self.parse_expr()
            self.expect(Tok.RPAREN)
        else:
            out = self.parse_expr()
        return inputs, out

    # --- effect ---

    def parse_effect(self) -> EffectDecl:
        self.expect_keyword("effect")
        name = self.expect(Tok.IDENT).value
        self.expect(Tok.LBRACE)
        sig_params: list[tuple[str, str | None]] = []
        sig_return: str | None = None
        authorization = "none"
        observable_by: list[str] = []
        while not self.check(Tok.RBRACE):
            field_name = self.expect(Tok.IDENT).value
            self.expect(Tok.COLON)
            if field_name == "signature":
                sig_params = self.parse_params()
                if self.match(Tok.ARROW):
                    sig_return = self.parse_type_name()
            elif field_name == "authorization":
                authorization = self.expect(Tok.IDENT).value
            elif field_name == "observable_by":
                self.expect(Tok.LBRACK)
                while not self.check(Tok.RBRACK):
                    observable_by.append(self.expect(Tok.IDENT).value)
                    if not self.match(Tok.COMMA):
                        break
                self.expect(Tok.RBRACK)
            else:
                # Skip unknown fields (MVP tolerance)
                self.parse_expr()
        self.expect(Tok.RBRACE)
        return EffectDecl(
            name=name, signature_params=sig_params, signature_return=sig_return,
            authorization=authorization, observable_by=observable_by,
        )

    # --- entry ---

    def parse_entry(self) -> EntryDecl:
        self.expect_keyword("entry")
        name = self.expect(Tok.IDENT).value
        params = self.parse_params()
        self.expect(Tok.LBRACE)
        body: list[Statement] = []
        while not self.check(Tok.RBRACE):
            body.append(self.parse_statement())
        self.expect(Tok.RBRACE)
        return EntryDecl(name=name, params=params, body=body)

    # --- import ---

    def parse_import(self) -> ImportDecl:
        self.expect_keyword("import")
        kind = "intent"
        if self.is_keyword("context") or self.is_keyword("effect"):
            kind = self.advance().value
        sym = self.expect(Tok.IDENT).value
        self.expect_keyword("from")
        source = self.expect(Tok.STRING).value
        return ImportDecl(symbol=sym, source=source, kind=kind)

    # --- evolve ---

    def parse_evolve(self) -> EvolveDecl:
        """Parse an evolve block.

        Per spec/04 §2, an evolve block MUST contain metric, when, an
        action, rollback_on, and history. Missing any of these is a
        compile error (enforced here).

        MVP-supported action: `retune <target>: within [lo, hi]`.
        Other actions are reserved and raise ParseError if encountered.
        """
        from .ast import EvolveAction

        self.expect_keyword("evolve")
        intent_name = self.expect(Tok.IDENT).value
        self.expect(Tok.LBRACE)

        metric: Expr | None = None
        metric_sample_rate = 1.0
        when_condition: Expr | None = None
        action: EvolveAction | None = None
        rollback_on: Expr | None = None
        history_keep: int | None = None
        bounded_by: dict[str, tuple[float, float]] = {}
        review_by: str | None = None
        raw: dict[str, Any] = {}

        while not self.check(Tok.RBRACE):
            if self.check(Tok.EOF):
                raise ParseError("unterminated evolve block")

            field_name = self.expect(Tok.IDENT).value

            if field_name == "metric":
                self.expect(Tok.COLON)
                # metric may be `name` or `name(sampled: 0.05)`
                metric_name = self.expect(Tok.IDENT).value
                metric = Identifier(name=metric_name)
                if self.match(Tok.LPAREN):
                    # parse sampled: <number> (only recognized kwarg)
                    while not self.check(Tok.RPAREN):
                        kw = self.expect(Tok.IDENT).value
                        self.expect(Tok.COLON)
                        if kw == "sampled":
                            metric_sample_rate = float(self.expect(Tok.NUMBER).value)
                        else:
                            # tolerate unknown kwargs for forward compat
                            self.parse_expr()
                        if not self.match(Tok.COMMA):
                            break
                    self.expect(Tok.RPAREN)

            elif field_name == "when":
                when_condition = self.parse_expr()
                # Optional `{ action }` block follows the when clause
                if self.match(Tok.LBRACE):
                    action = self._parse_evolve_action()
                    # Optional bounded_by inside the action block
                    if self.is_keyword("bounded_by"):
                        self.advance()
                        self.expect(Tok.LBRACE)
                        while not self.check(Tok.RBRACE):
                            bname = self.expect(Tok.IDENT).value
                            # allow field.path via dot
                            while self.match(Tok.DOT):
                                bname += "." + self.expect(Tok.IDENT).value
                            self.expect(Tok.COLON)
                            lo, hi = self._parse_bounded_range()
                            bounded_by[bname] = (lo, hi)
                        self.expect(Tok.RBRACE)
                    self.expect(Tok.RBRACE)

            elif field_name == "rollback_on":
                self.expect(Tok.COLON)
                rollback_on = self.parse_expr()

            elif field_name == "history":
                self.expect(Tok.COLON)
                # expect: keep_last N
                self.expect_keyword("keep_last")
                history_keep = int(self.expect(Tok.NUMBER).value)

            elif field_name == "require":
                # `require review_by: <role>`
                self.expect_keyword("review_by")
                self.expect(Tok.COLON)
                review_by = self.expect(Tok.IDENT).value

            else:
                # Tolerate unknown fields for forward compatibility, skip the value
                if self.match(Tok.COLON):
                    self.parse_expr()
                raw[field_name] = "<unparsed>"

        self.expect(Tok.RBRACE)

        # Required fields check (per spec/04 §2)
        missing = []
        if metric is None: missing.append("metric")
        if when_condition is None: missing.append("when")
        if action is None: missing.append("action (inside when block)")
        if rollback_on is None: missing.append("rollback_on")
        if history_keep is None: missing.append("history")
        if missing:
            raise ParseError(
                f"evolve {intent_name}: missing required field(s): "
                + ", ".join(missing)
                + " (per spec/04 §2)"
            )

        return EvolveDecl(
            intent_name=intent_name,
            metric=metric,
            metric_sample_rate=metric_sample_rate,
            when_condition=when_condition,
            action=action,
            rollback_on=rollback_on,
            history_keep=history_keep,
            bounded_by=bounded_by,
            review_by=review_by,
            raw=raw,
        )

    def _parse_evolve_action(self):
        """Parse a single action inside a when { ... } block.

        MVP grammar:
            retune <target>: within [<lo>, <hi>]
            rewrite constraints tighten_numeric_thresholds_by <delta>
        """
        from .ast import EvolveAction

        # Read action keyword (first identifier)
        kw = self.expect(Tok.IDENT).value

        if kw == "retune":
            target = self.expect(Tok.IDENT).value
            self.expect(Tok.COLON)
            self.expect_keyword("within")
            self.expect(Tok.LBRACK)
            lo = float(self.expect(Tok.NUMBER).value)
            self.expect(Tok.COMMA)
            hi = float(self.expect(Tok.NUMBER).value)
            self.expect(Tok.RBRACK)
            return EvolveAction(
                kind="retune", target=target,
                range_lo=lo, range_hi=hi,
            )

        if kw == "rewrite":
            what = self.expect(Tok.IDENT).value
            if what != "constraints":
                raise ParseError(
                    f"'rewrite {what}' not supported in MVP; "
                    f"only 'rewrite constraints' is implemented. "
                    f"See spec/04 §4 for the full action set."
                )
            # Expect the specific tightening directive (only supported variant)
            mode = self.expect(Tok.IDENT).value
            if mode != "tighten_numeric_thresholds_by":
                raise ParseError(
                    f"'rewrite constraints {mode}' not recognized; "
                    f"expected 'tighten_numeric_thresholds_by <delta>'."
                )
            delta = float(self.expect(Tok.NUMBER).value)
            return EvolveAction(
                kind="rewrite_constraints",
                tighten_delta=delta,
            )

        raise ParseError(
            f"evolve action '{kw}' not supported in MVP. "
            f"Supported: 'retune', 'rewrite constraints'. "
            f"See spec/04 §4 for the full action set."
        )

    def _parse_bounded_range(self) -> tuple[float, float]:
        """Parse a bounded_by range value. Supports:
            [lo, hi]
            >= lo
            <= hi
        """
        if self.match(Tok.LBRACK):
            lo = float(self.expect(Tok.NUMBER).value)
            self.expect(Tok.COMMA)
            hi = float(self.expect(Tok.NUMBER).value)
            self.expect(Tok.RBRACK)
            return (lo, hi)
        if self.match(Tok.GEQ):
            lo = float(self.expect(Tok.NUMBER).value)
            return (lo, float("inf"))
        if self.match(Tok.LEQ):
            hi = float(self.expect(Tok.NUMBER).value)
            return (float("-inf"), hi)
        raise ParseError(f"expected [lo, hi] or >= N or <= N at {self.peek()}")

    # --- common pieces ---

    def parse_params(self) -> list[tuple[str, str | None]]:
        self.expect(Tok.LPAREN)
        params: list[tuple[str, str | None]] = []
        if not self.check(Tok.RPAREN):
            params.append(self.parse_param())
            while self.match(Tok.COMMA):
                params.append(self.parse_param())
        self.expect(Tok.RPAREN)
        return params

    def parse_param(self) -> tuple[str, str | None]:
        name = self.expect(Tok.IDENT).value
        ty = None
        if self.match(Tok.COLON):
            ty = self.parse_type_name()
        return (name, ty)

    def parse_type_name(self) -> str:
        # Parses parametric types like List[Number], Map[Text, Number],
        # Result[Text], Tuple[Number, Text]. Spec §2.3 freezes this
        # surface syntax; the parser previously ignored the bracket
        # part, which made spec-valid programs fail to parse. The
        # type is still not used for static checking — brackets are
        # consumed and discarded — but the model's preferred shape
        # is now accepted.
        name = self.expect(Tok.IDENT).value
        if self.match(Tok.LBRACK):
            depth = 1
            while depth > 0 and not self.check(Tok.EOF):
                if self.match(Tok.LBRACK):
                    depth += 1
                elif self.match(Tok.RBRACK):
                    depth -= 1
                else:
                    self.advance()
        return name

    # --- statements ---

    def _parse_effect_name(self) -> str:
        """Parse `IDENT ('.' IDENT)*` as a namespaced effect name.

        Returns the dotted form as a single string, e.g. `http.get`.
        Supports the legacy bare form (`human_ask`) without change.
        """
        parts = [self.expect(Tok.IDENT).value]
        while self.match(Tok.DOT):
            parts.append(self.expect(Tok.IDENT).value)
        return ".".join(parts)

    def parse_statement(self) -> Statement:
        if self.is_keyword("return"):
            self.advance()
            if self.check(Tok.RBRACE):
                return ReturnStmt(value=None)
            return ReturnStmt(value=self.parse_expr())
        if self.is_keyword("perform"):
            self.advance()
            effect_name = self._parse_effect_name()
            self.expect(Tok.LPAREN)
            args, kwargs = self.parse_call_args()
            self.expect(Tok.RPAREN)
            return PerformStmt(effect=effect_name, args=args, kwargs=kwargs)
        if self.is_keyword("branch"):
            return self.parse_branch()
        if self.is_keyword("with"):
            return self.parse_with()
        if self.is_keyword("if"):
            return self.parse_if()
        if self.is_keyword("for"):
            return self.parse_for()

        # Assignment: IDENT = expr, if next is EQ
        if self.peek().kind == Tok.IDENT and self.tokens[self.i + 1].kind == Tok.EQ:
            name = self.advance().value
            self.advance()  # =
            # allow `name = perform effect(...)` as a special rhs
            if self.is_keyword("perform"):
                self.advance()
                effect_name = self._parse_effect_name()
                self.expect(Tok.LPAREN)
                args, kwargs = self.parse_call_args()
                self.expect(Tok.RPAREN)
                from .ast import PerformExpr
                return Assignment(name=name, value=PerformExpr(effect=effect_name, args=args, kwargs=kwargs))
            value = self.parse_expr()
            return Assignment(name=name, value=value)

        return ExprStmt(expr=self.parse_expr())

    def parse_branch(self) -> BranchStmt:
        self.expect_keyword("branch")
        subject = self.parse_expr()
        self.expect(Tok.LBRACE)
        arms: list[BranchArm] = []
        while not self.check(Tok.RBRACE):
            self.expect(Tok.LBRACK)
            if self.is_keyword("otherwise"):
                cond: Expr = Identifier(name="otherwise")
                self.advance()
            else:
                cond = self.parse_expr()
            self.expect(Tok.RBRACK)
            self.expect(Tok.FATARROW)
            action = self.parse_statement()
            arms.append(BranchArm(condition=cond, action=action))
        self.expect(Tok.RBRACE)
        calibrate_on = None
        if self.is_keyword("calibrate_on"):
            self.advance()
            calibrate_on = self.expect(Tok.IDENT).value
        return BranchStmt(subject=subject, arms=arms, calibrate_on=calibrate_on)

    def parse_with(self) -> WithContextStmt:
        self.expect_keyword("with")
        self.expect_keyword("context")
        name = self.expect(Tok.IDENT).value
        self.expect(Tok.COLON)
        # MVP: with body is a braced block OR a single statement
        body: list[Statement] = []
        if self.match(Tok.LBRACE):
            while not self.check(Tok.RBRACE):
                body.append(self.parse_statement())
            self.expect(Tok.RBRACE)
        else:
            body.append(self.parse_statement())
        return WithContextStmt(context_name=name, body=body)

    def parse_fn(self, *, purity: str = "default"):
        """Parse a `fn` declaration.

        When called with purity="pure" the caller has already seen the
        `pure` keyword; we consume `fn` and continue. The purity field is
        attached to the resulting FnDecl for later static checking.
        """
        from .ast import FnDecl
        if purity == "pure":
            self.expect_keyword("pure")
        self.expect_keyword("fn")
        name = self.expect(Tok.IDENT).value
        params = self.parse_params()
        return_type = None
        if self.match(Tok.ARROW):
            return_type = self.parse_type_name()
        self.expect(Tok.LBRACE)
        body: list[Statement] = []
        while not self.check(Tok.RBRACE):
            body.append(self.parse_statement())
        self.expect(Tok.RBRACE)
        return FnDecl(name=name, params=params, return_type=return_type,
                      body=body, purity=purity)

    def parse_if(self):
        """Parse `if COND { ... } else if ... { ... } else { ... }`."""
        from .ast import IfStmt
        self.expect_keyword("if")
        cond = self.parse_expr()
        self.expect(Tok.LBRACE)
        then_body: list[Statement] = []
        while not self.check(Tok.RBRACE):
            then_body.append(self.parse_statement())
        self.expect(Tok.RBRACE)
        else_body: list[Statement] = []
        if self.is_keyword("else"):
            self.advance()
            if self.is_keyword("if"):
                # else if -> recursive
                else_body.append(self.parse_if())
            else:
                self.expect(Tok.LBRACE)
                while not self.check(Tok.RBRACE):
                    else_body.append(self.parse_statement())
                self.expect(Tok.RBRACE)
        return IfStmt(condition=cond, then_body=then_body, else_body=else_body)

    def parse_for(self):
        """Parse `for VAR in COLLECTION { ... }`."""
        from .ast import ForStmt
        self.expect_keyword("for")
        var_name = self.expect(Tok.IDENT).value
        self.expect_keyword("in")
        collection = self.parse_expr()
        self.expect(Tok.LBRACE)
        body: list[Statement] = []
        while not self.check(Tok.RBRACE):
            body.append(self.parse_statement())
        self.expect(Tok.RBRACE)
        return ForStmt(var_name=var_name, collection=collection, body=body)

    # --- expressions (precedence climbing) ---

    def parse_expr(self) -> Expr:
        return self.parse_or()

    def parse_or(self) -> Expr:
        left = self.parse_and()
        while self.is_keyword("or"):
            self.advance()
            right = self.parse_and()
            left = BinaryOp(op="or", left=left, right=right)
        return left

    def parse_and(self) -> Expr:
        left = self.parse_not()
        while self.is_keyword("and"):
            self.advance()
            right = self.parse_not()
            left = BinaryOp(op="and", left=left, right=right)
        return left

    def parse_not(self) -> Expr:
        if self.is_keyword("not"):
            self.advance()
            return UnaryOp(op="not", operand=self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Expr:
        left = self.parse_additive()
        cmp_map = {Tok.EQEQ: "==", Tok.NEQ: "!=", Tok.LT: "<", Tok.GT: ">",
                   Tok.LEQ: "<=", Tok.GEQ: ">=", Tok.GGT: ">>", Tok.GGGT: ">>>"}
        if self.peek().kind in cmp_map:
            op = cmp_map[self.advance().kind]
            right = self.parse_additive()
            return BinaryOp(op=op, left=left, right=right)
        # Membership: `x in collection` or `x not in collection`
        if self.is_keyword("in"):
            self.advance()
            collection = self.parse_additive()
            from .ast import MembershipOp
            return MembershipOp(element=left, collection=collection, negated=False)
        if self.is_keyword("not") and self._peek_keyword(1, "in"):
            self.advance()  # not
            self.advance()  # in
            collection = self.parse_additive()
            from .ast import MembershipOp
            return MembershipOp(element=left, collection=collection, negated=True)
        return left

    def _peek_keyword(self, offset: int, kw: str) -> bool:
        """Check whether the token at `offset` ahead of current is the given keyword."""
        pos = self.i + offset
        if pos >= len(self.tokens):
            return False
        t = self.tokens[pos]
        return t.kind == Tok.IDENT and t.value == kw

    def parse_additive(self) -> Expr:
        left = self.parse_multiplicative()
        while self.peek().kind in (Tok.PLUS, Tok.MINUS):
            op = self.advance().value
            right = self.parse_multiplicative()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_multiplicative(self) -> Expr:
        left = self.parse_postfix()
        while self.peek().kind in (Tok.STAR, Tok.SLASH, Tok.PERCENT):
            op = self.advance().value
            right = self.parse_postfix()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.match(Tok.DOT):
                field_name = self.expect(Tok.IDENT).value
                expr = FieldAccess(target=expr, field=field_name)
            elif self.check(Tok.LPAREN):
                self.advance()
                args, kwargs = self.parse_call_args()
                self.expect(Tok.RPAREN)
                expr = Call(callee=expr, args=args, kwargs=kwargs)
            else:
                break
        return expr

    def parse_call_args(self) -> tuple[list[Expr], dict[str, Expr]]:
        args: list[Expr] = []
        kwargs: dict[str, Expr] = {}
        if self.check(Tok.RPAREN):
            return args, kwargs
        while True:
            # named arg?
            if (self.peek().kind == Tok.IDENT
                    and self.tokens[self.i + 1].kind == Tok.COLON):
                name = self.advance().value
                self.advance()  # :
                kwargs[name] = self.parse_expr()
            else:
                args.append(self.parse_expr())
            if not self.match(Tok.COMMA):
                break
        return args, kwargs

    def parse_primary(self) -> Expr:
        t = self.peek()
        if t.kind == Tok.STRING:
            self.advance()
            return Literal(value=t.value)
        if t.kind == Tok.NUMBER:
            self.advance()
            v = float(t.value) if "." in t.value else int(t.value)
            return Literal(value=v)
        if t.kind == Tok.LBRACK:
            self.advance()
            items: list[Expr] = []
            if not self.check(Tok.RBRACK):
                items.append(self.parse_expr())
                while self.match(Tok.COMMA):
                    items.append(self.parse_expr())
            self.expect(Tok.RBRACK)
            return ListLiteral(items=items)
        if t.kind == Tok.LPAREN:
            self.advance()
            e = self.parse_expr()
            self.expect(Tok.RPAREN)
            return e
        if self.match(Tok.MINUS):
            return UnaryOp(op="-", operand=self.parse_primary())
        if t.kind == Tok.IDENT and t.value == "attempt":
            return self.parse_attempt()
        if t.kind == Tok.IDENT and t.value == "match":
            return self.parse_match()
        if t.kind == Tok.IDENT:
            self.advance()
            if t.value == "true":
                return Literal(value=True)
            if t.value == "false":
                return Literal(value=False)
            return Identifier(name=t.value)
        raise ParseError(f"unexpected token {t!r}")

    def parse_attempt(self):
        """Parse `attempt { try EXPR; try EXPR; ... }`.

        Each `try` introduces a single candidate expression. Evaluation is
        left-to-right at runtime; first qualifying result wins. Threshold
        configuration is reserved for a future syntax extension.
        """
        from .ast import AttemptExpr
        self.expect_keyword("attempt")
        self.expect(Tok.LBRACE)
        tries: list[Expr] = []
        while not self.check(Tok.RBRACE):
            self.expect_keyword("try")
            tries.append(self.parse_expr())
        self.expect(Tok.RBRACE)
        if not tries:
            raise ParseError("attempt block must contain at least one `try`")
        return AttemptExpr(tries=tries)

    def parse_match(self):
        """Parse `match EXPR { PATTERN [with confidence OP N] => BODY, ... }`.

        Arm separation is comma-delimited. Trailing comma is optional.
        The pattern is a single expression (literal or identifier); the
        optional confidence guard syntax is `with confidence OP NUMBER`.
        """
        from .ast import MatchExpr, MatchArm
        self.expect_keyword("match")
        subject = self.parse_expr()
        self.expect(Tok.LBRACE)
        arms: list[MatchArm] = []
        while not self.check(Tok.RBRACE):
            arm = self._parse_match_arm()
            arms.append(arm)
            # Optional comma between arms; trailing comma is fine.
            if not self.match(Tok.COMMA):
                # Next thing must be the closing brace.
                if not self.check(Tok.RBRACE):
                    t = self.peek()
                    raise ParseError(
                        f"expected ',' or '}}' after match arm, got "
                        f"{tokName(t.kind)}({t.value!r}) at {t.line}:{t.col}"
                    )
        self.expect(Tok.RBRACE)
        if not arms:
            raise ParseError("match expression must contain at least one arm")
        return MatchExpr(subject=subject, arms=arms)

    def _parse_match_arm(self):
        """Parse a single `PATTERN [with confidence OP N] => BODY`."""
        from .ast import MatchArm
        # Pattern: any expression (but typically literal or ident).
        pattern = self.parse_expr()
        # Optional confidence guard
        conf_op: str | None = None
        conf_threshold: float | None = None
        if self.checkKW_with():
            # `with confidence OP N`
            self.advance()   # consume 'with'
            self.expect_keyword("confidence")
            op_tok = self.advance()
            conf_op = _confidence_op_from_token(op_tok)
            if conf_op is None:
                raise ParseError(
                    f"expected confidence operator (>, <, >=, <=, ==) at "
                    f"{op_tok.line}:{op_tok.col}, got {op_tok.value!r}"
                )
            num_tok = self.expect(Tok.NUMBER)
            conf_threshold = float(num_tok.value)
        self.expect(Tok.FATARROW)
        body = self.parse_expr()
        return MatchArm(
            pattern=pattern, body=body,
            confidence_op=conf_op, confidence_threshold=conf_threshold,
        )

    def checkKW_with(self) -> bool:
        """True if next token is the `with` keyword."""
        return self.check(Tok.IDENT, "with")


def _confidence_op_from_token(tok: Token) -> str | None:
    """Map a Tok.* operator token to its string for confidence guards."""
    mapping = {
        Tok.GT: ">",
        Tok.LT: "<",
        Tok.GEQ: ">=",
        Tok.LEQ: "<=",
        Tok.EQEQ: "==",
    }
    return mapping.get(tok.kind)


def tokName(kind: Tok) -> str:
    """Human-readable token kind name (mirrors Go-impl's tokName)."""
    return kind.name


def parse(source: str) -> Program:
    tokens = tokenize(source)
    program = Parser(tokens).parse_program()
    # Static purity check: verify every `pure fn` body respects the
    # structural contract. Raises PurityError (a subclass of ParseError
    # via re-raise in __init__.py) on violation.
    from .purity import check_program
    check_program(program)
    return program
