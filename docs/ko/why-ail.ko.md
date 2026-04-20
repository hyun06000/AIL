# 왜 AIL 인가

> **AIL 은 키보드 앞의 사람이 아니라 AI 가 코드의 주 저자라는 전제 위에 설계된 프로그래밍 언어다. Python 은 그게 아니다.**

이 한 줄이 아래 모든 것을 결정합니다.

Python, JavaScript, Rust — 주류 언어는 전부 키보드 앞의 사람을 가정하고 설계됐습니다. 문법은 사람 눈에 편하게, 타입 시스템은 사람 실수를 잡으려고, 라이브러리는 사람 워크플로우에 맞춰져 있죠. 저자가 언어 모델로 바뀌면 이 결정들 중 일부는 적용되지 않게 되고, 일부는 오히려 새 저자의 작업을 방해합니다.

AIL 은 다른 전제에서 출발합니다 — 프로그래머는 언어 모델이고, 사람의 일은 의도를 표현하는 것이지 코드를 읽는 게 아닙니다. `pure fn`, 런타임 provenance, `attempt` 캐스케이드 같은 기능들은 Python 관용구의 개선판이 아니에요. 저자가 바뀐다는 전제에서 다시 쓴 **언어 계약**의 자연스러운 결과입니다.

아래가 오늘 실제로 돌아가는 것들입니다. 각 주장마다 직접 실행해 검증할 수 있는 파일이나 테스트가 연결되어 있습니다.

---

## 1. `pure fn` — "AI가 계산할 수 있는 것" vs "판단이 필요한 것" 컴파일 타임 분리

**Python + Anthropic SDK**: 텍스트를 읽고 쓰는 함수는 안에서 LLM 을 부르든 말든 겉모습이 같습니다. 본문을 끝까지 읽어야 압니다.

```python
# 순수 계산? 그렇게 보이긴 하네. 진짜 그런가?
def analyze(text: str) -> int:
    words = text.split()
    # 여섯 줄 아래 누군가 슬쩍 추가:
    sentiment = claude.messages.create(...)   # 깜짝 LLM 호출
    return len(words) if sentiment.value > 0.5 else 0
```

`mypy` 도 못 잡습니다. 런타임 트레이싱은 이미 호출된 뒤에야 알려주죠.

**AIL**: `pure fn` 은 파서가 강제하는 선언입니다. 바디에서 `intent` 호출, `perform` 이펙트, 순수하지 않은 다른 `fn` 호출 — 전부 금지. 위반 시 프로그램은 **실행은커녕 파싱도** 안 됩니다.

```ail
pure fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}

// 이건 파싱 시점에 PurityError 로 거부됩니다:
// pure fn analyze(text: Text) -> Text {
//     label = classify(text)     // pure fn 안의 intent 호출 — 거부
//     return label
// }
```

AI 가 `pure fn` 을 쓸 때 얻는 보증: 방금 자기가 쓴 코드에 LLM 서프라이즈도 파일 I/O 도 네트워크 호출도 없다. AI 가 주의했기 때문이 아니라, **컴파일러가 반대 경우를 허락하지 않았기 때문**입니다. [`tests/test_purity.py`](../../reference-impl/tests/test_purity.py) 가 이걸 검증하고, 누구나 `ail parse` 로 위 예제를 돌려 확인할 수 있습니다.

---

## 2. Provenance — 모든 값은 자신의 출처 트리를 지닌다

**Python + LLM SDK**: 리포트의 어떤 필드가 모델에서 왔고 어떤 게 계산된 건지 알고 싶다? `from_llm: bool` 플래그를 모든 헬퍼에 통과시키거나, LangSmith / OpenTelemetry 같은 트레이싱 라이브러리를 덧붙이고 계측이 빠짐없이 됐기를 기도해야 합니다.

**AIL**: 모든 값은 런타임이 관리하는 `origin` 트리를 가집니다. `has_intent_origin(value)` 가 트리를 따라가서 boolean 을 돌려줍니다. 셋업 없음, 라이브러리 없음, 인자로 전달할 필요 없음.

