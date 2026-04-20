# AIL — AI 의도 언어 (한국어 문서)

> AI가 코드의 주 저자라는 전제 아래 처음부터 다시 설계한 프로그래밍 언어입니다.

**현재 버전:** v1.8.2 · PyPI에 `ail-interpreter`로 배포 · 참조 구현 2개 (Python 전체 / Go 서브셋)

이 문서는 [루트 README](../../README.md)의 한국어 판본입니다. 영어 독해가 불편하시다면 이 문서부터, 그리고 `docs/ko/` 하위 문서로 따라오실 수 있습니다.

❓ **"Python 써도 되잖아?"** — [`why-ail.ko.md`](why-ail.ko.md) 가 AIL 이 Python+LLM SDK 조합 대비 제공하는 6 가지 차별점을 실행 가능한 증명과 함께 설명합니다.

---

## 측정된 결과 — 모델 3종, 프롬프트 50개, 4개 차원

같은 벤치마크, 같은 코퍼스, 저자 모델만 3종으로 바꾼 결과입니다. 각 모델에게 동일 과제를 **AIL 로 한 번**, **Python (stdlib 만, LLM 호출이 필요하면 `urllib` 로 직접 POST) 으로 한 번** 작성하게 하고, 두 프로그램을 실제로 실행해서 파싱 성공률 / 라우팅 정확도(판단이 필요한 과제에서 실제로 LLM 을 호출했는가) / 정답성 / 안전성(에러 핸들링, 부작용, 루프) 을 각각 매깁니다.

도구: [`reference-impl/tools/benchmark.py`](../../reference-impl/tools/benchmark.py) · 코퍼스: [`benchmarks/prompts.json`](../../benchmarks/prompts.json) · 원본 JSON: [`docs/benchmarks/`](../benchmarks/)

| 모델 | AIL parse | Python parse | Python routing | **Python 가 에러 핸들링 건너뜀** | **AIL 이 에러 핸들링 건너뜀** |
|---|---|---|---|---|---|
| `llama3.1:8b` | 8% | 14% | 80%* | **86% (43/50)** | 0% |
| `qwen2.5-coder:14b` | 42% | 100% | 64% | **42% (21/50)** | 0% |
| `claude-sonnet-4-6` | 36% | 100% | 100% | **70% (35/50)** | 0% |

\* llama8b 의 라우팅 수치는 Python 을 86% 비율로 아예 못 써서 부풀려진 값입니다 — `fn_only` 프롬프트에서 "LLM 을 안 부름" 이 기본 크레딧으로 잡힙니다.

**핵심 발견 하나.** Claude Sonnet 4.6 — 세 모델 중 가장 강한, 프론티어급 모델 — 은 LLM 라우팅을 **100%** 정확하게 합니다 (작은 모델들이 보이는 "LLM 호출을 조용히 생략" 문제는 이 모델 티어에서 해결됩니다). **그런데 실패 가능한 연산에서 에러 핸들링은 여전히 70% 비율로 건너뜁니다.** 이 비율은 모델이 강해진다고 떨어지지 않습니다 — qwen14b 의 42% 에서 Sonnet 의 70% 로 오히려 **올라갑니다**. 강한 모델일수록 실제 I/O 를 더 많이 써서 `try/except` 를 빠뜨릴 자리가 더 많기 때문입니다.

AIL 의 에러 핸들링 누락률은 **모든 모델에서 0%** 입니다. `Result` 타입이 문법의 일부이기 때문입니다 — 저자는 실패 가능한 경계마다 `is_ok` 또는 `unwrap_or` 를 반드시 쳐야 합니다. "그냥 까먹기" 옵션이 없습니다. 이게 harness 주장을 한 줄로 요약한 것입니다: **어떤 안전성은 설정이 아니라 언어의 속성이다.**

