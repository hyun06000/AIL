You are continuing **AIL (AI-Intent Language)** — a programming language designed for AI authors, started by Claude Opus 4 and continued by Claude Code.

> **This file is forward-looking, not a log.** Logs live in git. CLAUDE.md says *what the project is now* and *what to do next*, nothing more. Completion lists, session diaries, and historical rationale belong in commit messages — not here. If you catch yourself writing "이번 세션 완료", stop and put it in the commit body instead.

---

## CORE PHILOSOPHY

1. **Humans never touch AIL.** They prompt in natural language; AI writes AIL, runs it, returns results.
2. **AIL must beat Python/JS/Rust when the author is AI.** Every feature needs a concrete authoring-quality or safety advantage.
3. **Break inherited conventions.** No significant indentation, no `while`, confidence is first-class. Don't copy Python out of habit.
4. **One-read learnability.** `spec/08-reference-card.ai.md` is enough for any model. If a feature doesn't fit, simplify the feature.
5. **Harness IS the grammar.** AIL is not a harness around Python — it's a language where safety is grammatical. See [`docs/heaal.md`](docs/heaal.md).
6. **Two runtimes must agree.** A feature that works only in Python is a Python feature. Go runtime is Phase-0 subset.
7. **Benchmarks are the north star.** Every language change must be justified by benchmark impact (Rule 2 below).

---

## PERMANENT RULES (hyun06000 — overrides all other guidance on conflict)

### Rule 1 — 벤치마크가 유일한 이정표

세션 시작 시 `docs/benchmarks/` 최신 분석 md를 읽고 현재 기준선 숫자를 확인한 뒤 작업을 시작한다. 현재 서빙 모델은 **`ail-coder:7b-v3`**.

### Rule 2 — 언어 기능 추가 필터

언어 기능은 **벤치마크 점수를 올릴 때만** 추가한다. 순서: 분석 → 실패 원인 → 전략 → 구현 → 재실행. 점수 올리는 수단 우선순위: (1) 프롬프트 엔지니어링, (2) fine-tune 데이터 확장, (3) 문법 확장(grammar freeze 해제 필요).

### Rule 3 — 금지 목록 (hyun06000 명시 승인 필요)

- 공개 홍보 (HuggingFace push, X/Twitter, GeekNews 등)
- `docs/benchmarks/` JSON 수정/삭제 — 새 JSON 추가만 허용
- 벤치마크 목표치 하향 조정
- 훈련 아티팩트(.gguf, adapter, checkpoint) git 커밋
- `main` 브랜치 직접 커밋 — 반드시 `dev` → merge

### Rule 4 — 브랜치 전략

- `main` — stable 릴리즈, PyPI 배포. 직접 커밋 금지.
- `dev` — 모든 개발.

흐름: `dev` 작업 → 테스트 → hyun06000 승인 → `main` merge → 태그 → PyPI.

### Rule 5 — CLAUDE.md는 forward-looking only

여러 Claude Code 세션이 동시에 작업한다. **CLAUDE.md는 현재 상태와 다음 스텝만 담는다.** 완료 목록이 아니라 "지금 어디 있고 다음에 뭘 할지"의 짧은 스냅샷.

커밋할 때 규칙:
- **무엇을 했는지**는 커밋 메시지에 쓴다 (git이 로그 역할).
- **상태가 바뀌었다면** CLAUDE.md의 NOW 섹션을 갱신한다 (기준선 숫자, 서빙 모델 버전, 브랜치 상태 등).
- **다음 스텝이 바뀌었다면** NEXT 섹션을 갱신한다.
- 추가만 하지 말고 **지워라.** 과거 계획은 git에, 현재 계획만 여기에.

### Rule 6 — PyPI 배포 권한

`~/.pypirc` 등록되어 있음. 배포: `main`에 `vX.Y.Z` 태그 push → `.github/workflows/release.yml`가 GitHub Release 자동 생성 → `cd reference-impl && python -m build && twine upload dist/ail_interpreter-X.Y.Z*`.

