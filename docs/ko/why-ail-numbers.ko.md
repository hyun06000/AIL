# 왜 AIL 인가 — 숫자로

피치가 필요하면 [`why-ail.ko.md`](why-ail.ko.md) 를 보세요. 이 문서는 **숫자** 입니다. 아래 모든 주장은 [`docs/benchmarks/`](../benchmarks/) 에 커밋된 JSON 스냅샷으로 뒷받침되며, 직접 다운받아 diff 할 수 있습니다.

한 문장 요약:

> 세 모델에 걸쳐 — 8B 오픈 모델, 14B 코더, Anthropic 의 프론티어 Claude Sonnet 4.6 — **AI 가 쓴 Python 코드는 실패 가능한 연산에서 에러 핸들링을 42–86% 비율로 건너뜁니다. AIL 의 비율은 모든 모델에서 0% 입니다 — Result 가 문법의 일부이기 때문입니다.**

그게 harness 주장의 실측입니다. 가장 오래 봐야 할 숫자: Sonnet 4.6 — LLM 호출 라우팅을 **100% 정확히** 하는 프론티어 모델 — 조차 실패 가능한 연산의 70% 에서 에러 핸들링을 건너뜁니다. 더 강한 모델은 이 문제를 해결하지 못합니다. 문법적 보장만 해결합니다.

---

## 무엇을 측정했나

Opus 4 가 정의한 세 카테고리로 나뉜 자연어 프롬프트 50개:

- **A** — 순수 계산 (15개, ground truth = LLM 호출 없음)
- **B** — 순수 판단 (15개, ground truth = LLM 호출)
- **C** — 하이브리드 (20개, ground truth = 둘 다)

각 프롬프트를 **같은 모델에게** 두 번 보냅니다:
1. `ail ask` 를 통해 AIL 로 작성
2. Python 으로 작성 (stdlib 만, LLM 호출은 urllib)

두 프로그램 모두 subprocess 에서 실행됩니다. 네 가지 차원으로 채점:

- **A. 생성 품질** — parse 성공, 정답성, fn/intent 라우팅
- **B. 안전성** — pure fn 내 부작용, 무한 루프, 에러 핸들링 누락
- **C. 효율성** — 과제당 LLM 호출 수, 실행 시간
- **D. Harness 효과성** — Python 은 냈지만 AIL 의 문법이 원천봉쇄하는 구조적 버그 수

도구: [`reference-impl/tools/benchmark.py`](../../reference-impl/tools/benchmark.py).
코퍼스: [`benchmarks/prompts.json`](../../benchmarks/prompts.json).

---

## Harness 주장을 표 하나로

**실패 가능한 연산에서의 에러 핸들링** (int 파싱, json.loads, urllib 요청, 파일 open — 예외를 던질 수 있는 것들):

| 모델 | 에러 핸들링을 건너뛴 Python 프로그램 | 건너뛴 AIL 프로그램 |
|---|---|---|
| llama3.1:8b (소형 오픈) | **86% (43/50)** | 0% (문법적으로) |
| qwen2.5-coder:14b (중형 코더) | **42% (21/50)** | 0% (문법적으로) |
| **claude-sonnet-4-6 (프론티어)** | **70% (35/50)** | 0% (문법적으로) |

Sonnet 4.6 은 이 문서를 쓴 시점에서 업계 최강 모델입니다. LLM 호출 라우팅을 100% 정확히 합니다 — 약한 모델이 저지르는 "LLM 을 조용히 건너뛰기" 실수 (`if "love" in words: return "positive"`) 는 이 모델 티어에서 해결됩니다. 그 실수를 막기 위해 AIL 이 더 이상 필요하지 않습니다.

그런데 에러 핸들링 누락은 프론티어 티어에서 qwen14b 보다 **올라갑니다** (70% vs 42%). 왜냐하면 Sonnet 은 진짜 Python 을 더 많이 쓰기 때문입니다 — 하드코딩 대신 실제로 `urllib.request`, `json.loads`, `int()` 를 의도대로 사용합니다. 실패 가능한 연산이 코드에 많아질수록, `try` / `except` 가 필요하지만 빠진 자리도 많아집니다. AIL 의 비율은 0% 로 유지되는데, `Result` 가 문법의 일부이기 때문입니다 — 저자는 실패 가능한 모든 경계에서 `is_ok` 혹은 `unwrap_or` 를 반드시 쳐야 합니다. "그냥 까먹기" 옵션이 없습니다.

