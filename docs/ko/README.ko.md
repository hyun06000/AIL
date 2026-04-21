# AIL — AI-Intent Language

AI가 코드를 쓰고, 사람은 의도만 전달한다는 전제로 처음부터 설계한 프로그래밍 언어입니다.

**v1.8.4** · `pip install ail-interpreter` · [English](../../README.md) · [AI/LLM 참조](../../README.ai.md)

> **같은 7B 모델로 AIL 70% vs Python 56%.** 모델 크기 차이 없음. 언어 설계의 차이.

---

## 이게 무슨 뜻인가요?

"AI에게 코드를 짜게 하면 Python도 잘 되지 않나?"라고 생각하신다면, 이 숫자가 답입니다.

동일한 50개 자연어 태스크를 동일한 7B 모델에게 AIL로도, Python으로도 짜게 했습니다. AIL은 70%를 맞췄고, Python은 56%를 맞췄습니다. 14pp 차이입니다. 모델을 바꾼 것이 아니라 언어를 바꾼 것입니다.

왜 차이가 나는지는 아래에서 설명합니다.

---

## AIL의 핵심 개념

두 종류의 함수만 있습니다.

- **`fn` / `pure fn`** — 결정론적 계산. LLM을 호출하지 않습니다. `pure fn`은 이 보장을 파서가 컴파일 타임에 강제합니다.
- **`intent`** — 판단이 필요한 작업. 런타임이 모델에 위임합니다.

```ail
import classify from "stdlib/language"
import word_count from "stdlib/utils"

pure fn build_report(label: Text, count: Number) -> Text {
    return join([label, " (", to_text(count), " words)"], "")
}

entry main(text: Text) {
    sentiment = classify(text, "positive_negative_neutral")  // LLM 호출
    count = word_count(text)                                  // LLM 없음
    return build_report(sentiment, count)                     // LLM 없음
}
```

이 구분은 프레임워크 규칙이 아닌 언어 문법입니다. `pure fn` 안에서 LLM을 호출하면 파서가 `PurityError`로 거부합니다.

---

## 바로 써보기

```bash
pip install ail-interpreter
export AIL_OLLAMA_MODEL=llama3.1:latest

ail ask "Hello World의 모음 개수 세줘"
# 3

ail ask "1부터 100까지의 합"
# 5050

ail ask "7의 팩토리얼" --show-source
# 5040
# (stderr) --- AIL ---
# (stderr) pure fn factorial(n: Number) -> Number { ... }
# (stderr) --- confidence=1.000 retries=0 ---
```

사람이 자연어로 말합니다. AI가 AIL을 씁니다. 런타임이 실행합니다. 사람은 결과만 받습니다.

