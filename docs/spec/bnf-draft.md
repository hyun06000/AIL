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
stmt      := "let" target "=" expr       # 불변 바인딩 (D4)
           | "set" target "=" expr        # 대입 (D4)
           | target                        # 표현식 문장 (무선언 대입은 거부)
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
| P2-ail-v2 | OK → **REJECT** (결정 반영 후) | done 문자열(D2 확정 거부) |
| P3-ail-v2 | REJECT → **OK** (결정 반영 후) | D8 위치 기반으로 해소 |

## 문법 결정 목록 — 사람 승인 대기

| # | 미정 지점 | 골격의 보수 선택 | 권고 |
|---|---|---|---|
| D1 | goal·limit 의 형식 | 행 끝까지 자유 텍스트 | goal 은 자유 텍스트 유지, limit 은 구조화(`limit 2000 tokens, 5 s` 파싱) 예정 |
| D2 | ~~done 문자열~~ | **확정: 거부** (기본 strict, 정책 플래그로 완화 가능 — "꽉 닫지는 말자") | 성공 판정에 LLM 이 필요해지면 H3 위반 |
| D3 | never 대괄호 생략 | 수용+경고 | 거부 권고 (형태 하나 원칙) |
| D4 | ~~무선언 대입~~ | **확정: let=불변 바인딩, `set`=대입, 무선언 대입 거부** | H2 정신 |
| D5 | 주석 `#` | 수용 | AIL.md §2 "주석 문화 폐기"와 긴장 — 금지 권고 |
| D6 | 미지 문자 | 무시 | 거부로 전환 예정 (골격 한정 임시) |
| D7 | 명명 인자 `timeout 5` | 수용 | 유지 권고 (bareword 원칙과 정합) |
| D8 | ~~예약어 변수명~~ | **확정: 위치 기반** — 슬롯 키워드(goal·done·never·limit·uses·again)는 행 선두에서만 키워드 | 다중 모델(GPT·오픈소스)로 하이쿠 편향 점검 실험 예정(사람 지시) |