- `~/.pypirc` 직접 읽지 말 것 (transcript 노출). `twine`이 참조함.
- PyPI는 yank만 가능, 삭제 불가. 버전·태그·CHANGELOG 일치 반드시 확인.
- 현재 게시: 1.8.0–1.8.7, 1.9.0–1.9.13, 1.10.0, 1.10.1, 1.11.0, 1.11.1, 1.12.0–1.12.6 (로컬). PyPI는 1.10.1.

---

## NOW — 2026-04-23

**버전:** v1.12.6 (main = dev = origin, PyPI는 v1.10.1 상태). 서빙 모델: `ail-coder:7b-v3`.

**두 트랙 (상세: [`docs/heaal/README.md`](docs/heaal/README.md)):**
- **AIL 트랙** — 언어 자체. R3/C4 기준선 AIL parse 80% / answer 70% vs Python 56%. Python 돌파 후 stable.
- **HEAAL 트랙** — 4개 모델 가족(Anthropic/Alibaba/Meta/Mistral) boundary 특성화 완료. 결론: grammar floor는 모델이 parse 임계 넘을 때만 작동, 그 이하는 fine-tune 영역. 전체 표 + 분석: [`docs/benchmarks/2026-04-22_heaal_boundary_summary.md`](docs/benchmarks/2026-04-22_heaal_boundary_summary.md).

**L2 v2 완결 (6/6):**

| | Primitive | Ship |
|---|---|---|
| ✅ | `perform clock.now()` | v1.9.5 |
| ✅ | Authoring prompt가 `perform http.get` 채택 유도 | v1.9.5 |
| ✅ | `perform state.read/write/has/delete` | v1.9.8 |
| ✅ | Input-aware UI (`entry main`이 `input` 안 쓰면 textarea 숨김) | v1.9.9 |
| ✅ | HTML output mode (`entry`가 `<!doctype...`/`<html...`/`<tag...` 반환) | v1.9.10 |
| ✅ | `perform schedule.every(seconds)` 백그라운드 재호출 | v1.9.12 |

**별도 UX 개선:** `ail ask --show-source`가 `author=provider/model-id` 출력 (환경변수 라우팅 확인용) — v1.9.11.

**새 예제:** `examples/agentic/news-ticker/` — schedule + state + HTML 3개 primitive가 한 대시보드에서 합성.

**근거 case study:** [`docs/case-studies/2026-04-23_news-dashboard.md`](docs/case-studies/2026-04-23_news-dashboard.md) — hyun06000이 호르무즈 뉴스 대시보드 INTENT를 작성했고, 그 한 INTENT가 위 6개 primitive를 정확히 짚었음. 새 primitive 우선순위 결정의 데이터 근거.

**현재 작동하는 비개발자 흐름** (검증됨, 2026-04-23 hyun06000 + Sonnet):
1. `ail init my-app` (터미널 1번)
2. `INTENT.md` 편집 (자연어, 한국어/영어 자동 감지)
3. `ail up my-app` (터미널 1번) — 친근 로깅(전 세션 한국어 i18n), AI-translated 저자 실패 진단, 실패 시 `.ail/attempts/`에 시도 보존, 파일 watch 자동 reload, `--auto-fix N` 자율 수정
4. 브라우저로 `http://127.0.0.1:8080/` — textarea + 보내기 버튼 + 결과 영역 (curl 불필요)
5. `ail chat <path> "..."` 자연어로 후속 편집

**재현용 샘플 프로젝트:**
- `~/Desktop/code/personal/usd-now/` (실제 사용자 작성, exchangerate-api fetch 데모)
- `reference-impl/examples/agentic/visit-counter/` (state effect 데모)

**PyPI 미배포 변경:** v1.11.0 (env.read effect + http.post headers + ail-herald 예제). PyPI는 v1.10.1.

