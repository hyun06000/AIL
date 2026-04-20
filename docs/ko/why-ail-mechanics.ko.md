# 왜 이런 수치가 나오는가 — 메커니즘

🇬🇧 English: [`../why-ail-mechanics.md`](../why-ail-mechanics.md)

[FAQ](why-ail-faq.ko.md)가 숫자를 보여준다면, 이 문서는 **왜**
그 숫자가 나오는지를 메커니즘 수준에서 설명합니다. 추측이 아니라
벤치마크 JSON 기록으로 증명 가능한 것들만.

---

## 1. 왜 AIL 에러 핸들링 누락률 0%, Python은 44%인가

**관찰.** 테스트된 모든 모델 — llama3.1:8b (86%), qwen2.5-coder:14b
(42%), `ail-coder:7b-v3` (44%), Claude Sonnet 4.6 (70%) — 에서
Python 코드는 실패 가능 연산의 에러 핸들링을 빠뜨립니다. AIL은
**모든 모델에서 0%**.

**메커니즘.** AIL의 `to_number("42")`는 `Number`가 아닌
`Result[Number]`를 반환합니다. 파서는 `Result`를 `Number`처럼
쓰는 걸 거부합니다:

```ail
pure fn safe_parse(raw: Text) -> Number {
    n = to_number(raw)       // n : Result[Number]
    return n + 1             // PARSE ERROR — Result와 Number를 더할 수 없음
}
```

컴파일되려면 내부 값을 명시적으로 꺼내야 합니다:

```ail
pure fn safe_parse(raw: Text, default: Number) -> Number {
    return unwrap_or(to_number(raw), default)
}
```

Python의 `int("42")`는 `int`를 리턴하거나 예외를 던집니다. 두
형태 모두 `int` 어노테이션 변수에 대입 가능해서 `try` 생략도
"문법적으로는" 유효한 Python입니다. 런타임에만 터집니다:

```python
def safe_parse(raw: str) -> int:
    return int(raw) + 1   # 완벽히 유효 — raw가 "abc"일 때만 터짐
```

**모델 크기로는 못 메우는 이유.** Sonnet 4.6 — 이 코퍼스에서
LLM 라우팅을 **100% 정확하게** 하는 프론티어 모델 — 조차 Python
코드에서는 실패 가능 연산의 70%에 에러 핸들링을 안 씁니다.
모델은 에러 핸들링의 존재를 *알지만* 매번 의무를 느끼지 않습니다.
AIL의 타입 시스템은 이 옵션성을 문법에서 제거합니다. 모델에
의존하지 않습니다.

전체 논증:
[`2026-04-20_claude_sonnet46_summary.md`](../benchmarks/2026-04-20_claude_sonnet46_summary.md).

---

## 2. 왜 AIL 정답률 70%, Python 48%인가

**관찰.** 같은 프롬프트, 같은 모델(`ail-coder:7b-v3`)에서 AIL로
작성된 프로그램은 70%, Python 프로그램은 48% 정답.

**메커니즘: "조용한 LLM 스킵"**

Python이 작성한 프로그램 중 15/50 (30%) 개가 판단 작업을 해결하는
코드라고 *선언*하고선 **LLM을 한 번도 안 부르고** 하드코딩된
키워드 매칭으로 대답을 찍습니다. AIL은 이게 불가능합니다 —
`intent`는 디스패치 선언이고, 런타임이 저자의 의도와 무관하게
모델 어댑터로 라우팅합니다.

**실제 사례 — B09 "수동태로 바꾸기":**

Python (같은 모델, LLM 호출 0회):
```python
def passive_voice(text):
    parts = text.split()
    subject, verb, object_ = parts[0], parts[1], parts[2]
    return f"{object_} was {verb} by {subject}"
```

입력 "The cat chased the mouse" → 출력 "chased was cat by The".
틀림 — 하드코딩된 룰이 "the"가 관사인 걸 모름.

