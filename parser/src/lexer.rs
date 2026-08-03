//! 렉서 — 키워드는 온전한 영어 단어(원칙 1·2). `while` 은 토큰으로 존재하되
//! 파서가 무조건 거부한다: "표현은 되나 성립하지 않는" H4 강제의 최전선.

#[derive(Debug, Clone, PartialEq)]
pub enum Tok {
    // 계약 슬롯
    Task, Fn, Goal, Done, Never, Limit, Uses, Again, Wait, Set,
    // 문장
    Let, Each, In, If, Else, Match, Case, Return, Fail,
    // 금지어 (렉싱은 되고 파싱에서 거부 — 진단 메시지를 위해)
    While,
    Ident(String), Num(String), Str(String),
    LBrace, RBrace, LParen, RParen, LBracket, RBracket,
    Comma, Dot, Assign,
    Op(String), // == != >= <= < > && || + - * / % !
    Newline,
    FreeText(String), // goal/limit 의 행 끝까지 자유 텍스트 (렉서 모드)
}

pub fn lex(src: &str) -> Vec<Tok> {
    let mut out = Vec::new();
    for raw_line in src.lines() {
        let line = raw_line.trim_end();
        let trimmed = line.trim_start();
        if trimmed.is_empty() { continue; }
        // goal / limit 슬롯은 행 끝까지 자유 텍스트 (보수 선택 — 결정 목록 D1)
        let mut consumed = false;
        for (kw, tok) in [("goal", Tok::Goal), ("limit", Tok::Limit)] {
            if let Some(rest) = trimmed.strip_prefix(kw) {
                if rest.starts_with(' ') || rest.is_empty() {
                    out.push(tok);
                    out.push(Tok::FreeText(rest.trim().to_string()));
                    out.push(Tok::Newline);
                    consumed = true;
                    break;
                }
            }
        }
        if consumed { continue; }
        lex_line(trimmed, &mut out);
        out.push(Tok::Newline);
    }
    out
}

fn lex_line(line: &str, out: &mut Vec<Tok>) {
    let mut first_word = true; // D8: 슬롯 키워드는 행 첫 토큰일 때만 키워드
    let b: Vec<char> = line.chars().collect();
    let mut i = 0;
    while i < b.len() {
        let c = b[i];
        if c.is_whitespace() { i += 1; continue; }
        if c == '#' { break; } // 주석 (결정 목록 D5: 임시 허용)
        if c.is_alphabetic() || c == '_' {
            let start = i;
            while i < b.len() && (b[i].is_alphanumeric() || b[i] == '_') { i += 1; }
            let w: String = b[start..i].iter().collect();
            let slot = first_word; first_word = false;
            out.push(match w.as_str() {
                // 전역 키워드
                "task" => Tok::Task, "fn" => Tok::Fn, "let" => Tok::Let, "set" => Tok::Set,
                "each" => Tok::Each, "in" => Tok::In,
                "if" => Tok::If, "else" => Tok::Else, "match" => Tok::Match,
                "case" => Tok::Case, "return" => Tok::Return, "fail" => Tok::Fail,
                "while" => Tok::While, // H4: 어디서든 예약
                // 슬롯 키워드 — 행 선두에서만 (D8, 사람 확정)
                "done" if slot => Tok::Done,
                "never" if slot => Tok::Never,
                "uses" if slot => Tok::Uses,
                "again" if slot => Tok::Again,
                "wait" => Tok::Wait, // again 문맥 전용이나 렉서 단순화로 전역 유지
                _ => Tok::Ident(w),
            });
            continue;
        }
        if c.is_ascii_digit() {
            let start = i;
            while i < b.len() && (b[i].is_ascii_digit() || b[i] == '.') { i += 1; }
            out.push(Tok::Num(b[start..i].iter().collect()));
            continue;
        }
        if c == '"' {
            let start = i + 1; i += 1;
            while i < b.len() && b[i] != '"' { i += 1; }
            out.push(Tok::Str(b[start..i.min(b.len())].iter().collect()));
            i += 1;
            continue;
        }
        // 2글자 연산자 우선
        if i + 1 < b.len() {
            let two: String = [b[i], b[i + 1]].iter().collect();
            if ["==", "!=", ">=", "<=", "&&", "||", "++"].contains(&two.as_str()) {
                out.push(Tok::Op(two)); i += 2; continue;
            }
        }
        match c {
            '{' => out.push(Tok::LBrace), '}' => out.push(Tok::RBrace),
            '(' => out.push(Tok::LParen), ')' => out.push(Tok::RParen),
            '[' => out.push(Tok::LBracket), ']' => out.push(Tok::RBracket),
            ',' => out.push(Tok::Comma), '.' => out.push(Tok::Dot),
            '=' => out.push(Tok::Assign),
            '<' | '>' | '+' | '-' | '*' | '/' | '%' | '!' => out.push(Tok::Op(c.to_string())),
            _ => {} // 미지 문자는 골격 단계에선 무시 (결정 목록 D6)
        }
        i += 1;
    }
}
