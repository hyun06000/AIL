# 5-Way Same-Size Benchmark — Analysis
**날짜:** 2026-04-21  
**모델 크기:** 7B (all conditions)  
**총 케이스:** 50 prompts × 4 AIL conditions

---

## 실험 설계

| 조건 | AIL 모델 | AIL 프롬프트 | Python 모델 | Python baseline |
|---|---|---|---|---|
| C1 (base/nofs) | qwen2.5-coder:7b-base | default | qwen7b-base | ✅ 공정 |
| C2 (base/tut)  | qwen2.5-coder:7b-base | tutorial | qwen7b-base | ✅ 공정 |
| C3 (Py only)   | — | — | qwen7b-base | = C1 Python side |
| C4 (ft/nofs)   | ail-coder:7b-v3 | default | ail-coder:7b-v3 | ⚠️ degraded |
| C5 (ft/tut)    | ail-coder:7b-v3 | tutorial | ail-coder:7b-v3 | ⚠️ degraded |

> **C4/C5 Python 주의**: GPU가 하나라 fine-tune 서버에서 Python도 작성함. fine-tune 모델은 Python 생성 능력이 저하(parse 46% vs base 66%). C4/C5 AIL 성능의 공정한 Python 비교선은 **C1 Python side(56% answer)** 를 사용한다.

---

## 종합 결과

### A. 정답률 (answer_ok_rate)

| 조건 | AIL | Python (동일 모델) | Python baseline(C3) |
|---|---|---|---|
| C1 base/nofs | 42% | 56% | 56% |
| C2 base/tut  | 48% | 56% | 56% |
| C4 ft/nofs   | 48% | 38%⚠️ | 56% |
| C5 ft/tut    | **52%** | 38%⚠️ | 56% |

**파인튜닝 + tutorial 조합(C5)이 최고**: 42% → 52% (+10pp)  
**공정 비교**: 최고 AIL(C5) 52% vs Python qwen7b-base 56% = **−4pp**

---

### B. 카테고리별 정답률

#### Category A — 순수 계산 (fn만, 15문제)

```
xychart-beta
  title "Cat A (순수 계산) 정답률"
  x-axis ["C1 base/nofs", "C2 base/tut", "C4 ft/nofs", "C5 ft/tut", "Py(C3)"]
  y-axis "정답률 %" 0 --> 100
  bar [47, 33, 40, 47, 73]
```

- Python qwen7b-base **73%** vs 최고 AIL 47% — **Py 우세 (+26pp)**
- tutorial이 오히려 Cat A AIL을 낮춤 (C1 47%→C2 33%): tutorial이 intent 사용을 유도해 fn 문제에서 역효과
- fine-tune이 Cat A에서 큰 차이 없음

#### Category B — 순수 판단 (intent만, 15문제)

```
xychart-beta
  title "Cat B (순수 판단) 정답률"
  x-axis ["C1 base/nofs", "C2 base/tut", "C4 ft/nofs", "C5 ft/tut", "Py(C3)"]
  y-axis "정답률 %" 0 --> 100
  bar [53, 87, 60, 80, 7]
```

- **AIL 압도적 우세**: 최고 AIL C2 87% vs Python 7%
- Python 7%의 이유: base 모델은 intent 없이 Python 함수만 작성 → LLM 호출 없이 빈 응답
- tutorial 효과 극적: base C1 53% → C2 87% (+34pp)
- fine-tune 효과: C1 53% → C4 60% (+7pp)

#### Category C — 하이브리드 (fn+intent, 20문제)

```
xychart-beta
  title "Cat C (하이브리드) 정답률"
  x-axis ["C1 base/nofs", "C2 base/tut", "C4 ft/nofs", "C5 ft/tut", "Py(C3)"]
  y-axis "정답률 %" 0 --> 100
  bar [30, 30, 45, 35, 80]
```

- Python qwen7b-base **80%** vs 최고 AIL C4 45% — Cat C가 현재 AIL 최대 약점
- **fine-tune이 Cat C에서 효과 있음**: C1 30% → C4 45% (+15pp)
- tutorial은 Cat C에서 neutral~역효과

---

### C. parse 성공률

| 조건 | AIL parse | Py parse |
|---|---|---|
| C1 base/nofs | 54% | 66% |
| C2 base/tut  | **60%** | 66% |
| C4 ft/nofs   | 58% | 46%⚠️ |
| C5 ft/tut    | 56% | 46%⚠️ |