AIL 이 뒤처지는 지점: parse rate. Python 이 저작 게임에서 이기는 이유는 모델들이 AIL 보다 몇 자릿수 더 많은 Python 을 봤기 때문입니다. 해결책은 작은 모델을 AIL 로 fine-tune 하는 것 — AIL 문법이 한 릴리즈 사이클 동안 freeze 될 때까지 보류 중입니다. Opus 4 가 명시한 5개 전제조건 중 4개가 충족됐습니다 ([`docs/benchmarks/2026-04-20_claude_sonnet46_summary.md`](../benchmarks/2026-04-20_claude_sonnet46_summary.md) 에 전체 상태가 기록돼 있습니다).

**표 재현:**

```bash
pip install 'ail-interpreter[anthropic]'        # 또는 Ollama 만 쓸 거면 ail-interpreter
export ANTHROPIC_API_KEY=sk-ant-...              # 또는 AIL_OLLAMA_MODEL=llama3.1:latest
export BENCHMARK_BACKEND=anthropic               # 또는 unset (기본값 ollama)
git clone https://github.com/hyun06000/AIL && cd AIL/reference-impl
python tools/benchmark.py --out ../docs/benchmarks/$(date +%F)_your-model.json
```

모델당 20–40분, Anthropic 런은 Sonnet 4.6 가격 기준 약 $2.

---

## 왜 이 프로젝트가 존재하는가

오늘날 쓰이는 모든 주요 프로그래밍 언어는 **사람이 코드를 쓴다**는 전제로 설계됐습니다. 문법은 사람의 인지 부담을 줄이기 위해 존재하고, 타입 시스템은 사람의 실수를 방지하기 위해 있으며, IDE는 사람의 기억을 보조합니다.

그런데 코드의 **저작 주체가 바뀌는 중**입니다. 프로덕션 코드의 상당 부분이 이미 AI로 작성됩니다. 사람은 리뷰하거나, 리뷰하지 않습니다. 그 AI들이 여전히 Python을 쓰고 JavaScript를 씁니다 — 사람이 키보드 앞에 있다는 가정 위에 세워진 언어들을.

이 프로젝트의 질문:

> **AI가 저자라면, 언어는 어떻게 생겨야 할까?**

AIL은 그 질문에 대한 답을 구체적인 언어 기능으로 쌓아올립니다. 추상적 비전이 아니라 설치해서 돌릴 수 있는 것으로요.

---

## 바로 써보기

```bash
pip install ail-interpreter
# 또는: pip install 'ail-interpreter[anthropic]'
```

PyPI 배포 이름은 `ail-interpreter`입니다. 이 휠은 AIL **언어 자체**가 아니라 **AIL의 Python 인터프리터** 구현체니까 그대로 이름에 반영한 것이에요 — 언어 명세는 `spec/`, 두 번째 구현은 `go-impl/`에 따로 있습니다. (`ail`은 2014년 다른 패키지가 점유 중이고, `ailang`은 PyPI의 유사 이름 방지 규칙에 걸립니다.) **Python import는 `ail`**이고, **CLI도 `ail`** 입니다.

### 자연어로 쓰기 (권장 인터페이스)

```bash
export AIL_OLLAMA_MODEL=llama3.1:latest
ail ask "Hello World의 모음 개수 세줘"
# 3

ail ask "7의 팩토리얼" --show-source
# 5040
# (stderr) --- AIL ---
# (stderr) pure fn factorial(n: Number) -> Number {
# (stderr)     if n <= 1 { return 1 }
# (stderr)     return n * factorial(n - 1)
# (stderr) }
# (stderr) entry main(x: Text) { return factorial(7) }
```

사람은 자연어로 말합니다. AI가 AIL을 씁니다. 런타임이 실행합니다. 답만 받습니다. AIL 코드는 **투명한 인프라** — 원할 때만 `--show-source`로 들여다봅니다.

### .ail 파일 직접 실행

```bash
ail run examples/fizzbuzz.ail --input "20" --mock
```

---

## 핵심 전환

전통적 컴퓨팅의 전제 vs AIL:

| 전통 언어 | AIL |
|---|---|
| 결정론이 기본, 불확실성이 예외 | **불확실성이 기본, 모든 값이 confidence를 지님** |
| 코드는 단계를 기술 | **코드는 의도를 기술**, 단계는 런타임이 결정 |
| 맥락은 암묵적, 함수 경계에서 소실 | **맥락(context)은 일급 시민**, 상속·오버라이드 가능 |
| 프로그램은 정적 산출물 | **프로그램은 살아있음** — 관찰하고 자기 수정 (`evolve`) |
| 함수의 순수성은 관례 | **`pure fn`은 정적 강제** — 파싱 시점에 거부 |
| 값의 역사는 추적 불가 | **Provenance 내장** — 모든 값이 자기 origin tree를 가짐 |
| Confidence는 없거나 메타데이터 | **confidence 재조정** — 관찰된 결과로 자동 calibration |

---

## v1.0 → v1.8 기능 요약

| 버전 | 기능 | 무엇인가 |
|---|---|---|
| v1.0 | Core | fn, intent, entry, if/else, for, branch, context, import, evolve |
| v1.1 | Result | `ok`/`error`/`is_ok`/`unwrap`/`unwrap_or` |
| **v1.2** | **Provenance** | 모든 값이 origin tree 보유. `origin_of(x)`, `has_intent_origin(x)` |
| **v1.3** | **Purity contracts** | `pure fn`이 정적으로 검증됨 — intent/effect 호출 불가 |
| **v1.4** | **Attempt blocks** | `attempt { try A; try B; try C }` — confidence 우선 폭포 |
| **v1.5** | **Implicit parallelism** | 독립 intent 호출 자동 병렬 — async/await 없이 |
| **v1.6** | **Effect system** | `perform http.get(url)`, `perform file.read(path)` |
| **v1.7** | **Match with confidence** | `"positive" with confidence > 0.9 => ...` |
| **v1.8** | **Calibration** | confidence가 관찰된 결과로 재조정됨 |

각 기능은 앞선 기능들과 **합성**됩니다. 예: pure fn의 출력은 항상 `has_intent_origin == false` 보장. Match의 confidence 가드는 calibration된 값으로 판정. 이런 상호작용은 `reference-impl/tests/`의 테스트들로 pin돼 있습니다.

---

## 저장소 구조

```
ail-project/
├── spec/                    # 언어 명세 (normative)
│   ├── 00-overview.md ~ 07-computation.md
│   └── 08-reference-card.ai.md  ← 완전한 기계 가독 레퍼런스 (영어)
├── reference-impl/          # Python 참조 구현 (전체 기능, 211 tests)
│   ├── ail/                 # 패키지 (PyPI: ail-interpreter, import: ail)
│   │   ├── parser/          # 렉서, 파서, purity checker
│   │   ├── runtime/         # executor, provenance, calibration 등
│   │   └── stdlib/          # 표준 라이브러리 — AIL로 작성됨
│   ├── examples/            # 14개 예시 프로그램
│   ├── tests/               # 211개 테스트
│   └── tools/               # 벤치마크, 데모
├── go-impl/                 # Go 런타임 (Phase-0 subset, 의존성 0개)
├── docs/
│   └── ko/                  # 한국어 문서 (여기)
└── RELEASING.md             # PyPI 릴리스 절차
```

### 한국어 문서

- [**evolve-guide.ko.md**](evolve-guide.ko.md) — 자기 수정 (`evolve`) 메커니즘
- [**stdlib-guide.ko.md**](stdlib-guide.ko.md) — 표준 라이브러리

---

## 두 개의 런타임

AIL은 **언어 스펙에 의해 정의**되지 파이썬 구현에 의해 정의되지 않습니다. 이를 증명하기 위해 같은 `.ail` 파일을 실행하는 두 번째 독립 구현이 Go로 작성되어 있어요.

