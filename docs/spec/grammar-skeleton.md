# AIL 문법 뼈대 — 초안

> **초안이다. 사양이 아니다.** gil 사이클 `ail-grammar-skeleton/grammar-draft` 산출물.
> 모든 표기는 실측(`experiments/tokenizer/keyword_scan.py`) 위에서 제안되며, 사람 승인과 파서 구현(Rust)의 검증 전까지 바뀔 수 있다.

## 0. 형태 한눈에

```
task fetchUser(url) {
  goal profile
  done profile.name != none
  never [fs, shell]
  limit 2000 tokens, 5 s
  again 3 wait 2
  let data = http.get(url).json
  return { ok, name data.name, email data.email }
  fail return { ok false, error }
}
```

같은 로직의 실측 (사이클 ① A군과 동일 로직):

| | 문자 | o200k | cl100k | qwen2.5 | deepseek | phi3 |
|---|---|---|---|---|---|---|
| **AIL 초안** | 248 | **76** | **76** | **78** | **77** | **89** |
| Python | 461 | 105 | 105 | 105 | 109 | 131 |
| Go | 770 | 189 | 188 | 190 | 197 | 245 |

**5계열 전부에서 Python 대비 −26~−32%.** 절감의 출처는 표기 압축이 아니라 **의례의 흡수**다: Python의 `for attempt in range(retries):`/`try/except`/`time.sleep(2**attempt)` 루프 전체(≈40토큰)가 `again 3 wait 2` 한 줄(6토큰)로, 타임아웃 설정이 `budget` 선언으로 들어갔다 — 원칙 7의 첫 실증.

## 1. 의도 계약 — 프로그램의 단위

모든 실행 단위는 계약 블록이다. 세 슬롯은 **파서 수준 필수**다 (하나라도 없으면 파싱 실패 — HEAAL §5):

| 슬롯 | 키워드 | 뜻 |
|---|---|---|
| 목적 | `goal` | 무엇을 이루려는가 |
| 성공 조건 | `done` | 무엇이 관측되면 달성인가 (판정 가능식) |
| 금지 경계 | `never` | 쓸 수 없는 capability 목록 (기본 전면 금지, 명시 허용은 `uses`) |

## 2. 키워드 — 전수 실측으로 선별

후보 60개 × 5계열 × (단독/공백 뒤) 실측. **기준: 최신 4계열(o200k·cl100k·qwen2.5·deepseek)에서 단독·공백 뒤 모두 1토큰** (phi3 32k는 참고 — 설계 비대상, [tokenizer-survey.md](../research/tokenizer-survey.md) §1).

| 슬롯 | 통과 후보 (전부 1토큰) | 초안 채택 |
|---|---|---|
| 계약 선언 | contract, task, aim, act | `task` ✅ |
| 목적 | goal, target, want | `goal` |
| 성공 조건 | done, success, check, expect, until | `done` |
| 금지 | never, ban, without | `never` ✅ |
| 효과 | effect, perform, does, uses, with | `uses` |
| 예산 | limit, cost, cap | `limit` ✅ |
| 실패 처리 | fail, catch, else, or | `fail` |
| 재시도 | again, repeat, attempt | `again` |
| 반환 / 바인딩 / 조건 / 매칭 | return / let / if / match | 그대로 |

✅ **사람 결정(4차 인터뷰)**: 엄격 1토큰 기준 채택 — `task`·`never`·`limit`. 반직관 발견(키워드 비용은 문맥형으로 잰다)은 기록으로 유지. 또 하나: `retry`는 deepseek 공백 뒤 2토큰이라 탈락 — `again` 채택.

## 3. 원칙 7 반영 지점

| 원칙 | 반영 |
|---|---|
| 1 온전 단어 | 키워드·표준 어휘 전부 실단어, 신조 축약 없음 |
| 2 1토큰 키워드 | §2 전수 실측 선별 |
| 3 camelCase | 식별자 표준 (`fetchUser`) |
| 4 중괄호 | 계약 블록 `{ }` |
| 5 기호 연산자 | `!=` `>=` 등 관용 기호 유지 |
| 6 bareword 구조 | `{ ok, name data.name }` — 따옴표·콜론 없는 키-값 |
| 7 의례 흡수 | `again`·`budget`·`fail`이 재시도 루프·타임아웃·예외 블록을 대체 (§0 실측 −28%) |

## 4. H1~H4 대응 (방향)

- **H1 비가역**: `never` 기본 전면 금지 + `uses`의 명시 capability만 허용
- **H2 기술부채**: `fail` 슬롯 없는 실패 가능 계약은 파싱 실패 — 에러를 버리려면 `fail return …`으로 버렸다고 선언해야 함
- **H3 오남용**: **결정론적으로 풀리는 문제에서는 LLM콜이 절대 일어나지 않는다**(사람 확정, 4차 인터뷰). LLM 호출은 `uses llm`을 선언한 계약에서만 — 판정은 보수적 허용 목록으로
- **H4 발산**: `budget` 필수화 후보 — 루프·재시도(`again`)는 유한 횟수 리터럴만 허용, `while` 부재

## 5. 미설계로 남는 것

타입 시스템 · 효과 목록 · 예산 단위의 의미론 · 모듈/조합 · 표준 라이브러리 · 정확한 문법(BNF) — 파서 사이클(Rust)에서 BNF와 함께 확정 제안한다.
