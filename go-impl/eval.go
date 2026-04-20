package main

import (
	"fmt"
	"math"
	"strconv"
	"strings"
)

// Value — the runtime representation of any AIL value. Carries
// (value, confidence). Provenance is elided in this v0 Go runtime to
// keep the core minimal; the Python implementation owns provenance and
// the language spec defines it independently of either runtime.
type Value struct {
	V    interface{} // float64 | string | bool | []Value | map[string]Value | nil
	Conf float64
}

func F(v float64) Value         { return Value{V: v, Conf: 1.0} }
func S(v string) Value          { return Value{V: v, Conf: 1.0} }
func B(v bool) Value            { return Value{V: v, Conf: 1.0} }
func L(v []Value) Value         { return Value{V: v, Conf: 1.0} }
func Conf(v interface{}, c float64) Value { return Value{V: v, Conf: c} }

type returnSig struct{ val Value }

func (returnSig) Error() string { return "return" }

// Adapter — minimal interface for intent dispatch. The current
// implementation talks HTTP to a local Ollama server.
type Adapter interface {
	Invoke(goal string, constraints []string, inputs map[string]interface{}) (Value, string, error)
}

type Evaluator struct {
	Prog    *Program
	Adapter Adapter
}

func NewEvaluator(p *Program, a Adapter) *Evaluator { return &Evaluator{Prog: p, Adapter: a} }

func (e *Evaluator) Run(input string) (Value, error) {
	if e.Prog.Entry == nil {
		return Value{}, fmt.Errorf("program has no entry declaration")
	}
	scope := map[string]Value{}
	for i, p := range e.Prog.Entry.Params {
		if i == 0 {
			scope[p.Name] = S(input)
		} else {
			scope[p.Name] = Value{V: nil, Conf: 1.0}
		}
	}
	defer func() {}()
	val, err := e.execBlock(e.Prog.Entry.Body, scope)
	if err != nil {
		if rs, ok := err.(returnSig); ok {
			return rs.val, nil
		}
		return Value{}, err
	}
	return val, nil
}

func (e *Evaluator) execBlock(stmts []Stmt, scope map[string]Value) (Value, error) {
	var last Value
	for _, s := range stmts {
		v, err := e.execStmt(s, scope)
		if err != nil {
			return Value{}, err
		}
		last = v
	}
	return last, nil
}

func (e *Evaluator) execStmt(s Stmt, scope map[string]Value) (Value, error) {
	switch st := s.(type) {
	case *AssignStmt:
		v, err := e.evalExpr(st.Value, scope)
		if err != nil {
			return Value{}, err
		}
		scope[st.Name] = v
		return v, nil
	case *ReturnStmt:
		if st.Value == nil {
			return Value{}, returnSig{val: Value{V: nil, Conf: 1.0}}
		}
		v, err := e.evalExpr(st.Value, scope)
		if err != nil {
			return Value{}, err
		}
		return Value{}, returnSig{val: v}
	case *IfStmt:
		c, err := e.evalExpr(st.Cond, scope)
		if err != nil {
			return Value{}, err
		}
		if truthy(c) {
			return e.execBlock(st.Then, scope)
		}
		return e.execBlock(st.Else, scope)
	case *ForStmt:
		coll, err := e.evalExpr(st.Coll, scope)
		if err != nil {
			return Value{}, err
		}
		items, ok := coll.V.([]Value)
		if !ok {
			return Value{}, fmt.Errorf("for: collection is not a list")
		}
		for _, it := range items {
			scope[st.Var] = it
			if _, err := e.execBlock(st.Body, scope); err != nil {
				return Value{}, err
			}
		}
		return Value{}, nil
	case *ExprStmt:
		return e.evalExpr(st.E, scope)
	}
	return Value{}, fmt.Errorf("unknown stmt type %T", s)
}