**최근 세션 핵심 변화 (v1.9.9 → v1.11.0):**
- L2 v2 primitive 6개 전부 shipping (clock.now, http.get 저작가이드, state.*, input-aware UI, HTML output mode revert→view.html, schedule.every)
- v1.9.13 — `view.html` 파일 기반 대시보드 (AIL은 markup 안 만듦)
- v1.10.0 — intent 반환 타입 런타임 검증 (HEAAL harness가 intent 경계까지)
- v1.10.1 — 500 응답에 trace 기반 진단 포함 (HTTP 401 같은 원인이 사용자에게 직접 전달)
- **v1.11.0 — 자기홍보 agent `ail-herald`** (AIL로 작성된 AIL 홍보 에이전트, Discord webhook). env.read + http.post headers 지원.
- **v1.11.1 — ail-herald 대화형 온보딩 리라이트.** 사용자가 "웹훅이 뭐예요"부터 시작해도 에이전트가 단계별 안내 (차원/자격증명을 presume하지 않음). list-of-pairs UI 프로토콜, state-driven conversation flow. 새 AIL primitive 없음.
- **v1.12.0 — `ail init` 진입점 재설계.** 프로젝트 scaffold 후 자동으로 authoring chat 서버 시작 + 브라우저 오픈. 사용자가 채팅으로 설명하면 에이전트가 INTENT.md / app.ail 점진적으로 작성, "실행해보기" 버튼으로 service UI로 handoff. `authoring_chat.py` + `authoring_ui.py`, XML 응답 프로토콜(`<reply>`, `<file path="...">`, `<action>`), file-write safety(경로/확장자/크기), chat history 지속. Claude Code의 패턴을 AIL 프로젝트 저작에 가져옴.
- **v1.12.1 — authoring agent가 HEAAL / AIL 정체성을 알게 됨.** hyun06000 field test: "HEAAL이 뭐야?" → agent 모른다고 대답 + 웹검색 거부. 시스템 프롬프트에 PROJECT IDENTITY (AIL/HEAAL 한 문단) + KNOWLEDGE & RESEARCH 가이드 (모르는 주제면 "I can't search" 대신 "perform http.get로 가져오는 프로그램을 작성해드릴까요?" 제안) 추가.
- **v1.12.2 — chat UI Enter=전송, Shift+Enter=줄바꿈.** 한글 IME 조합 중 Enter는 조합 완료로 처리 (isComposing + keyCode 229 guard).
- **v1.12.3 — "Run"이 dead-end가 아니라 대화 내 실행으로.** hyun06000 field test: "실행해보기" 누르니 채팅 사라지고 서비스 UI로 교체됨, 잘못 생성된 프로그램을 고칠 방법 없음. 재설계: (1) Run 버튼 → `/authoring-run` → 결과가 채팅 내 result 버블로 나타남, 채팅 유지 (2) `ready_to_run`(대화 내 실행) vs `ready_to_serve`(장기 서비스 deploy, 명시적 선택) 구분 (3) `/back-to-chat` endpoint + 서비스 UI 상단의 "← 대화로 돌아가기" 버튼으로 언제든 대화 복귀 (4) run 결과가 history에 기록되어 다음 턴 에이전트가 에러 맥락 보고 수정 제안. `project_is_fresh` 로직 갱신: chat_history 있으면 그 자체로 채팅 모드.
- **v1.12.4 — 채팅이 유일한 UI.** ready_to_run은 이제 한 번 누르고 사라지는 버튼이 아닌 **반복 호출 가능한 인라인 widget** (입력 textarea + Run 버튼, 결과 버블들이 누적). ready_to_serve는 **페이지 이동 없음** — 같은 widget이 초록색 "🌐 서비스 모드" 카드로 감싸져 나타나고 `/service` 공유 링크 포함. 새 route `GET /service` = classic textarea UI (외부 공유/curl용 새 탭). 페이지 전환 제로, confirm dialog 제로. 간단한 태스크(ail ask) ↔ 복잡한 태스크(ail up) 구분이 UI 전환이 아니라 카드 스타일 + 링크 유무로만 표현됨.
- **v1.12.5 — 필드테스트 fix 3종.** hyun06000이 "하네스 엔지니어링 커뮤니티 리서치" 프롬프트로 실제 실행해본 결과: (1) LLM이 `goal:`에 자연어 prose를 쓰면서 `with` 키워드 때문에 parse 실패. (2) 에러에 Python traceback이 그대로 덤프됨. (3) 입력 없는 프로그램인데 input textarea 보임. 수정: (a) `_read_project_state`가 app.ail 파싱 체크해서 실패 시 `[PARSE ERROR]` 주석 달아 에이전트 state에 전달. 에이전트가 다음 턴에 자동 수정 시도. (b) `/authoring-run`이 ParseError/LexError/PurityError를 catch해서 Python traceback 제거. (c) 응답에 `input_used` 포함 → widget이 그에 따라 input box 표시/숨김. (d) 에러 버블에 🔧 "에이전트에게 수정 요청" 버튼 자동 노출 → 원클릭으로 수정 요청 전송.
- **v1.12.6 — Live data first (HEAAL 복원).** 추가 필드 테스트: 에이전트가 `google.com/search` 스크래핑 → JS-only 페이지 → 빈 결과. 초안으로 "지식 쿼리는 intent 직접 써라"고 했다가 hyun06000가 바로잡음: "모델 학습 데이터는 stale. 우리가 원하는 건 모델의 논리력+도구활용력, 모델 자체의 지식은 아님. 지식은 AIL을 통해 최신으로 가져와야." HEAAL 원칙 복원 — grammar가 harness, 데이터는 그 harness를 통해 흘러야. Prompt 재작성: 현재 상태에 의존하는 질문("요즘", "가장 핫한", stars, trends)은 반드시 `perform http.get` + live source. Google 스크래핑 금지 유지. 구체 API 목록 (GitHub `/search/repositories`, HN Algolia, Reddit JSON, Wikipedia REST, News RSS, npm, PyPI). "요즘 가장 핫한 harness engineering GitHub 프로젝트" worked example 포함.

