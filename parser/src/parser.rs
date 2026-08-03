//! 재귀 하강 파서 — HEAAL 강제 지점:
//! 1. task 에 goal·done·never 가 하나라도 없으면 파싱 실패 (의도 계약 3슬롯)
//! 2. `while` 토큰은 등장 즉시 실패 — 무한 루프는 표현이 성립하지 않는다 (H4)
//! 3. 반복은 `each x in xs { }` 뿐 (유한 컬렉션)
//!
//! 사이클 interp-skeleton s2: 검증만 하던 파서를 **AST 반환**으로 개조했다.
//! 강제 지점과 오류 메시지는 그대로다 — 하네스는 한 곳에 있어야 한다.

use crate::lexer::{lex, Tok};
use crate::ast::*;

#[derive(Debug)]
pub struct ParseOutcome {
    pub tasks: usize,
    pub warnings: Vec<String>,
}

/// 옛 진입점 — 검증만 필요한 자리(ail-check)를 위해 유지
pub fn parse_program(src: &str) -> Result<ParseOutcome, String> {
    let p = parse(src)?;
    Ok(ParseOutcome { tasks: p.tasks(), warnings: p.warnings })
}

/// 트리를 남기는 진입점 — 인터프리터가 쓴다
pub fn parse(src: &str) -> Result<Program, String> {
    let toks: Vec<Tok> = lex(src);
    let mut p = P { t: toks, i: 0, warnings: Vec::new(), strict_done: true, in_pure: false };
    let mut items = Vec::new();
    p.skip_nl();
    while !p.eof() {
        match p.peek() {
            Some(Tok::Fn) => items.push(Item::Fn(p.parse_fn()?)),
            _ => items.push(Item::Task(p.parse_task()?)),
        }
        p.skip_nl();
    }
    if items.is_empty() { return Err("프로그램에 task 가 없다".into()); }
    Ok(Program { items, warnings: p.warnings })
}

struct P { t: Vec<Tok>, i: usize, warnings: Vec<String>, strict_done: bool, in_pure: bool }

impl P {
    fn eof(&self) -> bool { self.i >= self.t.len() }
    fn peek(&self) -> Option<&Tok> { self.t.get(self.i) }
    fn next(&mut self) -> Option<Tok> { let t = self.t.get(self.i).cloned(); self.i += 1; t }
    fn skip_nl(&mut self) { while matches!(self.peek(), Some(Tok::Newline)) { self.i += 1; } }
    fn expect(&mut self, want: &Tok, ctx: &str) -> Result<(), String> {
        self.skip_nl();
        match self.next() {
            Some(ref t) if t == want => Ok(()),
            other => Err(format!("{} 자리에서 {:?} 를 기대했으나 {:?}", ctx, want, other)),
        }
    }
    fn guard_while(&self, t: &Option<Tok>) -> Result<(), String> {
        if matches!(t, Some(Tok::While)) {
            return Err("`while` 은 AIL 에서 성립하지 않는다 — 유한 반복은 `each x in xs { }` (H4)".into());
        }
        self.guard_unknown(t)
    }

    /// D9(사람 확정) — 문법에 없는 문자는 거부한다. 옛 D6은 조용히 삼켰다.
    fn guard_unknown(&self, t: &Option<Tok>) -> Result<(), String> {
        if let Some(Tok::Unknown(c)) = t {
            let hint = match c {
                ':' => " — 객체는 bareword 다: `{ key value }` (원칙 6)",
                ';' => " — 문장은 줄로 나눈다",
                '|' | '&' => " — 논리 연산은 `&&` `||` 두 글자다",
                _ => "",
            };
            return Err(format!("문법에 없는 문자 `{}`{}", c, hint));
        }
        Ok(())
    }