AIL (같은 모델, LLM 호출 1회):
```ail
intent to_passive_voice(text: Text) -> Text {
    goal: sentence rewritten in passive voice
}
entry main(text: Text) { return to_passive_voice(text) }
```

출력 "The mouse was chased by the cat". 맞음 — `intent`가 실제
LLM 디스패치를 강제. 이 작업을 문자열 연산으로 속여 답하는 AIL
문법은 존재하지 않음.

**카테고리별 "조용한 LLM 스킵" 빈도:**

| 카테고리 | Python 스킵 | AIL 스킵 |
|---|---|---|
| A — 순수 계산 (n=15) | 해당 없음 | 해당 없음 |
| B — 순수 판단 (n=15) | 3/15 (20%) | 0/15 |
| C — 하이브리드 (n=20) | **12/20 (60%)** | 1/20 |

**하이브리드에서 Python이 무너집니다.** C 카테고리 작업의 60%에서
Python 저자는 계산처럼 보이고, 정상 실행되고, 쓰레기로 대답하는
코드를 씁니다. AIL의 `intent`/`pure fn` 구분은 문법적이라 요구되는
LLM 호출을 생략할 수 없습니다.

---

## 3. 왜 naive agent 대비 토큰 ~75% 절감인가

**관찰.** 50 task 전체:
- AIL: 총 37회 LLM 호출
- Python (같은 모델): 18회 (해야 할 15회를 조용히 스킵)
- Naive "뭐든 LLM" 에이전트: ~150회 (task당 평균 3회 추정)

**메커니즘.** `pure fn` / `intent` 분리가 비용 라우팅을 대신 해줌
— 계산은 로컬 실리콘, 판단은 LLM:

```ail
pure fn bmi(h_cm: Number, w_kg: Number) -> Number {      // LLM 0회
    return round(w_kg / pow(h_cm / 100, 2), 2)
}
intent assess_health(bmi: Number) -> Text {              // LLM 1회
    goal: health assessment
}
entry main(x: Text) {
    b = bmi(175, 70)
    return join([to_text(b), " ", assess_health(b)], "")
}
```

"모든 걸 프롬프트에 넣는" naive 에이전트는 이 형태에서 최소 3번
LLM을 호출합니다 — 스펙 파싱, 계산, 평가. AIL 런타임은 앞의 둘을
통째로 건너뜁니다.

**Python이 이걸 자동으로 못 매칭하는 이유.** Python은 언어 수준에서
"결정론적" vs "판단" 코드의 구분이 없어서, 둘 중 하나입니다:
- 저자가 매번 수동으로 판단하고, 벤치마크가 보여주듯 자주 틀림 —
  필요할 때 LLM 스킵, 또는 로컬 산술이면 되는데 LLM 호출.
- 에이전트 프레임워크(LangChain, AutoGPT)가 기본값으로 모든 걸
  LLM 경유 — 저자 버그를 피하려고 4배 비용을 지불.

AIL은 이 선택을 제거합니다. 문법이 라우팅합니다.

---

## 4. 왜 fine-tuning이 프롬프팅을 이기는가 (+ 왜 작은 tuned 모델이 Sonnet 4.6을 이기는가)

**관찰 (프롬프트 천장):**

| `qwen2.5-coder:14b`에서의 variant | Hybrid (C) parse |
|---|---|
| v1 기본 프롬프트 | 15% |
| v2: "`List[T]` 금지, `Array<T>` 금지" 명시 추가 | 15% |
| v3: 하이브리드 few-shot 예시 3개 추가 | 15% |

두 개의 직교하는 개입 — 부정 지시와 긍정 시연 — 각각 0건도 안
움직였습니다. 전체 데이터:
[`2026-04-20_prompt_ab_v3_analysis.md`](../benchmarks/2026-04-20_prompt_ab_v3_analysis.md).

**관찰 (tuning vs 스케일):**

