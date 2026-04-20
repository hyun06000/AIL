# 왜 AIL인가

> AIL은 AI가 코드의 주 저자라는 전제로 설계됐습니다. Python은 그렇지 않습니다.

Python, JavaScript, Rust는 키보드 앞의 사람을 위해 설계됐습니다. 문법은 사람 눈에 편하고, 타입 시스템은 사람의 실수를 잡고, 라이브러리는 사람의 워크플로우에 맞습니다.

저자가 언어 모델로 바뀌면 이 결정들 중 일부는 의미가 없어지고, 일부는 오히려 방해가 됩니다.

AIL은 다른 전제에서 출발합니다. 프로그래머는 언어 모델이고, 사람의 역할은 의도를 표현하는 것이지 코드를 읽는 것이 아닙니다. `pure fn`, provenance, `attempt` 같은 기능들은 Python 관용구의 개선판이 아닙니다. 저자가 바뀐다는 전제에서 처음부터 다시 설계한 결과입니다.

아래가 지금 실제로 동작하는 것들입니다. 각 주장마다 직접 실행해서 확인할 수 있는 파일이 연결되어 있습니다.

---

## 1. `pure fn` — LLM 호출 여부를 컴파일 타임에 알 수 있습니다

**Python + Anthropic SDK:** 텍스트를 처리하는 함수가 내부에서 LLM을 부르는지 알려면 본문을 끝까지 읽어야 합니다.

```python
# 순수 계산처럼 보입니다. 진짜 그럴까요?
def analyze(text: str) -> int:
    words = text.split()
    # 여섯 줄 아래:
    sentiment = claude.messages.create(...)   # 깜짝 LLM 호출
    return len(words) if sentiment.value > 0.5 else 0
```

`mypy`도 못 잡습니다. 런타임 트레이싱은 호출이 이미 일어난 후에야 알려줍니다.

**AIL:** `pure fn`은 파서가 강제하는 선언입니다. body에서 `intent` 호출, `perform` 이펙트, 순수하지 않은 fn 호출이 있으면 파싱 자체가 거부됩니다.

```ail
pure fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}

// 파싱 시점에 PurityError:
// pure fn analyze(text: Text) -> Text {
//     label = classify(text)     // pure fn 안의 intent 호출 — 거부
//     return label
// }
```

AI가 `pure fn`을 쓸 때 얻는 보장: 방금 쓴 코드에 LLM 호출도 파일 I/O도 없습니다. AI가 주의했기 때문이 아니라, 컴파일러가 그 반대를 허락하지 않기 때문입니다.

확인: [`tests/test_purity.py`](../../reference-impl/tests/test_purity.py) 또는 `ail parse`로 직접 검증.

---

## 2. `Result` 타입 — 에러 핸들링 누락이 문법 수준에서 불가능합니다

**왜 이게 중요한가:** AI는 코드를 확률로 생성합니다. 학습 데이터에서 `int(x)`, `json.loads(s)`, `open(f)` 같은 함수가 에러 핸들링 없이 쓰인 예제가 압도적으로 많습니다. 그래서 모델은 실패 가능한 연산을 자연스럽게 처리 없이 내놓습니다. 사람은 경험으로 "이 함수가 터질 수 있다"는 걸 압니다. AI는 그걸 확률로만 알고, 종종 빠뜨립니다.

더 강한 모델을 써도 이 문제는 해결되지 않습니다. 벤치마크에서 Claude Sonnet 4.6은 Python 코드에서 실패 가능한 연산의 70%를 에러 핸들링 없이 씁니다. llama3.1:8b는 86%, qwen2.5-coder:14b는 42%입니다. 모델이 강해진다고 수렴하는 경향이 없습니다. Python이 허용하는 한 이 문제는 남습니다.

AI가 코드를 생성하고 자율적으로 실행하는 파이프라인에서 이 누락은 특히 위험합니다. 사람이 코드를 리뷰하면 `try/except`가 없는 걸 발견할 수 있습니다. 하지만 AI가 생성→실행→결과 반환을 자동으로 처리하면, 잘못된 값이 다음 단계로 조용히 전달됩니다.

**AIL:** `to_number(x)`, `perform file.read(path)` 같은 실패 가능한 연산은 `Result` 타입을 반환합니다. 그 결과를 `is_ok()`나 `unwrap_or()`로 처리하지 않으면 파서가 거부합니다.

```ail
raw = perform file.read("data.csv")
if is_ok(raw) {
    lines = split(unwrap(raw), "\n")
} else {
    return error("파일을 읽을 수 없습니다")
}
```

`unwrap(raw)` 한 줄만 쓰면 파서가 에러를 냅니다. 에러 핸들링은 모델이 기억해야 할 것이 아니라 문법이 강제하는 것입니다.

