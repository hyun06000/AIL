package main

import (
	"fmt"
	"strconv"
	"strings"
)

// Parser — recursive-descent parser mirroring the Python reference
// implementation. Only the subset needed for Go v0 is implemented:
//
//   fn NAME(params) -> Type { body }
//   intent NAME(params) -> Type { goal: ...  constraints { ... } }
//   entry NAME(params) { body }
//   Statements: VAR = EXPR ; return EXPR ; if / else ; for VAR in EXPR ; expr-stmt
//   Expressions: literals, ident, field access, calls, binary & unary ops,
//                lists, membership (in / not in)
//
// Not yet supported (skipped from the AST): context, evolve, effect,
// import, perform, branch, attempt, with. A program using those will
// fail to parse — matching the scope advertised by the go-impl.

type ParseError struct {
	Msg  string
	Line int
	Col  int
}

func (e ParseError) Error() string {
	return fmt.Sprintf("parse error at %d:%d: %s", e.Line, e.Col, e.Msg)
}

type Parser struct {
	tokens []Token
	i      int
}

func NewParser(tokens []Token) *Parser { return &Parser{tokens: tokens} }

func (p *Parser) peekAt(off int) Token { return p.tokens[p.i+off] }
func (p *Parser) peek() Token          { return p.peekAt(0) }
func (p *Parser) advance() Token       { t := p.tokens[p.i]; p.i++; return t }

func (p *Parser) check(kind TokKind) bool { return p.peek().Kind == kind }
func (p *Parser) checkKW(kw string) bool {
	return p.peek().Kind == TokIdent && p.peek().Value == kw
}
func (p *Parser) match(kind TokKind) bool {
	if p.check(kind) {
		p.advance()
		return true
	}
	return false
}
func (p *Parser) matchKW(kw string) bool {
	if p.checkKW(kw) {
		p.advance()
		return true
	}
	return false
}

func (p *Parser) expect(kind TokKind) (Token, error) {
	if !p.check(kind) {
		t := p.peek()
		return Token{}, ParseError{
			Msg:  fmt.Sprintf("expected %s, got %s(%q)", tokName(kind), tokName(t.Kind), t.Value),
			Line: t.Line, Col: t.Col,
		}
	}
	return p.advance(), nil
}

func (p *Parser) expectKW(kw string) error {
	if !p.checkKW(kw) {
		t := p.peek()
		return ParseError{Msg: fmt.Sprintf("expected %q, got %s(%q)", kw, tokName(t.Kind), t.Value), Line: t.Line, Col: t.Col}
	}
	p.advance()
	return nil
}

func (p *Parser) ParseProgram() (*Program, error) {
	prog := NewProgram()
	for !p.check(TokEOF) {
		if err := p.parseTopLevel(prog); err != nil {
			return nil, err
		}
	}
	return prog, nil
}

func (p *Parser) parseTopLevel(prog *Program) error {
	t := p.peek()
	if t.Kind != TokIdent {
		return ParseError{Msg: fmt.Sprintf("unexpected top-level token %s", tokName(t.Kind)), Line: t.Line, Col: t.Col}
	}
	// `pure fn` is accepted for syntax compatibility, but the Go runtime
	// does not enforce the purity check — reaching a pure fn containing
	// an intent call at parse time is acceptable here since the Python
	// implementation owns the static guarantees.
	if t.Value == "pure" && p.peekAt(1).Kind == TokIdent && p.peekAt(1).Value == "fn" {
		p.advance() // consume `pure`
		fn, err := p.parseFn()
		if err != nil {
			return err
		}
		prog.Fns[fn.Name] = fn
		return nil
	}
	switch t.Value {
	case "fn":
		fn, err := p.parseFn()
		if err != nil {
			return err
		}
		prog.Fns[fn.Name] = fn
	case "intent":
		it, err := p.parseIntent()
		if err != nil {
			return err
		}
		prog.Intents[it.Name] = it
	case "entry":
		en, err := p.parseEntry()
		if err != nil {
			return err
		}
		prog.Entry = en
	case "import":
		// Imports are skipped for the v0 Go runtime — the stdlib isn't
		// re-implemented here. Consume the declaration shape to keep
		// parsing. Syntax: `import NAME from "source"`.
		p.advance() // import
		if _, err := p.expect(TokIdent); err != nil {
			return err
		}
		if err := p.expectKW("from"); err != nil {
			return err
		}
		if _, err := p.expect(TokString); err != nil {
			return err
		}
	default:
		return ParseError{Msg: fmt.Sprintf("unexpected top-level keyword %q", t.Value), Line: t.Line, Col: t.Col}
	}
	return nil
}

