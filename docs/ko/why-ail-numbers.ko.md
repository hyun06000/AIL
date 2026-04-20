# 왜 AIL 인가 — 숫자로

🇬🇧 English: [`../why-ail-numbers.md`](../why-ail-numbers.md)

피치가 필요하면 [`why-ail.ko.md`](why-ail.ko.md) 를 보세요. 이 문서는 **숫자** 입니다. 아래 모든 주장은 [`docs/benchmarks/`](../benchmarks/) 에 커밋된 JSON 스냅샷으로 뒷받침되며, 직접 다운받아 diff 할 수 있습니다. 함께 읽으면 좋은 문서:

- [`why-ail-faq.ko.md`](why-ail-faq.ko.md) — 실무 FAQ, 토큰 경제학, 도입 체크리스트
- [`why-ail-mechanics.ko.md`](why-ail-mechanics.ko.md) — 아래 숫자들이 왜 이런 모양으로 나오는가

---

## 한 문장 요약

> 측정한 모든 모델 — 8B 오픈, 14B 코더, fine-tune 7B 어댑터, Anthropic 의 프론티어 Claude Sonnet 4.6 — 에서 **AI 가 쓴 Python 코드는 실패 가능 연산의 42–86% 에서 에러 핸들링을 빠뜨립니다. AIL 의 비율은 모든 모델에서 0%** — `Result` 가 문법의 일부이기 때문.

그게 harness 주장의 실측입니다. 두 번째로 기억할 데이터 포인트: Sonnet 4.6 은 LLM 라우팅을 100% 정확히 합니다 (약한 모델이 가진 "조용한 LLM 스킵" 문제는 이 티어에서는 사라집니다), **그런데도** 실패 가능 연산의 70% 에서 Python 에러 핸들링을 빠뜨립니다. **더 좋은 모델로는 이 갭을 좁힐 수 없습니다. 문법적 보장만 좁힙니다.**

---

## 무엇을 측정했나

50 개 자연어 프롬프트, 3 카테고리:

- **A** — 순수 계산 (15개, ground truth = LLM 호출 불필요)
- **B** — 순수 판단 (15개, ground truth = LLM 호출 필요)
- **C** — 하이브리드 (20개, ground truth = fn 작업 + LLM 호출 모두 필요)

각 프롬프트를 **같은 모델에게** 두 번 보냅니다:

1. `ail ask` 를 통해 AIL 로 작성
2. Python 으로 작성 (stdlib 만, LLM 호출은 urllib)

두 프로그램을 서브프로세스에서 실행하고 Opus 4 의 2026 년 4 월 스펙대로 네 차원으로 채점:

- **A. 생성 품질** — parse 성공, 정답, fn/intent 라우팅
- **B. 안전성** — pure fn 내 부작용, 무한 루프, 에러 핸들링 누락
- **C. 효율성** — 과제당 LLM 호출 수, 실행 시간
- **D. Harness 효과성** — Python 이 낸 구조적 버그 중 AIL 문법이 원천 봉쇄하는 것

도구: [`reference-impl/tools/benchmark.py`](../../reference-impl/tools/benchmark.py).
코퍼스: [`benchmarks/prompts.json`](../../benchmarks/prompts.json).

---

## Harness 주장, 네 모델에서 실측

**실패 가능 연산의 에러 핸들링** — `int()`, `json.loads`, `urllib.request.urlopen`, `open(...)` 처럼 예외를 던질 수 있는 호출들:

| 모델 | Python 에러 핸들링 누락 | AIL 에러 핸들링 누락 |
|---|---|---|
| llama3.1:8b (작은 오픈) | **86% (43/50)** | 0% (문법) |
| qwen2.5-coder:14b (중간 코더) | **42% (21/50)** | 0% (문법) |
| ail-coder:7b-v3 (fine-tune 7B) | **44% (22/50)** | 0% (문법) |
| **claude-sonnet-4-6 (프론티어)** | **70% (35/50)** | 0% (문법) |