**측정값:** AIL 에러 핸들링 누락률은 테스트한 모든 모델 티어에서 **0%**. Python의 동일 수치는 42–86%.

---

## 3. Provenance — 값이 어디서 왔는지 자동으로 추적됩니다

**Python + LLM SDK:** 리포트의 어떤 필드가 모델에서 왔는지 알고 싶다면? `from_llm: bool` 플래그를 모든 헬퍼에 넘기거나, LangSmith 같은 트레이싱 라이브러리를 붙이고 계측이 빠짐없이 됐기를 기도해야 합니다.

**AIL:** 모든 값은 런타임이 관리하는 origin 트리를 가집니다. `has_intent_origin(value)`가 트리를 탐색해서 boolean을 돌려줍니다. 셋업 없이, 라이브러리 없이, 인자 전달 없이.

```ail
sentiment = classify(text)       // intent — LLM 개입
words = word_count(text)         // pure fn — 결정론적
has_intent_origin(sentiment)     // true
has_intent_origin(words)         // false
```

[`examples/audit_provenance.ail`](../../reference-impl/examples/audit_provenance.ail)을 보면, 프로그램이 리포트를 만들고 각 필드에 `[LLM]` 또는 `[pure]` 라벨을 스스로 붙입니다. 래퍼가 아니라 언어가 직접 합니다.

Python에서의 비용: 별도 트레이싱 미들웨어와 계측 누락 방지 노력. AIL에서의 비용: 사용자 코드 0줄.

---

## 4. `intent` vs `fn` — 키워드만 보면 LLM 여부를 알 수 있습니다

**Python + LLM SDK:** 모든 함수는 그냥 함수입니다. `classify_sentiment`는 LLM을 부를 것 같고 `word_count`는 안 부를 것 같지만, 확실하려면 본문을 읽어야 합니다.

**AIL:** 최상위 키워드가 본문 한 줄도 읽기 전에 말해줍니다.

```ail
fn parse_csv(raw: Text) -> Text { ... }         // body 미검사 — plain fn은 intent도 가능
pure fn word_count(s: Text) -> Number { ... }   // 정적 검사 완료 — LLM 없음 보장
intent classify(text: Text) -> Text {            // 판단 — 런타임이 모델로 디스패치
    goal: positive_or_negative
}
```

`intent` 선언에는 실행 가능한 코드가 없습니다. `goal`과 선택적 `constraints`만 있습니다. 런타임이 goal을 모델 어댑터에 넘기고 `(value, confidence)`를 받습니다. AI는 API 호출 코드를 쓰지 않습니다. 언어 계약이 씁니다.

[`examples/review_analyzer.ail`](../../reference-impl/examples/review_analyzer.ail)에서 `intent classify` 하나가 루프 안에서 리뷰마다 호출되고, 나머지 파싱·필터링·카운팅·리포트 생성은 전부 `fn` 헬퍼로 처리되는 것을 볼 수 있습니다.

---

## 5. `attempt` — 폴백 캐스케이드가 언어 구문입니다

**Python + LLM SDK:** "먼저 빠른 룩업, 실패하면 작은 모델, 그래도 실패하면 큰 모델"을 구현하려면 confidence 임계값 기반 if/else를 직접 짜고 여러 곳에 유지해야 합니다.

```python
# 직접 짠 캐스케이드, 코드 여러 곳에 흩어짐:
result = lookup_table.get(key)
if result is None or confidence < 0.9:
    result = small_model(key)
if confidence < 0.7:
    result = big_model(key)
```

**AIL:** `attempt`는 블록 구문입니다. `try`로 전략을 나열하면 런타임이 순서대로 시도하고, `Result` 에러가 아닌 첫 번째 결과가 승리합니다.

```ail
entry main(text: Text) {
    return attempt {
        try direct_parse(text)    // pure fn — ok(n) 또는 error(...)
        try scan_tokens(text)     // pure fn — ok(n) 또는 error(...)
        try infer_number(text)    // intent — 앞 두 개가 에러일 때만 실행
    }
}
```

ok인 try가 나오면 나머지는 평가하지 않습니다.

실행 가능한 예제: [`examples/cascade_extract.ail`](../../reference-impl/examples/cascade_extract.ail). 캐스케이드는 패턴이 아니라 구조입니다.

---

## 6. Implicit parallelism — async 없이 LLM 호출이 병렬로 실행됩니다

**Python:** LLM 호출 3개를 병렬로 실행하려면 관련 함수 모두에 `async def`, 사방에 `await`, 이벤트 루프가 필요합니다. async coloring이 콜 스택을 타고 전파됩니다. 함수 하나가 async면 그 위 전체가 async가 됩니다.