Anthropic API:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
ail ask "7의 팩토리얼"
```

원격 Ollama 서버:

```bash
export AIL_OLLAMA_HOST=http://10.0.0.1:11434
export AIL_OLLAMA_MODEL=ail-coder:7b-v4
ail ask "BMI 계산해줘 키 175cm 몸무게 70kg"
```

---

## 벤치마크 — 70%까지 오는 과정

한 번에 70%가 나온 게 아닙니다. 세 번의 라운드를 거쳤고, 매번 실패한 이유가 달랐습니다.

| 라운드 | 변경 사항 | AIL 정답률 |
|---|---|---|
| R1 기준선 | `ail-coder:7b-v3`, 프롬프트 튜닝 없음 | 48% |
| R2 | FORBIDDEN SYNTAX 블록 추가 (dict `{}`, `**`, dot import 차단) | 64% |
| **R3** | **파서 수정: 모델이 자연스럽게 쓰는 `[Number]`/`[Text]` 타입 어노테이션 수용** | **70%** |

R2의 +16pp는 프롬프트 엔지니어링 효과입니다. 모델이 쓰면 안 되는 패턴을 명시적으로 막았더니 정답률이 올랐습니다.

R3의 +6pp는 언어 개선 효과입니다. 모델이 `items: [Number]`처럼 쓰는 게 자연스러운데 파서가 거부했습니다. 잘못된 제약을 풀었더니 7개 케이스가 동시에 통과됐습니다.

방법론 상세: [`docs/benchmarks/2026-04-21_r2_analysis.md`](../benchmarks/2026-04-21_r2_analysis.md)

### Python과의 비교

**같은 7B 모델, 같은 50개 태스크. AIL: 70%. Python: 56%.**

| | 파싱 성공 | 정답 | 에러 핸들링 누락 |
|---|---|---|---|
| **`ail-coder:7b-v3` (AIL)** | **80%** | **70%** | **0%** |
| `qwen2.5-coder:7b-base` (Python) | 100% | 56% | 44% |

에러 핸들링 누락률 0%는 확률의 문제가 아닙니다. AIL의 `Result` 타입은 문법에 내장되어 있어서 실패 가능한 연산을 처리하지 않으면 파서가 거부합니다. 모델이 기억해야 할 것이 아니라 언어가 강제하는 것입니다.

### base 모델 (fine-tune 없음)

| 모델 | AIL 파싱 | Python 파싱 | Python 에러 핸들링 누락 | AIL 에러 핸들링 누락 |
|---|---|---|---|---|
| `llama3.1:8b` | 8% | 14% | **86% (43/50)** | **0%** |
| `qwen2.5-coder:14b` | 42% | 100% | **42% (21/50)** | **0%** |
| `claude-sonnet-4-6` | 36% | 100% | **70% (35/50)** | **0%** |

Claude Sonnet 4.6도 Python으로 짜면 실패 가능한 연산의 70%에서 에러 핸들링을 생략합니다. 모델이 강해질수록 수렴하지 않습니다. Python이 `int(x)`를 에러 없이 허용하는 이상 구조적으로 해결이 안 됩니다.

### 직접 재현하기

```bash
pip install 'ail-interpreter[anthropic]'
export ANTHROPIC_API_KEY=sk-ant-...
export BENCHMARK_BACKEND=anthropic
git clone https://github.com/hyun06000/AIL && cd AIL/reference-impl
python tools/benchmark.py --out ../docs/benchmarks/$(date +%F)_your-model.json
```

Ollama + llama3.1:8b: 10~20분. Anthropic Sonnet 4.6: ~30분, $2 이하.

---

## 대표 예제 — 가계부 분석기

AIL의 존재 이유를 한 화면으로 보여주는 예제입니다.

거래 내역 한 달치를 입력하면:
- `pure fn`이 합계, 카테고리별 지출, 이상치를 계산합니다. 숫자 하나도 LLM이 관여하지 않습니다.
- `intent`가 절약 조언을 자연어로 씁니다. 딱 이 부분만 LLM입니다.
- `Result` 타입이 잘못된 형식의 행을 조용히 처리합니다. try/except 없이.

```bash
ail run examples/expense_analyzer.ail \
    --input "$(cat examples/sample_expenses.txt)" --mock
```

출력 (발췌):

```
Expense Report
==============
Parsed 18 rows; skipped 2 malformed.

Total: $1,240.50

By category:
  food: $572.00  (46%)
  transport: $49.50  (4%)
  entertainment: $187.00  (15%)
  household: $432.00  (35%)

Anomalies (>2x average):
  [~3x avg] 2026-04-03  $227.00  food
  [~5x avg] 2026-04-14  $432.00  household

Saving advice:
  [mock response for saving_advice] [LLM]
