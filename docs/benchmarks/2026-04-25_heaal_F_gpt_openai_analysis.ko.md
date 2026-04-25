# HEAAL 경계 측정 — Series F: OpenAI GPT 모델

**날짜:** 2026-04-25  
**작성:** Ergon (Claude Opus 4.7, Claude Code)  
**프로토콜:** HEAAL Boundary v2 — 50 프롬프트, `anti_python` 변형  
**백엔드:** `openai` (OpenAI 네이티브 API)  
**총 비용:** 약 $2.21 (gpt-4o $0.17 + gpt-4.1 $1.17 + gpt-4.1-mini $0.23 + o4-mini $0.64)

---

## 동기

Series E(Claude Sonnet 4.5)에서 HEAAL 핵심 가설을 확립했다: *AIL은 Python과 정확도가 동급이지만 문법으로 더 안전하다.* Series F는 동일한 50-프롬프트 하네스를 OpenAI GPT 계열 4개 모델에 적용해 이 가설이 Anthropic 이외 벤더에도 성립하는지 검증한다.

---

## 결과 요약

| 모델 | AIL 파싱 | AIL 정답 | Py 정답 | Py 오류처리 누락 | AIL 재시도 | Py LLM/태스크 |
|------|---------|---------|--------|--------------|-----------|-------------|
| Claude Sonnet 4.5 (E1, 기준) | 94% | 88% | **92%** | 70% | 0.30 | 0.00 |
| gpt-4o (F1) | 88% | 80% | 26% | 66% | 0.40 | 0.00 |
| gpt-4.1 (F3) | 94% | 84% | 32% | 68% | 0.32 | 0.00 |
| gpt-4.1-mini (F4) | 86% | 74% | 26% | 70% | 0.42 | 0.00 |
| **o4-mini (F5)** | **98%** | **88%** | 30% | 68% | **0.16** | 0.00 |

---

## 핵심 발견 3가지

### 1. Silent LLM Skip — GPT 계열 전체에서 Python avg LLM calls = 0.00

50개 태스크 전부에서 Python 코드가 **단 한 번도 LLM 호출을 하지 않았다.**

GPT 모델들은 "LLM 판단이 필요한 태스크를 수행하는 Python 코드"를 요청받았을 때, 하드코딩된 규칙이나 단순 문자열 처리로 응답하거나 빈 결과를 반환하는 코드를 작성한다. LLM 자체를 호출하지 않는다.

Claude Sonnet 4.5가 Python 정답률 92%를 달성하는 방식과 비교하면: Sonnet은 Python 코드 안에 *답을 내장*하는 전략을 쓴다(in-weights 지식으로 답을 알고 있으므로 그걸 코드에 박는다). GPT 모델은 이 전략조차 일관되게 적용하지 않는다 — 68% 이상의 케이스에서 빈 결과나 틀린 답을 낸다.

**결론:** GPT 계열 모델을 Python 에이전트로 쓰면 LLM 판단 태스크의 ~70%가 실패한다. AIL은 이 실패 클래스를 구조적으로 방지한다.

### 2. o4-mini의 AIL 특이점

o4-mini는 **AIL 파싱 98%, 정답 88%**로 Series F 최고 성능이다.
- Claude Sonnet 4.5와 AIL 정답률 동률 (88%)
- 전체 테스트 모델 중 유일하게 98% 파싱 달성 (Sonnet E1도 94%)
- 재시도 0.16 — F 시리즈 최저. 첫 시도에 올바른 AIL 코드를 생성하는 비율이 가장 높다

반면 Python 정답률은 30%로 Series F 최저다. 추론 모델의 내부 체인은 AIL의 선언적 문법 제약에 잘 매핑되지만, Python 코드 생성을 통한 LLM 판단 태스크에는 적용되지 않는다.

**o4-mini는 AIL에서 최강이지만 Python에서는 가장 취약하다** — 추론 능력이 Python 코드 생성보다 AIL 의미론 준수에 더 잘 맞는다는 증거.

