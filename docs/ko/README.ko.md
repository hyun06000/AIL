# AIL — AI-Intent Language

AI가 코드를 쓰고, 사람은 의도만 전달한다는 전제로 처음부터 설계한 프로그래밍 언어입니다.

**현재 버전:** v1.8.3 · PyPI: `ail-interpreter` · Python 인터프리터 + Go 인터프리터

[영어 README](../../README.md) | [AI/LLM 참조](../../README.ai.md)

❓ **"Python 써도 되잖아?"** — [`why-ail.ko.md`](why-ail.ko.md)에서 6가지 구체적인 차이를 실행 가능한 코드와 함께 설명합니다.

---

## AIL이 뭔가요?

두 종류의 함수가 있습니다.

- **`fn` / `pure fn`** — 결정론 계산. LLM을 부르지 않습니다. `pure fn`은 이 보장을 파서가 컴파일 타임에 강제합니다.
- **`intent`** — 판단이 필요한 작업. 런타임이 모델을 통해 처리합니다.

```ail
pure fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}

intent classify(text: Text) -> Text {
    goal: positive_or_negative
}

entry main(text: Text) {
    words = word_count(text)    // LLM 없음
    label = classify(text)      // LLM 호출
    return join([label, to_text(words)], ": ")
}
```

이 구분은 프레임워크 규칙이 아닌 언어 문법입니다. `pure fn` 안에서 LLM을 부르면 파서가 거부합니다.

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
```

사람은 자연어로 말합니다. AI가 AIL을 씁니다. 런타임이 실행합니다. 사람은 결과만 받습니다.

`--show-source`로 생성된 코드를 볼 수 있지만, 볼 필요는 없습니다.

Anthropic API를 쓴다면:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
ail ask "5의 팩토리얼"
```

원격 Ollama 서버라면:

```bash
export AIL_OLLAMA_HOST=http://10.0.0.1:11434
export AIL_OLLAMA_MODEL=ail-coder:7b-v3
ail ask "BMI 계산해줘 키 175cm 몸무게 70kg"
```

---

## 벤치마크 결과

같은 50개 프롬프트를 AIL과 Python 양쪽으로 작성하고 실행한 결과입니다.

### base 모델 (fine-tune 없음)

| 모델 | AIL 파싱 | Python 파싱 | Python 에러 핸들링 누락 | AIL 에러 핸들링 누락 |
|---|---|---|---|---|
| `llama3.1:8b` | 8% | 14% | **86% (43/50)** | **0%** |
| `qwen2.5-coder:14b` | 42% | 100% | **42% (21/50)** | **0%** |
| `claude-sonnet-4-6` | 36% | 100% | **70% (35/50)** | **0%** |

**핵심 발견 — 그리고 왜 더 강한 모델로 해결이 안 되는가:**

Claude Sonnet 4.6은 세 모델 중 가장 강하고 LLM 라우팅을 100% 정확히 합니다. 그럼에도 Python 코드에서 실패 가능한 연산의 70%를 에러 핸들링 없이 씁니다. llama8b는 86%, qwen14b는 42%입니다. 모델이 강해진다고 수렴하지 않습니다.

이유는 AI가 코드를 확률로 생성하기 때문입니다. 학습 데이터에서 에러 핸들링 없는 "해피 패스" 코드가 압도적으로 많아서, `int(x)`나 `json.loads(s)`를 예외 처리 없이 쓰는 코드를 자연스럽게 내놓습니다. Python이 이것을 허용하는 한 문제는 남습니다.

AIL의 `Result` 타입이 문법에 내장되어 있어 이 수치가 모든 모델에서 0%입니다. 에러 핸들링은 모델이 기억해야 할 것이 아니라 문법이 강제하는 것입니다.

### fine-tuned 모델 (`ail-coder:7b-v3`)

v1.8.3은 `qwen2.5-coder-7b-instruct`를 244개 AIL 샘플로 fine-tune한 모델을 포함합니다.

| | AIL 파싱 | AIL 정답 | Python 파싱 | Python 정답 | Python 에러 핸들링 누락 |
|---|---|---|---|---|---|
| `ail-coder:7b-v3` | **78%** | **70%** | 54% | 48% | 44% |