func (p *Parser) parseParams() ([]Param, error) {
	if _, err := p.expect(TokLParen); err != nil {
		return nil, err
	}
	var params []Param
	if !p.check(TokRParen) {
		for {
			name, err := p.expect(TokIdent)
			if err != nil {
				return nil, err
			}
			typ := ""
			if p.match(TokColon) {
				t, err := p.parseTypeName()
				if err != nil {
					return nil, err
				}
				typ = t
			}
			params = append(params, Param{Name: name.Value, TypeName: typ})
			if !p.match(TokComma) {
				break
			}
		}
	}
	if _, err := p.expect(TokRParen); err != nil {
		return nil, err
	}
	return params, nil
}

func (p *Parser) parseTypeName() (string, error) {
	t, err := p.expect(TokIdent)
	if err != nil {
		return "", err
	}
	return t.Value, nil
}

func (p *Parser) parseFn() (*FnDecl, error) {
	if err := p.expectKW("fn"); err != nil {
		return nil, err
	}
	name, err := p.expect(TokIdent)
	if err != nil {
		return nil, err
	}
	params, err := p.parseParams()
	if err != nil {
		return nil, err
	}
	retType := ""
	if p.match(TokArrow) {
		retType, err = p.parseTypeName()
		if err != nil {
			return nil, err
		}
	}
	if _, err := p.expect(TokLBrace); err != nil {
		return nil, err
	}
	body, err := p.parseBlock()
	if err != nil {
		return nil, err
	}
	if _, err := p.expect(TokRBrace); err != nil {
		return nil, err
	}
	return &FnDecl{Name: name.Value, Params: params, ReturnType: retType, Body: body}, nil
}

func (p *Parser) parseIntent() (*IntentDecl, error) {
	if err := p.expectKW("intent"); err != nil {
		return nil, err
	}
	name, err := p.expect(TokIdent)
	if err != nil {
		return nil, err
	}
	params, err := p.parseParams()
	if err != nil {
		return nil, err
	}
	retType := ""
	if p.match(TokArrow) {
		retType, err = p.parseTypeName()
		if err != nil {
			return nil, err
		}
	}
	if _, err := p.expect(TokLBrace); err != nil {
		return nil, err
	}
	it := &IntentDecl{Name: name.Value, Params: params, ReturnType: retType}
	for !p.check(TokRBrace) {
		if p.checkKW("goal") {
			p.advance()
			if _, err := p.expect(TokColon); err != nil {
				return nil, err
			}
			// Goal is free-form prose up to the next field-terminator or brace.
			// We consume tokens until we see RBRACE or a known field keyword.
			var b strings.Builder
			for !p.check(TokRBrace) && !p.checkKW("constraints") && !p.checkKW("examples") && !p.checkKW("on_low_confidence") && !p.checkKW("trace") {
				if b.Len() > 0 {
					b.WriteByte(' ')
				}
				tok := p.advance()
				b.WriteString(tok.Value)
			}
			it.Goal = strings.TrimSpace(b.String())
		} else if p.checkKW("constraints") {
			p.advance()
			if _, err := p.expect(TokLBrace); err != nil {
				return nil, err
			}
			for !p.check(TokRBrace) {
				var b strings.Builder
				// consume until we reach an identifier that looks like the start
				// of the next constraint, or the closing brace. For simplicity
				// we treat each identifier run as one constraint.
				for !p.check(TokRBrace) {
					tok := p.peek()
					if tok.Kind == TokIdent {
						if b.Len() > 0 {
							break
						}
						b.WriteString(p.advance().Value)
					} else {
						break
					}
				}
				if b.Len() == 0 {
					p.advance() // skip unknown token
				} else {
					it.Constraints = append(it.Constraints, b.String())
				}
			}
			if _, err := p.expect(TokRBrace); err != nil {
				return nil, err
			}
		} else {
			// Skip unknown intent field for v0
			p.advance()
		}
	}
	if _, err := p.expect(TokRBrace); err != nil {
		return nil, err
	}
	return it, nil
}