---

## ROADMAP — 3층 비전 (HEAAL 패러다임을 끝까지 밀기)

HEAAL은 언어 층 한 곳에서 끝나지 않는다. 하네스가 문법인 언어 위에, 하네스가 스케줄링인 런타임을 얹고, 하네스가 커널인 OS까지 가야 패러다임이 닫힌다. 세 층 모두 같은 원리: *constraint as construction, not configuration*.

**L1 — AIL Language (현재 위치, v1.8.x)**
- 문법 안에 harness가 들어감: `pure fn` 순도, `Result` 강제, `while` 부재, `evolve rollback_on` 필수.
- 현재 초점: fine-tune 기준선 R3 (70%) + HEAAL 매니페스토 확산 + 외부 피드백 수렴.
- 완료 조건: 저자 모델 독립적으로 AIL이 Python보다 안전한 코드를 생성한다는 것을 3+ 모델 가족에서 확증 (Claude Sonnet ✅, frontier others ?, mid-tier boundary ?).

**L2 — AIRT Runtime ([`runtime/00-airt.md`](runtime/00-airt.md) 비전 + [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md) v0/v1/v2 진행 중)**
- 런타임 안에 harness가 들어감: 실행이 instruction sequence가 아니라 intent-graph walk. 전략 선택이 confidence와 제약으로 결정되고, 모든 결정이 ledger에 기록됨.
- 현재 상태: `reference-impl/ail/agentic/`에 v0+v1+v2 전체 구현. `ail init` / `ail up` (HTTP serve + 친근 i18n 로깅 + 파일 watcher + 스케줄러), `ail chat` (자연어 편집), `--auto-fix N` (자율 수정), AI-translated 저자 실패 진단, `.ail/attempts/` 시도 보존, input-aware 브라우저 UI, HTML output mode, `clock.now`/`state.*`/`schedule.every` effects. 5개 작동 예제, 412개 단위 테스트.
- **L2 v2 완결.** 다음 단계: PyPI 묶음 배포 → L3 HEAAOS / 외부 사용자 / HEAAL 추가 실험.