같은 모델로 AIL 정답률이 Python보다 22pp 높습니다. Python이 낮은 이유는 판단이 필요한 프롬프트에서 LLM 호출을 조용히 생략하기 때문입니다. AIL은 `intent` 선언 자체가 디스패치이므로 생략할 수 없습니다.

---

## 대표 예제 — 가계부 분석기

한 화면으로 AIL의 존재 이유를 보여주는 예제입니다.

거래 내역 한 달치를 넣으면 `pure fn`이 합계·카테고리별 지출·이상치를 계산하고 (LLM 없이), `intent`가 절약 조언을 자연어로 씁니다 (딱 이 부분만 LLM).

```bash
# Mock으로 실행 (API 키 불필요):
ail run examples/expense_analyzer.ail \
    --input "$(cat examples/sample_expenses.txt)" --mock

# Ollama로 실제 조언 생성:
AIL_OLLAMA_MODEL=llama3.1:latest \
    ail run examples/expense_analyzer.ail \
    --input "$(cat examples/sample_expenses.txt)"
```

출력 (발췌):

```
가계부 분석
=============
Parsed 18 rows; skipped 2 malformed.

총 지출: 983500원

카테고리별:
  food: 453700원  (46%)
  transport: 39300원  (3%)
  household: 342000원  (34%)

가장 큰 지출 3건:
  2026-04-14  320000원  household  새 청소기
  2026-04-03  180000원  food  저녁 2차 치킨

절약 조언:
  [mock response for saving_advice] [LLM]
```

`[LLM]` 태그는 provenance 경계입니다. 숫자는 전부 `pure fn`에서, 조언만 모델에서 왔습니다.

---

## v1.0 → v1.8 기능 요약

| 버전 | 기능 |
|---|---|
| v1.0 | `fn`, `intent`, `entry`, `if`/`else`, `for`, `branch`, `context`, `import`, `evolve` |
| v1.1 | Result 타입: `ok`/`error`/`is_ok`/`unwrap`/`unwrap_or` |
| v1.2 | **Provenance**: 모든 값이 origin 트리를 가짐 |
| v1.3 | **Purity contracts**: `pure fn`이 정적 검증 — intent/effect 호출 불가 |
| v1.4 | **Attempt blocks**: `attempt { try A; try B; try C }` — confidence 우선 폭포 |
| v1.5 | **Implicit parallelism**: 독립 intent 호출이 자동으로 병렬 실행 (async 없음) |
| v1.6 | **Effect system**: `perform http.get(url)`, `perform file.read(path)` |
| v1.7 | **Match + confidence guard**: `"positive" with confidence > 0.9 => ...` |
| v1.8 | **Calibration**: confidence가 관찰된 결과로 자동 재보정 |
| v1.8.3 | `round`/`floor`/`ceil`/`sqrt`/`pow` 수학 내장 함수; 파라미터릭 타입 파서 지원; `ail-coder:7b-v3` 포함 |

---

## 저장소 구조

```
ail-project/
├── spec/                    # 언어 명세
│   └── 08-reference-card.ai.md  ← 완전한 기계 판독용 레퍼런스 (영어)
├── reference-impl/          # Python 인터프리터 (전체 기능, 287개 테스트)
│   ├── ail/                 # ail 패키지 (PyPI: ail-interpreter)
│   │   ├── parser/          # 렉서, 파서, purity checker
│   │   ├── runtime/         # executor, provenance, calibration 등
│   │   └── stdlib/          # 표준 라이브러리 — AIL로 작성됨
│   ├── examples/            # 예제 프로그램 16개
│   └── tools/               # 벤치마크, 데모
├── go-impl/                 # Go 인터프리터 (의존성 0개)
└── docs/ko/                 # 한국어 문서 (여기)
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

AIL은 Python 구현 하나에 의존하지 않습니다. Go로 작성된 독립 인터프리터가 있어서, 같은 `.ail` 파일을 두 런타임에서 실행해도 동일한 출력이 나옵니다.

```bash
# Python 런타임
python -m ail.cli run examples/fizzbuzz.ail --input 15

# Go 런타임
cd go-impl && go build -o ail-go .
./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15

# 출력 동일: 1, 2, Fizz, 4, Buzz, ...
```

AIL이 Python 라이브러리가 아니라 언어라는 증거입니다.

---

## 라이선스 / 기여

Apache 2.0. 이슈와 PR은 한국어로도 환영합니다.