- tutorial이 AIL parse에 효과 있음 (C1 54% → C2 60%, +6pp)
- fine-tune 모델의 Python parse 저하(66%→46%)는 fine-tune이 AIL 문법에 특화된 결과

---

### D. fn/intent 정확도

| 조건 | AIL fnint | Py fnint |
|---|---|---|
| C1 base/nofs | 48% | 72% |
| C2 base/tut  | 52% | 72% |
| C4 ft/nofs   | **54%** | 80% |
| C5 ft/tut    | **54%** | 80% |

- fine-tune이 fn/intent 결정에서 일관된 효과 (+6pp)
- Python이 fn/intent 정확도에서 여전히 앞섬: qwen7b-base가 기본적으로 Python에서 더 잘 훈련됨

---

### E. 하네스 엔지니어링 (언어 속성)

| 지표 | AIL (전 조건) | Python qwen7b-base |
|---|---|---|
| Error handling miss | **0%** | **40–50%** |
| 무한루프 발생 | **0%** | 0% (이번 run에서) |
| 구조적 안전 보장 | **100% (문법)** | 0% (외부 도구 필요) |

- 이 수치는 모델/프롬프트와 무관하게 **언어 설계에서 나오는 것** — 조건이 바뀌어도 불변
- Python 40-50% error handling miss: failable op에서 try/except 생략

---

### F. 토큰 & 시간 효율

| 조건 | AIL 총토큰 | Py 총토큰 | AIL 벽시계(ms) | Py 벽시계(ms) |
|---|---|---|---|---|
| C1 | 4,261 | 327 | 14,092 | 1,633 |
| C2 | 4,537 | 327 | 12,891 | 1,594 |
| C4 | 4,126 | 334 | 11,501 | 1,810 |
| C5 | 4,398 | 334 | 13,629 | 1,775 |

- AIL은 Python 대비 **~13× 토큰** 소모 — authoring 프롬프트(reference card 포함)가 대부분
- AIL 벽시계 **~7-8× 느림** — authoring LLM call이 병목
- fine-tune이 벽시계를 개선: C1 14,092ms → C4 11,501ms (−18%)

---

## 핵심 발견 요약

### AIL이 이기는 곳

| 항목 | AIL | Python |
|---|---|---|
| **Cat B (pure intent)** | **87%** (C2) | 7% |
| **Error handling** | **0% miss** | 40-50% miss |
| **구조적 안전** | **100%** (문법 보장) | 0% |

Cat B에서 AIL 87% vs Python 7%는 **12× 격차**. Python base 모델은 `intent`를 선언할 방법이 없어 LLM 호출 자체를 건너뜀.

### Python이 이기는 곳

| 항목 | Python | 최고 AIL |
|---|---|---|
| **Cat A (순수 계산)** | 73% | 47% |
| **Cat C (하이브리드)** | 80% | 45% |
| **전체 정답률** | 56% | 52% |
| **토큰 효율** | 327 | 4,261 |
| **속도** | 1,633ms | 11,501ms |

### 개선 궤적

| 조건 | AIL 정답률 | vs Py(C3) |
|---|---|---|
| C1 base/nofs (시작점) | 42% | −14pp |
| C2 base/tut | 48% | −8pp |
| C4 ft/nofs | 48% | −8pp |
| **C5 ft/tut (최고)** | **52%** | **−4pp** |

fine-tune + tutorial 조합으로 격차를 −14pp → −4pp로 좁힘. **Cat B에서는 이미 AIL이 역전.**

---

## 다음 우선순위

### 1. Cat A / Cat C 개선이 핵심
- Cat A (fn): AIL이 47%에 머무는 이유 → fn 내 반복/산술 생성 실패 케이스 분석 필요
- Cat C (hybrid): 30-45% → 파이썬은 hybrid 질문을 단순 fn으로 풀어버림(80%)이 오히려 이기는 구조. AIL의 fn+intent 인터리빙 few-shot 예제 추가 고려

### 2. 토큰 효율 개선
- authoring 프롬프트에서 reference card 압축 또는 선택적 로딩 검토
- 현재 ~4,000 prompt tokens의 대부분이 reference card

### 3. v4 fine-tune 시 Cat C 샘플 확대
- HANDOFF.md 조건: Cat C 실패 케이스 ≥20개 추가 시 재훈련 검토

---

*Generated from:*  
- `2026-04-21_5way_cond1_base_nofewshot.json`  
- `2026-04-21_5way_cond2_base_tutorial.json`  
- `2026-04-21_5way_cond4_finetuned_nofewshot.json`  
- `2026-04-21_5way_cond5_finetuned_tutorial.json`
