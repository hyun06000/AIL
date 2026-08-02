# AIL BNF 초안 + 문법 결정 목록

> gil 사이클 `ail-grammar-skeleton/parser-skeleton`. **초안** — 구현체는 `parser/`(Rust, cargo test 8/8).
> HEAAL 강제 지점: goal·done·never 누락 task 는 파싱 실패, `while` 은 등장 즉시 실패, 반복은 `each` 뿐.

## BNF (v0 — 파서 골격이 구현하는 범위)

```
program   := task+
task      := "task" IDENT "(" params? ")" "{" member* "}"
member    := slot | stmt
slot      := "goal" FREETEXT NL            # 필수
           | "done" (expr | STRING) NL     # 필수 (STRING 은 경고 — D2)
           | "never" "[" idents? "]"       # 필수
           | "limit" FREETEXT NL
           | "uses" "[" idents? "]"
           | "again" NUM ("wait" NUM)?     # 유한 리터럴만 (H4)
stmt      := "let" target "=" expr
           | target ("=" expr)?            # let 없는 대입은 경고 — D4
           | "each" IDENT "in" expr block  # 유일한 반복
           | "if" expr block ("else" (block | if-stmt))?
           | "match" expr "{" ("case" expr block)* "}"
           | "return" expr
           | "fail" "return" expr
block     := "{" stmt* "}"
target    := IDENT ("." IDENT | "[" expr "]")*
expr      := unary (BINOP unary)*
unary     := ("!" | "-")? postfix
postfix   := atom ("." IDENT | "(" args ")" | "[" expr "]")*
atom      := IDENT | NUM | STRING | "(" expr ")" | list | object
list      := "[" (expr ("," expr)*)? "]"
object    := "{" (KEY expr? ("," KEY expr?)*)? "}"   # KEY = bareword (예약어 허용)
```

## Haiku v2 생성물 판정 (ail-check)

| 생성물 | 판정 | 비고 |
|---|---|---|
| P1-ail-v2 | **OK** | 경고 0 |
| P2-ail-v2 | **OK** | 경고: done 문자열(D2), let 없는 대입 ×6(D4) |
| P3-ail-v2 | **REJECT** | `let done = 0` — 예약어를 변수명으로 (D8, 신규 발견) |

## 문법 결정 목록 — 사람 승인 대기

| # | 미정 지점 | 골격의 보수 선택 | 권고 |
|---|---|---|---|
| D1 | goal·limit 의 형식 | 행 끝까지 자유 텍스트 | goal 은 자유 텍스트 유지, limit 은 구조화(`limit 2000 tokens, 5 s` 파싱) 예정 |
| D2 | done 이 문자열일 때 | 수용+경고 | **거부 권고** — done 은 판정 가능식이어야 계약이다 (Haiku 도 P2 에서 문자열로 흘렀음 — 강제 없으면 샌다) |
| D3 | never 대괄호 생략 | 수용+경고 | 거부 권고 (형태 하나 원칙) |
| D4 | let 없는 대입 | 수용+경고 | 결정 필요 — 불변 기본(let=바인딩, 재대입 금지)이 H2 정신이나, Haiku 관용은 대입. `set` 도입? |
| D5 | 주석 `#` | 수용 | AIL.md §2 "주석 문화 폐기"와 긴장 — 금지 권고 |
| D6 | 미지 문자 | 무시 | 거부로 전환 예정 (골격 한정 임시) |
| D7 | 명명 인자 `timeout 5` | 수용 | 유지 권고 (bareword 원칙과 정합) |
| D8 | **예약어를 변수명으로** (`let done = 0`) | 거부됨 | 결정 필요 — Haiku 가 자연스럽게 쓴다. 슬롯 키워드는 행 선두에서만 키워드로 취급(위치 기반)하면 해소 가능 |
