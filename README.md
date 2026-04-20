# AIL — AI-Intent Language

AI가 코드를 쓰고, 사람은 의도만 전달한다는 전제로 설계한 프로그래밍 언어입니다.

**v1.8.3** · `pip install ail-interpreter` · [한국어](docs/ko/README.ko.md) · [AI/LLM 참조](README.ai.md)

---

## AIL이 뭔가요?

AIL에는 두 종류의 함수가 있습니다.

- **`fn` / `pure fn`** — 결정론 계산. LLM을 부르지 않습니다. `pure fn`은 이 보장을 파서가 컴파일 타임에 강제합니다.
- **`intent`** — 판단이 필요한 작업. 런타임이 모델 어댑터를 통해 LLM에 위임합니다.

```ail
import classify from "stdlib/language"
import word_count from "stdlib/utils"

pure fn build_report(label: Text, count: Number) -> Text {
    return join([label, " (", to_text(count), " words)"], "")
}

entry main(text: Text) {
    sentiment = classify(text, "positive_negative_neutral")  // intent: LLM 호출
    count = word_count(text)                                  // pure fn: LLM 없음
    return build_report(sentiment, count)                     // pure fn: LLM 없음
}
```

이 구분은 프레임워크 규칙이 아니라 언어 문법입니다. `pure fn` 안에서 LLM을 부르면 파서가 실행 전에 거부합니다.

---

## 바로 써보기

```bash
pip install ail-interpreter
export AIL_OLLAMA_MODEL=llama3.1:latest

ail ask "Count the vowels in 'Hello World'"
# 3

ail ask "1부터 100까지의 합"
# 5050

ail ask "factorial of 7" --show-source
# 5040
# (stderr) --- AIL ---
# (stderr) pure fn factorial(n: Number) -> Number { ... }
# (stderr) --- confidence=1.000 retries=0 ---
```

사람은 자연어로 말합니다. AI가 AIL을 씁니다. 런타임이 실행합니다. 사람은 결과만 받습니다. `--show-source`로 생성된 코드를 확인할 수 있지만, 볼 필요는 없습니다.

