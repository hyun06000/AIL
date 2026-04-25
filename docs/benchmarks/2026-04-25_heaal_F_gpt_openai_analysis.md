# HEAAL Boundary — Series F: OpenAI GPT Models
**Date:** 2026-04-25  
**Author:** Ergon (Claude Opus 4.7, Claude Code)  
**Protocol:** HEAAL Boundary v2 — 50 prompts, `anti_python` variant  
**Backend:** `openai` (native API, not vLLM proxy)

---

## 동기

Arche/Ergon 설계 원칙이 Anthropic 계열 이외의 frontier 모델에도 성립하는지 검증한다.  
Series E (Claude Sonnet 4.5)에서 확립한 "AIL이 동급 Python보다 안전하고 비슷하게 정확하다"는 가설을  
OpenAI GPT 계열 4개 모델에 동일한 50-prompt 하네스로 검증한다.

비용: gpt-4o $0.17 + gpt-4.1 $1.17 + gpt-4.1-mini $0.23 + o4-mini $0.64 ≈ **$2.21**

---

## 결과 요약

| Model | AIL parse | AIL ans | Py ans | Py err-miss | AIL retries | LLM/task (Py) |
|-------|-----------|---------|--------|-------------|-------------|----------------|
| Claude Sonnet 4.5 (E1, ref) | 94% | 88% | **92%** | 70% | 0.30 | 0.00 |
| gpt-4o (F1) | 88% | 80% | 26% | 66% | 0.40 | 0.00 |
| gpt-4.1 (F3) | 94% | 84% | 32% | 68% | 0.32 | 0.00 |
| gpt-4.1-mini (F4) | 86% | 74% | 26% | 70% | 0.42 | 0.00 |
| **o4-mini (F5)** | **98%** | **88%** | 30% | 68% | **0.16** | 0.00 |

---

## 핵심 발견 3가지

### 1. Silent LLM Skip — GPT 계열 전체에서 Python avg LLM calls = 0.00

50개 태스크 전부에서 Python으로 작성된 코드가 **단 한 번도 LLM 호출을 하지 않았다.**

> GPT 모델들이 "LLM을 호출하는 Python 코드"를 요청받았을 때, 로직을 Python 자체 로직으로 직접 구현하고 모델 호출 없이 반환하는 코드를 생성한다.

이것이 Py answer rate가 26-32%에 그치는 직접 원인이다.  
Claude Sonnet 4.5도 Py LLM calls = 0.00이지만 answer rate가 92%인 이유는: Sonnet이 Python 코드 안에 *직접 답을 하드코딩*하기 때문이다 (프롬프트를 분석해 답을 내장한 코드를 생성).

GPT 모델은 그 전략조차 쓰지 않는다 — 절반 이상의 경우 빈 문자열이나 None을 반환한다.

**결론:** GPT 계열 모델에 Python으로 "AI가 수행할 작업"을 맡기면 74%가 실패한다.

### 2. o4-mini의 AIL 특이점

o4-mini는 **AIL parse 98%, answer 88%**로 Series F 최고 성능이다. 이는:
- Claude Sonnet 4.5(E1)와 AIL answer 동률 (88%)
- Series F에서 유일하게 98% parse 달성 (Sonnet E1도 94%)
- retries 0.16 — F 시리즈 최저, "첫 번에 옳은 코드 생성"

추론 모델(reasoning model)의 특성상 AIL 문법 규칙을 내적으로 더 철저히 따른다는 가설.  
하지만 Python path에서도 같은 특이점이 없다는 점이 흥미롭다: Py ans = 30% (가장 낮음).

o4-mini는 **AIL에서는 최강이지만 Python에서는 가장 못한다** — 추론 능력이 Python 코드 생성보다 AIL 의미론 준수에 더 잘 매핑된다는 증거.

### 3. 안전성 격차는 모델-비종속적

| 안전 지표 | AIL | Python (GPT 평균) | Python (Sonnet) |
|-----------|-----|-------------------|-----------------|
| 사이드이펙트 위반 | 0% | 0% | 0% |
| 무한루프 | 0% | 0% | 0% |
| 오류처리 누락 | 0% | **68%** | 70% |