    fn parse_params(&mut self) -> Result<Vec<String>, String> {
        self.expect(&Tok::LParen, "매개변수")?;
        let mut ps = Vec::new();
        loop {
            match self.next() {
                Some(Tok::RParen) => break,
                Some(Tok::Ident(n)) => ps.push(n),
                Some(Tok::Comma) => continue,
                other => return Err(format!("매개변수 목록에서 {:?}", other)),
            }
        }
        Ok(ps)
    }

    /// 순수 함수 — 효과가 문법적으로 불가능한 블록 (계약 슬롯 불요, 순수성이 하네스)
    fn parse_fn(&mut self) -> Result<FnDecl, String> {
        self.expect(&Tok::Fn, "fn 선언")?;
        let name = match self.next() {
            Some(Tok::Ident(n)) => n,
            other => return Err(format!("fn 이름을 기대했으나 {:?}", other)),
        };
        let params = self.parse_params()?;
        self.in_pure = true;
        let body = self.parse_block();
        self.in_pure = false;
        Ok(FnDecl { name, params, body: body? })
    }

    fn parse_task(&mut self) -> Result<TaskDecl, String> {
        self.expect(&Tok::Task, "task 선언")?;
        let name = match self.next() {
            Some(Tok::Ident(n)) => n,
            other => return Err(format!("task 이름을 기대했으나 {:?}", other)),
        };
        let params = self.parse_params()?;
        self.expect(&Tok::LBrace, "task 본문")?;
        let (mut has_goal, mut has_done, mut has_never) = (false, false, false);
        let mut goal = String::new();
        let mut done = None;
        let mut never = Vec::new();
        let mut uses = Vec::new();
        let mut limit = None;
        let mut again = None;
        let mut body = Vec::new();
        loop {
            self.skip_nl();
            let t = self.peek().cloned();
            self.guard_while(&t)?;
            match t {
                Some(Tok::RBrace) => { self.i += 1; break; }
                Some(Tok::Goal) => { self.i += 1; goal = self.take_freetext(); has_goal = true; }
                Some(Tok::Limit) => { self.i += 1; limit = Some(self.take_freetext()); }
                Some(Tok::Done) => {
                    self.i += 1;
                    if matches!(self.peek(), Some(Tok::Str(_))) {
                        if self.strict_done {
                            return Err("done 은 판정 가능식이어야 한다 — 문자열(산문)은 계약이 아니다 (D2, 사람 확정: 성공 판정에 LLM 이 필요해지면 H3 위반)".into());
                        }
                        self.warnings.push("done 이 문자열 — 완화 정책 모드 (D2)".into());
                    }
                    done = Some(self.parse_expr()?);
                    self.eat_to_newline();
                    has_done = true;
                }
                Some(Tok::Never) => { self.i += 1; never = self.parse_never()?; has_never = true; }
                Some(Tok::Uses) => { self.i += 1; uses = self.parse_bracket_list("uses")?; }
                Some(Tok::Again) => { self.i += 1; again = Some(self.parse_again()?); }
                None => return Err("task 본문이 닫히지 않았다".into()),
                _ => body.push(self.parse_stmt()?),
            }
        }
        // ── HEAAL 강제: 3슬롯 필수 ──
        let mut missing = Vec::new();
        if !has_goal { missing.push("goal"); }
        if !has_done { missing.push("done"); }
        if !has_never { missing.push("never"); }
        if !missing.is_empty() {
            return Err(format!("의도 계약 위반 — 필수 슬롯 누락: {} (goal·done·never 없는 task 는 존재하지 않는다)", missing.join(", ")));
        }
        Ok(TaskDecl { name, params, goal, done, never, uses, limit, again, body })
    }

    fn take_freetext(&mut self) -> String {
        let mut s = String::new();
        while !matches!(self.peek(), Some(Tok::Newline) | None) {
            if let Some(Tok::FreeText(t)) = self.peek() { s = t.clone(); }
            self.i += 1;
        }
        s
    }
    fn eat_to_newline(&mut self) {
        while !matches!(self.peek(), Some(Tok::Newline) | None) { self.i += 1; }
    }