func (p *Parser) parseEntry() (*EntryDecl, error) {
	if err := p.expectKW("entry"); err != nil {
		return nil, err
	}
	name, err := p.expect(TokIdent)
	if err != nil {
		return nil, err
	}
	params, err := p.parseParams()
	if err != nil {
		return nil, err
	}
	if _, err := p.expect(TokLBrace); err != nil {
		return nil, err
	}
	body, err := p.parseBlock()
	if err != nil {
		return nil, err
	}
	if _, err := p.expect(TokRBrace); err != nil {
		return nil, err
	}
	return &EntryDecl{Name: name.Value, Params: params, Body: body}, nil
}

// --- statements ---

func (p *Parser) parseBlock() ([]Stmt, error) {
	var out []Stmt
	for !p.check(TokRBrace) && !p.check(TokEOF) {
		s, err := p.parseStmt()
		if err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, nil
}

func (p *Parser) parseStmt() (Stmt, error) {
	t := p.peek()
	if t.Kind == TokIdent {
		switch t.Value {
		case "return":
			p.advance()
			if p.check(TokRBrace) {
				return &ReturnStmt{Value: nil}, nil
			}
			e, err := p.parseExpr()
			if err != nil {
				return nil, err
			}
			return &ReturnStmt{Value: e}, nil
		case "if":
			return p.parseIf()
		case "for":
			return p.parseFor()
		}
		// lookahead for assignment: IDENT '=' ... (but not '==')
		if p.peekAt(1).Kind == TokEq {
			name := p.advance().Value
			p.advance() // '='
			val, err := p.parseExpr()
			if err != nil {
				return nil, err
			}
			return &AssignStmt{Name: name, Value: val}, nil
		}
	}
	e, err := p.parseExpr()
	if err != nil {
		return nil, err
	}
	return &ExprStmt{E: e}, nil
}

func (p *Parser) parseIf() (Stmt, error) {
	if err := p.expectKW("if"); err != nil {
		return nil, err
	}
	cond, err := p.parseExpr()
	if err != nil {
		return nil, err
	}
	if _, err := p.expect(TokLBrace); err != nil {
		return nil, err
	}
	thenBody, err := p.parseBlock()
	if err != nil {
		return nil, err
	}
	if _, err := p.expect(TokRBrace); err != nil {
		return nil, err
	}
	var elseBody []Stmt
	if p.matchKW("else") {
		if p.checkKW("if") {
			nested, err := p.parseIf()
			if err != nil {
				return nil, err
			}
			elseBody = []Stmt{nested}
		} else {
			if _, err := p.expect(TokLBrace); err != nil {
				return nil, err
			}
			elseBody, err = p.parseBlock()
			if err != nil {
				return nil, err
			}
			if _, err := p.expect(TokRBrace); err != nil {
				return nil, err
			}
		}
	}
	return &IfStmt{Cond: cond, Then: thenBody, Else: elseBody}, nil
}

func (p *Parser) parseFor() (Stmt, error) {
	if err := p.expectKW("for"); err != nil {
		return nil, err
	}
	name, err := p.expect(TokIdent)
	if err != nil {
		return nil, err
	}
	if err := p.expectKW("in"); err != nil {
		return nil, err
	}
	coll, err := p.parseExpr()
	if err != nil {
		return nil, err
	}
	if _, err := p.expect(TokLBrace); err != nil {
		return nil, err
	}
	body, err := p.parseBlock()
	if err != nil {
		return nil, err
	}
	if _, err := p.expect(TokRBrace); err != nil {
		return nil, err
	}
	return &ForStmt{Var: name.Value, Coll: coll, Body: body}, nil
}

// --- expressions ---
//
// Precedence (low to high):
//   or
//   and
//   == != in not-in
//   < <= > >=
//   + -
//   * / %
//   unary (- not)
//   primary (literal, ident, call, list, paren)

func (p *Parser) parseExpr() (Expr, error) { return p.parseOr() }

func (p *Parser) parseOr() (Expr, error) {
	left, err := p.parseAnd()
	if err != nil {
		return nil, err
	}
	for p.matchKW("or") {
		right, err := p.parseAnd()
		if err != nil {
			return nil, err
		}
		left = &BinaryExpr{Op: "or", Left: left, Right: right}
	}
	return left, nil
}

func (p *Parser) parseAnd() (Expr, error) {
	left, err := p.parseEq()
	if err != nil {
		return nil, err
	}
	for p.matchKW("and") {
		right, err := p.parseEq()
		if err != nil {
			return nil, err
		}
		left = &BinaryExpr{Op: "and", Left: left, Right: right}
	}
	return left, nil
}

func (p *Parser) parseEq() (Expr, error) {
	left, err := p.parseRel()
	if err != nil {
		return nil, err
	}
	for {
		// `in` / `not in` for membership
		if p.checkKW("in") {
			p.advance()
			right, err := p.parseRel()
			if err != nil {
				return nil, err
			}
			left = &MembershipExpr{Element: left, Collection: right, Negated: false}
			continue
		}
		if p.checkKW("not") && p.peekAt(1).Kind == TokIdent && p.peekAt(1).Value == "in" {
			p.advance()
			p.advance()
			right, err := p.parseRel()
			if err != nil {
				return nil, err
			}
			left = &MembershipExpr{Element: left, Collection: right, Negated: true}
			continue
		}
		if p.match(TokEqEq) {
			right, err := p.parseRel()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "==", Left: left, Right: right}
			continue
		}
		if p.match(TokNeq) {
			right, err := p.parseRel()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "!=", Left: left, Right: right}
			continue
		}
		return left, nil
	}
}