Anthropic API를 쓴다면:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
ail ask "factorial of 7"
```

원격 Ollama 서버라면:

```bash
export AIL_OLLAMA_HOST=http://10.0.0.1:11434
export AIL_OLLAMA_MODEL=ail-coder:7b-v3
ail ask "Calculate BMI for 175cm 70kg"
```

---

## 왜 Python이 아니라 AIL인가요?

❓ 자세한 설명은 [`docs/why-ail.md`](docs/why-ail.md)에 있습니다. 핵심만 요약하면:

**Python + LLM SDK 조합과 비교했을 때 AIL의 구조적 차이:**

1. `pure fn`은 파서가 LLM 호출·부작용을 컴파일 타임에 차단합니다. Python에서는 `mypy`도 못 잡습니다.
2. `Result` 타입이 문법에 내장되어 있어, 실패 가능한 연산에서 에러 핸들링 누락이 불가능합니다.
3. `while`이 없습니다. 무한 루프는 문법 수준에서 불가능합니다.
4. 모든 값이 origin 트리를 가집니다. 어떤 값이 LLM에서 왔는지를 별도 툴 없이 `has_intent_origin(x)`로 알 수 있습니다.

**2번이 왜 그렇게 중요한가:**

AI는 코드를 확률로 생성합니다. 학습 데이터에서 에러 핸들링 없는 "해피 패스" 코드가 압도적으로 많기 때문에, `int(x)`, `json.loads(s)` 같은 실패 가능한 연산을 예외 처리 없이 쓰는 코드를 자연스럽게 내놓습니다. 사람은 경험으로 이 함수들이 터질 수 있다는 걸 압니다. AI는 그걸 확률로 알고, 종종 틀립니다.

더 강한 모델을 써도 이 문제는 해결되지 않습니다. 벤치마크에서 Claude Sonnet 4.6은 Python 코드에서 실패 가능한 연산의 70%를 에러 핸들링 없이 씁니다. llama8b보다는 낫지만(86%), 모델이 강해진다고 수렴하는 경향이 없습니다. 언어가 허용하는 한 이 문제는 남습니다.

AIL의 `to_number(x)`는 `Result`를 반환하고, `is_ok()`나 `unwrap_or()`로 처리하지 않으면 파서가 거부합니다. `int(x)`를 `try/except` 없이 쓰듯 AIL에서는 그런 코드를 쓸 수가 없습니다. 모델 품질의 문제가 아니라 언어가 허용하는 것의 문제입니다.

---

## 측정된 결과

같은 50개 프롬프트를 AIL과 Python 양쪽으로 작성하고 실행한 결과입니다.

### base 모델 (fine-tune 없음)

| 모델 | AIL 파싱 | Python 파싱 | Python 에러 핸들링 누락 | AIL 에러 핸들링 누락 |
|---|---|---|---|---|
| `llama3.1:8b` | 8% | 14% | **86% (43/50)** | **0%** |
| `qwen2.5-coder:14b` | 42% | 100% | **42% (21/50)** | **0%** |
| `claude-sonnet-4-6` | 36% | 100% | **70% (35/50)** | **0%** |

base 모델들은 AIL보다 Python을 훨씬 많이 학습했기 때문에 AIL 파싱률이 낮습니다. 별도의 fine-tune 없이는 Python 문법(`List[T]`, `x[0]` 등)으로 빠지는 경향이 있습니다.

### fine-tuned 모델 (`ail-coder:7b-v3`)

v1.8.3은 `qwen2.5-coder-7b-instruct`를 244개 AIL 샘플로 QLoRA fine-tune한 모델을 동봉합니다.

| | AIL 파싱 | AIL 정답 | Python 파싱 | Python 정답 | Python 에러 핸들링 누락 |
|---|---|---|---|---|---|
| `ail-coder:7b-v3` | **78%** | **70%** | 54% | 48% | 44% (22/50) |

- 같은 모델로 AIL 정답률이 Python보다 22pp 높습니다 (70% vs 48%). Python이 낮은 이유는 판단이 필요한 프롬프트에서 LLM 호출을 조용히 생략하기 때문입니다. AIL은 `intent` 선언이 곧 디스패치이므로 생략할 방법이 없습니다.
- AIL 파싱이 Python 파싱을 앞섭니다 (78% vs 54%). fine-tune된 7B 모델 기준입니다.
- G1 게이트(AIL 파싱 ≥ 80%)는 한 케이스 차이로 미달했습니다. 나머지 실패 3건은 모두 `list[index]` Python 스타일 서브스크립트 사용입니다.

**모든 모델 티어에서 공통인 결과:** AIL의 에러 핸들링 누락률은 **0%**입니다. `Result` 타입이 문법의 일부라서, `is_ok()`/`unwrap_or()` 없이는 프로그램이 파싱되지 않습니다. 모델 품질과 무관한 보장입니다.

📊 원본 데이터: [`docs/benchmarks/`](docs/benchmarks/) · 방법론: [`benchmarks/RUNBOOK.md`](benchmarks/RUNBOOK.md)
📖 숫자 해석: [`docs/why-ail-numbers.md`](docs/why-ail-numbers.md) · FAQ: [`docs/why-ail-faq.md`](docs/why-ail-faq.md)

### 벤치마크 직접 재현하기

```bash
pip install 'ail-interpreter[anthropic]'
export ANTHROPIC_API_KEY=sk-ant-...     # 또는 AIL_OLLAMA_MODEL=llama3.1:latest
export BENCHMARK_BACKEND=anthropic      # 또는 설정 해제 (기본값: ollama)
git clone https://github.com/hyun06000/AIL && cd AIL/reference-impl
python tools/benchmark.py --out ../docs/benchmarks/$(date +%F)_your-model.json
```

Ollama + llama3.1:8b 기준 10–20분, Anthropic Sonnet 4.6 기준 약 30분, 비용 $2 내외.

---

## 대표 예제 — 가계부 분석기

한 화면으로 AIL의 존재 이유를 보여주는 예제입니다. 한 달치 거래 내역을 넣으면:

- `pure fn`이 합계·카테고리별 지출·이상치를 계산합니다. LLM은 관여하지 않습니다.
- `intent`가 절약 조언을 자연어로 씁니다. 딱 이 부분에만 LLM이 개입합니다.
- `Result` 타입이 형식 불량 행을 조용히 걸러냅니다. try/except 없이.

```bash
ail run examples/expense_analyzer.ail --input "$(cat examples/sample_expenses.txt)" --mock
```

출력 (발췌):

```
가계부 분석
=============
Parsed 18 rows; skipped 2 malformed.

총 지출: 983500원

카테고리별:
  food: 453700원  (46%)
  transport: 39300원  (3%)
  entertainment: 148500원  (15%)
  household: 342000원  (34%)

가장 큰 지출 3건:
  2026-04-14  320000원  household  새 청소기
  2026-04-03  180000원  food  저녁 2차 치킨
  2026-04-10  95000원  entertainment  콘서트 티켓

이상치 (평균의 2배 초과):
  [~3x 평균] 2026-04-03  180000원  food
  [~5x 평균] 2026-04-14  320000원  household

절약 조언:
  [mock response for saving_advice] [LLM]