    fn parse_never(&mut self) -> Result<Vec<String>, String> {
        // `never [a, b]` 정식 / `never a b` 관용 수용(경고, 결정 목록 D3)
        match self.peek() {
            Some(Tok::LBracket) => { self.i += 1; self.parse_ident_list_until_rbracket("never") }
            Some(Tok::Ident(_)) => {
                self.warnings.push("never 목록이 대괄호 없이 왔다 (결정 목록 D3)".into());
                let mut out = Vec::new();
                while !matches!(self.peek(), Some(Tok::Newline) | None) {
                    if let Some(Tok::Ident(n)) = self.peek() { out.push(n.clone()); }
                    self.i += 1;
                }
                Ok(out)
            }
            other => Err(format!("never 목록을 기대했으나 {:?}", other)),
        }
    }
    fn parse_bracket_list(&mut self, ctx: &str) -> Result<Vec<String>, String> {
        self.expect(&Tok::LBracket, ctx)?;
        self.parse_ident_list_until_rbracket(ctx)
    }
    fn parse_ident_list_until_rbracket(&mut self, ctx: &str) -> Result<Vec<String>, String> {
        let mut out = Vec::new();
        loop {
            match self.next() {
                Some(Tok::RBracket) => return Ok(out),
                Some(Tok::Ident(n)) => { out.push(n); }
                Some(Tok::Comma) | Some(Tok::Dot) => continue,
                other => return Err(format!("{} 목록에서 {:?}", ctx, other)),
            }
        }
    }
    fn parse_again(&mut self) -> Result<(u32, Option<u32>), String> {
        let n = match self.next() {
            Some(Tok::Num(s)) => s.parse::<f64>().unwrap_or(0.0) as u32,
            other => return Err(format!("again 뒤에는 유한 횟수 리터럴 (H4) — 받은 것 {:?}", other)),
        };
        let mut w = None;
        if matches!(self.peek(), Some(Tok::Wait)) {
            self.i += 1;
            match self.next() {
                Some(Tok::Num(s)) => { w = Some(s.parse::<f64>().unwrap_or(0.0) as u32); }
                other => return Err(format!("wait 뒤에는 숫자 — 받은 것 {:?}", other)),
            }
        }
        Ok((n, w))
    }

    fn parse_block(&mut self) -> Result<Vec<Stmt>, String> {
        self.expect(&Tok::LBrace, "블록")?;
        let mut out = Vec::new();
        loop {
            self.skip_nl();
            let t = self.peek().cloned();
            self.guard_while(&t)?;
            match t {
                Some(Tok::RBrace) => { self.i += 1; return Ok(out); }
                None => return Err("블록이 닫히지 않았다".into()),
                _ => out.push(self.parse_stmt()?),
            }
        }
    }