| 모델 | AIL parse |
|---|---|
| `llama3.1:8b` (base) | 8% |
| `qwen2.5-coder:14b` (base) | 42% |
| `claude-sonnet-4-6` (프론티어 base) | 36% |
| `ail-coder:7b-v3` (fine-tune, 244 samples) | **78%** |

**메커니즘.** base 모델의 출력 분포는 훈련된 모든 토큰의
적분입니다. Qwen2.5-Coder 사전학습은 메가바이트~기가바이트 단위의
Python을 봤기 때문에, `fn` 키워드를 가진 어떤 언어로든 코드를
작성하라면 Python의 `List[T]` 타입 힌트, `x[0]` 서브스크립트
문법을 자연스럽게 꺼냅니다 — AIL 형태보다 확률 질량이 몇 배
차이나는 패턴들입니다.

프롬프트는 1-2 KB 토큰입니다. 분포를 *살짝 기울일* 수는 있지만
*뒤집지는* 못합니다. qwen14b에서 프롬프트 3라운드가 15%에서
정체된 이유입니다.

Fine-tuning은 분포를 직접 바꿉니다. 검증된 AIL 샘플 244개는
모델의 prior를 파서가 수용하는 형태 쪽으로 이동시킵니다. 효과는
더 큰 base 모델을 쓰는 것보다 훨씬 큽니다: `ail-coder-7b-v3`
(78%)가 Sonnet 4.6 (36%)을 AIL 작성에서 이기는 이유는 — 작은
모델은 AIL을 봤고, 프론티어 모델은 안 봤기 때문입니다.

**일반화 가능한 주장.** 좁은 DSL의 경우, DSL 분포로 fine-tune된
작은 모델이 프론티어 base 모델보다 더 잘 작성합니다. 도메인이
사전학습에 잘 대표된 경우엔 모델 스케일이 fine-tuning을 이기고,
그 반대 경우엔 역전됩니다.

---

## 5. 왜 하이브리드(C) 카테고리가 가장 크게 점프했나 (45% → 70%)

**관찰.** v2 → v3 변화:

| 카테고리 | v2 AIL parse | v3 AIL parse | Δ |
|---|---|---|---|
| A — pure fn | 53% | 73% | +20 pp |
| B — pure intent | 100% | 93% | −7 pp |
| C — hybrid | **45%** | **70%** | **+25 pp** |

C가 가장 약했고 *동시에* 가장 많이 얻었습니다. 세 개의 동시 수정이
각각 하이브리드 특유의 실패 클래스를 타겟팅:

1. **파서가 parametric 타입을 수용.** `List[Number]` 등은 스펙상
   유효(§2.3)였는데 파서가 브래킷을 조용히 버리고 있었음. 리스트
   타입 파라미터를 쓰는 하이브리드 프로그램이 이제 파싱됨. v2의
   7개 실패 해결.

2. **수학 빌트인 추가.** `round`, `sqrt`, `floor`, `ceil`, `pow`가
   trusted-pure. 하이브리드 BMI / 표준편차 / 복리 이자 프롬프트는
   모델이 자연스럽게 `round()`를 쓰는데 이제 `PurityError` 안 남.
   v2의 2개 실패 해결.

3. **하이브리드 학습 샘플 +14개** — 올바른 `pure fn`(계산) +
   `intent`(판단) 분해를 직접 보여줌. 이 카테고리의 분포를 직접
   학습시킴.

**왜 C만이고 A/B는 아닌가?**
- A는 base qwen14b에서 이미 85% (pure fn이 Python 형태와 가까움).
- B는 v2 fine-tune 후 100% 도달 (`intent` 선언은 AIL 고유라 v2
  학습 셋에 이미 잘 대표됨).
- C는 모델이 fn vs intent를 *선택*해야 하는 곳, Python 문법
  오염이 가장 잘 새어나올 수 있던 곳.