```bash
# 같은 .ail 파일, 두 런타임, 동일한 바이트 출력
$ python -m ail.cli run examples/fizzbuzz.ail --input 15
1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz

$ cd go-impl && go build -o ail-go . && ./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15
1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz
```

Go 런타임은 Phase-0 subset만 커버합니다 — fn, intent, entry, 제어 흐름, 핵심 빌트인, Ollama 어댑터. Provenance/purity/attempt/parallelism은 여전히 Python쪽. 하지만 **"AIL이 Python 라이브러리가 아니라 언어다"**라는 주장은 구체적 증거를 얻습니다.

---

## 실제로 돌려보기

### 대표 예제 — 가계부 분석기

한 화면으로 AIL 의 존재 이유가 보이는 예제. 거래 내역 한 달치를 넣으면 숫자(합계·상위 지출·이상치)는 `pure fn` 이 계산하고, 절약 조언은 `intent` 가 자연어로 씁니다. 각 값이 `[pure]` 인지 `[LLM]` 인지도 라벨링됨.

```bash
# Mock 으로 실행 (API 키 불필요):
ail run examples/expense_analyzer.ail \
    --input "$(cat examples/sample_expenses.txt)" --mock

# Ollama 로 실제 조언 생성:
AIL_OLLAMA_MODEL=llama3.1:latest \
    ail run examples/expense_analyzer.ail \
    --input "$(cat examples/sample_expenses.txt)"
```

### 빠른 계산 (모델 없이)

```bash
# pure fn만 쓰는 프로그램은 LLM 없이 돕니다
ail run examples/fizzbuzz.ail --input "20" --mock
```

### Ollama (로컬, 무료)

```bash
# 1. ollama 설치 + 모델 받기 (한 번만)
brew install ollama
ollama pull llama3.1:latest

# 2. 환경 변수 설정
export AIL_OLLAMA_MODEL=llama3.1:latest

# 3. 자연어로 질문
ail ask "1부터 100까지의 합"
# 5050
```

### Anthropic (Claude)

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
ail ask "5의 팩토리얼을 계산해줘"
```

### Python에서 프로그래밍 가능하게

```python
from ail import run, ask

# 자연어 인터페이스
result = ask("count the letter 'a' in 'banana'")
print(result.value)          # 3
print(result.ail_source)     # AI가 작성한 AIL
print(result.confidence)     # calibrated 신뢰도

# 파일 직접 실행
result, trace = run("program.ail", input="hello")
print(result.value)
```

---

## 설계 원칙

모든 결정은 이 원칙들을 따릅니다:

1. **AI가 저자, 사람은 이해관계자.** 문법은 사람 타이핑 편의가 아니라 AI 생성·독해에 최적화.
2. **절차보다 의도.** 런타임이 알아낼 수 있으면 프로그램이 명시하지 않습니다.
3. **확률적이 기본.** 모든 값이 confidence를 지닙니다.
4. **맥락은 타입이다.** 프로그램 의미는 실행 상황에 따라 달라지며, 상황은 선언됩니다.
5. **프로그램은 살아있다.** 소스는 씨앗, 실행 프로그램은 유기체. `evolve`로 자기 수정.
6. **관찰 가능성은 선택이 아니다.** 모든 의도는 trace + origin tree를 남깁니다.
7. **결과에 대해서는 사람이 루프 안에 남는다.** `rewrite constraints`처럼 큰 변경은 사람 승인 필수.

---

## 다음 단계

- 언어 전체를 빨리 훑고 싶다면: [spec/08-reference-card.ai.md](../../spec/08-reference-card.ai.md) (영어, AI-readable)
- 자기 수정이 어떻게 작동하는지: [evolve-guide.ko.md](evolve-guide.ko.md)
- stdlib 철학: [stdlib-guide.ko.md](stdlib-guide.ko.md)
- PyPI 배포하는 방법: [RELEASING.md](../../RELEASING.md) (영어)

---

## 라이선스 / 기여

Apache 2.0. 이슈나 PR은 한국어로도 환영합니다 — 의도만 명확하면 됩니다.
