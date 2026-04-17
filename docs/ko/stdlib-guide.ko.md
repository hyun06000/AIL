# 표준 라이브러리 (`stdlib`) 이해하기

**대상 독자:** AIL 프로그램을 작성할 때 매번 `intent summarize`, `intent translate`를 처음부터 정의하는 게 이상하다고 느끼신 분.

**전제:** [README.ko.md](README.ko.md)를 먼저 읽으시거나 AIL의 기본 개념을 알고 계신다면 도움이 됩니다.

---

## 왜 표준 라이브러리가 필요한가

AIL이 정말 "언어"가 되려면, 프로그램들이 공통 기반을 공유해야 합니다. 모든 프로그램이 매번 `intent summarize`, `intent classify`를 처음부터 정의한다면 그건 **언어라기보단 그냥 파이썬 같은 호스트 언어의 특이한 문법 풍습** 에 가깝죠.

Python이 Python인 이유 중 하나는 `import os`, `import json`이 그냥 되기 때문입니다. SQL이 SQL인 이유는 `SELECT`, `JOIN`이 어디서든 같은 의미를 갖기 때문이고요. AIL도 그래야 합니다.

---

## 중요한 설계 결정: stdlib은 AIL로 작성된다

`reference-impl/ail/stdlib/` 디렉토리를 보시면 세 개의 파일이 있어요:

- `core.ail` — `identity`, `refuse` (공통 intent)
- `language.ail` — NLP 주력 intent 6개
- `utils.ail` — 11개의 `pure fn` 유틸리티 (v1.3부터 전부 정적 검증된 pure fn)

**이것들은 Python 파일이 아니라 AIL 파일입니다.** 런타임은 `stdlib/language`를 import하라는 요청을 받으면, 그냥 `language.ail` 파일을 읽고 파싱합니다. 사용자가 쓴 어떤 `.ail` 파일과도 똑같은 방식으로 처리돼요.

왜 이렇게 했을까요? 두 가지 이유:

1. **특권층 intent를 만들지 않기 위해.** 만약 stdlib을 Python으로 하드코딩했다면, stdlib intent는 "진짜 AIL 규칙이 적용되지 않는 특별한 존재"가 됐을 겁니다. 그러면 사용자가 stdlib을 흉내낼 수도, 개선할 수도 없어요.

2. **언어가 스스로를 표현할 수 있다는 증거.** 만약 AIL로 stdlib을 쓸 수 없다면, 그건 언어가 뭔가 중요한 걸 표현 못 한다는 뜻입니다. 실제로 stdlib을 쓰는 과정에서 파서의 한계 두 가지가 발견됐고, 문서화됐어요 (커밋 `69ec236` 참고).

---

## 현재 제공되는 것

### `stdlib/core`

가장 기본적인 유틸리티:

```ail
intent identity(x: Text) -> Text {
    goal: return the input value unchanged
}

intent refuse(reason: Text) -> Text {
    goal: a structured refusal carrying the declared reason
}
```

### `stdlib/language`

자연어 처리의 주력 여섯 개:

| Intent | 하는 일 |
|---|---|
| `summarize(source, max_tokens)` | 주어진 길이 한도 내에서 요약 |
| `translate(source, target_language)` | 다른 언어로 번역 |
| `classify(text, labels)` | 주어진 레이블 중 하나로 분류 |
| `extract(source, schema_description)` | 구조화된 데이터 추출 (JSON) |
| `rewrite(source, instruction)` | 지시에 따라 재작성 |
| `critique(artifact, rubric)` | 평가 루브릭에 따른 비평 |

`classify`와 `extract`는 자체적으로 `on_low_confidence` 핸들러를 가지고 있어요 — 확신이 낮으면 안전한 기본값으로 돌아갑니다. **v1.8부터 이 threshold는 calibrated confidence로 판정됩니다** — 모델이 "0.9"라고 주장해도 과거 관찰이 "실제로는 0.3"이라고 말하면 핸들러가 작동합니다.

### `stdlib/utils` (v1.3부터 전부 `pure fn`)

수치·문자열·리스트 처리 유틸리티 11개:

| Fn | 시그니처 |
|---|---|
| `word_count(text)` | 공백 단위 단어 수 |
| `char_count(text)` | 글자 수 |
| `is_empty(text)` | 공백만 있어도 true |
| `repeat(text, n)` | 반복 |
| `pad_left(text, len, pad)` | 왼쪽 패딩 |
| `clamp(value, lo, hi)` | 범위로 자르기 |
| `sum_list(nums)` | 합 |
| `average(nums)` | 평균 |
| `flatten(nested)` | 중첩 리스트 펼치기 |
| `unique(items)` | 중복 제거 |
| `take(items, n)` | 앞 n개 |
| `zip_lists(a, b)` | 두 리스트 결합 |

**전부 `pure fn`이라는 게 중요합니다.** 이들 유틸로 계산한 값은 **컴파일 시점에** `has_intent_origin == false` 보장. 다시 말해: `sum_list([...])`의 결과가 LLM을 거쳤는지 런타임 쿼리가 필요 없습니다. 언어가 이미 압니다.

---

## 사용법

```ail
import summarize from "stdlib/language"
import classify from "stdlib/language"

context editorial_review extends default {
    register: "neutral"
    audience: "general_reader"
    preserve: [names, dates, numbers]
}

entry main(article: Text) {
    with context editorial_review:
        brief = summarize(article, 80)
        mood = classify(brief, "positive_negative_mixed_unclear")
    return mood
}
```

이 프로그램은 `reference-impl/examples/summarize_and_classify.ail`에 있어요. 직접 돌려보세요:

```bash
cd reference-impl
ail run examples/summarize_and_classify.ail --input "기사 내용..." --mock
```

---

## 현재 한계 (v1.8)

지금 import는 "모듈 전체를 가져온다"는 단순한 의미:

```ail
import summarize from "stdlib/language"
```

이렇게 쓰면 **`language` 전체**가 스코프에 들어옵니다 — `summarize`뿐 아니라 `classify`, `translate`, ...도 함께. **심볼 단위 import**는 아직 구현 안 됐습니다.

그 외:

- **상대 경로 import** (`./helpers.ail`): 거부. 같은 프로젝트 내 파일 공유는 향후 추가 예정.
- **URL import** (`org://company/lib@v1`): 거부. 외부 레지스트리는 NOOS 수준 기능.
- **stdlib 확장 여지**: `stdlib/data` (CSV·JSON 처리), `stdlib/math` (통계·선형대수), `stdlib/text` (regex·템플릿) 등이 로드맵에 있지만 아직 없음.

---

## 로컬 선언이 이깁니다

같은 이름으로 로컬 intent를 정의하면 import된 것을 가립니다:

```ail
import summarize from "stdlib/language"

// 내가 원하는 대로 정의한 summarize
intent summarize(source: Text, max_tokens: Number) -> Text {
    goal: my_special_summary_logic
}

entry main(text: Text) {
    return summarize(text, 50)  // 여기는 로컬 버전이 쓰임
}
```

이건 버그가 아니라 의도된 동작입니다. 사용자의 코드가 stdlib보다 권위를 가져요.

---

## 관련

- `reference-impl/ail/stdlib/` — 실제 구현
- `reference-impl/ail/stdlib/__init__.py` — import resolver
- [`../../spec/06-stdlib.md`](../../spec/06-stdlib.md) — 표준 라이브러리 명세 (영어)
- [`../../reference-impl/examples/summarize_and_classify.ail`](../../reference-impl/examples/summarize_and_classify.ail) — stdlib을 쓰는 예제

---

## 요약

표준 라이브러리가 있다는 건:

- ✅ AIL 프로그램이 **공통 기반을 공유**할 수 있음
- ✅ AIL이 **스스로를 표현**할 수 있음 (stdlib은 AIL로 작성됨)
- ✅ 사용자 코드는 **로컬 정의로 stdlib을 재정의**할 수 있음
- ✅ 새로운 intent나 pure fn을 stdlib에 기여하는 것 = **.ail 파일을 편집**하는 것
- ✅ `utils.ail`의 모든 fn은 **정적 검증된 `pure fn`** — 이 유틸들을 거친 값은 LLM에 닿지 않음이 컴파일 타임에 보장됨 (v1.3)