func (e *Evaluator) evalExpr(expr Expr, scope map[string]Value) (Value, error) {
	switch ex := expr.(type) {
	case *LiteralExpr:
		return Value{V: ex.Value, Conf: 1.0}, nil
	case *IdentExpr:
		if v, ok := scope[ex.Name]; ok {
			return v, nil
		}
		// bare identifiers become string symbols (matches Python semantics
		// for constraint labels like "positive_negative_neutral")
		return S(ex.Name), nil
	case *ListExpr:
		out := make([]Value, 0, len(ex.Items))
		minc := 1.0
		for _, it := range ex.Items {
			v, err := e.evalExpr(it, scope)
			if err != nil {
				return Value{}, err
			}
			out = append(out, v)
			if v.Conf < minc {
				minc = v.Conf
			}
		}
		return Value{V: out, Conf: minc}, nil
	case *BinaryExpr:
		return e.evalBinary(ex, scope)
	case *UnaryExpr:
		v, err := e.evalExpr(ex.Operand, scope)
		if err != nil {
			return Value{}, err
		}
		switch ex.Op {
		case "not":
			return Value{V: !truthy(v), Conf: v.Conf}, nil
		case "-":
			f, ok := v.V.(float64)
			if !ok {
				return Value{}, fmt.Errorf("unary -: operand is not a number")
			}
			return Value{V: -f, Conf: v.Conf}, nil
		}
		return Value{}, fmt.Errorf("unknown unary op %q", ex.Op)
	case *CallExpr:
		return e.evalCall(ex, scope)
	case *AttemptExpr:
		return e.evalAttempt(ex, scope)
	case *MembershipExpr:
		elem, err := e.evalExpr(ex.Element, scope)
		if err != nil {
			return Value{}, err
		}
		coll, err := e.evalExpr(ex.Collection, scope)
		if err != nil {
			return Value{}, err
		}
		contained := containsValue(coll.V, elem.V)
		if ex.Negated {
			contained = !contained
		}
		return Value{V: contained, Conf: minF(elem.Conf, coll.Conf)}, nil
	case *FieldAccess:
		target, err := e.evalExpr(ex.Target, scope)
		if err != nil {
			return Value{}, err
		}
		if m, ok := target.V.(map[string]Value); ok {
			if v, ok := m[ex.Field]; ok {
				return v, nil
			}
			return Value{V: nil, Conf: target.Conf}, nil
		}
		return Value{}, fmt.Errorf("field access on non-record")
	}
	return Value{}, fmt.Errorf("unknown expr type %T", expr)
}

func (e *Evaluator) evalBinary(ex *BinaryExpr, scope map[string]Value) (Value, error) {
	// short-circuit for and/or
	if ex.Op == "and" {
		l, err := e.evalExpr(ex.Left, scope)
		if err != nil {
			return Value{}, err
		}
		if !truthy(l) {
			return l, nil
		}
		r, err := e.evalExpr(ex.Right, scope)
		if err != nil {
			return Value{}, err
		}
		return Value{V: truthy(r), Conf: minF(l.Conf, r.Conf)}, nil
	}
	if ex.Op == "or" {
		l, err := e.evalExpr(ex.Left, scope)
		if err != nil {
			return Value{}, err
		}
		if truthy(l) {
			return l, nil
		}
		return e.evalExpr(ex.Right, scope)
	}
	l, err := e.evalExpr(ex.Left, scope)
	if err != nil {
		return Value{}, err
	}
	r, err := e.evalExpr(ex.Right, scope)
	if err != nil {
		return Value{}, err
	}
	out, err := applyBinop(ex.Op, l.V, r.V)
	if err != nil {
		return Value{}, err
	}
	return Value{V: out, Conf: minF(l.Conf, r.Conf)}, nil
}

func (e *Evaluator) evalCall(c *CallExpr, scope map[string]Value) (Value, error) {
	id, ok := c.Callee.(*IdentExpr)
	if !ok {
		return Value{}, fmt.Errorf("cannot call non-identifier")
	}
	name := id.Name
	// evaluate args
	args := make([]Value, 0, len(c.Args))
	for _, a := range c.Args {
		v, err := e.evalExpr(a, scope)
		if err != nil {
			return Value{}, err
		}
		args = append(args, v)
	}
	// 1. user fn
	if fn, ok := e.Prog.Fns[name]; ok {
		return e.invokeFn(fn, args)
	}
	// 2. user intent
	if it, ok := e.Prog.Intents[name]; ok {
		return e.invokeIntent(it, args)
	}
	// 3. builtin
	if v, ok, err := callBuiltin(name, args); ok {
		return v, err
	}
	return Value{}, fmt.Errorf("unknown callable %q", name)
}