**AIL:** `async`도 `await`도 없습니다. 런타임이 각 할당문의 독립성을 분석해서 자동으로 병렬 처리합니다.

```ail
entry main(text: Text) {
    sentiment = classify_sentiment(text)   // 독립된 intent
    topic = classify_topic(text)           // 독립된 intent
    tone = classify_tone(text)             // 독립된 intent
    // 셋이 동시에 실행됩니다. async/await를 쓰지 않았습니다.
    return join([sentiment, topic, tone], " / ")
}
```

독립된 intent N개가 병렬로 실행되면 벽시계 시간은 N×t가 아니라 t에 가까워집니다.

실행 가능한 예제: [`examples/parallel_analysis.ail`](../../reference-impl/examples/parallel_analysis.ail).

---

## 7. Calibration — confidence가 관찰된 결과로 자동 재보정됩니다

**Python + LLM SDK:** 모델이 "0.9 확신"이라고 했을 때 실제로 90% 정확도인지 알려면 별도 로깅 + ML 파이프라인을 직접 구축해야 합니다.

**AIL:** 런타임이 intent별로 결과를 기록하고 confidence 구간(0.0–0.1, …, 0.9–1.0)으로 버킷팅합니다. 버킷에 샘플이 5개 이상 쌓이면 이후 같은 구간의 호출은 모델 자기 신고값 대신 관측 평균을 씁니다.

```ail
calibration_of("classify_sentiment")
// 반환값:
// {
//   "0.8-0.9": { "count": 12, "mean_observed": 0.71, "calibrated": true  },
//   "0.9-1.0": { "count":  3, "mean_observed": 0.88, "calibrated": false }
// }
```

`match` confidence guard와 `if confidence > …` 체크가 모델의 자기 신뢰가 아니라 관측된 현실을 기반으로 동작하게 됩니다.

확인: [`tools/calibration_demo.py`](../../reference-impl/tools/calibration_demo.py).

---

## AIL이 못하는 것들

이게 위 목록보다 중요합니다.

- **툴링이 없습니다.** IDE 플러그인, LSP, 디버거, 포매터가 없습니다.
- **에코시스템이 작습니다.** stdlib 모듈 3개뿐입니다.
- **느립니다.** Python 트리-워킹 인터프리터입니다.
- **외부 사용자가 없습니다.** v1.8.3 기준 외부 기여자·사용자 ~0명입니다.
- **의견이 강합니다.** `while` 없음, 클래스 없음, OOP 없음. 빠진 기능이 아니라 설계 결정입니다.

---

## 언제 AIL이 맞는 선택인가요?

아래가 대부분 해당하면 AIL을 써볼 만합니다.

- AI 모델이 코드의 주 저자입니다. 사람은 의도를 표현하고 결과를 받습니다.
- 어떤 값이 LLM에서 왔고 어떤 값이 계산에서 나왔는지 구분해야 합니다.
- 파이프라인의 일부는 결정론적(파싱, 집계)이고 일부는 판단이 필요(분류, 요약)합니다.
- 미들웨어 없이 `attempt`, confidence guard, calibration을 쓰고 싶습니다.

이런 경우에는 AIL이 맞지 않습니다.

- 이미 잘 돌아가는 Python 파이프라인이 있습니다. 재작성은 연구 투자입니다.
- I/O 집약, DB 접근, UI 위주의 작업입니다.
- 사람 팀이 소스를 읽고 유지보수해야 합니다.

---

## 직접 확인하는 법

```bash
pip install ail-interpreter
export AIL_OLLAMA_MODEL=llama3.1:latest   # 또는 ANTHROPIC_API_KEY=...

git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl

ail run examples/review_analyzer.ail --input "Great product!\nTerrible\nLoved it" --mock
ail run examples/audit_provenance.ail --input "I love this product" --mock
ail run examples/cascade_extract.ail --input "extract a date from: meeting next thursday" --mock
ail run examples/parallel_analysis.ail --input "The Fed raised rates today." --mock

# Purity 강제 확인:
python -m pytest tests/test_purity.py -v

# Calibration drift 확인:
python tools/calibration_demo.py
```

설명과 결과가 다르다면 문서가 틀린 겁니다. 이슈를 열어주세요.

---

## 관련 문서

- [`README.ko.md`](README.ko.md) — 프로젝트 개요 (한국어)
- [`why-ail-faq.ko.md`](why-ail-faq.ko.md) — 실무 질문과 실측 데이터로 답변
- [`spec/08-reference-card.ai.md`](../../spec/08-reference-card.ai.md) — 언어 완전 레퍼런스 (기계 판독용)
- [`CHANGELOG.md`](../../CHANGELOG.md) — 버전별 변경사항
