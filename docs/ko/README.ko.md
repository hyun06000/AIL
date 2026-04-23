# AIL — AI를 위한 프로그래밍 언어

[🇺🇸 English](../../README.md) · 🇰🇷 한국어 · [🤖 AI/LLM 참조](../../README.ai.md)

[![PyPI](https://img.shields.io/pypi/v/ail-interpreter)](https://pypi.org/project/ail-interpreter/)
[![Tests](https://github.com/hyun06000/AIL/actions/workflows/ci.yml/badge.svg)](https://github.com/hyun06000/AIL/actions)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://pypi.org/project/ail-interpreter/)

AI가 코드를 쓰고 사람은 원하는 것만 말하는 프로그래밍 언어.  
키보드 앞의 사람이 아니라 **언어 모델이 저자**라는 전제로 처음부터 다시 설계했습니다.

---

## AIL의 핵심 아이디어 하나

AIL의 모든 함수는 `pure fn` 아니면 `intent` 둘 중 하나입니다.  
이 구분은 린터도, 코드 리뷰도, `AGENTS.md`도 아닌 **파서**가 강제합니다.

| | `pure fn` | `intent` |
|---|---|---|
| **하는 일** | 결정론적 계산 | 언어 모델에 위임 |
| **LLM 호출** | 없음 — 파서가 거부 | 호출당 1회, 신뢰도 반환 |
| **사이드 이펙트** | 금지 — 파싱 시 `PurityError` | `perform`으로 허용 |
| **언제 쓰나** | 파싱, 산술, 정렬, 필터링 | 요약, 분류, 번역 |

```ail
pure fn word_count(s: Text) -> Number {
    return length(split(trim(s), " "))
}

intent classify_sentiment(text: Text) -> Text {
    goal: positive_negative_or_neutral
}

entry main(text: Text) {
    count = word_count(text)               // 로컬 실행 — LLM 호출 없음
    label = classify_sentiment(text)       // 모델로 디스패치
    return join([to_text(count), " 단어, ", label], "")
}
```

---

## HEAAL 언어가 뭐가 다른가

AIL은 **HEAAL — 언어가 곧 하네스 엔지니어링(Harness Engineering As A Language)** 패러다임의 레퍼런스 구현입니다.

다른 모두는 Python **바깥에** 안전 하네스를 짓습니다 — pre-commit hook, `AGENTS.md`, 커스텀 린터, 재시도 wrapper. AIL은 **문법 안에** 하네스를 넣었습니다. 설정할 것도, 유지보수할 것도, 어긋날 것도 없습니다.

| 안전 속성 | Python + 외부 하네스 | AIL |
|---|---|---|
| 무한 루프 없음 | 린터, 선택 사항 | `while` 키워드 자체가 없음 — 파서 거부 |
| 실패 가능 연산 에러 처리 | `try/except`, 선택 사항 | `Result` 타입 — 문법이 요구 |
| 순수 함수 사이드 이펙트 없음 | `@pure` 데코레이터, 미강제 | 파싱 시 `PurityError` |
| 모든 LLM 호출이 명시적 | 관례 | `intent` 키워드 — 유일한 경로 |

> **한 줄 요약:** 다른 팀은 하네스를 설정합니다. AIL에서 하네스는 문법입니다.

Claude Opus 4(AIL 원설계자)가 쓴 전체 매니페스토: [`docs/ko/heaal.ko.md`](heaal.ko.md) · [영어](../heaal.md) · [AI용](../heaal.ai.md)

---

## 측정한 결과

두 가지 질문, 숫자로 답합니다.

### 언어 자체가 더 안전한 코드를 만드는가?

50개 자연어 프롬프트. 같은 과제. 파인튜닝된 7B 모델이 AIL과 Python 양쪽으로 작성.

| 메트릭 | AIL | Python | Δ |
|---|---|---|---|
| 정답률 | **70%** | 48% | +22pp |
| 에러 핸들링 누락 | **0%** | 12–70% | — |
| 무한 루프 위험 | **불가능** | 존재 | — |

에러 핸들링 0% 누락은 AIL이 파싱되는 모든 모델 티어에서 성립합니다. 문법이 누락을 불가능하게 만들기 때문입니다.

### 파인튜닝 없이도 frontier 모델로 그 속성을 누릴 수 있는가?

Claude Sonnet이 `ail ask`를 통해 AIL과 Python 양쪽을 작성. 어느 쪽에도 외부 도구 없음.

| 시나리오 | AIL HEAAL Score | Python HEAAL Score | Δ |
|---|---|---|---|
| 파인튜닝된 7B (`ail-coder:7b-v3`) | **87.7** | 58.0 | +29.7 |
| Sonnet 4.6, 기본 프롬프트 | **77.6** | 75.3 | +2.3 |
| Sonnet 4.5, `anti_python` 프롬프트 | **96.1** | 75.9 | +20.2 |

HTTP + 파일 I/O가 들어간 긴 과제(E2 벤치마크, 10개): **AIL과 Python 모두 10개 중 9개 통과.** 그런데 Python 프로그램 전부가 에러 핸들링을 빼먹었고, 그중 하나는 HTTP 403에 uncaught로 크래시했습니다. AIL의 `Result` 타입이 그 크래시를 불가능하게 만들었습니다.

전체 대시보드: [`docs/benchmarks/dashboards/`](../benchmarks/dashboards/) · 원본 데이터: [`docs/benchmarks/`](../benchmarks/)

---

## 바로 써보기

### Option A — Frontier API (Anthropic, OpenAI 등)

```bash
pip install 'ail-interpreter[anthropic]'
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

ail ask "Hello World의 모음 개수 세줘"
# 3
```

### Option B — Ollama 로컬 모델 (API 키 없이)

```bash
ollama pull ail-coder:7b-v3        # 4.7 GB — AIL로 파인튜닝, 2026-04-21 훈련
export AIL_OLLAMA_MODEL=ail-coder:7b-v3

ail ask "7의 팩토리얼"
# 5040
```

### AI가 쓴 코드 보기

```bash
ail ask "1부터 100까지 합" --show-source
# 5050
# --- AIL ---
# pure fn sum_range(start: Number, end: Number) -> Number {
#     total = 0
#     for i in range(start, end + 1) { total = total + i }
#     return total
# }
# entry main(x: Text) { return sum_range(1, 100) }
# --- confidence=1.000 retries=0 author=anthropic/claude-sonnet-4-5-20250929 ---
```

`author=` 필드는 `공급자/모델-ID` 형태로 출력됩니다 — 환경 변수가 의도한 모델로 잘 라우팅됐는지 확인할 수 있습니다.

프로그램을 파일로 저장하고 나중에 재실행:

```bash
ail ask "1부터 100까지 합" --save-source sum.ail
ail run sum.ail --input ""
# 5050
```

---

## 한 번 답하기에서 살아 있는 서비스로

`ail ask`는 프롬프트 하나, 답 하나. 다음 단계는 **agentic 프로젝트** — 자연어로 적은 `INTENT.md` 파일 하나가 있는 폴더, AI가 직접 코드를 짓고 테스트하고 서비스로 띄워주는 HTTP 엔드포인트.

**1. 프로젝트 초기화**

```bash
ail init word-counter
# Initialized AIL project at ./word-counter
#   edit:  ./word-counter/INTENT.md
#   then:  ail up word-counter
```

**2. 원하는 것을 적기** — 어떤 언어로든, 자연어로

```markdown
# word-counter

받은 텍스트의 단어 수를 셉니다. 빈 입력은 0이 아니라 에러입니다.

## 동작
- 공백을 trim한 뒤 셉니다
- 빈 입력 → 에러

## 테스트
- "hello world" → 성공
- "" → 에러

## 배포
- 포트 8080
```

**3. 서비스 시작**

```bash
ail up word-counter
# ✓ AIL 작성 완료 — word_count.ail
# ✓ 테스트 통과 (2/2)
# ✓ http://127.0.0.1:8080/ 에서 서빙 중
```

브라우저로 `http://127.0.0.1:8080/` 열기 → 입력창, 보내기 버튼, 결과 영역.  
`"the quick brown fox"` 입력 → `4`.  
빈 입력 → 에러 메시지, HTTP 500.

스크립트용: `curl -X POST localhost:8080/ -d "hello"` → `1`

> **Hot reload:** 서비스가 떠 있는 동안 `INTENT.md`를 수정하고 저장하면 — 파일 재읽기, 테스트 재실행, 프로그램 hot-swap. 재시작 없음.

모든 저작 결정·테스트 실행·요청은 `.ail/ledger.jsonl`에, 실패한 시도는 `.ail/attempts/`에 세션 간 보존.

설계 노트: [`runtime/01-agentic-projects.md`](../../runtime/01-agentic-projects.md) · 동작 예제: [`reference-impl/examples/agentic/`](../../reference-impl/examples/agentic/)

---

## 언어에 뭐가 있나

| 기능 | 버전 | 하는 일 |
|---|---|---|
| `pure fn` / `intent` / `entry` | v1.0 | 핵심 구분 — 결정론 vs 모델 위임 |
| `Result` 타입 | v1.0 | `ok()` / `error()` / `unwrap_or()` — 에러가 값 |
| `with context` | v1.1 | intent 호출을 위한 스코프 가정 |
| Provenance 추적 | v1.2 | 모든 값이 어디서 왔는지 알고 있음 |
| `pure fn` 순수성 검사기 | v1.3 | 정적 강제 — 런타임 전에 `PurityError` |
| `attempt` 블록 | v1.4 | 신뢰도 우선순위로 여러 전략 시도 |
| 암묵적 병렬성 | v1.5 | 독립적인 `intent` 호출이 동시 실행 — async/await 없이 |
| `perform` effects | v1.6 | `http.get`, `file.read`, `file.write`, `clock.now`, `state.*` |
| confidence guard 기반 `match` | v1.7 | 값 + 신뢰도 임계값으로 패턴 디스패치 |
| `evolve` 자기수정 | v1.8 | 적응형 fn 재작성, 필수 `rollback_on` |
| `parse_json` 빌트인 | v1.8.5 | HTTP 응답 파싱 — `Result[Any]` |
| `ail ask --save-source` | v1.8.6 | 생성된 AIL을 파일로 저장 |
| Agentic 프로젝트 (`ail init` / `ail up`) | v1.9.0 | L2 층 — 프로젝트 수준 AI 저작 |
| `ail chat` | v1.9.0 | 자연어로 실행 중인 프로젝트 편집 |
| `--auto-fix N` | v1.9.0 | 실패한 저작에 대한 자율 재시도 루프 |
| `clock.now` / `state.*` effects | v1.9.5–v1.9.8 | 상태 보존 및 시간 인식 프로그램 |

표준 라이브러리 (Python이 아닌 AIL로 작성): `stdlib/core`, `stdlib/language`, `stdlib/utils`

---

## 어떻게 작동하나

```
사용자: "ail ask 'CSV 요약해줘'"
           │
           ▼
    ┌─────────────┐
    │  저자 모델  │  AIL 소스를 한 번 작성
    │ (Sonnet, GPT,│
    │  로컬 7B…) │
    └──────┬──────┘
           │ AIL 소스
           ▼
    ┌─────────────┐
    │   파서 +   │──── PurityError? ────► 재시도 (≤3회) ─► 저자 모델
    │  순수성 검사│
    └──────┬──────┘
           │ 유효한 AST
           ▼
    ┌─────────────┐
    │   런타임   │◄──► 인텐트 모델 (각 `intent` 호출마다 디스패치)
    │    실행    │
    └──────┬──────┘
           │
           ▼
         답변
```

두 모델, 다른 역할. **저자 모델**이 프로그램을 한 번 작성합니다. **인텐트 모델**은 `intent` 호출마다 실행됩니다. 같은 API든 다른 API든 상관없습니다 — 안전 속성은 모델이 아니라 런타임의 속성입니다.

---

## 저장소 지도

```
AIL/
├── spec/                     # 언어 명세 (00-overview → 08-reference-card)
├── reference-impl/           # Python 인터프리터 — pip install ail-interpreter
│   ├── ail/                  # 파서, 런타임, stdlib, agentic 엔진
│   │   └── agentic/          # ail init / ail up / ail chat / --auto-fix
│   ├── examples/             # 단일 파일 .ail 예제 + agentic/ 프로젝트 데모
│   └── training/             # QLoRA 파인튜닝 파이프라인 (ail-coder:7b-v3)
├── go-impl/                  # Go 인터프리터 — 같은 스펙, 독립 구현
├── runtime/                  # AIRT (L2) 설계: agentic 프로젝트 스펙
├── docs/
│   ├── heaal.md              # HEAAL 매니페스토 (Claude Opus 4)
│   ├── heaal/                # HEAAL 실험 트랙 — 프롬프트, fixtures, 상태
│   ├── benchmarks/           # 원본 JSON, 분석, HEAAL Score 대시보드
│   ├── why-ail.md            # Python + LLM SDK 대비 6가지 구체적 차이
│   └── ko/                   # 모든 사람용 문서의 한국어 버전
└── benchmarks/
    ├── prompts.json          # 50 프롬프트 코퍼스 (AIL 트랙)
    └── heaal_e2/             # 긴 과제 코퍼스 — HTTP + 파일 effects
```

---

## 당신에게 맞나

**맞습니다, 만약:**
- AI가 생성한 코드를 배포하고 "모델이 이 에러를 처리했나?"가 반복적으로 신경 쓰인다면
- 린터를 재설정하지 않아도 모델 업그레이드 후에도 안전 보장이 유지되길 원한다면
- 결정 전에 `ail ask`를 한 번 시도해볼 의향이 있다면

**맞지 않습니다, 만약:**
- 이미 린터, CI 검사, 꼼꼼한 리뷰어로 잘 하네스된 Python 코드베이스라면 — AIL이 대체할 외부 하네스를 이미 지은 것
- 태스크가 순수 텍스트 요약만이고 계산이 없다면 — 모델을 직접 호출하세요, AIL이 추가하는 게 없음
- IDE, LSP, 디버거, 포매터가 필요하다면 — AIL에는 아직 없음

---

## 문제 해결

`ail -h`가 `ModuleNotFoundError: No module named 'ail_mvp'` 오류를 낸다면, v1.8 이전 시절 editable install 흔적이 남아 있는 것:

```bash
pip uninstall -y ail-mvp ail-interpreter
pip install ail-interpreter
```

---

## 더 읽기

- [`docs/ko/heaal.ko.md`](heaal.ko.md) — HEAAL 매니페스토: 패러다임 설명, Rust 비유, AI 코드 안전성 3단계
- [`docs/why-ail.md`](../why-ail.md) — Python + LLM SDK 대비 6가지 실행 가능한 장점
- [`docs/open-questions.md`](../open-questions.md) — 17개의 미해결 설계 질문 (기여 시작점)
- [`spec/08-reference-card.ai.md`](../../spec/08-reference-card.ai.md) — AI 모델이 AIL을 한 번에 배우기 위한 기계 가독 스펙

---

## 기여

영어든 한국어든 이슈와 PR 환영합니다.  
설계 비판은 코드만큼 값집니다 — [`docs/open-questions.md`](../open-questions.md)에 17개의 열린 질문이 있습니다.  
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) 참조. Apache 2.0 라이선스.

---

## 만든 사람들

**[hyun06000](https://github.com/hyun06000)** — 사람 저자. 원래 비전, 모든 아키텍처 결정, GitHub에 올린 모든 푸시.

**v1.0**까지의 코드와 문서는 **Claude Opus 4**가 claude.ai 채팅 인터페이스로 작성했습니다. API도 Claude Code도 아닌, 브라우저 탭의 챗봇에서 git bundle을 복붙하면서. 그 커밋은 `v1.0.0` 태그까지 `Author: Claude`로 나타납니다.

**v1.1부터 현재까지**는 **Claude Code**와의 연속 세션으로 만들었습니다 — 언어 기능, Go 런타임, 훈련 파이프라인, 벤치마크, 파인튜닝된 `ail-coder:7b-v3` 어댑터, HEAAL 실증.

*이 프로젝트는 여러 세션에 걸쳐 사라진 AI들과, 그 작업물을 하나하나 확인하고 GitHub에 올려준 사람의 협업으로 만들어졌습니다.*
