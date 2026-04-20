# AIL FAQ — 실무자가 궁금한 것만

🇬🇧 English: [`../why-ail-faq.md`](../why-ail-faq.md)

이 문서는 AIL 도입을 검토하는 개발자/팀이 실제로 던지는 질문에,
2026년 4월 벤치마크 실측 데이터로 답합니다. 수사 없음, 벤치마크
JSON 스냅샷은 [`../benchmarks/`](../benchmarks/)에 전부 커밋되어
있습니다.

---

## 한 줄 요약

> 같은 7B 모델을 썼을 때, **AIL로 작성된 코드는 정답 비율 70%, Python은 48%**.
> **AIL은 에러 핸들링을 문법이 강제해서 누락률 0%**. Python은 44%가 누락.

이 두 문장이 전부입니다. 나머지는 "어떤 조건에서, 얼마나" 입니다.

---

## Q1. 토큰은 얼마나 아낄 수 있나?

**짧은 답:** AI에게 "뭐든 LLM으로 처리해" 식의 naive agent(LangChain
기본 패턴)와 비교하면 **LLM 호출 수 약 75% 감소**. 품질은 같거나 더
좋음.

**긴 답 — 실제 측정값:**

50개 프롬프트를 3개 카테고리로 나눠 측정했습니다.

| 카테고리 | 작업 성격 | AIL LLM 호출/task | naive agent 예상 |
|---|---|---|---|
| A (15개) | 순수 계산 | **0.07** (거의 0) | ~1개 이상 |
| B (15개) | 순수 판단 | 0.93 | ~1개 |
| C (20개) | 하이브리드 (계산+판단) | 1.10 | ~3개 이상 |

**50개 전체:** AIL 37회 vs naive agent ~150회. **비용 환산(Claude
Sonnet 기준, 호출당 평균 500토큰)** 50개 task당:

- AIL: ~$0.14
- naive agent: ~$0.59
- **절감: 약 76%**

**왜 가능한가?** AIL은 `pure fn`(결정론적 계산)과 `intent`(판단
필요)를 문법으로 분리합니다. 계산은 런타임이 직접 실행하고, LLM은
판단이 필요한 부분에만 호출됩니다. Python에서는 이 구분이 없어서
개발자가 수동으로 결정하거나, 에이전트 프레임워크가 과도하게
LLM을 호출합니다.

**단, 주의:**
- AIL이 Python보다 LLM을 **더** 많이 부릅니다 (AIL 37회 vs 저 위
  Python 18회). 왜냐하면 Python이 LLM이 필요한 판단 작업을 몰래
  스킵하기 때문입니다 — Q3 참조.
- 코드 작성 단계의 LLM 호출(fine-tuned 7B 모델로 한 번 코드 생성)은
  이 계산에 포함되지 않았습니다. 7B 모델은 보통 로컬 GPU로 돌려
  사실상 무료.

---

## Q2. 품질은 진짜 더 좋은가?

**예. 같은 모델로 22%p 차이.**

| 지표 | AIL | Python |
|---|---|---|
| 최종 정답 비율 (50 task) | **70%** | 48% |
| pure_intent 정답 (15 task) | **80%** | 13% |
| 파싱 성공 | **78%** | 54% |

같은 fine-tuned 7B 모델이 Python으로 같은 문제를 풀었을 때 14개
case(30%)에서 "LLM 호출이 필요한 판단 작업을 스킵하고" 하드코딩된
키워드 매칭으로 대충 대답합니다. AIL은 `intent` 선언이 없으면
문법적으로 판단 작업을 선언할 수 없고, `intent` 선언 후에는
실행 시 반드시 LLM이 호출되어야 합니다. 문법이 에이전트를
"대충 하게" 놔두지 않습니다.

---

## Q3. Python보다 안전하다는 건 구체적으로 뭐가?

측정된 3가지 구조적 차이:

| 위험 | Python | AIL | 이유 |
|---|---|---|---|
| 에러 핸들링 누락 (`to_number` 실패 등) | 44% | **0%** | AIL의 `Result` 타입이 `is_ok()` / `unwrap()` 을 강제 |
| 무한 루프 | 런타임 발견 | **불가능** | AIL에 `while`이 없음 (`for VAR in COLLECTION`만) |
| pure 함수 안의 몰래 I/O | mypy로 못 잡음 | **파싱 거부** | `pure fn` 안에서 `intent` / `perform` 호출 불가 |

가장 큰 숫자는 **에러 핸들링 44% vs 0%**. 같은 모델이 Python에서는
`int(x)`, `open(f)`, `json.loads(s)` 같은 실패 가능 연산의 44%를
아무 처리 없이 그대로 씁니다. AIL에서는 이 숫자가 Sonnet 4.6
(70%), qwen14b (42%), llama8b (86%) **어느 모델에서나 0%**. 문법이
강제하는 거라 모델 품질과 무관합니다.

"프론티어 모델 쓰면 되지 않냐?"의 반례: Sonnet 4.6도 Python
코드에서는 70%의 실패 가능 연산을 에러 핸들링 없이 씁니다.
**모델을 바꿔서 해결되는 문제가 아닙니다.**

---

## Q4. 실행 속도는?

AIL이 **느립니다**. task당 평균:

- AIL: 4.8초
- Python: 1.9초

이유 2개:
1. AIL이 LLM을 더 "정직하게" 부릅니다 — Python은 안 불러야 할 때만
   빠릅니다.
2. AIL 런타임은 trace, provenance, confidence 추적에 오버헤드가
   있습니다. 현재 구현은 Python reference 구현이고 Go 구현은 Phase-0
   subset.