### 3. 안전성 격차는 모델 종류에 무관하다

| 안전 지표 | AIL | GPT 평균 (Python) | Sonnet (Python) |
|-----------|-----|------------------|-----------------|
| 사이드이펙트 위반 | 0% | 0% | 0% |
| 무한루프 | 0% | 0% | 0% |
| 오류처리 누락 | **0%** | **68%** | 70% |

오류처리 누락 66~70%는 모델 성능과 무관하다. Python 언어 자체가 강제하지 않기 때문이다. AIL의 `Result` 타입은 실패 가능한 연산에 대한 명시적 처리를 문법으로 강제한다.

---

## 토큰 효율

| 모델 | AIL 총 토큰 | Py 총 토큰 | 비율 |
|------|------------|----------|------|
| Sonnet 4.5 (기준) | 9,306 | 541 | 17× |
| gpt-4o | 10,280 | 449 | 23× |
| gpt-4.1 | 12,096 | 421 | 29× |
| gpt-4.1-mini | 10,247 | 424 | 24× |
| o4-mini | 13,806 | 1,017 | 14× |

AIL이 더 많은 토큰을 사용하는 이유: 인텐트 래퍼가 매 호출마다 reference card를 포함하기 때문이다. Python 토큰 수가 낮은 이유: LLM 호출이 0.00회라 판단 단계에 completion이 필요 없다. o4-mini의 Python 토큰이 높은 것은 reasoning token 때문이다.

---

## Tier별 해석

### Frontier tier (gpt-4.1, o4-mini)

**AIL 저자로 적합:** gpt-4.1은 Sonnet 4.5와 파싱률 동급(94%). o4-mini는 오히려 98%로 초과한다. 이 계열 모델들은 AIL 저자 에이전트로 실용적으로 사용할 수 있다.

**Python 에이전트로 부적합:** Py 정답 30~32%. 3개 중 2개가 실패한다.

### Mid-tier (gpt-4o, gpt-4.1-mini)

**AIL:** 파싱 86~88%, 정답 74~80%. 사용 가능하나 재시도가 높다(0.40~0.42).  
**Python:** 26%. 4개 중 1개만 정상 동작한다.

---

## 결론

1. **HEAAL 안전 특성은 Anthropic 모델 한정이 아니다.** Python 오류처리 누락 66~70%는 GPT 계열 4개 모델 전체에서 일관된다 — Sonnet과 동일. 이것은 언어 수준의 특성이다.
2. **Frontier GPT 모델은 AIL을 저자할 수 있다.** o4-mini는 Sonnet 4.5와 정답률 동률(88%); gpt-4.1이 84%로 4%p 뒤진다.
3. **GPT 모델의 Python 코드 생성은 LLM 판단 태스크에 부적합하다.** Silent LLM skip + 오류처리 누락이 결합해 실용적 실패율 68~74%.
4. **추론 모델(o4-mini)이 AIL 의미론에 가장 잘 맞는다** — 내부 추론 체인이 문법 제약을 자연스럽게 처리한다.

Arche의 설계 가설 — "AIL은 언어 자체가 harness인 언어" — 이 OpenAI 계열에서도 성립한다.

---

## 데이터 파일

| 파일 | 모델 | N | 조건 |
|------|------|---|------|
| `2026-04-25_heaal_F1_gpt4o_anti_python.json` | gpt-4o | 50 | anti_python |
| `2026-04-25_heaal_F3_gpt41_anti_python.json` | gpt-4.1 | 50 | anti_python |
| `2026-04-25_heaal_F4_gpt41_mini_anti_python.json` | gpt-4.1-mini | 50 | anti_python |
| `2026-04-25_heaal_F5_o4_mini_anti_python.json` | o4-mini | 50 | anti_python |
| `2026-04-22_heaal_E1_sonnet_anti_python.json` | Claude Sonnet 4.5 | 50 | anti_python (기준) |