func (p *Parser) parseRel() (Expr, error) {
	left, err := p.parseAdd()
	if err != nil {
		return nil, err
	}
	for {
		switch {
		case p.match(TokLT):
			r, err := p.parseAdd()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "<", Left: left, Right: r}
		case p.match(TokGT):
			r, err := p.parseAdd()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: ">", Left: left, Right: r}
		case p.match(TokLEQ):
			r, err := p.parseAdd()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "<=", Left: left, Right: r}
		case p.match(TokGEQ):
			r, err := p.parseAdd()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: ">=", Left: left, Right: r}
		default:
			return left, nil
		}
	}
}

func (p *Parser) parseAdd() (Expr, error) {
	left, err := p.parseMul()
	if err != nil {
		return nil, err
	}
	for {
		switch {
		case p.match(TokPlus):
			r, err := p.parseMul()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "+", Left: left, Right: r}
		case p.match(TokMinus):
			r, err := p.parseMul()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "-", Left: left, Right: r}
		default:
			return left, nil
		}
	}
}

func (p *Parser) parseMul() (Expr, error) {
	left, err := p.parseUnary()
	if err != nil {
		return nil, err
	}
	for {
		switch {
		case p.match(TokStar):
			r, err := p.parseUnary()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "*", Left: left, Right: r}
		case p.match(TokSlash):
			r, err := p.parseUnary()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "/", Left: left, Right: r}
		case p.match(TokPercent):
			r, err := p.parseUnary()
			if err != nil {
				return nil, err
			}
			left = &BinaryExpr{Op: "%", Left: left, Right: r}
		default:
			return left, nil
		}
	}
}

func (p *Parser) parseUnary() (Expr, error) {
	if p.matchKW("not") {
		operand, err := p.parseUnary()
		if err != nil {
			return nil, err
		}
		return &UnaryExpr{Op: "not", Operand: operand}, nil
	}
	if p.match(TokMinus) {
		operand, err := p.parseUnary()
		if err != nil {
			return nil, err
		}
		return &UnaryExpr{Op: "-", Operand: operand}, nil
	}
	return p.parsePostfix()
}