**어떤 워크로드에 크리티컬한가:**
- 저지연 챗봇 응답 → 별로 안 맞음
- 배치 처리, 데이터 파이프라인, 코드 에이전트 → 거의 영향 없음

---

## Q5. 어떤 조건에서 AIL을 선택해야 하나?

**선택:**
- ✅ AI가 코드를 작성하는 워크플로 (agentic coding, auto-pipeline)
- ✅ 계산과 판단이 섞인 task (C 카테고리: **45% → 70%**, 하이브리드
  에서 AIL이 압도)
- ✅ 에러 핸들링 누락을 외부 린터로 잡고 싶지 않을 때
- ✅ LLM 호출 비용을 중요하게 생각할 때 (Q1 참조)

**선택하지 않기:**
- ❌ 사람이 직접 읽고 디버깅하는 코드 (AIL의 디자인 전제가 "사람은
  AIL을 안 읽는다"입니다 — 이 전제가 당신 팀에 안 맞으면 Python이
  맞습니다)
- ❌ 이미 잘 돌고 있는 Python 파이프라인을 교체하려는 경우 (ROI가
  보통 안 맞음)
- ❌ 100% 순수 판단 작업 (AIL의 `intent` vs 일반 LLM 호출 — AIL이
  주는 게 없음)
- ❌ 프로덕션 low-latency 요구 (Q4 — 지금 런타임은 개발용)

---

## Q6. 어떤 모델이 필요한가?

**최소 요구사항:**
- 7B 이상의 code-specialized 모델을 AIL 데이터셋으로 fine-tune
- 3070 (8GB VRAM) GPU 1대로 10분 내 훈련 가능
- Ollama로 로컬 서빙 (inference 비용 $0)

**테스트된 모델:**

| 모델 | AIL parse rate | 비고 |
|---|---|---|
| `llama3.1:8b` | 8% | 너무 작음 — 작동 안 함 |
| `qwen2.5-coder:14b` | 42% | base 모델 (fine-tune 없이) |
| `claude-sonnet-4-6` | 36% | base 모델 |
| **`ail-coder:7b-v3`** | **78%** | qwen2.5-coder-7b + AIL fine-tune |

**핵심 발견:** base 모델에 "AIL 문법을 프롬프트로 설명"하는 방식은
잘 안 됩니다. Python 훈련 분포가 너무 강해서 프롬프트로 덮이지
않습니다. 7B 정도면 fine-tune이 반드시 필요하지만, 한 번 하면
작은 모델이 프론티어 모델보다 나은 결과를 냅니다.

---

## Q7. 실제 사례 하나로 보여줘

**프롬프트:** "키 175cm, 몸무게 70kg의 BMI를 계산하고 건강
상태를 평가해줘"

**AIL 출력 (`ail-coder:7b-v3`, 실제 벤치마크 결과):**

```ail
pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {
    return round(weight_kg / pow(height_cm / 100, 2), 2)
}
intent assess_health(bmi: Number) -> Text {
    goal: health_assessment
}
entry main(x: Text) {
    b = bmi(175, 70)
    return join([to_text(b), " ", assess_health(b)], "")
}
```

무슨 일이 일어나는가:
1. `bmi` 함수는 **LLM 없이** 직접 계산 → 22.86
2. `assess_health` 는 LLM을 **정확히 1번** 호출 → "정상 범위입니다"
3. 결과: "22.86 정상 범위입니다"

**같은 프롬프트를 Python으로:** 같은 모델이 `bmi`도 LLM으로
물어보거나, `assess_health`를 하드코딩된 `if bmi < 25: "정상"` 으로
대체해버립니다. 벤치마크 기록에서 확인 가능.

**토큰 사용:** AIL = LLM 호출 1번. 계산식은 런타임이 직접 돌림.
naive agent = LLM 호출 3번 (파싱 + 계산 + 판단 각각).

---

## 8. 체크리스트 — 지금 시도해볼지 말지

10개 체크 중 5개 이상이면 AIL을 실험해볼 가치가 있습니다.

- [ ] 우리 팀은 AI에게 코드를 작성시켜 실행하는 파이프라인이 있다
- [ ] LLM 호출 비용이 월 $100 이상이다
- [ ] "이 AI가 LLM을 호출했어야 하는데 하드코딩으로 때웠네" 같은
      버그를 본 적이 있다
- [ ] pre-commit hook, custom linter 등 Python용 안전장치를 계속
      추가하고 있다
- [ ] 작업 중에 계산과 판단이 섞인 task가 많다 (예: 데이터 파싱 +
      요약, 스코어 계산 + 등급 분류)
- [ ] 에러 핸들링 누락이 프로덕션 이슈를 낸 적이 있다
- [ ] 3070급 GPU 1대 이상, fine-tune 경험 있음
- [ ] 코드 감사 부담이 점점 늘어나고 있다
- [ ] 프로젝트 규모가 한 번에 다 재작성 못 할 정도는 아니다 (<10K LOC)
- [ ] "harness engineering" 이라는 개념을 이해하고 있다

---

## 추가 읽을거리

- **왜 이런 숫자가 나오는가 — 메커니즘**: [`why-ail-mechanics.ko.md`](why-ail-mechanics.ko.md) (이 FAQ의 모든 숫자가 나오는 *이유*)
- 벤치마크 방법론과 전체 JSON: [`../benchmarks/README.md`](../benchmarks/README.md)
- v3 상세 분석: [`../benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md`](../benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md)
- 언어 철학: [`../why-ail.md`](../why-ail.md)
- 원시 수치 리포트: [`../why-ail-numbers.md`](../why-ail-numbers.md)