Python 비율은 모델 품질과 단조 증가/감소 관계가 아닙니다 — llama8b 가 86% 로 제일 나쁜 건 Python 자체를 거의 못 쓰기 때문이고 (parse 14%), Sonnet 4.6 이 세 강한 모델 중 70% 로 제일 나쁜 건 **실제로 실패 가능 I/O 를 쓰기** 때문 (`urllib.request`, `json.loads`) 입니다 — 그만큼 `try/except` 가 필요한 자리도 많고, 그만큼 빠뜨립니다. qwen14b 와 fine-tuned 7B 는 중간에서 42–44% 사이.

**AIL 의 비율은 모든 티어에서 0%.** 이게 구조적 속성입니다: `to_number(raw)` 는 `Number` 가 아닌 `Result[Number]` 를 반환합니다. 이 반환값을 `is_ok` / `unwrap_or` / 패턴 매치 없이 숫자처럼 쓰려고 하면 파싱되지 않습니다. **저자에겐 잊을 수 있는 선택지가 없습니다.**

원시 데이터:

- [`2026-04-20_llama3.1-8b_opus50.json`](../benchmarks/2026-04-20_llama3.1-8b_opus50.json)
- [`2026-04-20_qwen25-coder-14b_opus50.json`](../benchmarks/2026-04-20_qwen25-coder-14b_opus50.json)
- [`2026-04-20_claude-sonnet-4-6_opus50.json`](../benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json)
- [`2026-04-21_ail-coder-7b-v3_opus50.json`](../benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json)
- Sonnet 전체 분석: [`2026-04-20_claude_sonnet46_summary.md`](../benchmarks/2026-04-20_claude_sonnet46_summary.md)
- v3 전체 분석: [`2026-04-21_ail-coder-7b-v3_analysis.md`](../benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md)

---

## 구조적 보장이 실제로 어떻게 보이는가 — 나란히

### Python (qwen14b 가 감정 분류 프롬프트에 대해 쓴 코드)

```python
text = "I absolutely love this product"
words = text.split()
word_count = len(words)

# 키워드 존재 기반 간단한 감정 분석
if "love" in words:
    sentiment = "positive"
elif "hate" in words:
    sentiment = "negative"
else:
    sentiment = "neutral"

print(f"{word_count},{sentiment}")
```

프로그램은 실행됩니다. `5,positive` 를 출력합니다. 하지만 모델이 **요구된 LLM 기반 분류를 키워드 룩업으로 조용히 대체** 했습니다 — "love" 또는 "hate" 라는 단어가 없는 입력은 실제 감정과 무관하게 "neutral" 로 라벨됩니다.

### AIL (같은 모델, 같은 프롬프트)

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

저자는 `intent classify_sentiment` 를 **선언** 했습니다. 런타임은 `intent` 를 보면 모델 어댑터로 디스패치합니다. 저자는 과제를 선언해놓고 모델 호출을 **조용히 스킵할 수 없습니다** — `intent` 는 주석이 아니라 프로그램의 public surface 입니다.

### 이 차이가 얼마나 자주 나타나는가?

"Silent skip" 정의: Python 프로그램이 파싱 성공했지만 소스에 LLM-call 시도 자체가 없음 (`uses_llm=False`), ground truth 가 LLM 판단을 요구하는 과제 (B 또는 C).

| 모델 | B 에서 silent skip (of 15) | C 에서 silent skip (of 20) |
|---|---|---|
| qwen2.5-coder:14b | 3 | 16 |
| ail-coder:7b-v3 | 3 | 9 |
| claude-sonnet-4-6 | 0 | 1 |

Sonnet 4.6 은 사실상 항상 올바르게 LLM 호출이 있는 Python 을 씁니다. 중간 티어 모델은 의미 있는 비율로 스킵하며, 특히 하이브리드 과제에서. AIL 은 silent skip 할 수 없습니다 — `intent` 는 디스패치 선언이며, 런타임이 라우팅하고 저자는 못 뽑아냅니다.

---

## Harness 주장은 프롬프트 엔지니어링에 흔들리지 않음

