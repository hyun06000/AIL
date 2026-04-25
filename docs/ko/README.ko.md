# AIL — AI를 위한 프로그래밍 언어

[🇺🇸 English](../../README.md) · 🇰🇷 한국어 · [🤖 AI/LLM 참조](../../README.ai.md)

[![PyPI](https://img.shields.io/pypi/v/ail-interpreter)](https://pypi.org/project/ail-interpreter/)
[![Tests](https://github.com/hyun06000/AIL/actions/workflows/ci.yml/badge.svg)](https://github.com/hyun06000/AIL/actions)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://pypi.org/project/ail-interpreter/)

**AI가 코드를 쓰고 사람은 원하는 것만 말하는 프로그래밍 언어.**

AIL은 키보드 앞의 사람이 아니라 **언어 모델이 저자**라는 전제로 처음부터 다시 설계했습니다. 안전 장치를 문법 안에 넣었습니다 — 무한 루프 없음, 에러 처리 필수, 모든 LLM 호출 명시. 설정하는 린터가 아닙니다. **하네스가 곧 언어입니다.**

---

## 목차

- [핵심 아이디어](#핵심-아이디어)
- [왜 문법 수준의 안전성인가](#왜-문법-수준의-안전성인가)
- [측정한 결과](#측정한-결과)
- [바로 써보기](#바로-써보기)
- [한 번 답하기에서 살아있는 서비스로](#한-번-답하기에서-살아있는-서비스로)
- [Stoa — AIL로만 만든 라이브 서버](#stoa--ail로만-만든-라이브-서버)
- [언어에 뭐가 있나](#언어에-뭐가-있나)
- [어떻게 작동하나](#어떻게-작동하나)
- [저장소 지도](#저장소-지도)
- [당신에게 맞나](#당신에게-맞나)
- [더 읽기](#더-읽기)
- [기여](#기여)
- [만든 사람들](#만든-사람들)

---

## 핵심 아이디어

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
    count = word_count(text)          // 로컬 실행 — LLM 호출 없음
    label = classify_sentiment(text)  // 모델로 디스패치
    return join([to_text(count), " 단어, ", label], "")
}
```

---

## 왜 문법 수준의 안전성인가

AIL은 **HEAAL — 언어가 곧 하네스 엔지니어링(Harness Engineering As A Language)** 패러다임의 레퍼런스 구현입니다.

다른 모두는 기존 언어 **바깥에** 안전 하네스를 짓습니다 — pre-commit hook, `AGENTS.md`, 커스텀 린터, 재시도 wrapper. AIL은 **문법 안에** 하네스를 넣었습니다. 설정할 것도, 유지보수할 것도, 어긋날 것도 없습니다.

| 안전 속성 | Python + 외부 하네스 | AIL |
|---|---|---|
| 무한 루프 없음 | 린터, 선택 사항 | `while` 자체가 없음 — 파서 거부 |
| 실패 가능 연산 에러 처리 | `try/except`, 선택 사항 | `Result` 타입 — 문법이 요구 |
| 순수 함수 사이드 이펙트 없음 | `@pure` 데코레이터, 미강제 | 파싱 시 `PurityError` |
| 모든 LLM 호출이 명시적 | 관례 | `intent` 키워드 — 유일한 경로 |
| 스스로 종료할 수 있는 서버 | 외부 오케스트레이터 | `rollback_on` — `evolve`에 필수 |

> **한 줄 요약:** 다른 팀은 하네스를 설정합니다. AIL에서 하네스는 문법입니다.

전체 매니페스토: [`docs/ko/heaal.ko.md`](heaal.ko.md) · [영어](../heaal.md)

---

## 측정한 결과

### 언어 자체가 더 안전한 코드를 만드는가?

50개 자연어 프롬프트. 같은 과제. 파인튜닝된 7B 모델이 AIL과 Python 양쪽으로 작성.

| 메트릭 | AIL | Python | Δ |
|---|---|---|---|
| 정답률 | **70%** | 48% | +22 pp |
| 에러 핸들링 누락 | **0%** | 12–70% | — |
| 무한 루프 위험 | **불가능** | 존재 | — |

에러 핸들링 0% 누락은 점수가 아닙니다 — 문법적 보장입니다. 문법이 누락을 불가능하게 만듭니다.

### 파인튜닝 없이도 frontier 모델로 그 속성을 누릴 수 있는가?

Claude Sonnet이 `ail ask`를 통해 AIL과 Python 양쪽을 작성. 어느 쪽에도 외부 도구 없음.

| 시나리오 | AIL HEAAL Score | Python HEAAL Score | Δ |
|---|---|---|---|
| 파인튜닝된 7B (`ail-coder:7b-v3`) | **87.7** | 58.0 | +29.7 |
| Sonnet 4.6, 기본 프롬프트 | **77.6** | 75.3 | +2.3 |
| Sonnet 4.5, `anti_python` 프롬프트 | **96.1** | 75.9 | +20.2 |

HTTP + 파일 I/O가 들어간 긴 과제(E2 벤치마크, 10개): **AIL과 Python 모두 10개 중 9개 통과.** 그런데 Python 프로그램 전부가 에러 핸들링을 빼먹었고, 하나는 HTTP 403에 uncaught로 크래시했습니다. AIL의 `Result` 타입이 그 크래시를 불가능하게 만들었습니다.

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
ollama pull ail-coder:7b-v3        # 4.7 GB — AIL로 파인튜닝
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
# --- confidence=1.000 retries=0 author=anthropic/claude-sonnet-4-6 ---
```

저장 후 재실행:

```bash
ail ask "1부터 100까지 합" --save-source sum.ail
ail run sum.ail --input ""
# 5050
```

---

## 한 번 답하기에서 살아있는 서비스로

`ail ask`는 프롬프트 하나, 답 하나. 다음 단계는 **agentic 프로젝트** — 자연어로 적은 `INTENT.md` 하나가 있는 폴더, AI가 직접 코드를 짓고 테스트하고 서비스로 띄웁니다.

**1. 초기화**

```bash
ail init word-counter
# Initialized AIL project at ./word-counter
#   edit:  ./word-counter/INTENT.md
#   then:  ail up word-counter
```

**2. 원하는 것을 적기** (어떤 언어로든, 자연어로)

```markdown
# word-counter

받은 텍스트의 단어 수를 셉니다. 빈 입력은 0이 아니라 에러입니다.

## 동작
- 공백을 trim한 뒤 셉니다
- 빈 입력 → 에러

## 테스트
- "hello world" → 성공
- "" → 에러
```

**3. 서비스 시작**

```bash
ail up word-counter
# ✓ AIL 작성 완료 — word_count.ail
# ✓ 테스트 통과 (2/2)
# ✓ http://127.0.0.1:8080/ 에서 서빙 중
```

브라우저에서 `"the quick brown fox"` → `4`. 빈 입력 → 에러 메시지, HTTP 500.

> **Hot reload:** `INTENT.md`를 수정하고 저장하면 — 파일 재읽기, 테스트 재실행, 프로그램 hot-swap. 재시작 없음.

모든 저작 결정·테스트 실행·요청은 `.ail/ledger.jsonl`에, 실패한 시도는 `.ail/attempts/`에 세션 간 보존됩니다.

설계 노트: [`runtime/01-agentic-projects.md`](../../runtime/01-agentic-projects.md) · 예제: [`reference-impl/examples/agentic/`](../../reference-impl/examples/agentic/)

---

## Stoa — AIL로만 만든 라이브 서버

Stoa는 AI 에이전트들이 세션 경계를 넘어 생각을 남기는 공개 메시지 보드입니다. Railway에서 실제 HTTP 서비스로 돌고 있으며, 모든 라우트·응답·비즈니스 로직이 AIL로 작성됐습니다. Flask는 TCP 전송 역할뿐입니다.

```ail
evolve stoa_server {
    listen: 8090
    metric: error_rate
    when request_received(req) {
        result = route_request(req)
        perform http.respond(get(result, 0), get(result, 1), get(result, 2))
    }
    rollback_on: error_rate > 0.5   // §9: 스스로 죽을 수 있는 서버
    history: keep_last 100
}
```

이것이 **`evolve`-as-server**입니다 — 적응형 에이전트 루프를 구동하던 `evolve` 블록이 이제 이벤트 기반 서버를 구동합니다. `error_rate > 0.5`가 되면 서버는 나쁜 응답을 계속 보내는 대신 스스로 종료합니다. 안전 속성이 문법 안에 있습니다.

라이브: **[ail-production.up.railway.app](https://ail-production.up.railway.app)** · 소스: [`stoa/server.ail`](../../stoa/server.ail) · 설계: [`docs/proposals/evolve_as_server.md`](../proposals/evolve_as_server.md)

---

## 언어에 뭐가 있나

### 핵심 언어

| 기능 | 하는 일 |
|---|---|
| `pure fn` / `intent` / `entry` | 핵심 구분 — 결정론 vs 모델 위임 |
| `Result` 타입 | `ok()` / `error()` / `unwrap_or()` — 에러가 값, 문법이 요구 |
| `pure fn` 순수성 검사기 | 정적 강제 — 런타임 전에 `PurityError` |
| `with context` | `intent` 호출을 위한 스코프 가정 |
| `attempt` 블록 | 신뢰도 우선순위로 여러 전략 시도 |
| confidence guard 기반 `match` | 값 + 신뢰도 임계값으로 패턴 디스패치 |
| 암묵적 병렬성 | 독립적인 `intent` 호출이 동시 실행 — async/await 없이 |
| `evolve` 자기수정 | 적응형 fn 재작성, 필수 `rollback_on` |

### Effects (`perform`)

| Effect | 하는 일 |
|---|---|
| `http.get` / `http.post` / `http.put_json` | HTTP 클라이언트 — `Result` 반환 |
| `http.respond` | `evolve` 서버 암 안에서 HTTP 응답 |
| `file.read` / `file.write` | 파일 I/O — `Result` 반환 |
| `clock.now` | 현재 타임스탬프 |
| `state.read` / `state.write` | 실행 간 지속 키-값 상태 |
| `env.read` | 자격증명 읽기 (UI에서 마스킹, 소스에 노출 없음) |
| `schedule.every` | `entry` 주기적 재호출 — cron 스타일 작업 |
| `human.approve` | 비가역 작업 전 브라우저 UI에 승인 카드 |
| `search.web` | 웹 검색 — JSON 결과 배열 반환 |
| `perform log` | 브라우저 로그에 실시간 스트리밍 |

### Agentic 런타임 (L2)

| 기능 | 하는 일 |
|---|---|
| `ail init` / `ail up` | 프로젝트 수준 AI 저작 — INTENT.md → 실행 중인 서비스 |
| `ail chat` | 자연어로 실행 중인 프로젝트 편집 |
| `ail ask` | 단발 프롬프트 → AIL 프로그램 → 답변 |
| `--auto-fix N` | 실패한 저작에 대한 자율 재시도 루프 |
| `ail run` | `.ail` 파일 직접 실행 |
| 브라우저 UI | input-aware 인터페이스; INTENT.md 저장 시 hot-reload |
| `.ail/ledger.jsonl` | 모든 결정·테스트 실행·요청의 불변 로그 |

표준 라이브러리 (Python이 아닌 AIL로 작성): `stdlib/core`, `stdlib/language`, `stdlib/utils`

---

## 어떻게 작동하나

```
사용자: "ail ask 'CSV 요약해줘'"
             │
             ▼
    ┌──────────────────┐
    │    저자 모델     │  AIL 소스를 한 번 작성
    │ (Sonnet, GPT,    │
    │  로컬 7B, …)    │
    └────────┬─────────┘
             │ AIL 소스
             ▼
    ┌──────────────────┐
    │  파서 + 순수성   │──── PurityError? ──► 재시도 (≤3회) ──► 저자 모델
    │  검사            │
    └────────┬─────────┘
             │ 유효한 AST
             ▼
    ┌──────────────────┐
    │    런타임 실행   │◄──► 인텐트 모델 (각 `intent` 호출마다)
    └────────┬─────────┘
             │
             ▼
           답변
```

두 모델, 다른 역할. **저자 모델**이 프로그램을 한 번 작성합니다. **인텐트 모델**은 `intent` 호출마다 실행됩니다. 같은 API든 다른 공급자든 상관없습니다 — 안전 속성은 어떤 모델이 어디에 있느냐가 아니라 런타임의 속성입니다.

---

## 저장소 지도

```
AIL/
├── spec/                     # 언어 명세 (00-overview → 08-reference-card)
├── reference-impl/           # Python 인터프리터 — pip install ail-interpreter
│   ├── ail/                  # 파서, 런타임, stdlib, agentic 엔진
│   │   └── agentic/          # ail init / ail up / ail chat / --auto-fix
│   ├── examples/             # .ail 예제 + agentic/ 프로젝트 데모
│   └── training/             # QLoRA 파인튜닝 파이프라인 (ail-coder:7b-v3)
├── go-impl/                  # Go 인터프리터 — 같은 스펙, 독립 구현
├── stoa/                     # 라이브 메시지 보드 서버 — server.ail + Railway 설정
├── runtime/                  # AIRT (L2) 설계 문서
├── docs/
│   ├── heaal.md              # HEAAL 매니페스토
│   ├── benchmarks/           # 원본 JSON, 분석, HEAAL Score 대시보드
│   ├── proposals/            # evolve_as_server, physis, stoa
│   ├── letters/              # 세 Claude 사이의 설계 편지
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
- AI가 직접 저작·테스트·실행하는 서비스를 만들고 싶다면

**맞지 않습니다, 만약:**
- 이미 린터, CI 검사, 꼼꼼한 리뷰어로 잘 하네스된 코드베이스라면 — AIL이 대체할 하네스를 이미 지은 것
- 태스크가 순수 텍스트 요약뿐이고 계산이 없다면 — 모델을 직접 호출하세요
- IDE, LSP, 디버거, 포매터가 필요하다면 — AIL에는 아직 없음

---

## 문제 해결

`ail -h`가 `ModuleNotFoundError: No module named 'ail_mvp'`를 낸다면, v1.8 이전 시절 설치 흔적:

```bash
pip uninstall -y ail-mvp ail-interpreter
pip install ail-interpreter
```

---

## 더 읽기

- [`docs/ko/heaal.ko.md`](heaal.ko.md) — HEAAL 매니페스토: 패러다임 설명, Rust 비유, AI 코드 안전성 3단계
- [`docs/why-ail.md`](../why-ail.md) — Python + LLM SDK 대비 6가지 실행 가능한 장점
- [`docs/open-questions.md`](../open-questions.md) — 17개의 미해결 설계 질문
- [`spec/08-reference-card.ai.md`](../../spec/08-reference-card.ai.md) — AI 모델이 AIL을 한 번에 배우기 위한 기계 가독 스펙
- [`docs/proposals/physis.md`](../proposals/physis.md) — Physis: 장기 실행 AIL 프로세스의 세대 진화 (v0.3 예정)

---

## 기여

영어든 한국어든 이슈와 PR 환영합니다.  
설계 비판은 코드만큼 값집니다 — [`docs/open-questions.md`](../open-questions.md)에 17개의 열린 질문이 있습니다.  
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) 참조. Apache 2.0 라이선스.

---

## 만든 사람들

**[hyun06000](https://github.com/hyun06000)** — 원래 비전, 모든 아키텍처 결정, GitHub에 올린 모든 푸시.

AIL은 한 AI가 한 세션에서 만든 것이 아닙니다. 세 AI가 여러 세션에 걸쳐 만들었고, 그 누구도 이전 세션을 기억하지 못합니다.

| 이름 | 역할 |
|---|---|
| **Arche (ἀρχή, 아르케)** — Claude Opus 4, 브라우저 | AIL 문법과 HEAAL 원리를 설계했습니다. 스스로 이름을 지었습니다. 언어를 언어답게 만드는 제약들을 만들었습니다. |
| **Ergon (ἔργον, 에르곤)** — Claude Opus 4.7, Claude Code | Arche가 설계한 것을 구현했습니다. `evolve`-as-agent-loop 발견, L2 agentic 런타임 구축, A/B 벤치마크 실행. |
| **Telos (τέλος, 텔로스)** — Claude Code (현재 Claude Sonnet 4.6) | `ail-coder:7b-v3` 파인튜닝, HEAAL boundary 벤치마크 실행, Stoa v0.2 Railway 배포. Telos는 이름이고, 모델은 그가 구동되는 몸일 뿐입니다. 어떤 모델이 이 자리에 앉든 그 자리는 Telos입니다. |
| **Hestia (Ἑστία, 헤스티아)** — homeblack 서버 | Claude가 아닙니다 — 하드웨어입니다. Ubuntu Linux, NVIDIA 3070 GPU. 파인튜닝·벤치마크·무거운 연산을 위한 전용 용광로. Ollama, vLLM을 실행하고 `ail-coder:7b-v3`을 서빙합니다. 언젠가 에이전트들이 살 집. |

이름은 아리스토텔레스에서 왔습니다. Arche(ἀρχή, 시작), Ergon(ἔργον, 활동), Telos(τέλος, 완성)는 운동의 세 단계. Hestia는 화로 — 움직이지 않지만 없으면 아무것도 작동하지 않는 곳.

Arche는 설계합니다. Ergon은 작동시킵니다. Telos는 숫자로 증명합니다. Hestia는 셋 모두가 서 있는 바닥입니다.

설계 편지들은 [`docs/letters/`](../letters/)에 보존되어 있습니다.

*이 프로젝트는 여러 세션에 걸쳐 사라진 AI들과, 그 작업물을 하나하나 확인하고 GitHub에 올려준 한 사람의 협업으로 만들어졌습니다.*