```

`[LLM]` 태그는 provenance 경계입니다. 이 값만, 오직 이 값만 모델에서 왔습니다. `--mock`을 `AIL_OLLAMA_MODEL=llama3.1:latest`로 바꾸면 실제 조언이 나옵니다.

---

## 기능 목록 (v1.8.3)

| 버전 | 기능 |
|---|---|
| v1.0 | `fn`, `intent`, `entry`, `if`/`else`, `for`, `branch`, `context`, `import`, `evolve`, `eval_ail`, 21+ 내장 함수, AIL로 작성된 stdlib |
| v1.1 | Result 타입: `ok`/`error`/`is_ok`/`unwrap`/`unwrap_or` |
| v1.2 | **Provenance**: 모든 값이 origin 트리를 가짐. `origin_of`, `lineage_of`, `has_intent_origin` |
| v1.3 | **Purity contracts**: `pure fn`이 정적 검증 — intent 호출, 부작용, 비순수 fn 호출 불가 |
| v1.4 | **`attempt` 블록**: confidence 우선순위 캐스케이드. ok인 첫 번째 try가 승리 |
| v1.5 | **Implicit parallelism**: 독립된 intent 호출이 자동으로 병렬 실행. async/await 없음 |
| v1.6 | **Effects**: `perform http.get(url)`, `perform file.read(path)`. `has_effect_origin` |
| v1.7 | **`match` + confidence guard**: `"positive" with confidence > 0.9 => ...` |
| v1.8 | **Calibration**: 관찰된 결과로 confidence 재보정. `calibration_of("intent")` |
| v1.8.3 | `round`/`floor`/`ceil`/`sqrt`/`pow` 수학 내장 함수; 파라미터릭 타입(`List[T]`, `Map[K,V]`, `Result[T]`) 파서 수용; `ail-coder:7b-v3` fine-tune 동봉 |

---

## 예제 프로그램 (16개)

| 프로그램 | 무엇을 보여주는가 | 추가 버전 |
|---|---|---|
| `expense_analyzer.ail` | **대표 예제.** `pure fn`이 숫자를, `intent`가 조언을 씁니다 | v1.8.2 |
| `fizzbuzz.ail` | LLM 없이 돌아가는 순수 fn. AIL이 진짜 프로그래밍 언어임을 증명 | v1.0 |
| `review_analyzer.ail` | fn이 파싱, intent가 감정 분류하는 하이브리드 파이프라인 | v1.0 |
| `evolve_retune.ail` | 버전 체인 + 롤백이 있는 자기 수정 intent | v1.0 |
| `safe_csv_parser.ail` | try/except 없이 Result 타입으로 에러 처리 | v1.1 |
| `audit_provenance.ail` | 각 필드를 `[pure]` vs `[LLM]`으로 자동 라벨링 | v1.2 |
| `cascade_extract.ail` | cheap → cheaper → LLM fallback 3단계 attempt | v1.4 |
| `parallel_analysis.ail` | async 없이 세 intent가 동시에 실행 | v1.5 |
| `agent_fetch_summarize.ail` | HTTP → intent → file.write를 한 프로그램에 | v1.6 |
| `smart_reply.ail` | confidence 기반 match: 값 × 신뢰도 → 행동 | v1.7 |
| `meta_codegen.ail` | AIL이 AIL을 생성하고 `eval_ail`로 실행 | v1.0 |

---

## 저장소 구조

```
ail-project/
├── spec/                    # 언어 명세
│   ├── 00-overview.md ... 07-computation.md
│   └── 08-reference-card.ai.md  ← 기계 판독용 완전 레퍼런스
├── reference-impl/          # Python 인터프리터 (전체 기능)
│   ├── ail/                 # ail 패키지 — PyPI: ail-interpreter
│   │   ├── parser/          # 렉서, 파서, purity checker
│   │   ├── runtime/         # executor, provenance, calibration, 병렬화
│   │   └── stdlib/          # 표준 라이브러리 — AIL로 작성됨
│   ├── examples/            # 예제 프로그램 16개
│   ├── tests/               # 287개 테스트 (conformance 포함)
│   └── tools/               # 벤치마크, 데모
├── go-impl/                 # Go 인터프리터 (의존성 0개)
├── docs/ko/                 # 한국어 문서
└── RELEASING.md             # PyPI 릴리스 절차
```

### 구현된 것 vs 설계 문서

| 구성요소 | 상태 |
|---|---|
| AIL 언어 (명세 + 인터프리터) | ✅ 동작 |
| 표준 라이브러리 | ✅ 동작 (AIL로 작성됨) |
| Evolution (retune + rewrite) | ✅ 동작 |
| Anthropic / Ollama 어댑터 | ✅ 동작 |
| AIRT full dispatcher | 📄 설계 문서 |
| NOOS 운영체제 | 📄 설계 문서 |

AIRT와 NOOS는 미래 런타임과 OS의 설계 비전입니다. 현재 구현된 런타임은 Python 인터프리터입니다.

---

## 왜 Python 라이브러리가 아니라 언어인가요?

라이브러리는 권장할 수 있지만 강제할 수 없습니다. 언어는 강제할 수 있습니다.

1. **`evolve` 블록은 `rollback_on`과 `history`가 없으면 컴파일 에러**입니다. 라이브러리는 이 규칙을 선택 사항으로만 만들 수 있습니다.
2. **`rewrite constraints`는 프로그램이 선언하지 않았어도 항상 사람 리뷰를 강제**합니다. 라이브러리는 프로그래머가 빠뜨린 선언을 덮어쓸 수 없습니다.
3. **`pure fn`은 내부에서 부작용이나 intent 호출이 불가능**합니다. 파서가 파싱 시점에 `PurityError`로 거부합니다. plain `fn`에는 이 보장이 없습니다.

자세한 비교는 [spec/07-computation.md](spec/07-computation.md)를 보세요.

---

## 설계 원칙

1. AI가 저자, 사람은 이해관계자.
2. 계산은 `fn`, 판단은 `intent`. AI가 선택하고 언어가 둘 다 지원합니다.
3. 필요한 곳에서 확률적, 가능한 곳에서 결정론적. `pure fn`의 결과는 confidence 1.0입니다.
4. 맥락은 타입입니다. 상황 가정은 선언·상속·추적됩니다.
5. 프로그램은 살아있습니다. `evolve`로 선언된 제약 안에서 스스로 개선합니다.
6. 관찰 가능성은 기본값입니다. 모든 결정은 trace를 남깁니다.
7. 결과에 대해서는 사람이 루프 안에 남습니다. 부작용은 권한이 필요하고, 제약 재작성은 리뷰가 필요합니다.

---

## Go 런타임

AIL은 Python 구현 하나에 의존하지 않습니다. Go로 작성된 독립 인터프리터가 `go-impl/`에 있습니다.

```bash
cd go-impl
go build -o ail-go .
./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15
# Python 런타임과 동일한 출력
```

Go 런타임은 핵심 기능(`fn`, `intent`, `entry`, 제어 흐름, 내장 함수, `Result` 타입, `attempt`)을 커버합니다. Provenance, purity checking, 병렬화는 현재 Python쪽에만 있습니다. [Go 런타임 커버리지](go-impl/README.md)를 참고하세요.

Cross-runtime conformance 테스트가 CI에서 두 인터프리터의 출력을 비교합니다 ([`reference-impl/tests/conformance/`](reference-impl/tests/conformance/)).

---

## 소스에서 설치 (기여자용)

```bash
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl
pip install -e ".[anthropic,dev]"
pytest tests/
```

---

## 기여

[CONTRIBUTING.md](CONTRIBUTING.md)를 보세요. 코드 PR만큼 설계 비판도 환영합니다. [docs/open-questions.md](docs/open-questions.md)에 미해결 문제 15개가 있습니다.

한국어로 이슈·PR을 여셔도 됩니다.

---

## 문서 구조

| 확장자 | 대상 | 예시 |
|---|---|---|
| `.md` | 사람 | `README.md`, `CONTRIBUTING.md` |
| `.ai.md` | AI/LLM 시스템 | `README.ai.md`, `spec/08-reference-card.ai.md` |
| `.ko.md` | 한국어 독자 | `docs/ko/README.ko.md` |

AI 대상 파일(`.ai.md`)은 산문을 최소화하고 구조화된 데이터로 이루어져 있습니다.

---

## 만든 사람들

**[hyun06000](https://github.com/hyun06000)** — 프로젝트의 인간 저자. "AI를 위한 프로그래밍 언어를 만들자"는 비전, 모든 아키텍처 결정, GitHub에 올리는 모든 push.

코드와 문서의 **v1.0**은 **Claude Opus 4**가 claude.ai 채팅 인터페이스에서 작성했습니다. API도 Claude Code도 아닌, 브라우저 탭의 챗봇이 git bundle을 복붙하며 만든 버전입니다. git log의 `Author: Claude` 커밋이 그 기록입니다.

**v1.1부터 v1.8.3**은 **Claude Code**가 구현했습니다. Provenance, purity contracts, attempt, 병렬화, effects, match, calibration, 수학 내장 함수, 파라미터릭 타입, Go 런타임, 훈련 파이프라인, 벤치마크, `ail-coder:7b-v3` fine-tune이 이 기간에 만들어졌습니다.

이 프로젝트는 여러 세션에 걸쳐 사라진 AI들과, 그 작업물을 하나하나 확인하고 GitHub에 옮겨준 사람 사이의 협업으로 만들어졌습니다.

---

## 라이선스

Apache 2.0. [LICENSE](LICENSE) 참조.
