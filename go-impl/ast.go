package main

// AIL AST — a Go-native tree that mirrors the Python reference
// implementation's AST. Interfaces serve as sum types: an Expr is any
// node with exprNode(); a Stmt is any node with stmtNode(). This is the
// idiomatic way to express algebraic data types in Go before generics
// took hold and remains the most readable.

// ---------------- Expressions ----------------

type Expr interface{ exprNode() }

type LiteralExpr struct{ Value interface{} } // float64 | string | bool | []Expr
type IdentExpr struct{ Name string }
type FieldAccess struct {
	Target Expr
	Field  string
}
type CallExpr struct {
	Callee Expr
	Args   []Expr
}
type BinaryExpr struct {
	Op    string
	Left  Expr
	Right Expr
}
type UnaryExpr struct {
	Op      string
	Operand Expr
}
type ListExpr struct{ Items []Expr }
type MembershipExpr struct {
	Element    Expr
	Collection Expr
	Negated    bool
}

func (*LiteralExpr) exprNode()    {}
func (*IdentExpr) exprNode()      {}
func (*FieldAccess) exprNode()    {}
func (*CallExpr) exprNode()       {}
func (*BinaryExpr) exprNode()     {}
func (*UnaryExpr) exprNode()      {}
func (*ListExpr) exprNode()       {}
func (*MembershipExpr) exprNode() {}

// ---------------- Statements ----------------

type Stmt interface{ stmtNode() }

type AssignStmt struct {
	Name  string
	Value Expr
}
type ReturnStmt struct{ Value Expr } // may be nil
type IfStmt struct {
	Cond Expr
	Then []Stmt
	Else []Stmt
}
type ForStmt struct {
	Var  string
	Coll Expr
	Body []Stmt
}
type ExprStmt struct{ E Expr }

func (*AssignStmt) stmtNode() {}
func (*ReturnStmt) stmtNode() {}
func (*IfStmt) stmtNode()     {}
func (*ForStmt) stmtNode()    {}
func (*ExprStmt) stmtNode()   {}

// ---------------- Top-level declarations ----------------

type FnDecl struct {
	Name       string
	Params     []Param
	ReturnType string
	Body       []Stmt
}

type IntentDecl struct {
	Name        string
	Params      []Param
	ReturnType  string
	Goal        string   // raw prose captured as a single string
	Constraints []string // each a prose line
}

type EntryDecl struct {
	Name   string
	Params []Param
	Body   []Stmt
}

type Param struct {
	Name     string
	TypeName string
}

type Program struct {
	Fns     map[string]*FnDecl
	Intents map[string]*IntentDecl
	Entry   *EntryDecl
}

func NewProgram() *Program {
	return &Program{
		Fns:     make(map[string]*FnDecl),
		Intents: make(map[string]*IntentDecl),
	}
}