```ail
sentiment = classify(text)          // intent — LLM 개입
words = word_count(text)            // pure fn — 결정론적
has_intent_origin(sentiment)        // true
has_intent_origin(words)            // false
```

[`examples/audit_provenance.ail`](../../reference-impl/examples/audit_provenance.ail) 을 보세요. 프로그램이 리포트를 만들고, 각 필드에 대해 **자기 자신을 감사** 해서 `[LLM]` 또는 `[pure]` 라벨을 붙입니다. 래퍼가 아니라 **언어가 직접** 합니다.

Python 에서의 비용: 별도 추적 미들웨어 (LangSmith, OpenTelemetry, 또는 모든 헬퍼에 플래그를 손으로 넘기는 방식) — 저자가 계측을 빼먹지 말아야 한다는 추가 의존이 생깁니다. AIL 에서의 비용: 사용자 코드 0 줄. 런타임은 origin 노드 할당 비용을 값마다 지불하므로 기계 수준에서 공짜는 아니지만, **프로그래머 수준에서는 공짜** — 감사 기록을 작성하지 않고도 얻습니다.

---

## 3. `intent` vs `fn` — 어떤 도구를 쓸지 선언이 말한다

**Python + LLM SDK**: 모든 함수는 그냥 함수입니다. "이거 LLM 부르나?" 는 본문 읽거나 네이밍 컨벤션 (`classify_sentiment` 는 아마 부를 거고, `word_count` 는 아마 안 부를 거고 — 근데 확실하진 않음) 을 믿어야 합니다.

**AIL**: 최상위 키워드가 본문 한 줄 읽기 전에 말해줍니다.

```ail
fn parse_csv(raw: Text) -> Text { ... }         // 본문 미검사 — plain fn 은 intent 호출도 가능
pure fn word_count(s: Text) -> Number {          // 본문 정적 검사 (LLM 없음, 이펙트 없음)
    return length(split(s, " "))
}
intent classify(text: Text) -> Text {            // 판단 — 런타임이 모델로 디스패치
    goal: positive_or_negative
}
```

`intent` 선언에는 실행 가능 코드가 들어가지 않습니다. `goal` 과 선택적 `constraints` 만. 런타임이 goal 을 모델 어댑터에 넘기고 `(value, confidence)` 를 받아옵니다. 저자는 API 호출을 쓰지 않아요 — **언어 계약이 씁니다.**

`pure fn` 은 바디에 `intent` 호출도, `perform` 이펙트도, 순수하지 않은 `fn` 호출도 없다는 **정적 보증**을 추가합니다. plain `fn` 에는 이 보증이 없습니다 — 컴파일러가 LLM 부재를 증명해주길 원하면 `pure fn` 을 쓰세요.

[`examples/review_analyzer.ail`](../../reference-impl/examples/review_analyzer.ail) — 한 프로그램 안에 `intent classify` 한 개가 루프 안에서 리뷰마다 호출되고, 나머지는 전부 `fn` 헬퍼로 파싱·필터링·카운트·리포트 생성을 결정론적으로 처리합니다. 최상위 키워드만 보면 어느 것이 모델로 가는지 **한눈에** 판단할 수 있습니다.

---

## 4. `attempt` — 신뢰도 우선순위 캐스케이드가 언어 구문

**Python + LLM SDK**: "먼저 빠른 룩업 시도, 안 되면 작은 모델, 그래도 안 되면 큰 모델" 이 필요하다? 신뢰도 threshold 에 대한 if/else 를 작성하고, 코드베이스 여기저기에 똑같은 패턴을 유지해야 합니다.

```python
# 손으로 짠 캐스케이드, 필요한 곳마다 뿌림:
result = lookup_table.get(key)
if result is None or confidence < 0.9:
    result = small_model(key)
if confidence < 0.7:
    result = big_model(key)
```

**AIL**: `attempt` 는 블록입니다. 전략을 `try` 로 나열하고, 런타임이 순서대로 시도해서 `Result` 오류가 아닌 첫 번째 결과가 승리합니다. 실제 문법은 최소 형태 — 라벨도 접미 절도 없습니다:

```ail
entry main(text: Text) {
    return attempt {
        try direct_parse(text)    // pure fn, ok(n) 또는 error(...)
        try scan_tokens(text)      // pure fn, ok(n) 또는 error(...)
        try infer_number(text)     // intent — 위 두 개가 에러일 때만 실행
    }
}
```

ok 인 첫 `try` 가 승리하면 이후 `try` 는 평가되지 않습니다. 신뢰도 임계 기반 변형 ("confidence 0.8 미만 건너뛰기") 은 미래 확장 — 현재 파서는 위 형태만 수용합니다.

[`examples/cascade_extract.ail`](../../reference-impl/examples/cascade_extract.ail) 에서 실행 가능한 버전을 볼 수 있습니다. 캐스케이드는 **구조적** 이에요 — 매번 떠올려서 적용해야 하는 패턴이 아니라.

---

## 5. Implicit parallelism — 독립된 LLM 호출이 `async` 없이 병렬로 도는

**Python**: LLM 호출 세 개를 병렬로 돌리려면 관련된 모든 함수에 `async def`, 사방에 `await`, 이벤트 루프 실행, 그리고 불가피한 "`await` 하나 빼먹음" 버그 감수. async coloring 이 콜 스택을 타고 전파됩니다 — 함수 하나가 async 면 그 위로 전부 async.

**AIL**: `async` 도 `await` 도 없습니다. 런타임이 각 할당문의 RHS 독립성을 분석해서 배치화. 의존 관계 있는 호출 (`b = f(a)`) 은 자동으로 순차.

```ail
entry main(text: Text) {
    sentiment = classify_sentiment(text)   // 독립된 intent
    topic = classify_topic(text)            // 독립된 intent
    tone = classify_tone(text)              // 독립된 intent
    // 셋이 동시에 실행. async/await 안 썼음.
    return join([sentiment, topic, tone], " / ")
}
```

[`examples/parallel_analysis.ail`](../../reference-impl/examples/parallel_analysis.ail) 참고. 독립된 intent N 개가 감지되고 모델 어댑터가 동시 요청을 지원할 때, 벽시계 지연 시간은 N·t 가 아니라 대략 t 에 가까워집니다. 정확한 속도 향상은 어댑터 (HTTP/네트워크 오버헤드, 제공자 rate limit) 와 플래너의 의존성 추론에 따라 달라지지만, **저자는 이를 얻기 위해 함수를 color 하거나 await 체인을 관리할 필요가 없습니다.**

---

## 6. Calibration — 관찰된 결과로 신뢰도가 재보정

**Python + LLM SDK**: 모델이 신뢰도 점수를 돌려줍니다. 믿거나 말거나. 모델의 "0.9 확신" 이 실제로 90% 정확도에 대응하는지 알고 싶으면? 별도 로깅 + ML 파이프라인을 구축하세요.

**AIL**: 런타임이 intent 별로 결과를 기록합니다 — 보고된 신뢰도 구간 (0.0–0.1, 0.1–0.2, …, 0.9–1.0) 으로 버킷팅. 버킷에 샘플이 충분히 쌓이면 (기본 5 개), 해당 구간에 떨어지는 이후 호출은 모델의 자기 신고값 대신 **관측 평균** 으로 대체됩니다. AIL 에서 상태 직접 조회 가능:

```ail
calibration_of("classify_sentiment")
// 버킷별 레코드를 반환:
// {
//   "0.8-0.9": { "count": 12, "mean_observed": 0.71, "calibrated": true  },
//   "0.9-1.0": { "count":  3, "mean_observed": 0.88, "calibrated": false }
//   ...
// }
```

실용적 효과: 충분한 데이터가 쌓이면 `match` confidence guard 와 모든 `if confidence > …` 체크가 모델 자기 신념 대신 **관측된 현실** 을 씁니다. [`tools/calibration_demo.py`](../../reference-impl/tools/calibration_demo.py) 로 ~20 번 호출에 걸쳐 신뢰도가 실제 진실 쪽으로 이동하는 걸 볼 수 있어요.