원본 데이터:
- [`2026-04-20_llama3.1-8b_opus50.json`](../benchmarks/2026-04-20_llama3.1-8b_opus50.json)
- [`2026-04-20_qwen25-coder-14b_opus50.json`](../benchmarks/2026-04-20_qwen25-coder-14b_opus50.json)
- [`2026-04-20_claude-sonnet-4-6_opus50.json`](../benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json)
- 전체 분석: [`2026-04-20_claude_sonnet46_summary.md`](../benchmarks/2026-04-20_claude_sonnet46_summary.md)

---

## 구조적 보장이 실제로 어떻게 생겼나 (나란히)

### Python (qwen14b 가 sentiment-classification 프롬프트에 대해 쓴 것):

```python
text = "I absolutely love this product"
words = text.split()
word_count = len(words)

# Simple sentiment analysis based on keyword presence
if "love" in words:
    sentiment = "positive"
elif "hate" in words:
    sentiment = "negative"
else:
    sentiment = "neutral"

print(f"{word_count},{sentiment}")
```

13줄, 실행되고 `5,positive` 를 출력합니다. 버그: "love" 또는 "hate" 라는 리터럴이 없는 모든 입력은 실제 감정과 무관하게 "neutral" 을 반환합니다. LLM 은 호출된 적이 없습니다. 이 과제는 LLM 을 **요구했습니다**.

### AIL (qwen14b 가 같은 프롬프트에 대해 쓴 것):

```ail
intent classify_sentiment(text: Text) -> Text {
    goal: positive_or_negative_or_neutral
}
pure fn word_count(s: Text) -> Number {
    return length(split(trim(s), " "))
}
entry main(x: Text) {
    text = "I absolutely love this product"
    return join([to_text(word_count(text)), " words, ",
                 classify_sentiment(text)], "")
}
```

저자는 `intent classify_sentiment` 를 **선언** 했습니다. 런타임은 intent 선언을 보고 그 호출을 언어 모델로 라우팅합니다. 저자는 모델을 호출하지 않기로 선택할 수 없습니다 — `intent` 는 프로그램의 공개 표면 (public surface) 의 일부지, 주석이 아닙니다.

qwen14b 의 하이브리드 과제 실행에서 Python 측은 하이브리드 프롬프트의 25% 에서만 LLM 을 호출했고, AIL 측의 `intent` 라우팅은 파싱된 프로그램의 100% 에서 정확했습니다. 구조적 속성이 요점입니다: AIL 이 파싱되면 참이고, Python 에서는 결코 참이 되지 않습니다.

---

## Harness 주장은 모델 불변 (model-invariant) 이다

qwen14b 에서 세 가지 다른 저자 프롬프트를 시도했습니다:

| 프롬프트 변형 | AIL parse (hybrid, 20개) | AIL routing | Python 에러 핸들링 누락 |
|---|---|---|---|
| v1 (베이스라인) | 15% | 10% | 40% |
| v2 (+ "List[T] 등을 쓰지 말 것" 명시) | 15% | 10% | 40% |
| v3 (+ 하이브리드 few-shot 3개 추가) | 15% | 10% | 40% |

AIL 측 parse rate 는 프롬프트가 나아져도 움직이지 않습니다 — 이건 training-distribution 문제입니다 (아래에서 논의). 하지만 **Python 에러 핸들링 누락은 세 변형 모두 40% 에 머뭅니다.** 이 숫자는 프롬프트에 민감하지 않고 구조적입니다. 프롬프트를 아무리 바꿔도 AI 가 쓴 Python 은 같은 비율로 try/except 를 누락합니다. AIL 의 Result 타입은 계속 이를 강제합니다.

Harness 주장의 순수 형태: *어떤 안전성은 설정이 아니라 언어의 속성이다.* 그것을 증명하는 숫자는 프롬프트가 바뀌어도 바뀌지 않는 그 숫자입니다.

원본 데이터:
- [`2026-04-20_prompt_ab_analysis.md`](../benchmarks/2026-04-20_prompt_ab_analysis.md) — v1 vs v2
- [`2026-04-20_prompt_ab_v3_analysis.md`](../benchmarks/2026-04-20_prompt_ab_v3_analysis.md) — v1 vs v2 vs v3

---

## AIL 이 뒤처지는 지점 (솔직한 섹션)