**B의 −7 pp는 노이즈**, 회귀가 아닙니다 — 샘플 하나가 런마다
뒤집힘 (goal 절의 구문 `goal: positive, negative, neutral`의
comma 문제). 학습 효과 아님.

---

## 6. 왜 AIL이 Python보다 task당 2.5배 느린가

**관찰.** task당 wall clock (v3 run):

| 카테고리 | AIL | Python |
|---|---|---|
| A (순수 계산) | 3.8 s | 1.1 s |
| B (intent) | 3.1 s | 2.2 s |
| C (하이브리드) | 6.8 s | 2.4 s |

**메커니즘.** 두 가지 누적 원인:

1. **Python이 LLM 호출을 스킵해서 런타임을 속입니다** (C에서
   12/20). 스킵되는 호출당 ~2초 절약. 이 스킵을 보정하면 C의
   Python 시간은 AIL과 비슷해집니다.

2. **AIL 런타임 오버헤드.** Reference Python 구현은 모든 값의
   provenance, 모든 호출의 trace, intent의 calibration 상태를
   추적합니다. Go 런타임은 이걸 추적 안 함. ~200ms/task 기준선
   위에서는 실제 비용이지만 지배적 요인은 아닙니다.

**언제 중요한가.** 배치 파이프라인, 야간 배치, 에이전트 워크로드
— 3초 추가는 노이즈. <1초 지연 요구의 인터랙티브 챗봇 — 튜닝
필요 (또는 Go 런타임으로 전환).

---

## 7. 왜 이 효과들이 복합적으로 쌓이는가 — 3개의 독립 메커니즘

헤드라인 숫자(정답률 70%, 에러 누락 0%, 토큰 75% 절감)는 단일
트릭에서 나오지 않습니다. 각각 다른 실패 모드를 해결하는 3개
층에서 나옵니다:

| 레이어 | 메커니즘 | 해결하는 갭 |
|---|---|---|
| **문법** | `Result` 타입, `pure fn`, `while` 부재 | 에러 핸들링 (44% → 0%), 무한 루프, 사이드이펙트 숨김 |
| **학습** | 검증된 244 샘플 QLoRA | Parse rate (42% base → 78%), fn/intent 라우팅 |
| **런타임** | `intent`가 어댑터 경유 디스패치 | 조용한 LLM 스킵 (60% → 5% on C) |

셋 중 어느 하나 빼면 주장이 무너집니다. 셋 다 유지해야 모든 모델
티어에서 숫자가 재현됩니다.

**디자인 명제에 대해 이게 말하는 것.** "Python 주변에 하네스를
쌓는" 방식(AGENTS.md, pre-commit, 커스텀 린터)은 셋 중 하나를
해결합니다. "안전한 패턴으로 Python 작성 모델을 fine-tune"하는
방식은 다른 하나를 해결합니다. AIL의 베팅은 이 셋을 **언어 자체에
통합하는 게** 외부에서 조립하는 것보다 싸고 견고하다는 것 — 정확히
벤치마크 숫자가 보여주는 바입니다.

---

## 임의의 주장 재현하기

이 문서의 모든 숫자는 [`../benchmarks/`](../benchmarks/) JSON
스냅샷 중 하나에서 나옵니다. 숫자를 찾았으면 추적할 수 있습니다:

```bash
# 예: "하이브리드의 60%에서 Python이 LLM 스킵" 검증
python3 -c "
import json
d = json.load(open('docs/benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json'))
cases = [c for c in d['cases'] if c['category']=='C' and c['python'].get('parsed')]
skips = [c for c in cases if (c['python'].get('llm_call_count') or 0)==0]
print(f'Python hybrid parsed={len(cases)}, silent-skipped={len(skips)}')
"
# Python hybrid parsed=14, silent-skipped=12
```

JSON들은 각 케이스별 `source` 필드로 저자가 생성한 실제 코드도
담고 있어서, 어떤 프롬프트에 대해서도 어떤 코드가 나왔는지
읽을 수 있습니다.