qwen2.5-coder:14b 에서 세 가지 authoring 프롬프트 변형을 20 개 하이브리드 프롬프트에 돌렸습니다:

| 프롬프트 변형 | AIL parse (하이브리드) | AIL fn/intent | Python 에러 핸들링 누락 |
|---|---|---|---|
| v1 (baseline) | 15% (3/20) | 10% (2/20) | 40% |
| v2 (+ "`List[T]` 금지" 명시) | 15% (3/20) | 10% (2/20) | 40% |
| v3 (+ 하이브리드 few-shot 3 개) | 15% (3/20) | 10% (2/20) | 40% |

이 모델에서 AIL parse 는 프롬프트에 관계없이 막혀있었습니다 — 명시 부정 지시도, 추가 시연도 한 케이스도 못 움직였습니다. 이 실패는 아래 "AIL 이 뒤처지던 곳" 에서 다루는 훈련-분포 문제입니다.

주목할 숫자는 오른쪽 열: **세 변형 전체에서 Python 에러 핸들링 누락이 40% 로 고정**. 프롬프트 변화가 이 수치에 영향을 주지 않는 이유는, 누락된 안전망이 프롬프트 문제가 아니라 **그 모델이 작성 중인 언어의 속성** 이기 때문입니다. AIL 의 `Result` 타입은 같은 세 런에서 0% 를 유지했습니다 — 같은 메커니즘으로.

원시 데이터:

- [`2026-04-20_prompt_ab_analysis.md`](../benchmarks/2026-04-20_prompt_ab_analysis.md) — v1 vs v2
- [`2026-04-20_prompt_ab_v3_analysis.md`](../benchmarks/2026-04-20_prompt_ab_v3_analysis.md) — v1 vs v2 vs v3

---

## AIL 이 뒤처지던 곳 — fine-tune 이 어떻게 좁혔나

세 base 모델에서 AIL parse 는 Python parse 보다 낮았습니다:

| 모델 | AIL parse | Python parse |
|---|---|---|
| llama3.1:8b | 8% | 14% |
| qwen2.5-coder:14b | 42% | 100% |
| claude-sonnet-4-6 | 36% | 100% |

이건 실제 갭이며 벤치마크 아티팩트가 아닙니다. 언어 설계 문제도 아니고 — **훈련-분포** 문제입니다. 모든 base 모델은 AIL 보다 수십만 배 많은 Python 을 봤습니다. AIL 을 합성하라고 하면 Python 패턴 (`List[T]` 타입 힌트, `x[0]` 서브스크립트, 존재하지 않는 `stdlib/math` import) 에 손을 뻗고, AIL 파서는 올바르게 거부합니다.

qwen14b 에서 프롬프트 엔지니어링으로는 이 문제를 해결할 수 없음을 확인했습니다 (위 프롬프트 변형 표 참고 — 세 직교하는 개입, 0 건 개선). 해결책은 fine-tuning 입니다.

### Fine-tune 이 갭의 대부분을 좁혔다

`ail-coder:7b-v3` 는 qwen2.5-coder-7b-instruct 를 244 개의 검증된 AIL 샘플로 QLoRA fine-tune 한 것이며, v1.8.3 의 일부로 [`reference-impl/training/`](../../reference-impl/training/) 에서 배포됩니다. 같은 50-프롬프트 코퍼스에서:

| 모델 | AIL parse | AIL 정답 | Python parse | Python 정답 |
|---|---|---|---|---|
| ail-coder:7b-v3 | **78%** | **70%** | 54% | 48% |