---

## AIL 이 **못하는** 것들

위 목록보다 이 솔직함이 더 중요합니다.

- **툴링이 얇음.** IDE 플러그인 없음, LSP 없음, 디버거 없음, 포매터 없음. `.ail` 파일은 아무 에디터로 편집하고 CLI 로 돌립니다.
- **에코시스템이 작음.** stdlib 모듈 3 개 (`core`, `language`, `utils`). stdlib 이 안 커버하면 인라인으로 써야 합니다.
- **성능은 소박함.** Python 으로 짠 트리-워킹 인터프리터. 두 번째 런타임은 Go 지만 아직 Phase-0 부분집합. 뜨거운 루프는 느립니다.
- **사용자 유형이 한 가지.** 이 시점 (v1.8.3, 2026 년 4 월) 외부 기여자 ~0 명, 외부 사용자 ~0 명. "내 환경에서 잘 됨" 은 스케일에서 검증 안 됐습니다.
- **디자인이 완고함.** `while` 없음, 클래스 없음, OOP 없음, 상속 없음. 이펙트는 권한 게이트. 이런 것들을 당연시하는 머릿속 모델이면 AIL 이 **이상하게** 느껴질 겁니다 — 빠진 기능이 아니라 **설계 결정** 이에요.

---

## AIL 이 맞는 선택인 때

아래가 대부분 맞으면 AIL:

- AI 모델이 코드의 주 저자. 사람은 의도를 표현하지 `.ail` 파일을 읽지 않음 (보고 싶을 때만 봄).
- 코드의 출력을 사람이나 downstream 시스템이 소비하는데, **어떤 사실이 모델에서 왔고 어떤 게 계산에서 왔는지** 알아야 함 (provenance 중요).
- 파이프라인의 일부는 결정론적 (파싱, 집계, 변환), 일부는 판단 필요 (분류, 요약, 추출). 둘 다 한 언어 안에 있되 **정적 경계** 가 있기를 원함.
- 미들웨어를 매번 쓰지 않고 `attempt` / confidence guard / calibration 을 쓰고 싶음.

AIL 이 **아닌** 때:

- 이미 돌아가는 Python 파이프라인이 있음. AIL 로 재작성은 연구 투자지 생산성 개선이 아님.
- 워크로드가 I/O 집약, DB 접근, UI 위주. 이런 건 성숙한 에코시스템에 속함 — 라우팅 보증이 필요하면 AIL 을 서브프로세스로 부르세요.
- 사람 팀이 읽고 유지보수해야 함. AIL 은 그거 염두에 두고 만든 게 아닙니다.

---

## 주장을 직접 검증하는 법

```bash
pip install ail-interpreter
export AIL_OLLAMA_MODEL=llama3.1:latest   # 또는 ANTHROPIC_API_KEY=...

# 위에서 참조한 프로그램들:
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl

ail run examples/review_analyzer.ail --input "Great product!\nTerrible\nLoved it" --mock
ail run examples/audit_provenance.ail --input "I love this product" --mock
ail run examples/cascade_extract.ail --input "extract a date from: meeting next thursday" --mock
ail run examples/parallel_analysis.ail --input "The Fed raised rates today." --mock

# Purity 강제 증명:
python -m pytest tests/test_purity.py -v

# 시간에 따른 calibration drift:
python tools/calibration_demo.py
```

위 내용 중 뭔가 설명과 안 맞으면 문서가 틀린 거 — 이슈 열어주세요.

---

## 관련 문서

- [`README.md`](../../README.md) — 프로젝트 개요 (영어)
- [`README.ko.md`](README.ko.md) — 프로젝트 개요 (한국어)
- [`spec/08-reference-card.ai.md`](../../spec/08-reference-card.ai.md) — 언어 완전 레퍼런스 (기계 판독 가능)
- [`why-ail.md`](../why-ail.md) — 이 문서의 영어판
- [`CHANGELOG.md`](../../CHANGELOG.md) — 무엇이 언제 배포됐나