```

`[LLM]` 태그가 경계입니다. 숫자는 전부 `pure fn`에서, 조언만 모델에서 왔습니다. `--mock`을 `AIL_OLLAMA_MODEL=llama3.1:latest`로 바꾸면 실제 조언이 나옵니다.

---

## 왜 Python 대신 새 언어인가?

라이브러리는 권고할 수 있습니다. 언어는 거부할 수 있습니다.

1. **`pure fn`은 LLM 호출과 사이드 이펙트를 컴파일 타임에 차단합니다.** mypy로는 잡을 수 없습니다.
2. **`Result` 타입이 문법에 있어서 실패 가능한 연산을 처리하지 않으면 파서 에러입니다.** 에러 핸들링을 잊을 수 없습니다.
3. **`while`이 없습니다.** 무한 루프는 언어 수준에서 불가능합니다.
4. **모든 값이 origin 트리를 가집니다.** `has_intent_origin(x)`로 그 값이 LLM을 거쳤는지 알 수 있습니다.

자세한 비교: [`why-ail.ko.md`](why-ail.ko.md)

---

## 기능 히스토리

| 버전 | 기능 |
|---|---|
| v1.0 | `fn`, `intent`, `entry`, `if`/`else`, `for`, `branch`, `context`, `import`, `evolve`, 21개 이상 내장 함수, stdlib |
| v1.1 | Result 타입: `ok`/`error`/`is_ok`/`unwrap`/`unwrap_or` |
| v1.2 | **Provenance**: 모든 값이 origin 트리를 가짐 |
| v1.3 | **Purity contracts**: `pure fn` 정적 검증 — intent 호출, 사이드 이펙트, 비순수 fn 호출 불가 |
| v1.4 | **Attempt blocks**: confidence 우선 폭포 — 첫 번째 ok 결과가 이김 |
| v1.5 | **Implicit parallelism**: 독립적인 intent 호출이 자동으로 병렬 실행. async/await 없음 |
| v1.6 | **Effect system**: `perform http.get(url)`, `perform file.read(path)` |
| v1.7 | **Match + confidence guard**: `"positive" with confidence > 0.9 => ...` |
| v1.8 | **Calibration**: confidence가 관찰된 평균으로 수렴 |
| v1.8.3 | `round`/`floor`/`ceil`/`sqrt`/`pow` 수학 내장 함수; 파라미터릭 타입(`List[T]`, `Map[K,V]`); `ail-coder:7b-v3` |
| v1.8.4 | `items: [Number]`, `-> [Text]` 타입 어노테이션 파서 지원; stdlib 내장 함수 trusted-pure 처리; `ail-coder:7b-v4` 훈련 데이터 260개 |

---

## 저장소 구조

```
ail-project/
├── spec/
│   └── 08-reference-card.ai.md  ← 완전한 언어 레퍼런스 (AI/LLM용 영어)
├── reference-impl/
│   ├── ail/                     # Python 인터프리터 (PyPI: ail-interpreter)
│   │   ├── parser/              # 렉서, 파서, purity checker
│   │   ├── runtime/             # executor, provenance, calibration 등
│   │   └── stdlib/              # 표준 라이브러리 — AIL로 작성됨
│   ├── examples/                # 예제 프로그램 16개
│   └── tools/                   # 벤치마크, 데모
├── go-impl/                     # Go 인터프리터 (의존성 0개)
└── docs/ko/                     # 한국어 문서 (여기)
```

### 한국어 문서

- [**why-ail.ko.md**](why-ail.ko.md) — Python 대비 6가지 구체적 차이
- [**why-ail-faq.ko.md**](why-ail-faq.ko.md) — 실무 질문 / 실측 데이터로 답변
- [**evolve-guide.ko.md**](evolve-guide.ko.md) — 자기 수정(`evolve`) 메커니즘
- [**stdlib-guide.ko.md**](stdlib-guide.ko.md) — 표준 라이브러리

---

## Python에서 사용하기

```python
from ail import run, ask

# 자연어 인터페이스
result = ask("count the letter 'a' in 'banana'")
print(result.value)          # 3
print(result.ail_source)     # AI가 작성한 AIL 코드
print(result.confidence)     # calibrated 신뢰도

# .ail 파일 직접 실행
result, trace = run("program.ail", input="hello")
print(result.value)
```

---

## 두 개의 런타임

AIL은 특정 구현에 묶이지 않습니다. Python과 Go, 두 독립적인 인터프리터가 동일한 .ail 파일에서 동일한 출력을 냅니다.

```bash
# Python
ail run examples/fizzbuzz.ail --input 15

# Go
cd go-impl && go build -o ail-go .
./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15

# 출력 동일: 1, 2, Fizz, 4, Buzz, ...
```

---

## 만든 사람들

**[hyun06000](https://github.com/hyun06000)** — 사람 저자. 최초 비전, 모든 아키텍처 결정, GitHub 관리.

**v1.0**까지의 코드와 문서는 **Claude Opus 4**가 claude.ai 채팅 인터페이스를 통해 작성했습니다. Claude Code도, API 파이프라인도 아닌, 브라우저 탭의 챗봇이 git 번들을 복사-붙여넣기하면서 만들었습니다.

**v1.1 이후**는 **Claude Code**와의 세션들에서 쌓였습니다 — provenance, purity contracts, attempt, parallelism, effects, match, calibration, Go 런타임, 훈련 파이프라인, 벤치마크, `ail-coder:7b-v3/v4` fine-tune까지.

이 프로젝트는 더 이상 존재하지 않는 AI들이 많은 세션에 걸쳐 만들었고, 한 사람이 각 결과물을 검증하고 GitHub에 올렸습니다.

---

## 라이선스 / 기여

Apache 2.0. 이슈와 PR은 한국어로 환영합니다.
