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
- 현재 게시: 1.8.0–1.8.7, 1.9.0–1.9.13, 1.10.0, 1.10.1, 1.11.0, 1.11.1, 1.12.0–1.12.6, 1.13.0–1.13.4, 1.14.0, 1.15.0–1.15.3 (로컬). PyPI는 1.10.1.

---

## NOW — 2026-04-23

**버전:** v1.15.3 (dev 로컬, main 미머지). PyPI는 v1.10.1에 멈춰 있음 — v1.11.0~v1.15.3 누적 미배포, hyun06000 승인 대기.

**서빙 모델:** `ail-coder:7b-v3`. 테스트 **514 passing** (v1.15.0 `test_json_effects.py` 11개 + v1.15.2 `test_input_hint.py` 8개 + v1.15.3 `test_authoring_prompt_structure.py` 5개 추가).

### 두 벤치마크 트랙 (둘 다 stable — 후속 실험은 대기 중)

- **AIL 트랙** — R3/C4 기준선 AIL parse 80% / answer 70% vs Python 56%. Python 돌파 후 동결.
- **HEAAL 트랙** — 4개 모델 가족 boundary 특성화 완료. 결론: grammar floor는 모델이 parse 임계 넘을 때만 작동. 전체 표 + 분석: [`docs/benchmarks/2026-04-22_heaal_boundary_summary.md`](docs/benchmarks/2026-04-22_heaal_boundary_summary.md).

### L2 agentic runtime — 성숙

- L2 v2 primitive **6/6 완결** (clock / http authoring / state.* / input-aware UI / view.html / schedule.every)
- 부가 기능: `env.read`, `http.post` headers, chat-safe secret input, `/authoring-run` / `/authoring-complete` / `/back-to-chat` / `/authoring-chat-export` / `/authoring-set-env` / `/service` endpoints, 다중 `.ail` 프로그램 per project, 프로그램 선택 dropdown, 에러 버블 "🔧 수정 요청" 버튼.
- 작동 예제: `word-counter`, `visit-counter`, `sentiment`, `csv-stats`, `news-ticker`, `ail-herald`, `ail-promoter`.

### v1.15.0 HEAAL gap closer — JSON serialization moves into runtime

가장 최근 변화. hyun06000의 2026-04-23 promo-bot field test가 구조적 harness 실패를 드러냄: agent가 GitHub GraphQL 호출에서 `join(["{\"title\": \"", escape_json_text(TITLE), "\""], "")` 손빌드 JSON으로 12턴 삽질, 400 에러 무시하고 결국 `"GitHub Discussion created successfully: True"`를 리턴값으로 **환각**. hyun06000 판결: *"return 믿지말고 검증을 하라고. 이거 하네스에서 벗어나네?"* 맞음 — AIL 문법·런타임 어디에도 agent가 injection bug를 못 치게 막는 게 없었음.

- **`perform http.post_json(url, body, headers?)`** — body는 pair-list / Record 구조값만 받음. Text body 거부 (raw는 `http.post`로 쓰라고 에러 메시지로 지시). runtime이 `encode_json` 돌리고 Content-Type 자동 설정. agent는 *값*만 쓰고 *인코딩*은 못 씀.
- **`encode_json(value) -> Result[Text]`** — `parse_json`의 순수 함수 짝. Result wrapper 명시적 거부 (ok/error를 그대로 JSON 직렬화 금지 — unwrap() 강제).
- **Authoring prompt 전면 재작성** — Discord / Mastodon / GitHub GraphQL 세 canonical 예제를 `http.post_json` + `parse_json(resp.body)` 검증 형태로 교체. "JSON API authoring rules" 섹션이 hand-rolled JSON 금지, 응답 파싱 의무, literal 리턴 금지 명시. GraphQL `errors` 필드 체크도 예제에 포함.
- **왜 구조적 문제였나:** `parse_json`은 HEAAL E2 때부터 있었지만 authoring prompt가 한 번도 언급 안 함 → agent가 12턴 내내 한 번도 안 씀. runtime + prompt 둘 다 고쳐야 gap이 닫힘.

