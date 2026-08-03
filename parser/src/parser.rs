//! 재귀 하강 파서 — HEAAL 강제 지점:
//! 1. task 에 goal·done·never 가 하나라도 없으면 파싱 실패 (의도 계약 3슬롯)
//! 2. `while` 토큰은 등장 즉시 실패 — 무한 루프는 표현이 성립하지 않는다 (H4)
//! 3. 반복은 `each x in xs { }` 뿐 (유한 컬렉션)

use crate::lexer::{lex, Tok};

#[derive(Debug)]
pub struct ParseOutcome {
    pub tasks: usize,
    pub warnings: Vec<String>,
}

pub fn parse_program(src: &str) -> Result<ParseOutcome, String> {
    let toks: Vec<Tok> = lex(src).into_iter().filter(|t| *t != Tok::Newline || true).collect();
    let mut p = P { t: toks, i: 0, warnings: Vec::new(), strict_done: true, in_pure: false }; // D2 strict / in_pure: fn 순수성 강제
    let mut tasks = 0;
    p.skip_nl();
    while !p.eof() {
        match p.peek() {
            Some(Tok::Fn) => p.parse_fn()?,
            _ => p.parse_task()?,
        }
        tasks += 1;
        p.skip_nl();
    }
    if tasks == 0 { return Err("프로그램에 task 가 없다".into()); }
    Ok(ParseOutcome { tasks, warnings: p.warnings })
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
        Ok(())
    }

    /// 순수 함수 — 효과가 문법적으로 불가능한 블록 (계약 슬롯 불요, 순수성이 하네스)
    fn parse_fn(&mut self) -> Result<(), String> {
        self.expect(&Tok::Fn, "fn 선언")?;
        match self.next() {
            Some(Tok::Ident(_)) => {}
            other => return Err(format!("fn 이름을 기대했으나 {:?}", other)),
        }
        self.expect(&Tok::LParen, "매개변수")?;
        loop {
            match self.next() {
                Some(Tok::RParen) => break,
                Some(Tok::Ident(_)) | Some(Tok::Comma) => continue,
                other => return Err(format!("매개변수 목록에서 {:?}", other)),
            }
        }
        self.in_pure = true;
        let r = self.parse_block();
        self.in_pure = false;
        r
    }

    fn parse_task(&mut self) -> Result<(), String> {
        self.expect(&Tok::Task, "task 선언")?;
        match self.next() {
            Some(Tok::Ident(_)) => {}
            other => return Err(format!("task 이름을 기대했으나 {:?}", other)),
        }
        self.expect(&Tok::LParen, "매개변수")?;
        loop {
            match self.next() {
                Some(Tok::RParen) => break,
                Some(Tok::Ident(_)) | Some(Tok::Comma) => continue,
                other => return Err(format!("매개변수 목록에서 {:?}", other)),
            }
        }
        self.expect(&Tok::LBrace, "task 본문")?;
        let (mut has_goal, mut has_done, mut has_never) = (false, false, false);
        loop {
            self.skip_nl();
            let t = self.peek().cloned();
            self.guard_while(&t)?;
            match t {
                Some(Tok::RBrace) => { self.i += 1; break; }
                Some(Tok::Goal) => { self.i += 1; self.eat_freetext(); has_goal = true; }
                Some(Tok::Limit) => { self.i += 1; self.eat_freetext(); }
                Some(Tok::Done) => {
                    self.i += 1;
                    if matches!(self.peek(), Some(Tok::Str(_))) {
                        if self.strict_done {
                            return Err("done 은 판정 가능식이어야 한다 — 문자열(산문)은 계약이 아니다 (D2, 사람 확정: 성공 판정에 LLM 이 필요해지면 H3 위반)".into());
                        }
                        self.warnings.push("done 이 문자열 — 완화 정책 모드 (D2)".into());
                    }
                    self.eat_to_newline();
                    has_done = true;
                }
                Some(Tok::Never) => { self.i += 1; self.parse_never()?; has_never = true; }
                Some(Tok::Uses) => { self.i += 1; self.parse_bracket_list("uses")?; }
                Some(Tok::Again) => { self.i += 1; self.parse_again()?; }
                None => return Err("task 본문이 닫히지 않았다".into()),
                _ => self.parse_stmt()?,
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
        Ok(())
    }

    fn eat_freetext(&mut self) {
        while !matches!(self.peek(), Some(Tok::Newline) | None) { self.i += 1; }
    }
    fn eat_to_newline(&mut self) { self.eat_freetext(); }

    fn parse_never(&mut self) -> Result<(), String> {
        // `never [a, b]` 정식 / `never a b` 관용 수용(경고, 결정 목록 D3)
        match self.peek() {
            Some(Tok::LBracket) => { self.i += 1; self.parse_ident_list_until_rbracket("never") }
            Some(Tok::Ident(_)) => {
                self.warnings.push("never 목록이 대괄호 없이 왔다 (결정 목록 D3)".into());
                self.eat_to_newline(); Ok(())
            }
            other => Err(format!("never 목록을 기대했으나 {:?}", other)),
        }
    }
    fn parse_bracket_list(&mut self, ctx: &str) -> Result<(), String> {
        self.expect(&Tok::LBracket, ctx)?;
        self.parse_ident_list_until_rbracket(ctx)
    }
    fn parse_ident_list_until_rbracket(&mut self, ctx: &str) -> Result<(), String> {
        loop {
            match self.next() {
                Some(Tok::RBracket) => return Ok(()),
                Some(Tok::Ident(_)) | Some(Tok::Comma) | Some(Tok::Dot) => continue,
                other => return Err(format!("{} 목록에서 {:?}", ctx, other)),
            }
        }
    }
    fn parse_again(&mut self) -> Result<(), String> {
        match self.next() {
            Some(Tok::Num(_)) => {}
            other => return Err(format!("again 뒤에는 유한 횟수 리터럴 (H4) — 받은 것 {:?}", other)),
        }
        if matches!(self.peek(), Some(Tok::Wait)) {
            self.i += 1;
            match self.next() {
                Some(Tok::Num(_)) => {}
                other => return Err(format!("wait 뒤에는 숫자 — 받은 것 {:?}", other)),
            }
        }
        Ok(())
    }

    fn parse_block(&mut self) -> Result<(), String> {
        self.expect(&Tok::LBrace, "블록")?;
        loop {
            self.skip_nl();
            let t = self.peek().cloned();
            self.guard_while(&t)?;
            match t {
                Some(Tok::RBrace) => { self.i += 1; return Ok(()); }
                None => return Err("블록이 닫히지 않았다".into()),
                _ => self.parse_stmt()?,
            }
        }
    }

    fn parse_stmt(&mut self) -> Result<(), String> {
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
            Some(Tok::Let) => { self.i += 1; self.parse_target()?; self.expect(&Tok::Assign, "let")?; self.parse_expr()?; Ok(()) }
            Some(Tok::Set) => { self.i += 1; self.parse_target()?; self.expect(&Tok::Assign, "set")?; self.parse_expr()?; Ok(()) }
            Some(Tok::Each) => {
                self.i += 1;
                match self.next() { Some(Tok::Ident(_)) => {}, o => return Err(format!("each 변수 자리에서 {:?}", o)) }
                if matches!(self.peek(), Some(Tok::Comma)) { // each x, i in xs (원소+인덱스, 사람 승인)
                    self.i += 1;
                    match self.next() { Some(Tok::Ident(_)) => {}, o => return Err(format!("each 인덱스 변수 자리에서 {:?}", o)) }
                }
                self.expect(&Tok::In, "each")?;
                self.parse_expr()?;
                self.parse_block()
            }
            Some(Tok::If) => {
                self.i += 1; self.parse_expr()?; self.parse_block()?;
                self.skip_nl();
                if matches!(self.peek(), Some(Tok::Else)) {
                    self.i += 1;
                    self.skip_nl();
                    if matches!(self.peek(), Some(Tok::If)) { self.parse_stmt()?; } else { self.parse_block()?; }
                }
                Ok(())
            }
            Some(Tok::Match) => {
                self.i += 1; self.parse_expr()?;
                self.expect(&Tok::LBrace, "match")?;
                loop {
                    self.skip_nl();
                    match self.peek() {
                        Some(Tok::RBrace) => { self.i += 1; return Ok(()); }
                        Some(Tok::Case) => { self.i += 1; self.parse_expr()?; self.parse_block()?; }
                        other => return Err(format!("match 안에서 {:?}", other)),
                    }
                }
            }
            Some(Tok::Return) => { self.i += 1; self.parse_expr()?; Ok(()) }
            Some(Tok::Fail) => {
                self.i += 1;
                self.expect(&Tok::Return, "fail")?;
                self.parse_expr()?; Ok(())
            }
            Some(Tok::Ident(_)) => {
                // 표현식 문장. 무선언 대입은 거부 (D4, 사람 확정: let=불변 바인딩, 대입은 set)
                self.parse_target()?;
                if matches!(self.peek(), Some(Tok::Assign)) {
                    return Err("무선언 대입은 성립하지 않는다 — 바인딩은 `let`(불변), 대입은 `set` (D4, H2)".into());
                }
                Ok(())
            }
            other => Err(format!("문장 자리에서 {:?}", other)),
        }
    }

    /// 대입 좌변: ident (.ident | [expr])*
    fn parse_target(&mut self) -> Result<(), String> {
        match self.next() { Some(Tok::Ident(_)) => {}, o => return Err(format!("이름 자리에서 {:?}", o)) }
        loop {
            match self.peek() {
                Some(Tok::Dot) => { self.i += 1; match self.next() { Some(Tok::Ident(_)) | Some(Tok::Done) | Some(Tok::Num(_)) => {}, o => return Err(format!("멤버 이름 자리에서 {:?}", o)) } }
                Some(Tok::LBracket) => { self.i += 1; self.parse_expr()?; self.expect(&Tok::RBracket, "인덱스")?; }
                Some(Tok::LParen) => { self.i += 1; self.parse_args()?; }
                _ => return Ok(()),
            }
        }
    }
    fn parse_args(&mut self) -> Result<(), String> {
        loop {
            self.skip_nl();
            if matches!(self.peek(), Some(Tok::RParen)) { self.i += 1; return Ok(()); }
            self.parse_expr()?;
            // 명명 인자 관용 `timeout 5` (결정 목록 D7)
            if matches!(self.peek(), Some(Tok::Num(_)) | Some(Tok::Str(_)) | Some(Tok::Ident(_))) { self.parse_expr()?; }
            if matches!(self.peek(), Some(Tok::Comma)) { self.i += 1; }
        }
    }

    fn parse_expr(&mut self) -> Result<(), String> {
        self.parse_unary()?;
        loop {
            match self.peek().cloned() {
                Some(Tok::Op(_)) => { self.i += 1; self.parse_unary()?; }
                _ => return Ok(()),
            }
        }
    }
    fn parse_unary(&mut self) -> Result<(), String> {
        if matches!(self.peek(), Some(Tok::Op(o)) if o == "!" || o == "-") { self.i += 1; }
        self.parse_postfix()
    }
    fn parse_postfix(&mut self) -> Result<(), String> {
        self.parse_atom()?;
        loop {
            match self.peek() {
                Some(Tok::Dot) => { self.i += 1; match self.next() { Some(Tok::Ident(_)) | Some(Tok::Done) | Some(Tok::Num(_)) => {}, o => return Err(format!("멤버 이름 자리에서 {:?}", o)) } }
                Some(Tok::LParen) => { self.i += 1; self.parse_args()?; }
                Some(Tok::LBracket) => { self.i += 1; self.parse_expr()?; self.expect(&Tok::RBracket, "인덱스")?; }
                _ => return Ok(()),
            }
        }
    }
    fn parse_atom(&mut self) -> Result<(), String> {
        self.skip_nl();
        let t = self.peek().cloned();
        self.guard_while(&t)?;
        match self.next() {
            Some(Tok::If) => { // 조건식 (사람 승인): if c { a } else { b } — else 필수 (H2: 값이 비면 안 된다)
                self.parse_expr()?;
                self.expect(&Tok::LBrace, "조건식 참 가지")?;
                self.parse_expr()?;
                self.skip_nl();
                self.expect(&Tok::RBrace, "조건식 참 가지")?;
                self.skip_nl();
                self.expect(&Tok::Else, "조건식은 else 필수 (H2)")?;
                self.skip_nl();
                self.expect(&Tok::LBrace, "조건식 거짓 가지")?;
                self.parse_expr()?;
                self.skip_nl();
                self.expect(&Tok::RBrace, "조건식 거짓 가지")?;
                return Ok(());
            }
            Some(Tok::Ident(name)) => {
                if self.in_pure && ["http","fs","shell","state","env","llm","clock"].contains(&name.as_str())
                    && matches!(self.peek(), Some(Tok::Dot)) {
                    return Err(format!("fn 은 순수하다 — 효과 네임스페이스 `{}` 는 fn 안에서 표현되지 않는다 (H1: 구조적 순수성)", name));
                }
                // 단일 인자 화살표 람다 `x => expr` (사이클 stdlib-vocab s15, 가설 A)
                if matches!(self.peek(), Some(Tok::Arrow)) { self.i += 1; return self.parse_expr(); }
                Ok(())
            }
            Some(Tok::Num(_)) | Some(Tok::Str(_)) => Ok(()),
            // 예약어의 bareword/값 사용 허용 (v2 승인): `return { done 5 }`, `return ok`
            Some(Tok::Done) | Some(Tok::Fail) | Some(Tok::Case) => Ok(()),
            Some(Tok::LParen) => { self.parse_expr()?; self.expect(&Tok::RParen, "괄호식") }
            Some(Tok::LBracket) => { // 리스트 리터럴
                loop {
                    self.skip_nl();
                    if matches!(self.peek(), Some(Tok::RBracket)) { self.i += 1; return Ok(()); }
                    self.parse_expr()?;
                    if matches!(self.peek(), Some(Tok::Comma)) { self.i += 1; }
                }
            }
            Some(Tok::LBrace) => { // bareword 객체: { key value, key2 value2 } / {}
                loop {
                    self.skip_nl();
                    match self.next() {
                        Some(Tok::RBrace) => return Ok(()),
                        Some(Tok::Ident(_)) | Some(Tok::Done) | Some(Tok::Fail) => {
                            self.skip_nl();
                            if !matches!(self.peek(), Some(Tok::Comma) | Some(Tok::RBrace)) { self.parse_expr()?; }
                            self.skip_nl();
                            if matches!(self.peek(), Some(Tok::Comma)) { self.i += 1; }
                        }
                        other => return Err(format!("객체 키 자리에서 {:?} — 키는 bareword", other)),
                    }
                }
            }
            other => Err(format!("표현식 자리에서 {:?}", other)),
        }
    }
}