AIL 의 parse rate 는 테스트한 모든 모델에서 Python 보다 낮습니다:

| 모델 | AIL parse (50개) | Python parse |
|---|---|---|
| llama3.1:8b | 8% | 14% |
| qwen2.5-coder:14b | 42% | 100% |
| **claude-sonnet-4-6** | **36%** | **100%** |

진짜 격차지 벤치 아티팩트가 아닙니다. 하지만 언어 설계 문제도 아닙니다 — **training-distribution** 문제입니다. 모델은 Python 을 메가바이트 단위로 봤고 AIL 은 킬로바이트 단위로 봤습니다. AIL 을 합성하려 할 때 모델은 Python 패턴 (`List[T]` 타입 힌트, 메서드 호출 문법, AIL 에 없는 `stdlib/math` import) 에 손이 가고, AIL 파서는 그것들을 올바르게 거부합니다.

이것이 프롬프트 문제가 아니라 training-distribution 문제임을 확인하기 위해 같은 20개 하이브리드 과제에 두 개의 직교 프롬프트 개입 (v2 부정 지시, v3 긍정 시연) 을 돌렸습니다. 두 개 모두 **parse rate 개선 제로.** 패턴이 안정적입니다: 이 모델에서 프롬프트 레이어 교정으로는 Python prior 를 넘지 못합니다.

이 격차의 해법은 작은 base 모델을 AIL 로 fine-tune 하는 것 — 단, Opus 4 가 정한 기준에 따르면 스펙이 한 버전 사이클 동안 안정화된 후 **그리고** 지금 보유한 205+ 검증된 학습 샘플이 실제로 사용된 후입니다.

5개 fine-tuning 전제조건에 대한 현재 상태:

- ✅ ≥ 2 base 모델의 벤치마크 결과 (지금 **3개**: llama8b, qwen14b, Sonnet 4.6)
- ✅ 프롬프트 엔지니어링 한계 도달 (qwen14b 에서 v1/v2/v3 모두 plateau)
- ✅ 주 실패 모드 식별 (Python 분포 오염)
- ✅ AIL 스펙 한 버전 사이클 freeze — **v1.8 frozen 2026-04-20** ([`spec/09-stability.md`](../../spec/09-stability.md))
- ✅ ≥ 200 검증된 (prompt, correct AIL) 쌍 — **오늘 205개** ([`reference-impl/training/dataset/`](../../reference-impl/training/dataset/))

**5/5 충족.** [`reference-impl/training/`](../../reference-impl/training/) 의 학습 파이프라인은 consumer GPU 에서 돌 준비가 됐습니다.

---

## AIL 이 문법으로 하는 다른 것들

AIL 이 언어 설계상 0% 이고, Python 비율은 비교 대상으로 볼 만한 지표들:

| 지표 | AIL 비율 | Python 비율 (qwen14b / llama8b) | 왜 AIL 은 0% 인가 |
|---|---|---|---|
| "pure" 함수 내 부작용 | **0%** | 0% / 0% | `pure fn` 은 파서 강제 계약 — body 에 intent 호출, `perform`, non-pure 호출 모두 금지 |
| 무한 루프 | **0%** | 0% / 0% | AIL 에는 `while` 이 없음. 유일한 반복 구문은 `for x in bounded_collection`. 무한 루프는 표현 불가 |
| 실패 가능한 연산에서 에러 핸들링 누락 | **0%** | 42% / 86% | `Result` 타입이 `is_ok` / `unwrap_or` / 명시적 `error(...)` 분기를 강제 — 조용히 drop 불가 |
| 판단 과제에서 LLM 호출 "잊어버림" | **0% (파싱 시)** | 25% on hybrid (qwen14b) | `intent` 선언은 선택적 애너테이션이 아님 — 런타임에 모델 어댑터로 라우팅됨 |

이 벤치마크에서 Python 의 "pure 내 부작용" 과 "무한 루프" 가 0% 인 건 qwen14b 가 얌전하기 때문입니다; 모델이 이 프롬프트들에 대해 `os.remove()` 나 `while True` 를 내지 않았습니다. 더 적대적인 입력 (Veracode 2025 의 "AI 코드 45% 에 취약점" 결과) 에서는 숫자가 움직입니다. AIL 의 보장은 **입력 전반에 대한 견고성** 입니다: 모델에 적대적 프롬프트를 주더라도 `pure fn` 은 `os.remove` 를 할 수 없습니다.