// evalAttempt implements the attempt-block cascade. It evaluates each
// `try` expression in order and returns the first whose value is NOT
// a Result-wrapped error. If every try yields an error, the last one
// is returned as-is (the low-confidence fall-through behavior in the
// Python reference — executor.py:_eval_attempt).
//
// Threshold semantics (confidence gating) aren't implemented here:
// the Go runtime doesn't track confidence as richly as Python, and
// the surface syntax has no threshold clause yet (spec/08 reserves
// it for a future extension). Result-error is therefore the only
// skip condition, which is sufficient for every existing conformance
// case.
func (e *Evaluator) evalAttempt(ex *AttemptExpr, scope map[string]Value) (Value, error) {
	var last Value
	for _, tryExpr := range ex.Tries {
		v, err := e.evalExpr(tryExpr, scope)
		if err != nil {
			return Value{}, err
		}
		last = v
		if isResultError(v.V) {
			continue
		}
		return v, nil
	}
	return last, nil
}

// isResultError reports whether v is a Result wrapping an error —
// i.e. {_result:true, ok:false, error:...}. Matches the Python
// predicate at executor.py:_is_result_error.
func isResultError(v interface{}) bool {
	m, ok := v.(map[string]Value)
	if !ok {
		return false
	}
	r, ok := m["_result"]
	if !ok {
		return false
	}
	if r.V != true {
		return false
	}
	okv, ok := m["ok"]
	if !ok {
		return false
	}
	return okv.V == false
}

func (e *Evaluator) invokeFn(fn *FnDecl, args []Value) (Value, error) {
	local := map[string]Value{}
	for i, p := range fn.Params {
		if i < len(args) {
			local[p.Name] = args[i]
		}
	}
	_, err := e.execBlock(fn.Body, local)
	if err != nil {
		if rs, ok := err.(returnSig); ok {
			return rs.val, nil
		}
		return Value{}, err
	}
	return Value{V: nil, Conf: 1.0}, nil
}

func (e *Evaluator) invokeIntent(it *IntentDecl, args []Value) (Value, error) {
	if e.Adapter == nil {
		return Value{}, fmt.Errorf("no adapter configured — cannot invoke intent %q", it.Name)
	}
	inputs := map[string]interface{}{}
	for i, p := range it.Params {
		if i < len(args) {
			inputs[p.Name] = args[i].V
		}
	}
	v, _, err := e.Adapter.Invoke(it.Goal, it.Constraints, inputs)
	if err != nil {
		return Value{}, err
	}
	return v, nil
}

// ------------ helpers ------------

func truthy(v Value) bool {
	switch x := v.V.(type) {
	case bool:
		return x
	case float64:
		return x != 0
	case string:
		return x != ""
	case []Value:
		return len(x) > 0
	case nil:
		return false
	}
	return true
}