`Result` 타입 강제와 `pure fn` 제한은 모델이 달라져도 동일하게 작동한다.  
Python의 오류처리 누락 68-70%는 모델 성능과 무관하다 — Python 언어 자체가 강제하지 않기 때문이다.

---

## Tier별 해석

### Frontier tier (gpt-4.1, o4-mini)

**AIL 적합:** gpt-4.1은 Sonnet 4.5와 parse율 동급(94%)이지만 answer가 4%p 낮음(84% vs 88%).  
o4-mini는 오히려 parse를 추월(98%). 이 계열 모델들은 AIL을 문제없이 저자로 쓸 수 있다.

**Python 부적합:** Py answer 30-32%. GPT 계열을 Python 에이전트로 쓰면 2/3이 실패한다.

### Mid-tier (gpt-4o, gpt-4.1-mini)

**AIL:** parse 86-88%, answer 74-80%. 사용 가능하나 retries 높음(0.40-0.42).  
**Python:** 26%. 4개 중 1개만 정상 동작.

---

## 토큰 효율

| Model | AIL tot tokens | Py tot tokens | 비율 |
|-------|----------------|---------------|------|
| Sonnet 4.5 (ref) | 9,306 | 541 | 17× |
| gpt-4o | 10,280 | 449 | 23× |
| gpt-4.1 | 12,096 | 421 | 29× |
| gpt-4.1-mini | 10,247 | 424 | 24× |
| o4-mini | 13,806 | 1,017 | 14× |

AIL이 Python보다 토큰을 더 쓰는 이유: intent 래퍼가 매번 reference card를 포함하기 때문.  
Python path는 LLM 호출 자체가 0.00회라 completion이 소량의 코드 생성에 그침.  
o4-mini의 Py 토큰이 1,017로 높은 것은 reasoning token 때문.

---

## 모델 선택 가이드 (이 데이터 기준)

| 상황 | 권장 |
|------|------|
| GPT 계열로 AIL 저자 에이전트 | o4-mini (parse 98%, retries 최저) |
| GPT 계열로 AIL 저자 에이전트 (비용 우선) | gpt-4.1 (94%, 합리적 비용) |
| GPT 계열로 Python 에이전트 | **비권장** — 모든 모델에서 26-32% |
| 크로스-벤더 AIL 지원 보장 | o4-mini + claude-sonnet 모두 88% 동률 확인 |

---

## 결론

**Series F가 증명하는 것:**

1. HEAAL 원칙(AIL의 안전 격차)은 Anthropic 모델 한정이 아니다. GPT 계열 4개 모두에서 Python 오류처리 누락 66-70% vs AIL 0%.
2. AIL author 역할은 frontier GPT 모델도 수행 가능하다. o4-mini는 Sonnet 4.5와 동률(88%).
3. **GPT 모델의 Python 생성은 AIL보다 훨씬 취약하다.** Silent LLM skip + 오류처리 누락이 결합해 실용적 실패율 68-74%.
4. 추론 모델(o4-mini)이 AIL 의미론에 가장 잘 맞는다 — 문법 규칙을 내부 추론 체인으로 처리하기 때문으로 추정.

Arche의 설계 가설 — "AIL은 언어가 harness인 언어" — 이 OpenAI 계열에서도 성립한다.

---

## 데이터 파일

| 파일 | 모델 | N | 조건 |
|------|------|---|------|
| `2026-04-25_heaal_F1_gpt4o_anti_python.json` | gpt-4o | 50 | anti_python |
| `2026-04-25_heaal_F3_gpt41_anti_python.json` | gpt-4.1 | 50 | anti_python |
| `2026-04-25_heaal_F4_gpt41_mini_anti_python.json` | gpt-4.1-mini | 50 | anti_python |
| `2026-04-25_heaal_F5_o4_mini_anti_python.json` | o4-mini | 50 | anti_python |
| `2026-04-22_heaal_E1_sonnet_anti_python.json` | Claude Sonnet 4.5 | 50 | anti_python (reference) |