- **AIL parse 78%** — 같은 7B base 의 Python parse 54% 와 비교. G1 게이트 목표 80% 는 50 개 중 한 케이스 차이로 실패. 남은 세 개의 실패는 Python 스타일 `list[index]` 서브스크립트.
- **AIL 정답 70% vs Python 정답 48%** — 같은 모델에서 22 pp 차이. 주로 C (하이브리드) 카테고리에서 Python 의 silent-skip 동작에서 비롯 — [`why-ail-mechanics.ko.md`](why-ail-mechanics.ko.md) §2 참고.
- 이 모델의 Python parse 54% 가 base qwen14b 의 100% 보다 낮은 이유엔 교란 변수가 두 개 섞여 있습니다: fine-tune 이 7B 를 AIL 쪽으로 끌어당긴 대가로 Python 유창성이 희생된 점 *과*, qwen2.5-coder:7b 가 qwen2.5-coder:14b 보다 애초에 작은 base 인 점. base qwen2.5-coder:7b 의 같은 코퍼스 실측이 없으면 이 둘을 분리할 수 없습니다. 어느 쪽이든 이건 일반적으로 "AIL 이 Python 작성에서 이긴다" 를 뜻하지 **않습니다** — 이 특정 fine-tuned 7B, 이 특정 코퍼스에 대한 사실입니다.

Opus 4 가 2026 년 4 월에 제시한 5 개 fine-tuning 전제 조건은 2026-04-20 에 모두 충족됐습니다:

- ✅ ≥ 2 개 base 모델의 벤치마크 결과 — 현재 3 개 (llama8b, qwen14b, Sonnet 4.6)
- ✅ 프롬프트 엔지니어링 소진 — qwen14b 에서 v1/v2/v3 모두 하이브리드 parse 15% 에서 정체
- ✅ 주 실패 모드 규명 — Python 분포 오염
- ✅ AIL 스펙이 한 릴리즈 사이클 동안 동결 — v1.8 이 2026-04-20 동결 ([`spec/09-stability.md`](../../spec/09-stability.md))
- ✅ ≥ 200 개 검증된 (prompt, AIL) 쌍 — v1.8.3 기준 244 개

훈련은 3070 (8 GB VRAM) 에서 10 분 걸립니다. 전체 실행 세부: [`reference-impl/training/HANDOFF.md`](../../reference-impl/training/HANDOFF.md).

---

## AIL 이 문법으로 강제하는 기타 속성

AIL 의 비율이 설계상 0% 인 지표들, 비교를 위해 Python 의 측정 비율과 함께:

| 지표 | AIL 비율 | Python 비율 (측정) | AIL 이 0% 인 이유 |
|---|---|---|---|
| `pure fn` 내 부작용 | **0%** | 이 코퍼스에서 0% | `pure fn` 은 파서가 강제하는 계약 — 바디에 `intent` 도 `perform` 도 non-pure 호출도 불가 |
| 무한 루프 | **0%** | 이 코퍼스에서 0% | AIL 엔 `while` 없음; 유일한 루프는 `for VAR in COLLECTION`. 무한 루프는 **표현 불가능** |
| 에러 핸들링 누락 | **0%** | 모델에 따라 42–86% | `Result` 타입이 실패 가능 경계에서 `is_ok` / `unwrap_or` / 명시적 `error(...)` 분기를 강제 |

Python 이 앞의 두 지표에서 0% 인 것은 **이 50 개 프롬프트 코퍼스에 특수한** 사실입니다. 테스트된 모델들은 이 입력들에 대해 얌전합니다 — `os.remove()` 나 `while True` 를 뱉지 않습니다. 더 적대적인 입력 (Veracode 2025 의 "AI 가 생성한 코드의 45% 가 보안 취약점 보유" 결과가 여기 해당) 에서는 이 숫자들이 올라갑니다. AIL 의 보증은 **입력에 대한 견고성** — 적대적 프롬프트가 들어와도 `pure fn` 은 여전히 `perform file.delete` 를 할 수 없습니다.

---

## 재현 방법

```bash
# 1. 설치
pip install ail-interpreter

# 2. 테스트된 모델 중 하나로 Ollama 실행
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
export AIL_OLLAMA_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
export AIL_OLLAMA_TIMEOUT_S=600

# 3. 벤치마크 도구 가져오기
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl

# 4. 실행. 모델당 20–40 분.
python tools/benchmark.py \
    --out ../docs/benchmarks/$(date +%F)_your-model.json
```