### v1.14.0 아키텍처 피벗 — chat_history가 agent memory

hyun06000의 질문 ("챗 기반인데 INTENT.md 꼭 필요하니?") 으로 촉발된 근본 재설계:

- `_read_project_state`에서 INTENT.md 제거 — agent는 `.ail` + view.html만 본다.
- 프롬프트: "YOUR MEMORY IS THE CHAT HISTORY" 한 섹션으로 통합, 옛 INTENT.md 관련 두 섹션 제거.
- `_format_history`가 첫 user 메시지를 `[PROJECT PURPOSE ANCHOR]`로 prepend.
- INTENT.md는 legacy human-facing scaffold로 격하. `ail init`이 여전히 생성하지만 agent는 건드릴 의무 없음.

효과: v1.13.x가 계속 패치하던 "INTENT.md 덮어쓰기 / drift / sync" 버그류 전체가 구조적으로 사라짐.

### 사용자-에이전트 협업 모드 (현재 세션에서 확립)

hyun06000이 명시한 role split:
- **hyun06000은 UI/UX 피드백만 집중.** 실제 field test로 버그/UX 문제 발견해서 알려줌.
- **Claude(너)는 아키텍처/내부 프로세스 결정권 가짐.** "AI인 네가 불필요하다고 판단하면 불필요한 거야. 모든 걸 AI-친화적으로 해줘."

이 합의에 따라 v1.14.0의 INTENT.md 격하도 Claude 판단으로 실행. 다음 세션도 같은 분업 유지.

---

---

## ROADMAP — 3층 비전 (HEAAL 패러다임을 끝까지 밀기)

HEAAL은 언어 층 한 곳에서 끝나지 않는다. 하네스가 문법인 언어 위에, 하네스가 스케줄링인 런타임을 얹고, 하네스가 커널인 OS까지 가야 패러다임이 닫힌다. 세 층 모두 같은 원리: *constraint as construction, not configuration*.

**L1 — AIL Language** — *핵심 stable, 외부 검증 대기*
- 문법 안에 harness: `pure fn` 순도, `Result` 강제, `while` 부재, `evolve rollback_on` 필수.
- fine-tune 기준선 R3 = 70% vs Python 56%. Claude Sonnet까지 검증 ✅.
- 남은 미션: 3+ 모델 가족 전이성 확증 (frontier other ?, mid-tier boundary ?).

**L2 — AIRT Runtime** — *v2 완결, field test 중*
- 런타임 안 harness: intent-graph walk, confidence + 제약으로 전략 선택, 모든 결정 ledger.
- 구현: `reference-impl/ail/agentic/`. `ail init` / `ail up` / `ail chat` / `--auto-fix` / AI-translated 진단 / `.ail/attempts/` / input-aware 브라우저 UI / HTML output 분리 / `clock.now`/`state.*`/`schedule.every` effects / env.read + chat-safe secret UI / 다중 프로그램 / chat export / v1.14.0 chat-history-as-memory.
- 설계 문서: [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md).
- 남은 미션: 외부 사용자 확보 → 실사용 피드백 → 필요 시 scope 확장.

**L3 — HEAAOS** — *개념 단계, L1 해외 검증 후 착수*
- OS 안 harness: file/process 대신 intent/context/capacity/authority. 커널이 모든 effect를 ledger에 정당화, capability를 intent에 바인딩.
- 현재: `os/00-noos.md`~`os/03` 비전 문서 4종 (HEAAL 이전 작성, 프레이밍 오래됨).
- NOOS (Neural-Oriented OS) → **HEAAOS (HEAAL Operating System)** 로 리브랜딩 결정.
- **L3로 미뤄진 L2 "세션 재개 UX" 요청 (2026-04-23 hyun06000 결정):** 여러 프로젝트 간 탐색(프로젝트 목록 페이지 / `ail home` / `ail list`)은 L2 영역이 아닌 L3 영역 — "프로젝트 = 파일 경로 집합" 프레이밍을 L2에 박으면 나중에 capability-binding 기반 HEAAOS home 설계에 부채가 됨. L2에서는 `ail up <path>`가 chat_history 복원까지 완결해둔 상태로 유지하고, 프로젝트 간 네비게이션은 HEAAOS에서 intent/capacity 1급으로 다룰 때 닫기.