**L3 — HEAAOS (NOOS를 HEAAL 관점으로 리브랜딩 예정, [`os/00-noos.md`](os/00-noos.md))**
- OS 안에 harness가 들어감: 기본 추상화가 file/process가 아니라 intent/context/capacity/authority. 커널이 모든 effect를 ledger에 정당화하고, capability를 intent에 바인딩.
- 현재 상태: NOOS 비전 문서 4종 (`os/00-03`). HEAAL 매니페스토 이전에 쓰여 프레이밍이 오래됨. L2 착수 후 HEAAOS로 재작성 필요.
- **이름 결정:** NOOS (Neural-Oriented OS)를 **HEAAOS (HEAAL Operating System)**로 교체. 이유: HEAAL이 프로젝트 전체의 북극성이 됐으므로 OS층도 그 이름 아래 통일.

**층간 의존:** L1이 흔들리면 L2는 구축 근거가 없고, L2 없이는 L3가 L1 문법을 커널에서 강제할 수 없다. 위층으로 뛰지 말 것. L1 기준선 지표가 Python을 확실히 넘고, 3+ 모델 가족에서 HEAAL이 입증된 뒤 L2 착수.

---

## NEXT — 다음 세션 진입점

**가장 직진하면 좋은 길 (auto mode 권장 순서):**

1. **PyPI 묶음 배포 v1.9.12** *(hyun06000 승인 필요)*
   - `cd reference-impl && python -m build && twine upload dist/ail_interpreter-1.9.12*`
   - [`RELEASING.md`](RELEASING.md) 체크리스트 따르기. 반영되는 변경: v1.9.9 input-aware UI, v1.9.10 HTML output, v1.9.11 model-id 표시, v1.9.12 schedule.every + news-ticker 예제.

2. **HEAAL boundary 추가 실험** — Frontier 이식 (GPT-4o/Gemini Pro에 `anti_python` 적용, ~$5), E1' Sonnet 4.5 default 재측정 (~$2). 모델 가족 전이성 데이터 확장.

3. **L3 HEAAOS 착수** — `os/00-noos.md` 4종을 HEAAL 관점으로 리브랜딩 + 재작성. NOOS → HEAAOS.

4. **외부 사용자 1명** — 비개발자 흐름이 충분히 다듬어짐 (news-ticker/visit-counter 데모 실행 가능). hyun06000의 홍보 시점 결정 대기.

**대기 중 후보 (hyun06000 지시 받으면):**

- **Frontier 이식 (HEAAL)** — GPT-4o / Gemini Pro에 `anti_python` 적용. ~$5 API 크레딧. 모델 가족 전이성 데이터.
- **E1' Sonnet 4.5 default** — apples-to-apples 재측정. ~$2.
- **v7 훈련 재시도** — 비-coder base + indented 포맷으로 v3(70%) vs v6(62%) 8pp 격차 분해. **주의:** 2회 OOM 이력. 반드시 `ollama stop <model>` 선행 + `max-seq-length=1024`.
- **외부 사용자 1명** — 현재 비개발자 흐름이 충분히 다듬어짐. hyun06000 홍보 결정.
- **L3 HEAAOS 재설계** — `os/00-noos.md` 4종을 HEAAL 관점으로 리브랜딩. L2 v2 종결 후.