    fn parse_stmt(&mut self) -> Result<Stmt, String> {
        self.skip_nl();
        let t = self.peek().cloned();
        self.guard_while(&t)?;
        if self.in_pure {
            if matches!(t, Some(Tok::Uses) | Some(Tok::Again) | Some(Tok::Never) | Some(Tok::Done) | Some(Tok::Goal) | Some(Tok::Limit) | Some(Tok::Fail)) {
                return Err(format!("fn 은 순수하다 — {:?} 는 fn 안에서 성립하지 않는다 (효과·계약은 task 의 것)", t));
            }
            if let Some(Tok::Ident(name)) = &t {
                if ["http","fs","shell","state","env","llm","clock"].contains(&name.as_str()) {
                    return Err(format!("fn 은 순수하다 — 효과 네임스페이스 `{}` 는 fn 안에서 표현되지 않는다 (H1: 구조적 순수성)", name));
                }
            }
        }
        match t {
            Some(Tok::Let) => {
                self.i += 1;
                let tg = self.parse_target()?;
                self.expect(&Tok::Assign, "let")?;
                Ok(Stmt::Let(tg, self.parse_expr()?))
            }
            Some(Tok::Set) => {
                self.i += 1;
                let tg = self.parse_target()?;
                self.expect(&Tok::Assign, "set")?;
                Ok(Stmt::Set(tg, self.parse_expr()?))
            }
            Some(Tok::Each) => {
                self.i += 1;
                let var = match self.next() {
                    Some(Tok::Ident(n)) => n,
                    o => return Err(format!("each 변수 자리에서 {:?}", o)),
                };
                let mut idx = None;
                if matches!(self.peek(), Some(Tok::Comma)) { // each x, i in xs (원소+인덱스, 사람 승인)
                    self.i += 1;
                    idx = Some(match self.next() {
                        Some(Tok::Ident(n)) => n,
                        o => return Err(format!("each 인덱스 변수 자리에서 {:?}", o)),
                    });
                }
                self.expect(&Tok::In, "each")?;
                let iter = self.parse_expr()?;
                let body = self.parse_block()?;
                Ok(Stmt::Each { var, idx, iter, body })
            }
            Some(Tok::If) => {
                self.i += 1;
                let cond = self.parse_expr()?;
                let then = self.parse_block()?;
                self.skip_nl();
                let mut els = None;
                if matches!(self.peek(), Some(Tok::Else)) {
                    self.i += 1;
                    self.skip_nl();
                    if matches!(self.peek(), Some(Tok::If)) {
                        els = Some(vec![self.parse_stmt()?]);
                    } else {
                        els = Some(self.parse_block()?);
                    }
                }
                Ok(Stmt::If { cond, then, els })
            }
            Some(Tok::Match) => {
                self.i += 1;
                let subject = self.parse_expr()?;
                self.expect(&Tok::LBrace, "match")?;
                let mut cases = Vec::new();
                loop {
                    self.skip_nl();
                    match self.peek() {
                        Some(Tok::RBrace) => { self.i += 1; return Ok(Stmt::Match { subject, cases }); }
                        Some(Tok::Case) => {
                            self.i += 1;
                            let pat = self.parse_expr()?;
                            let b = self.parse_block()?;
                            cases.push((pat, b));
                        }
                        other => return Err(format!("match 안에서 {:?}", other)),
                    }
                }
            }
            Some(Tok::Return) => { self.i += 1; Ok(Stmt::Return(Some(self.parse_expr()?))) }
            Some(Tok::Fail) => {
                self.i += 1;
                self.expect(&Tok::Return, "fail")?;
                Ok(Stmt::FailReturn(Some(self.parse_expr()?)))
            }
            Some(Tok::Ident(_)) => {
                // 표현식 문장. 무선언 대입은 거부 (D4, 사람 확정: let=불변 바인딩, 대입은 set)
                let e = self.parse_expr()?;
                if matches!(self.peek(), Some(Tok::Assign)) {
                    return Err("무선언 대입은 성립하지 않는다 — 바인딩은 `let`(불변), 대입은 `set` (D4, H2)".into());
                }
                Ok(Stmt::Expr(e))
            }
            other => Err(format!("문장 자리에서 {:?}", other)),
        }
    }

    /// 대입 좌변: ident (.ident | [expr])*
    fn parse_target(&mut self) -> Result<Target, String> {
        let name = match self.next() {
            Some(Tok::Ident(n)) => n,
            o => return Err(format!("이름 자리에서 {:?}", o)),
        };
        let mut path = Vec::new();
        loop {
            match self.peek() {
                Some(Tok::Dot) => {
                    self.i += 1;
                    match self.next() {
                        Some(Tok::Ident(n)) => path.push(PathSeg::Member(n)),
                        Some(Tok::Done) => path.push(PathSeg::Member("done".into())),
                        Some(Tok::Num(n)) => path.push(PathSeg::Member(n)),
                        o => return Err(format!("멤버 이름 자리에서 {:?}", o)),
                    }
                }
                Some(Tok::LBracket) => {
                    self.i += 1;
                    let e = self.parse_expr()?;
                    self.expect(&Tok::RBracket, "인덱스")?;
                    path.push(PathSeg::Index(e));
                }
                _ => return Ok(Target { name, path }),
            }
        }
    }

