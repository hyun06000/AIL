//! AST — 파서가 남기는 트리. 인터프리터가 이것을 걷는다.
//!
//! 사이클 ail-runtime/interp-skeleton s2: 파서는 지금까지 검증만 하고 트리를 남기지
//! 않았다(ParseOutcome{tasks, warnings}). 실행하려면 트리가 필요하다 — 검증 로직은
//! 그대로 두고 결과물만 늘린다(하네스는 한 곳에).

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Num(f64),
    Str(String),
    Ident(String),
    /// bareword 객체 `{ key value, key2 value2 }`
    Obj(Vec<(String, Expr)>),
    List(Vec<Expr>),
    /// 이항 연산 `a + b`, `a == b`
    Bin(Box<Expr>, String, Box<Expr>),
    /// 단항 `-x`, `!x`
    Un(String, Box<Expr>),
    /// 호출 `f(a, b)`
    Call(Box<Expr>, Vec<Expr>),
    /// 멤버 `x.name`
    Member(Box<Expr>, String),
    /// 인덱스 `xs[i]`
    Index(Box<Expr>, Box<Expr>),
    /// 단일 인자 화살표 람다 `x => expr`
    Lambda(String, Box<Expr>),
    /// 식 위치 조건식 `if c { a } else { b }`
    IfExpr(Box<Expr>, Box<Expr>, Box<Expr>),
}

#[derive(Debug, Clone, PartialEq)]
pub enum Stmt {
    /// `let x = e` (불변 바인딩, D4)
    Let(Target, Expr),
    /// `set x = e` (재대입, D4)
    Set(Target, Expr),
    /// `each x in xs { .. }` / `each i in range(n) { .. }` / `each x, i in xs { .. }`
    Each { var: String, idx: Option<String>, iter: Expr, body: Vec<Stmt> },
    /// `if c { .. } else { .. }` — else 는 블록이거나 이어지는 if
    If { cond: Expr, then: Vec<Stmt>, els: Option<Vec<Stmt>> },
    Match { subject: Expr, cases: Vec<(Expr, Vec<Stmt>)> },
    Return(Option<Expr>),
    /// `fail return { .. }`
    FailReturn(Option<Expr>),
    Expr(Expr),
}

/// 대입 대상 — 이름 또는 인덱스/멤버 경로
#[derive(Debug, Clone, PartialEq)]
pub struct Target {
    pub name: String,
    pub path: Vec<PathSeg>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum PathSeg {
    Member(String),
    Index(Expr),
}

/// 순수 함수 — 효과가 문법적으로 불가능한 블록
#[derive(Debug, Clone, PartialEq)]
pub struct FnDecl {
    pub name: String,
    pub params: Vec<String>,
    pub body: Vec<Stmt>,
}

/// 의도 계약 — goal·done·never 필수
#[derive(Debug, Clone, PartialEq)]
pub struct TaskDecl {
    pub name: String,
    pub params: Vec<String>,
    pub goal: String,
    /// done 판정식 (D2: 문자열 산문 금지 — 파서가 strict 모드에서 거부)
    pub done: Option<Expr>,
    pub never: Vec<String>,
    pub uses: Vec<String>,
    /// limit 자유 텍스트 원문 — ops 예산은 여기서 파싱한다
    pub limit: Option<String>,
    pub again: Option<(u32, Option<u32>)>,
    pub body: Vec<Stmt>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Item {
    Fn(FnDecl),
    Task(TaskDecl),
}

#[derive(Debug)]
pub struct Program {
    pub items: Vec<Item>,
    pub warnings: Vec<String>,
}

impl Program {
    /// 옛 ParseOutcome 호환 — 항목 개수(테스트가 이것을 센다)
    pub fn tasks(&self) -> usize { self.items.len() }

    pub fn find_fn(&self, name: &str) -> Option<&FnDecl> {
        self.items.iter().find_map(|i| match i {
            Item::Fn(f) if f.name == name => Some(f),
            _ => None,
        })
    }
    pub fn find_task(&self, name: &str) -> Option<&TaskDecl> {
        self.items.iter().find_map(|i| match i {
            Item::Task(t) if t.name == name => Some(t),
            _ => None,
        })
    }
    /// 첫 진입점 — 이름을 모를 때 실행 대상으로 삼는다
    pub fn first_callable(&self) -> Option<&Item> { self.items.first() }
}