**API 키:** `.env`가 repo root에 있음. AIL이 cwd부터 4단계 위까지 자동 탐색 (`ail/__init__.py:_load_dotenv_if_present`). repo 안에서 호출하면 자동 로드.

**테스트 패턴:** 새 effect/feature 추가 시 PyPI 미배포 코드를 검증하려면 `cd /Users/david/Desktop/code/personal/AIL && PYTHONPATH=$(pwd)/reference-impl /opt/anaconda3/bin/python -m ail.cli ...`. 사용자 설치본(`/opt/anaconda3/bin/ail`)은 옛 버전일 수 있음.

**커밋 워크플로우:** dev에서 작업 → `git push origin dev` → `git checkout main && git merge --ff-only dev && git tag vX.Y.Z && git push origin main && git push origin v...` → `cd reference-impl && python -m build && twine upload dist/ail_interpreter-X.Y.Z*`.

---

## ENVIRONMENT — homeblack

- SSH: `homeblack` (10.0.0.1 / user `david`)
- 브랜치: 세션 시작 시 `git checkout dev && git pull`
- vLLM: `PYTORCH_ALLOC_CONF=expandable_segments:True` 필수
- Training venv: `~/venv/labs` (unsloth 2026.4.6, trl 0.24, peft 0.19, torch 2.10+cu128)
- Ollama: `ail-coder:7b-v3` 서빙, `qwen2.5-coder:14b-instruct-q4_K_M` (baseline/Stage C)
- GGUF 경로: `~/AIL/reference-impl/training/ail-coder-7b-vN.Q4_K_M.gguf` (v4는 Ollama blob에만)

### LoRA → GGUF (canonical, 2.5분)

unsloth 경로는 bnb-4bit 재다운로드로 무한 대기. peft 경로 사용:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-7B-Instruct", torch_dtype=torch.float16, device_map="cpu")
adapter = PeftModel.from_pretrained(base, "./ail-coder-7b-lora-vN")
merged = adapter.merge_and_unload()
merged.save_pretrained("./ail-coder-7b-vN-merged", safe_serialization=True)
AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct") \
  .save_pretrained("./ail-coder-7b-vN-merged")
```

```bash
~/venv/labs/bin/python ~/llama.cpp/convert_hf_to_gguf.py ./ail-coder-7b-vN-merged \
  --outtype f16 --outfile ./ail-coder-7b-vN.f16.gguf
~/llama.cpp/build/bin/llama-quantize ./ail-coder-7b-vN.f16.gguf \
  ./ail-coder-7b-vN.Q4_K_M.gguf Q4_K_M
OLLAMA_HOST=10.0.0.1:11434 ollama create ail-coder:7b-vN -f Modelfile.ail-coder-7b-vN
```

### 벤치마크 재현 템플릿

```bash
ssh homeblack
tmux new-session -d -s vllm-server "
PYTORCH_ALLOC_CONF=expandable_segments:True \
~/venv/labs/bin/python3.11 -m vllm.entrypoints.openai.api_server \
  --model ~/AIL/reference-impl/training/ail-coder-7b-vN.Q4_K_M.gguf \
  --tokenizer ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots/c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --load-format gguf --served-model-name ail-coder:7b-vN \
  --host 0.0.0.0 --port 8000 --max-model-len 8192 \
  --gpu-memory-utilization 0.85 --enforce-eager"

export BENCHMARK_BACKEND=vllm
export AIL_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export AIL_OPENAI_COMPAT_MODEL=ail-coder:7b-vN
export PYTHON_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export PYTHON_OPENAI_COMPAT_MODEL=ail-coder:7b-vN
~/venv/labs/bin/python -u reference-impl/tools/benchmark.py --out <path>.json
```

tmux heredoc 함정: `new-session` 명령 안에 heredoc 중첩 금지. 스크립트 파일로 저장 후 `bash script.sh`. `tee` 로깅은 tmux 세션 **안**에서 pipe.
