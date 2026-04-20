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

여기서 "silent skip" 의 정의: Python 프로그램이 *파싱 성공* 하고 실행 완료되어 답을 반환했지만, 소스에 LLM 호출 시도 자체가 없음 (`uses_llm=False`), ground truth 가 모델 판단을 요구하는 과제에서. AIL 은 silent skip 할 수 없습니다 — `intent` 는 디스패치 선언이고, 런타임은 선언된 모든 intent 를 모델 어댑터로 라우팅하며, "선언하고 호출 안 하기" 를 위한 AIL 문법은 존재하지 않습니다.

**실제 사례 — B09 "수동태로 바꾸기":**

Python (같은 모델, LLM 호출 0 회):

```python
def passive_voice(text):
    parts = text.split()
    subject, verb, object_ = parts[0], parts[1], parts[2]
    return f"{object_} was {verb} by {subject}"
```

입력 "The cat chased the mouse" → 출력 "chased was cat by The". 틀림 — 하드코딩된 룰이 "the" 가 관사인 걸 모름. LLM 은 한 번도 안 불렸습니다.

AIL (같은 모델, LLM 호출 1 회):

```ail
intent to_passive_voice(text: Text) -> Text {
    goal: sentence rewritten in passive voice
}
entry main(text: Text) { return to_passive_voice(text) }
```

출력: "The mouse was chased by the cat". 맞음 — `intent` 선언이 실제 LLM 디스패치를 강제.

**카테고리별 silent skip 빈도** (`ail-coder:7b-v3`, 파싱 성공한 프로그램 중):

| 카테고리 | Python silent skip | AIL silent skip |
|---|---|---|
| A — 순수 계산 (n=15) | 해당 없음 (LLM 불필요) | 해당 없음 |
| B — 순수 판단 (15 중 4 파싱) | 3 | 0 |
| C — 하이브리드 (20 중 14 파싱) | **9** | 1 |

즉 파싱된 18 개 Python 판단-과제 프로그램 중 12 개 (67%) 가 LLM 을 부르는 대신 판단 단계를 하드코딩했습니다. LLM 호출을 실제로 시도한 나머지는 대체로 정답을 얻었습니다 — silent-skip 패턴이 이 벤치마크에서 Python 오답의 대부분을 설명하지만 전부는 아닙니다 (parse 실패와 exec 오류가 나머지를 설명).

명시해둘 것: Python 의 이 행동은 **모델 의존적** 입니다. 같은 코퍼스에 대해 Claude Sonnet 4.6 에서는 하이브리드 20 개 중 1 개만 silent skip. silent-skip 패턴은 중간 티어 모델에서 심각하고 프론티어에선 거의 사라지지만, 에러 핸들링 누락 (§1) 은 Sonnet 에서도 70% 로 유지됩니다.

---

## 3. AIL 의 LLM 호출 수는 실제로 어디에 있나

**관찰.** `ail-coder:7b-v3` 에서 50 프롬프트 벤치마크 전체:

- AIL: 총 37 회 LLM 호출
- Python, 같은 모델: 총 18 회 (하지만 파싱된 판단 과제에서 12 건을 silent-skip)

**메커니즘.** `pure fn` / `intent` 분리가 비용 라우팅을 대신해줌 — 계산은 로컬 실리콘, 판단은 LLM:

```ail
pure fn bmi(h_cm: Number, w_kg: Number) -> Number {      // LLM 0 회 — 로컬 실행
    return round(w_kg / pow(h_cm / 100, 2), 2)
}
intent assess_health(bmi: Number) -> Text {              // entry 가 부를 때 LLM 1 회
    goal: health assessment
}
entry main(x: Text) {
    b = bmi(175, 70)
    return join([to_text(b), " ", assess_health(b)], "")
}
```

**비교를 어떻게 생각할 것인가.** 이 벤치마크에서 AIL 은 Python baseline 보다 LLM 을 *더* 씁니다 (37 vs 18) — 하지만 Python 이 필요한 호출을 silent-skip 했고 그 결과 정답률이 26% 낮기 때문. 적절한 질문은 "Python 과 AIL 중 누가 토큰을 덜 쓰나?" 가 아니라 **"정답 하나당 비용은 얼마냐?"** 입니다.

사람이 라우팅을 신중히 하는 수작업 Python 파이프라인 대비: AIL 은 대략 비슷한 호출 수를 씁니다 — 절감 없음. 모든 서브태스크에 LLM 을 거는 에이전트 프레임워크 (흔한 naive 패턴) 대비: AIL 이 의미 있게 적게 씁니다 — 라우팅이 모델의 런타임 선택이 아니라 구조적이기 때문. 정확한 비율은 에이전트 프레임워크와 과제 모양에 의존하며 벤치마크는 이를 직접 측정하지 않으므로, 특정 "N× 절감" 수치는 데이터가 아닌 추정일 것입니다.

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

## 6. 왜 AIL 이 task 당 더 느린가

**관찰.** task 당 wall clock (v3 run):