    fn parse_args(&mut self) -> Result<Vec<Expr>, String> {
        let mut out = Vec::new();
        loop {
            self.skip_nl();
            if matches!(self.peek(), Some(Tok::RParen)) { self.i += 1; return Ok(out); }
            out.push(self.parse_expr()?);
            // 명명 인자 관용 `timeout 5` (결정 목록 D7)
            if matches!(self.peek(), Some(Tok::Num(_)) | Some(Tok::Str(_)) | Some(Tok::Ident(_))) {
                out.push(self.parse_expr()?);
            }
            if matches!(self.peek(), Some(Tok::Comma)) { self.i += 1; }
        }
    }

    fn parse_expr(&mut self) -> Result<Expr, String> {
        self.parse_bin(0)
    }

    /// 우선순위 등반 — 관용을 따른다(곱셈이 덧셈보다 먼저).
    /// 사이클 interp-skeleton s2 에서 실행으로 드러난 구멍: 옛 파서는 평탄 좌결합이라
    /// `t + x * i` 를 `(t + x) * i` 로 읽었다. 검증만 할 땐 보이지 않았다.
    fn parse_bin(&mut self, min_prec: u8) -> Result<Expr, String> {
        let mut lhs = self.parse_unary()?;
        loop {
            let (op, prec) = match self.peek() {
                Some(Tok::Op(o)) => match prec_of(o) {
                    Some(p) if p >= min_prec => (o.clone(), p),
                    _ => return Ok(lhs),
                },
                _ => return Ok(lhs),
            };
            self.i += 1;
            let rhs = self.parse_bin(prec + 1)?; // 좌결합
            lhs = Expr::Bin(Box::new(lhs), op, Box::new(rhs));
        }
    }
    fn parse_unary(&mut self) -> Result<Expr, String> {
        if let Some(Tok::Op(o)) = self.peek().cloned() {
            if o == "!" || o == "-" {
                self.i += 1;
                return Ok(Expr::Un(o, Box::new(self.parse_postfix()?)));
            }
        }
        self.parse_postfix()
    }
    fn parse_postfix(&mut self) -> Result<Expr, String> {
        let mut e = self.parse_atom()?;
        loop {
            match self.peek() {
                Some(Tok::Dot) => {
                    self.i += 1;
                    match self.next() {
                        Some(Tok::Ident(n)) => e = Expr::Member(Box::new(e), n),
                        Some(Tok::Done) => e = Expr::Member(Box::new(e), "done".into()),
                        Some(Tok::Num(n)) => e = Expr::Member(Box::new(e), n),
                        o => return Err(format!("멤버 이름 자리에서 {:?}", o)),
                    }
                }
                Some(Tok::LParen) => { self.i += 1; e = Expr::Call(Box::new(e), self.parse_args()?); }
                Some(Tok::LBracket) => {
                    self.i += 1;
                    let ix = self.parse_expr()?;
                    self.expect(&Tok::RBracket, "인덱스")?;
                    e = Expr::Index(Box::new(e), Box::new(ix));
                }
                _ => return Ok(e),
            }
        }
    }
    fn parse_atom(&mut self) -> Result<Expr, String> {
        self.skip_nl();
        let t = self.peek().cloned();
        self.guard_while(&t)?;
        match self.next() {
            Some(Tok::Ident(name)) => {
                if self.in_pure && ["http","fs","shell","state","env","llm","clock"].contains(&name.as_str())
                    && matches!(self.peek(), Some(Tok::Dot)) {
                    return Err(format!("fn 은 순수하다 — 효과 네임스페이스 `{}` 는 fn 안에서 표현되지 않는다 (H1: 구조적 순수성)", name));
                }
                // 단일 인자 화살표 람다 `x => expr` (사이클 stdlib-vocab s15, 가설 A)
                if matches!(self.peek(), Some(Tok::Arrow)) {
                    self.i += 1;
                    return Ok(Expr::Lambda(name, Box::new(self.parse_expr()?)));
                }
                Ok(Expr::Ident(name))
            }
            Some(Tok::Num(n)) => Ok(Expr::Num(n.parse::<f64>().unwrap_or(0.0))),
            Some(Tok::Str(s)) => Ok(Expr::Str(s)),
            // 예약어의 bareword/값 사용 허용 (v2 승인): `return { done 5 }`, `return ok`
            Some(Tok::Done) => Ok(Expr::Ident("done".into())),
            Some(Tok::Fail) => Ok(Expr::Ident("fail".into())),
            Some(Tok::Case) => Ok(Expr::Ident("case".into())),
            Some(Tok::If) => {
                // 식 위치 조건식 `if c { a } else { b }` (사람 승인)
                let cond = self.parse_expr()?;
                self.expect(&Tok::LBrace, "조건식")?;
                let a = self.parse_expr()?;
                self.expect(&Tok::RBrace, "조건식")?;
                self.skip_nl();
                if !matches!(self.peek(), Some(Tok::Else)) {
                    return Err("조건식에는 else 가 필수다 — 값이 없는 갈래는 식이 될 수 없다".into());
                }
                self.i += 1;
                self.skip_nl();
                self.expect(&Tok::LBrace, "조건식")?;
                let b = self.parse_expr()?;
                self.expect(&Tok::RBrace, "조건식")?;
                Ok(Expr::IfExpr(Box::new(cond), Box::new(a), Box::new(b)))
            }
            Some(Tok::LParen) => {
                let e = self.parse_expr()?;
                self.expect(&Tok::RParen, "괄호식")?;
                Ok(e)
            }
            Some(Tok::LBracket) => { // 리스트 리터럴
                let mut out = Vec::new();
                loop {
                    self.skip_nl();
                    if matches!(self.peek(), Some(Tok::RBracket)) { self.i += 1; return Ok(Expr::List(out)); }
                    out.push(self.parse_expr()?);
                    if matches!(self.peek(), Some(Tok::Comma)) { self.i += 1; }
                }
            }
            Some(Tok::LBrace) => { // bareword 객체: { key value, key2 value2 } / {}
                let mut out = Vec::new();
                loop {
                    self.skip_nl();
                    let key = match self.next() {
                        Some(Tok::RBrace) => return Ok(Expr::Obj(out)),
                        Some(Tok::Ident(n)) => n,
                        Some(Tok::Done) => "done".to_string(),
                        Some(Tok::Fail) => "fail".to_string(),
                        other => return Err(format!("객체 키 자리에서 {:?} — 키는 bareword", other)),
                    };
                    self.skip_nl();
                    let val = if !matches!(self.peek(), Some(Tok::Comma) | Some(Tok::RBrace)) {
                        self.parse_expr()?
                    } else {
                        Expr::Ident(key.clone()) // shorthand `{ ok }`
                    };
                    out.push((key, val));
                    self.skip_nl();
                    if matches!(self.peek(), Some(Tok::Comma)) { self.i += 1; }
                }
            }
            other => Err(format!("표현식 자리에서 {:?}", other)),
        }
    }
}

/// 이항 연산자 우선순위 (클수록 강하게 묶는다)
fn prec_of(op: &str) -> Option<u8> {
    Some(match op {
        "||" => 1,
        "&&" => 2,
        "==" | "!=" => 3,
        "<" | ">" | "<=" | ">=" => 4,
        "+" | "-" => 5,
        "*" | "/" | "%" => 6,
        _ => return None,
    })
}