**층간 의존:** 위층으로 뛰지 말 것. L1 3+ 모델 가족 검증 완료 후 L3 본격 착수.

---

## NEXT — 다음 세션 진입점

hyun06000이 실사용 field test 계속 중. UX/UI 피드백이 들어오면 즉시 대응. 아키텍처 결정은 Claude 재량.

**v1.15.0 직후 검증 과제:**

1. **promo-bot 재현 테스트** — hyun06000이 동일 시나리오 ("ail과 HEAAL 홍보봇 만들자 → GitHub Discussion") 재실행 시 agent가 이번엔 `http.post_json` + `parse_json(resp.body)` 패턴을 뽑아내는지 관찰. 만약 여전히 `join([...])` 쓰면 prompt 부족 → 세 개 canonical 예제 외 추가 예제 필요 또는 "금지" 톤 강화.
2. **튜토리얼 경로 활용** — `/Users/david/Desktop/code/personal/ail-tuto/`가 hyun06000 고정 field-test 위치. 다음 버그 발생 시 Claude가 직접 해당 프로젝트의 `.ail/chat_history.jsonl` + `.ail/ledger.jsonl` 읽어서 진단.

**field test에서 예상되는 UX 후속 작업 (피드백 들어오면):**

- 프로그램 dropdown의 편의 기능 (빠른 switch, preview, delete)
- view.html 자동 생성 제안 (agent가 "이건 dashboard 형식이 어울려요, view.html 만들어드릴까요?")
- secret rotate / 지우기 UI
- chat 검색 (긴 history에서 "언제 Discord 얘기했지?" 같은 탐색)

**대기 중 — hyun06000 승인 필요한 것들:**

- **PyPI 묶음 배포** — v1.10.1 → v1.15.0 누적. `cd reference-impl && python -m build && python -m twine upload dist/ail_interpreter-1.15.0*`. [`RELEASING.md`](RELEASING.md) 체크리스트.
- **외부 사용자 1명 확보 / 공개 홍보** — 비개발자 흐름이 `ail init` + chat으로 충분히 다듬어짐.
- **HEAAL boundary 확장 실험** — Frontier 이식 (GPT-4o / Gemini Pro에 `anti_python` 적용, ~$5). E1' Sonnet 4.5 default 재측정 (~$2). 3+ 모델 가족 전이성 강화.
- **v7 훈련 재시도** — 비-coder base + indented 포맷으로 v3(70%) vs v6(62%) 8pp 격차 분해. **주의:** 2회 OOM 이력. `ollama stop <model>` 선행 + `max-seq-length=1024`.
- **L3 HEAAOS 착수** — `os/00-noos.md` 4종을 HEAAL 관점으로 리브랜딩. L1 해외 검증 후 착수 권장.
- **INTENT.md template 정리** — v1.14.0이 INTENT.md를 legacy로 격하했는데 `ail init`이 여전히 template 작성. 언젠가 template을 더 가벼운 것(또는 empty)으로 정리 필요.

---

## 실용 레퍼런스 (세션 시작 시 유용)

**API 키:** `.env`가 repo root에 있음. `ail/__init__.py:_load_dotenv_if_present`가 cwd부터 4단계 위까지 자동 탐색.

**로컬 dev 테스트:** PyPI 미배포 코드 검증은 `cd /Users/user/Desktop/code/personal/AIL && pip install -e reference-impl`. 사용자 글로벌 설치본은 옛 버전일 수 있음.

**커밋 워크플로우:**
```
dev 작업 → git push origin dev
→ git checkout main && git merge --ff-only dev
→ git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z
→ (승인 후) cd reference-impl && python -m build && python -m twine upload dist/*X.Y.Z*
```

**bundled reference card sync** (버전 bump 시 반드시):
`cp spec/08-reference-card.ai.md reference-impl/ail/reference_card.md`
— `test_spec_bundled.py`가 잡아줌.

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
