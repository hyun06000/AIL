# AIL의 자기 수정 (`evolve`) 이해하기

**대상 독자:** AIL 참조 구현에서 `evolve` 블록이 실제로 어떻게 작동하는지, 그리고 왜 그렇게 설계되었는지 알고 싶은 사람.

**전제:** [README.ko.md](README.ko.md)를 먼저 읽으시거나 프로젝트의 일반적 철학을 알고 계시면 도움이 됩니다.

---

## 왜 자기 수정인가

한 번 작성된 intent는 그 자체로는 괜찮은 약속입니다. 그런데 세상은 변합니다:

- 사용자의 선호가 달라집니다.
- 뒤따라 붙은 서비스가 업데이트됩니다.
- 모델이 더 좋아지거나 더 나빠집니다.
- 입력 데이터의 분포가 흘러갑니다 (drift).

정적 intent는 두 갈래 중 하나로 귀결됩니다 — **우연히 계속 옳거나**, **조용히 망가지거나**. 어느 쪽도 바람직하지 않습니다.

그런데 "그럼 프로그램이 자기를 고치면 되잖아" 라는 답은 위험합니다. 왜냐하면:

- **무한정 자기를 고치는 프로그램** 은 신뢰할 수 없습니다.
- **추적 불가능한 변경** 은 사고 후 복구가 불가능합니다.
- **검증되지 않은 변경** 은 더 나쁘게 만들 수 있습니다.
- **되돌릴 수 없는 변경** 은 탈출구가 없습니다.

AIL의 `evolve`는 **이 네 가지를 모두 구조적으로 봉쇄**합니다. 자기 수정은 허용하되, 경계·검증·관찰 가능성·되돌림을 전부 언어 수준에서 필수로 만듭니다.

---

## 필수 요소 다섯 가지

`evolve` 블록은 다음 다섯 가지를 **반드시** 포함해야 합니다. 하나라도 빠지면 컴파일 에러입니다 (spec/04 §2).

| 필드 | 의미 |
|---|---|
| `metric` | 성공을 정의하는 관찰 가능한 수치 |
| `when` | 수정을 고려하는 조건 |
| **액션** (when 블록 내부) | 무엇을 바꿀 것인가 |
| `rollback_on` | 가장 최근 변경을 되돌리는 조건 |
| `history` | 몇 개의 이전 버전을 보관하는가 |

추가로 선택적:

| 필드 | 의미 |
|---|---|
| `bounded_by` | 액션이 넘을 수 없는 수치 경계 |
| `require review_by` | 사람의 승인이 필요한지 |

---

## 최소 예제

```ail
intent classify_sentiment(text: Text) -> Text {
    goal: sentiment_label
    constraints {
        output in ["positive", "negative", "mixed", "unclear"]
    }
}

evolve classify_sentiment {
    metric: user_feedback_score(sampled: 1.0)

    when user_feedback_score < 0.7 {
        retune confidence_threshold: within [0.5, 0.95]
        bounded_by {
            confidence_threshold: [0.4, 1.0]
        }
    }

    rollback_on: user_feedback_score < 0.3

    history: keep_last 10
}
```

읽는 법:

- 사용자 피드백 점수가 지표입니다. 호출마다 샘플링해서 롤링 윈도우에 쌓습니다.
- 윈도우 평균이 **0.7 미만**이면 수정을 고려합니다.
- 수정 액션은 `confidence_threshold`를 `[0.5, 0.95]` 범위의 중점으로 **재조정 (retune)**.
- 단, `bounded_by`에 의해 절대로 `[0.4, 1.0]`을 벗어나지 못합니다.
- 수정 후 피드백이 **0.3 미만**으로 떨어지면 즉시 이전 버전으로 되돌립니다.
- 지난 10개 버전까지 보관합니다.

---

## 실제로 작동하는 것 보기

`reference-impl/examples/evolve_retune_demo.py`를 실행하세요:

```bash
cd reference-impl
python examples/evolve_retune_demo.py
```

출력:

```
── PHASE 1 — healthy feedback: 10 calls with feedback score = 0.9
   -> active version: v0, parameters: (none)

── PHASE 2 — feedback drops: 15 calls with feedback score = 0.5
   -> active version: v1, parameters: {'confidence_threshold': 0.725}

── PHASE 3 — feedback collapses: 5 calls with feedback score = 0.1
   -> active version: v0, parameters: (none)

── event log ──
  [version_applied] {'version_id': 1, 'parameters': {'confidence_threshold': 0.725}, 'reason': 'metric user_feedback_score fell below threshold; retune to midpoint'}
  [rollback] {'from_version': 1, 'to_version': 0, 'trigger_value': 0.1, 'threshold': 0.3}
```

해석:

- **Phase 1** — 피드백이 건강(0.9)할 땐 진화가 일어나지 않습니다. 필요 없기 때문입니다.
- **Phase 2** — 피드백이 0.5로 떨어지자 15번의 호출 후 v1이 적용됩니다. threshold는 정확히 `[0.5, 0.95]`의 중점인 **0.725**.
- **Phase 3** — 그런데 피드백이 0.1로 더 떨어집니다. `rollback_on: score < 0.3`이 발동되어 즉시 v0으로 복귀합니다.

---

## MVP가 지원하는 것 vs 지원하지 않는 것

현재 참조 구현이 지원하는 것:

- ✅ `retune` 액션 (수치 파라미터를 선언된 범위의 중점으로 조정)
- ✅ `rewrite constraints` 액션 — 제약식의 수치 임계값을 일정량만큼 타이트하게 재작성
- ✅ 버전 체인 (단조 증가하는 version_id)
- ✅ `bounded_by`로 범위 위반 제안 거부
- ✅ `rollback_on` 트리거 시 원자적 되돌림
- ✅ `history: keep_last`에 따른 옛 버전 가지치기 (단, v0는 항상 보존)
- ✅ `require review_by: human` — `approve_review` 콜백으로 동기 검토
- ✅ 진화 이벤트를 전부 trace에 기록

### `rewrite constraints` 문법과 안전 속성

```ail
evolve classify {
    metric: score
    when score < 0.7 {
        rewrite constraints tighten_numeric_thresholds_by 0.05
    }
    rollback_on: score < 0.2
    history: keep_last 5
}
```

이 액션은 intent의 `constraints` 블록에 있는 모든 **수치 비교**를 delta 만큼 타이트하게 만듭니다:

- `fidelity > 0.7` → `fidelity > 0.75` (더 엄격한 하한)
- `latency < 2000` → `latency < 1999.95` (더 엄격한 상한)

**중요한 안전 속성:** `rewrite constraints`는 **항상 사람 검토를 거칩니다.** `require review_by: human`을 프로그램이 선언하지 않아도, 런타임이 강제합니다. 제약식을 바꾸는 건 수치가 작더라도 "프로그램의 규칙 자체"를 바꾸는 것이라, 재조정보다 훨씬 무거운 변경이기 때문입니다.

이건 `retune`과의 결정적 차이예요. `retune`은 조용히 적용될 수 있어요 (파라미터는 구현 디테일이니까). 하지만 `rewrite constraints`는 프로그램이 "뭘 지킬 것인가"를 바꾸는 것이라, 사람이 반드시 봐야 합니다.

아직 지원하지 않는 것 (spec/04 §4):

- ❌ `rewrite examples` — 예제 블록을 재작성
- ❌ `rewrite goal` — 목표 자체를 재작성 (사람 검토 필수)
- ❌ `promote strategy` — 실증적으로 우수한 전략을 선호로 고정
- ❌ `escalate` — 판단을 상위 권한에게 위임

아직 지원하지 않는 런타임 특성:

- ❌ 세션 간 영속성 (현재 진화 상태는 `Executor` 수명 동안만 유지됨)
- ❌ `bounded_by`의 최솟값 샘플 수 (MVP는 하드코딩된 10회)
- ❌ shadow 모드 (spec/04 §4.7에서 요구하는 병렬 관찰 기간)

---

## 설계상 주의사항

### 지표는 외부에서 주입됩니다

`evolve` 블록은 `metric: user_feedback_score`처럼 지표의 **이름**을 선언하지만, 그 값이 실제로 어디서 오는지는 런타임이 결정합니다. 참조 구현에서는 `metric_fn` 콜백이 이 역할을 합니다:

```python
def metric_fn(intent_name, value, confidence):
    # 예: 최근 사용자 피드백 시스템에서 점수를 가져옴
    return (feedback_score, rollback_signal)

executor = Executor(program, adapter, metric_fn=metric_fn)
```

콜백이 없으면 `confidence`가 기본 지표로 사용됩니다. 이는 "자신 있는 답이 많으면 잘 작동하는 중"이라는 합리적 기본값이지만, 실제 품질과 상관관계가 있는 외부 신호(A/B 테스트 결과, 사용자 별점, 다운스트림 성공률)가 있다면 반드시 `metric_fn`을 제공하세요.

### 최소 샘플 수 보호

MVP는 지표 평균이 임계값 아래로 떨어져도 **최소 10개의 샘플**이 쌓이기 전까지는 수정을 트리거하지 않습니다. 이것은 첫 한두 번의 나쁜 결과가 성급한 진화를 일으키지 않도록 하는 안전장치입니다. 이 값은 향후 `metric`의 옵션으로 노출될 예정입니다.

### 버전 v0는 항상 남습니다

`history: keep_last 5`라고 써도, 초기 버전 v0는 **항상** 보관됩니다. 이유는: 모든 변경이 너무 나빠서 역추적이 필요한 최악의 경우에 기준점이 필요하기 때문입니다. 롤백은 `parent_id` 체인을 따라가는데, 이 체인은 결국 v0까지 닿아야 합니다.

### 윈도우는 버전이 바뀔 때 비워집니다

새로운 버전이 적용되면 지표 윈도우는 리셋됩니다. 이유는: 이전 버전의 평가는 새 버전의 성능과 무관하기 때문입니다. 새 버전이 충분히 관찰될 때까지는 다음 수정도 롤백도 트리거되지 않습니다.

---

## 관련 문서

- [spec/04-evolution.md](../../spec/04-evolution.md) — 정식 명세 (영어)
- `reference-impl/ail_mvp/runtime/evolution.py` — 구현 코드
- `reference-impl/tests/test_evolution.py` — 단독 테스트 9개
- `reference-impl/tests/test_executor.py` — 통합 테스트 (진화 부분)
- [../open-questions.md](../open-questions.md) — 남은 설계 질문들 (영어)

---

## 요약

AIL의 `evolve`는 **자기 수정을 허용하되, 그 자유에 대가를 치르게 합니다**. 모든 변경은:

- **지표로 정당화**되어야 하고,
- **선언된 경계**를 넘지 못하며,
- **되돌릴 수 있는 조건**과 함께 오고,
- **기록**에 남습니다.

이게 바로 "AI가 쓰는 코드"가 실세계에서 신뢰받기 위한 최소 요건이라고 저희는 생각합니다.