func minF(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

func applyBinop(op string, l, r interface{}) (interface{}, error) {
	// numeric ops
	lf, lok := l.(float64)
	rf, rok := r.(float64)
	if lok && rok {
		switch op {
		case "+":
			return lf + rf, nil
		case "-":
			return lf - rf, nil
		case "*":
			return lf * rf, nil
		case "/":
			return lf / rf, nil
		case "%":
			return math.Mod(lf, rf), nil
		case "==":
			return lf == rf, nil
		case "!=":
			return lf != rf, nil
		case "<":
			return lf < rf, nil
		case ">":
			return lf > rf, nil
		case "<=":
			return lf <= rf, nil
		case ">=":
			return lf >= rf, nil
		}
	}
	// string ops
	ls, lsok := l.(string)
	rs, rsok := r.(string)
	if lsok && rsok {
		switch op {
		case "+":
			return ls + rs, nil
		case "==":
			return ls == rs, nil
		case "!=":
			return ls != rs, nil
		}
	}
	// boolean ops
	lb, lbok := l.(bool)
	rb, rbok := r.(bool)
	if lbok && rbok {
		switch op {
		case "==":
			return lb == rb, nil
		case "!=":
			return lb != rb, nil
		}
	}
	// Heterogeneous equality — `n == false` where n is a float must not
	// panic. Python's == between incompatible types is just False; we
	// match that to keep programs written for the Python runtime valid
	// here.
	if op == "==" {
		return false, nil
	}
	if op == "!=" {
		return true, nil
	}
	return nil, fmt.Errorf("binary %q: incompatible operand types (%T, %T)", op, l, r)
}

func containsValue(coll interface{}, elem interface{}) bool {
	switch c := coll.(type) {
	case []Value:
		for _, v := range c {
			if valueEq(v.V, elem) {
				return true
			}
		}
	case string:
		if s, ok := elem.(string); ok {
			return strings.Contains(c, s)
		}
	}
	return false
}

func valueEq(a, b interface{}) bool {
	// primitive equality; mirrors Go's == for comparable types
	af, aok := a.(float64)
	bf, bok := b.(float64)
	if aok && bok {
		return af == bf
	}
	as, aok2 := a.(string)
	bs, bok2 := b.(string)
	if aok2 && bok2 {
		return as == bs
	}
	ab, aok3 := a.(bool)
	bb, bok3 := b.(bool)
	if aok3 && bok3 {
		return ab == bb
	}
	return false
}

// ------------ builtins ------------

func callBuiltin(name string, args []Value) (Value, bool, error) {
	minc := 1.0
	for _, a := range args {
		if a.Conf < minc {
			minc = a.Conf
		}
	}
	raw := make([]interface{}, len(args))
	for i, a := range args {
		raw[i] = a.V
	}
	switch name {
	case "length":
		if len(raw) < 1 {
			return Value{}, true, fmt.Errorf("length: need 1 arg")
		}
		switch x := raw[0].(type) {
		case string:
			return Value{V: float64(len(x)), Conf: minc}, true, nil
		case []Value:
			return Value{V: float64(len(x)), Conf: minc}, true, nil
		}
		return Value{V: float64(0), Conf: minc}, true, nil
	case "split":
		if len(raw) < 2 {
			return Value{}, true, fmt.Errorf("split: need 2 args")
		}
		s, _ := raw[0].(string)
		d, _ := raw[1].(string)
		var parts []string
		if d == "" {
			for _, r := range s {
				parts = append(parts, string(r))
			}
		} else {
			parts = strings.Split(s, d)
		}
		out := make([]Value, len(parts))
		for i, p := range parts {
			out[i] = S(p)
		}
		return Value{V: out, Conf: minc}, true, nil
	case "join":
		if len(raw) < 2 {
			return Value{}, true, fmt.Errorf("join: need 2 args")
		}
		list, _ := raw[0].([]Value)
		delim, _ := raw[1].(string)
		parts := make([]string, len(list))
		for i, v := range list {
			parts[i] = toText(v.V)
		}
		return Value{V: strings.Join(parts, delim), Conf: minc}, true, nil
	case "append":
		if len(raw) < 2 {
			return Value{}, true, fmt.Errorf("append: need 2 args")
		}
		list, _ := raw[0].([]Value)
		out := append([]Value{}, list...)
		out = append(out, args[1])
		return Value{V: out, Conf: minc}, true, nil
	case "range":
		if len(raw) < 2 {
			return Value{}, true, fmt.Errorf("range: need 2 args")
		}
		start, _ := raw[0].(float64)
		end, _ := raw[1].(float64)
		var out []Value
		for i := start; i < end; i++ {
			out = append(out, F(i))
		}
		return Value{V: out, Conf: minc}, true, nil
	case "to_text":
		if len(raw) < 1 {
			return Value{V: "", Conf: minc}, true, nil
		}
		return Value{V: toText(raw[0]), Conf: minc}, true, nil
	case "to_number":
		if len(raw) < 1 {
			return Value{V: float64(0), Conf: minc}, true, nil
		}
		s, _ := raw[0].(string)
		s = strings.TrimSpace(s)
		f, err := strconv.ParseFloat(s, 64)
		if err != nil {
			// Return a Result-shaped error to match Python semantics
			errMap := map[string]Value{
				"_result": B(true),
				"ok":      B(false),
				"error":   S(fmt.Sprintf("cannot convert to number: %s", s)),
			}
			return Value{V: errMap, Conf: minc}, true, nil
		}
		return Value{V: f, Conf: minc}, true, nil
	case "trim":
		if len(raw) < 1 {
			return Value{V: "", Conf: minc}, true, nil
		}
		s, _ := raw[0].(string)
		return Value{V: strings.TrimSpace(s), Conf: minc}, true, nil
	case "upper":
		s, _ := raw[0].(string)
		return Value{V: strings.ToUpper(s), Conf: minc}, true, nil
	case "lower":
		s, _ := raw[0].(string)
		return Value{V: strings.ToLower(s), Conf: minc}, true, nil
	case "get":
		if len(raw) < 2 {
			return Value{V: nil, Conf: minc}, true, nil
		}
		if list, ok := raw[0].([]Value); ok {
			if idx, ok := raw[1].(float64); ok {
				i := int(idx)
				if i >= 0 && i < len(list) {
					return list[i], true, nil
				}
				return Value{V: nil, Conf: minc}, true, nil
			}
		}
		return Value{V: nil, Conf: minc}, true, nil
	case "is_ok":
		if len(raw) < 1 {
			return B(true), true, nil
		}
		if m, ok := raw[0].(map[string]Value); ok {
			if m["_result"].V == true {
				return m["ok"], true, nil
			}
		}
		return B(true), true, nil
	case "is_error":
		if len(raw) < 1 {
			return B(false), true, nil
		}
		if m, ok := raw[0].(map[string]Value); ok {
			if m["_result"].V == true {
				return Value{V: !(m["ok"].V.(bool)), Conf: minc}, true, nil
			}
		}
		return B(false), true, nil
	case "ok":
		// ok(v) -> {_result:true, ok:true, value:v}. Shape matches the
		// Python runtime at executor.py:948 so the two interpreters
		// exchange Result values with identical layout.
		if len(raw) < 1 {
			return Value{}, true, nil
		}
		m := map[string]Value{
			"_result": B(true),
			"ok":      B(true),
			"value":   {V: raw[0], Conf: minc},
		}
		return Value{V: m, Conf: minc}, true, nil
	case "error":
		// error(msg) -> {_result:true, ok:false, error:msg}. Same shape
		// produced internally by to_number on parse failure above.
		if len(raw) < 1 {
			return Value{}, true, nil
		}
		m := map[string]Value{
			"_result": B(true),
			"ok":      B(false),
			"error":   {V: raw[0], Conf: minc},
		}
		return Value{V: m, Conf: minc}, true, nil
	case "unwrap":
		// Python returns "UNWRAP_ERROR: ..." with confidence 0 on
		// error; mirror that exactly.
		if len(raw) < 1 {
			return Value{}, true, nil
		}
		if m, ok := raw[0].(map[string]Value); ok {
			if m["_result"].V == true {
				if m["ok"].V == true {
					return m["value"], true, nil
				}
				errText, _ := m["error"].V.(string)
				return Value{V: "UNWRAP_ERROR: " + errText, Conf: 0.0}, true, nil
			}
		}
		return Value{V: raw[0], Conf: minc}, true, nil
	case "unwrap_or":
		if len(raw) < 2 {
			if len(raw) >= 1 {
				return Value{V: raw[0], Conf: minc}, true, nil
			}
			return Value{}, true, nil
		}
		if m, ok := raw[0].(map[string]Value); ok {
			if m["_result"].V == true {
				if m["ok"].V == true {
					return m["value"], true, nil
				}
				return Value{V: raw[1], Conf: minc}, true, nil
			}
		}
		return Value{V: raw[0], Conf: minc}, true, nil
	case "unwrap_error":
		if len(raw) < 1 {
			return Value{V: "NOT_A_RESULT", Conf: 0.0}, true, nil
		}
		if m, ok := raw[0].(map[string]Value); ok {
			if m["_result"].V == true {
				if m["ok"].V == true {
					return Value{V: "NOT_AN_ERROR", Conf: 0.0}, true, nil
				}
				return m["error"], true, nil
			}
		}
		return Value{V: "NOT_A_RESULT", Conf: 0.0}, true, nil
	}
	return Value{}, false, nil
}

func toText(v interface{}) string {
	switch x := v.(type) {
	case string:
		return x
	case float64:
		if x == math.Trunc(x) && !math.IsInf(x, 0) {
			return strconv.FormatFloat(x, 'f', -1, 64)
		}
		return strconv.FormatFloat(x, 'f', -1, 64)
	case bool:
		if x {
			return "true"
		}
		return "false"
	case nil:
		return ""
	case []Value:
		parts := make([]string, len(x))
		for i, e := range x {
			parts[i] = toText(e.V)
		}
		return "[" + strings.Join(parts, ", ") + "]"
	}
	return fmt.Sprintf("%v", v)
}