func (p *Parser) parsePostfix() (Expr, error) {
	e, err := p.parsePrimary()
	if err != nil {
		return nil, err
	}
	for {
		if p.match(TokDot) {
			field, err := p.expect(TokIdent)
			if err != nil {
				return nil, err
			}
			e = &FieldAccess{Target: e, Field: field.Value}
			continue
		}
		if p.match(TokLParen) {
			var args []Expr
			if !p.check(TokRParen) {
				for {
					a, err := p.parseExpr()
					if err != nil {
						return nil, err
					}
					args = append(args, a)
					if !p.match(TokComma) {
						break
					}
				}
			}
			if _, err := p.expect(TokRParen); err != nil {
				return nil, err
			}
			e = &CallExpr{Callee: e, Args: args}
			continue
		}
		return e, nil
	}
}

func (p *Parser) parsePrimary() (Expr, error) {
	t := p.peek()
	switch t.Kind {
	case TokString:
		p.advance()
		return &LiteralExpr{Value: t.Value}, nil
	case TokNumber:
		p.advance()
		f, err := strconv.ParseFloat(t.Value, 64)
		if err != nil {
			return nil, ParseError{Msg: fmt.Sprintf("bad number %q", t.Value), Line: t.Line, Col: t.Col}
		}
		return &LiteralExpr{Value: f}, nil
	case TokLBrack:
		p.advance()
		var items []Expr
		if !p.check(TokRBrack) {
			for {
				e, err := p.parseExpr()
				if err != nil {
					return nil, err
				}
				items = append(items, e)
				if !p.match(TokComma) {
					break
				}
			}
		}
		if _, err := p.expect(TokRBrack); err != nil {
			return nil, err
		}
		return &ListExpr{Items: items}, nil
	case TokLParen:
		p.advance()
		e, err := p.parseExpr()
		if err != nil {
			return nil, err
		}
		if _, err := p.expect(TokRParen); err != nil {
			return nil, err
		}
		return e, nil
	case TokMinus:
		p.advance()
		operand, err := p.parseUnary()
		if err != nil {
			return nil, err
		}
		return &UnaryExpr{Op: "-", Operand: operand}, nil
	case TokIdent:
		p.advance()
		switch t.Value {
		case "true":
			return &LiteralExpr{Value: true}, nil
		case "false":
			return &LiteralExpr{Value: false}, nil
		case "attempt":
			return p.parseAttempt()
		}
		return &IdentExpr{Name: t.Value}, nil
	}
	return nil, ParseError{Msg: fmt.Sprintf("unexpected token %s(%q)", tokName(t.Kind), t.Value), Line: t.Line, Col: t.Col}
}

// parseAttempt consumes the body of an `attempt { try EXPR ... }`
// block. The leading `attempt` ident has already been advanced past
// by parsePrimary. Mirrors reference-impl/ail/parser/parser.py
// parse_attempt — no threshold syntax yet, at-least-one try required.
func (p *Parser) parseAttempt() (Expr, error) {
	if _, err := p.expect(TokLBrace); err != nil {
		return nil, err
	}
	var tries []Expr
	for !p.check(TokRBrace) {
		if !p.checkKW("try") {
			t := p.peek()
			return nil, ParseError{
				Msg:  fmt.Sprintf("expected `try` inside attempt block, got %s(%q)", tokName(t.Kind), t.Value),
				Line: t.Line, Col: t.Col,
			}
		}
		p.advance() // consume `try`
		e, err := p.parseExpr()
		if err != nil {
			return nil, err
		}
		tries = append(tries, e)
	}
	if _, err := p.expect(TokRBrace); err != nil {
		return nil, err
	}
	if len(tries) == 0 {
		t := p.peek()
		return nil, ParseError{
			Msg:  "attempt block must contain at least one `try`",
			Line: t.Line, Col: t.Col,
		}
	}
	return &AttemptExpr{Tries: tries}, nil
}