| 카테고리 | AIL | Python |
|---|---|---|
| A (순수 계산) | 3.8 s | 1.1 s |
| B (intent) | 3.1 s | 2.2 s |
| C (하이브리드) | 6.8 s | 2.4 s |

**메커니즘 — 두 가지 누적 원인:**

1. **Python 이 빠른 건 일을 덜 하기 때문이기도 합니다.** C 카테고리 과제에서, 파싱된 Python 프로그램 14 개 중 9 개는 LLM 호출이 아예 없었습니다 — 그래서 LLM latency (이 벤치마크의 로컬 Ollama 서버에서 보통 호출당 1–3 초) 를 완전히 피했습니다. 이걸 보정하면 Python 의 C wall-clock 은 AIL 쪽으로 올라옵니다.
2. **AIL 런타임 오버헤드.** Reference Python 구현은 값마다 provenance, 호출마다 trace 엔트리, intent 마다 calibration 상태를 추적합니다. 단순 executor 위에 얹힌 실제 비용입니다. 측정 가능하지만 보통 task 당 수십 ms 단위 — 초 단위 아님. LLM 호출 latency 가 지배적입니다.

**언제 중요한가.** 배치 파이프라인, 야간 배치, 에이전트 워크로드 — 몇 초 추가는 노이즈. 서브초 응답이 필요한 인터랙티브 앱 — Go 런타임 (provenance/calibration 을 추적하지 않는) + 더 빠른 모델이 필요.

---

## 7. 왜 이 효과들이 복합적으로 쌓이는가 — 3 개의 독립 메커니즘

헤드라인 숫자 — **같은 모델에서 AIL 정답률 70% vs Python 48%**, **모든 모델 티어에서 AIL 에러 핸들링 누락 0% vs Python 42–86%**, **AIL 작성에서 프론티어 base 모델을 이기는 작은 fine-tuned 모델의 parse 78%** — 는 단일 트릭에서 나오지 않습니다. 각각 다른 실패 모드를 해결하는 3 개의 독립 레이어에서 나옵니다:

| 레이어 | 메커니즘 | 해결하는 갭 (`ail-coder:7b-v3` 실측) |
|---|---|---|
| **문법** | `Result` 타입, `pure fn`, `while` 부재 | 에러 핸들링 누락 0% (같은 모델 Python 44%, llama8b 에선 86% 까지) |
| **학습** | 검증된 244 샘플 QLoRA | Parse rate 가 qwen14b base 42% → fine-tuned 7B 78% |
| **런타임** | `intent` 선언이 모델 어댑터로 반드시 디스패치 | 하이브리드에서 silent LLM skip: AIL 1/20, Python 9/20 |

한 레이어를 빼면 나머지 둘만으로는 주장을 지탱하지 못합니다:

- 문법만 (fine-tune 없이) 쓰면 base 모델에서 AIL parse 36–42% — harness 는 살지만 authoring 신뢰도는 죽습니다.
- 학습만 (`Result` 없는 언어에) 있다면 에러 핸들링 0% 숫자는 나오지 않았을 겁니다; fine-tune 은 에러 핸들링을 가르치지 않고, 문법이 강제합니다.
- 런타임만 (함수 호출을 가로채는 라이브러리) 으로는 저자가 **intent 자체를 선언하지 않는 것** 을 막을 수 없습니다 — "선언하고 건너뛰기" 를 표현 불가능하게 만들려면 문법이 필요합니다.

3 레이어 스택이 주장입니다. 숫자가 증거입니다.

---

## 임의의 주장 재현하기

이 문서의 모든 숫자는 [`../benchmarks/`](../benchmarks/) JSON 스냅샷 중 하나에서 나옵니다. 숫자를 찾았으면 추적할 수 있습니다:

```bash
# 예: "하이브리드의 9/14 에서 Python 이 LLM 조용한 스킵" 검증
python3 -c "
import json
d = json.load(open('docs/benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json'))
cases = [c for c in d['cases'] if c['category']=='C' and c['python'].get('parsed')]
# Silent skip: 소스에 LLM 호출 시도가 없음 (uses_llm=False)
silent = [c for c in cases if not c['python'].get('uses_llm')]
print(f'Python hybrid parsed={len(cases)}, silent-skipped={len(silent)}')
"
# Python hybrid parsed=14, silent-skipped=9
```

참고: 대안으로 `uses_llm == False` 대신 `llm_call_count == 0` 을 써서 세는 방법이 있습니다. 둘은 갈릴 수 있는데 — 프로그램이 실제 LLM 호출 시도를 포함하지만 런타임에 발사되지 않는 경우 (잘못된 엔드포인트, timeout, 도달 안 되는 코드 경로) 때문. `uses_llm=False` 가 더 엄격한 지표 ("코드에 LLM 호출 자체가 없다") 이고 이 문서에서 쓰는 것입니다.

JSON 들은 각 케이스별 `source` 필드로 저자가 생성한 실제 코드도 담고 있어서, 어떤 프롬프트에 대해서도 어떤 코드가 나왔는지 읽을 수 있습니다.