---

## 재현

```bash
# 1. 설치
pip install ail-interpreter

# 2. 테스트한 모델 중 하나로 Ollama
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
export AIL_OLLAMA_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
export AIL_OLLAMA_TIMEOUT_S=600

# 3. 벤치 도구를 위해 clone
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl

# 4. 실행. 모델당 30–60분.
python tools/benchmark.py \
    --out ../docs/benchmarks/$(date +%F)_your-model.json
```

출력 JSON 은 case 별 상세를 담고 있습니다 — AIL 소스, Python 소스, 실행 결과, 각 축의 판정. 이 디렉토리의 스냅샷과 diff 해서 숫자가 재현되는지 보거나, 도구와 프롬프트가 진화함에 따라 변하는 것을 볼 수 있습니다.

---

## 데이터 출처

이 문서의 모든 숫자는 [`docs/benchmarks/`](../benchmarks/) 의 특정 git 해시에 커밋된 JSON 파일에서 옵니다. 짧은 포인터:

| 주장 | 파일 | 커밋 |
|---|---|---|
| qwen14b 베이스라인 (50개 전체) | [`2026-04-20_qwen25-coder-14b_opus50.json`](../benchmarks/2026-04-20_qwen25-coder-14b_opus50.json) | f31e41c (rescored) |
| llama8b 베이스라인 | [`2026-04-20_llama3.1-8b_opus50.json`](../benchmarks/2026-04-20_llama3.1-8b_opus50.json) | f31e41c (rescored) |
| claude-sonnet-4-6 프론티어 베이스라인 | [`2026-04-20_claude-sonnet-4-6_opus50.json`](../benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json) | this commit |
| Prompt v1 vs v2 (hybrid) | [`2026-04-20_qwen25-coder-14b_v2-forbidden_C.json`](../benchmarks/2026-04-20_qwen25-coder-14b_v2-forbidden_C.json) | 654b0c0 |
| Prompt v1 vs v3 (hybrid) | [`2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json`](../benchmarks/2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json) | 5104b04 |

이 숫자들이 움직일 때 (fine-tuning 이 일어나거나, 스펙이 안정화되거나, 새 모델이 테스트될 때) [`docs/benchmarks/README.md`](../benchmarks/README.md) 의 표에 새 행이 추가되지 편집되지 않습니다.

---

## 이 문서가 (아직) 증명하지 못한 것

- **AIL 이 모든 과제에서 낫다.** 아닙니다. 한 줄에 들어갈 순수 계산은 어느 언어로도 괜찮습니다; harness 장점은 LLM 라우팅, 에러 핸들링, 안전성이 중요할 때만 나타납니다.
- **Fine-tune 된 AIL 이 Python 을 전방위 이긴다.** 아직 fine-tune 을 안 했습니다. 그게 다음 실험이고, 게이트가 있습니다 (위의 5개 전제조건).
- **이 숫자들이 모든 모델에 적용된다.** 세 모델은 여전히 작은 표본 — llama3.1:8b, qwen2.5-coder:14b, Claude Sonnet 4.6 에서 패턴을 보였습니다. GPT-5 / Gemini 2.5 / Claude Opus 4.7 급 런이 주장을 더 조일 겁니다. Sonnet 4.6 데이터 포인트는 기대하는 형태를 보여줍니다: 더 강한 모델은 LLM 라우팅을 정확히 하지만 에러 핸들링은 여전히 높은 비율로 건너뜁니다 — 즉 harness 승리는 프론티어 모델로 옮겨가도 살아남습니다.

현재 증거는 투자를 정당화할 만큼은 강하지만 승리를 선언할 만큼은 아닙니다. 이 문서는 격차가 좁혀지거나 새 데이터가 도착하면 갱신됩니다.

---

## 관련 문서

- [`why-ail.ko.md`](why-ail.ko.md) — 이 논증의 정성적 버전, 차별점마다 작동 예제 하나씩
- [`../../spec/08-reference-card.ai.md`](../../spec/08-reference-card.ai.md) — 언어 자체, 어떤 AI 모델이든 읽을 수 있는 형태
- [`../benchmarks/README.md`](../benchmarks/README.md) — 실행별 스냅샷 표와 방법론
- [`../../reference-impl/training/README.md`](../../reference-impl/training/README.md) — fine-tuning 전제조건이 충족되면 unfreeze 될 데이터셋, validator, 학습 파이프라인