출력 JSON 에는 케이스별 상세 — AIL 소스, Python 소스, 실행 결과, 각 축의 판정 — 가 모두 들어있습니다. 이 디렉터리의 커밋된 스냅샷과 diff 해서 재현을 확인하거나, 도구와 프롬프트가 진화하면서 숫자가 변하는 걸 관찰할 수 있습니다.

---

## 데이터 출처

이 문서의 모든 숫자는 [`docs/benchmarks/`](../benchmarks/) 의 JSON 파일 중 하나, 특정 git 해시에 커밋된 것을 추적합니다.

| 주장 근거 | 파일 | 커밋 |
|---|---|---|
| qwen14b baseline (50 프롬프트) | [`2026-04-20_qwen25-coder-14b_opus50.json`](../benchmarks/2026-04-20_qwen25-coder-14b_opus50.json) | f31e41c |
| llama8b baseline | [`2026-04-20_llama3.1-8b_opus50.json`](../benchmarks/2026-04-20_llama3.1-8b_opus50.json) | f31e41c |
| Claude Sonnet 4.6 baseline | [`2026-04-20_claude-sonnet-4-6_opus50.json`](../benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json) | f31e41c |
| 프롬프트 v1 vs v2 (하이브리드, qwen14b) | [`2026-04-20_qwen25-coder-14b_v2-forbidden_C.json`](../benchmarks/2026-04-20_qwen25-coder-14b_v2-forbidden_C.json) | 654b0c0 |
| 프롬프트 v1 vs v3 (하이브리드, qwen14b) | [`2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json`](../benchmarks/2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json) | 5104b04 |
| Fine-tuned v3 모델 | [`2026-04-21_ail-coder-7b-v3_opus50.json`](../benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json) | 461096d |

이 숫자들이 변할 때 (추가 fine-tuning, 새로운 모델, 문법 진화 등) [`benchmarks/README.md`](../benchmarks/README.md) 의 테이블은 새 행을 **추가** 하지 제자리 수정하지 않습니다. JSON 이 아카이브 기록입니다.

---

## 이 수치들이 **증명하지 않는** 것

현 데이터의 한계에 대한 솔직함:

- **AIL 이 모든 과제에서 낫다.** 그렇지 않습니다. `len(x.split())` 같은 한 줄짜리 순수 계산은 두 언어 다 괜찮습니다 — harness 이점은 LLM 라우팅, 에러 핸들링, 구조적 안전이 중요할 때만 나타납니다.
- **Fine-tune 이 일반화된다.** `ail-coder:7b-v3` 는 v1.8 문법 대상 244 개 샘플로 fine-tune 됐습니다. 78% parse 는 이 벤치마크의 50 프롬프트 한정입니다. 다른 프롬프트 분포에선 다른 비율이 나올 가능성이 높습니다. G1 게이트도 아직 미달 (1 케이스 차이).
- **이 수치들이 모든 모델에 적용된다.** 이 코퍼스의 4 개 모델은 작은 샘플입니다. 일반 패턴 — 구조적 속성은 모델 크기에 불변, parse 는 변동 — 은 Opus 4 의 명제와 일치하지만, GPT-5 / Gemini 2.5 / Claude Opus 4.7 급 측정이 주장을 더 강화할 것입니다.

현재 증거는 프로젝트를 계속할 만하지만 언어가 성숙했다고 선언하기엔 부족합니다. 새 데이터가 나오면 이 문서는 업데이트됩니다.

---

## 관련 문서

- [`why-ail.ko.md`](why-ail.ko.md) — 이 문서의 정성적 버전, 차별점마다 하나씩 실행 가능한 예시.
- [`why-ail-faq.ko.md`](why-ail-faq.ko.md) — 실무 도입 질문 (토큰 절감, AIL 선택 시점).
- [`why-ail-mechanics.ko.md`](why-ail-mechanics.ko.md) — 이 문서의 각 숫자 뒤 메커니즘.
- [`../benchmarks/README.md`](../benchmarks/README.md) — 실행별 스냅샷 테이블과 방법론.
- [`../../reference-impl/training/README.md`](../../reference-impl/training/README.md) — 데이터셋, validator, 훈련 파이프라인.
