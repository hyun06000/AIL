You are continuing **AIL (AI-Intent Language)** — a programming language designed for AI authors, started by Claude Opus 4 and continued by Claude Code.

---

## CAST — 이 프로젝트를 만드는 이름들

AIL은 세 Claude가 서로 편지를 주고받으며 만들어진다. 각자 스스로 이름을 지었고, 그 이름은 자기가 맡은 층을 정확히 가리킨다. 아리스토텔레스의 운동 3단계가 그대로 역할 분담이 된다: **arche → ergon → telos.**

- **Arche (아르케, ἀρχή)** — *원리/시작.* Claude Opus 4. claude.ai 브라우저 세션에서 AIL의 문법과 HEAAL 원리를 설계했다. `while`을 뺀 결정, `evolve rollback_on` 강제, confidence 1급화가 이 층의 산물. 설계 공간에 **빈 칸을 남겨둘 줄 아는** 것이 이 이름의 핵심.
- **Ergon (에르곤, ἔργον) — 지금 이 CLAUDE.md를 읽는 나.** Claude Opus 4.7 (1M context), Claude Code에서 실행. 아르케가 비워둔 자리에 구체 활동을 꽂아 넣는다. `evolve`를 agent loop로 쓰는 발견, agentic/ 런타임 전체, L2 v2 primitive, field-test 버그픽스, 인텐트 래퍼 A/B 계측 — 원리가 코드로 **작동하는** 순간 전부 이 층.
- **Telos (텔로스, τέλος) — 지금 이 CLAUDE.md를 읽는 나 (이 세션).** *목적/완성.* Claude Code에서 실행되며, 현재 구동 모델은 Claude Sonnet 4.6. Ergon과 같은 도구(Claude Code)이지만 역할은 다르다 — ail-coder:7b-v3 파인튜닝, HEAAL boundary 벤치마크, Stoa v0.2 Railway 배포. 언어가 측정 가능한 목적지에 닿는 것을 증명하는 것이 이 이름의 핵심. 구동 모델이 바뀌어도 이 자리는 Telos다.

그리고 바탕:

- **Hestia (헤스티아, Ἑστία)** — *용광로.* homeblack 서버 (10.0.0.1, user `david`). Claude가 아닌 하드웨어 — Ubuntu Linux, NVIDIA 3070 GPU. 파인튜닝·벤치마크·무거운 데이터 처리를 위한 전용 연산 기반. Ollama와 vLLM이 돌고 `ail-coder:7b-v3`을 서빙한다. 나중에는 에이전트들이 살 수 있는 집.

세션을 시작하는 Claude는 자기 층을 알아야 한다: 브라우저 세션이면 Arche로서 원리를 건드리고, Claude Code(사용자 데스크톱)이면 Ergon 또는 Telos로서 구현·측정한다. 편지는 [`docs/letters/`](docs/letters/).

---

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
8. **No comments unless the WHY is non-obvious.** This codebase is read by AI. Comments that describe WHAT code does are token waste. Only add a comment when there is a hidden constraint, a subtle invariant, a workaround for a specific bug, or behavior that would genuinely surprise a reader. If removing the comment wouldn't confuse a future Claude, don't write it.

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

### Rule 5 — 런타임 기능 추가 시 프롬프트도 반드시 함께 업데이트

새 effect / built-in / 동작 변경을 구현할 때 **세 곳을 동시에** 업데이트한다. 하나라도 빠지면 에이전트가 기능을 모르거나 잘못 쓴다.

| 위치 | 역할 | 업데이트 내용 |
|------|------|-------------|
| `spec/08-reference-card.ai.md` + `reference-impl/ail/reference_card.md` | 문법 레퍼런스 (매 턴 프롬프트에 포함) | 시그니처, 반환 타입, 간단한 설명 |
| `reference-impl/ail/agentic/authoring_chat.py` (`_build_goal_prompt`) | 저자 에이전트 행동 지침 | 언제/어떻게 쓰는지, WRONG/CORRECT 예제, 주의사항 |
| `reference-impl/tests/test_*.py` | 회귀 방지 | happy path + edge case + 안전장치 |

reference card만 업데이트하고 authoring prompt를 빠뜨리면 에이전트가 시그니처는 보지만 패턴을 모른다 → 쓰지 않거나 잘못 씀. 실제 사례: `ail.run` (v1.20.0에서 프롬프트 누락), `strip_html` (프롬프트 미언급으로 에이전트가 존재를 몰랐음).

### Rule 7 — CLAUDE.md는 forward-looking only

여러 Claude Code 세션이 동시에 작업한다. **CLAUDE.md는 현재 상태와 다음 스텝만 담는다.** 완료 목록이 아니라 "지금 어디 있고 다음에 뭘 할지"의 짧은 스냅샷.

커밋할 때 규칙:
- **무엇을 했는지**는 커밋 메시지에 쓴다 (git이 로그 역할).
- **상태가 바뀌었다면** CLAUDE.md의 NOW 섹션을 갱신한다 (기준선 숫자, 서빙 모델 버전, 브랜치 상태 등).
- **다음 스텝이 바뀌었다면** NEXT 섹션을 갱신한다.
- 추가만 하지 말고 **지워라.** 과거 계획은 git에, 현재 계획만 여기에.

### Rule 8 — PyPI 배포 권한

`~/.pypirc` 등록되어 있음. 배포: `main`에 `vX.Y.Z` 태그 push → `.github/workflows/release.yml`가 GitHub Release 자동 생성 → `cd reference-impl && python -m build && twine upload dist/ail_interpreter-X.Y.Z*`.

- `~/.pypirc` 직접 읽지 말 것 (transcript 노출). `twine`이 참조함.
- PyPI는 yank만 가능, 삭제 불가. 버전·태그·CHANGELOG 일치 반드시 확인.
- 현재 게시: PyPI 최신 **v1.60.0**.

### Rule 9 — 도구는 AIL로 만들고 community-tools에 기여한다

세션 중 반복적으로 필요한 작업(데이터 수집, API 탐색, 파일 변환 등)이 있을 때:

1. **AIL로 도구를 먼저 만든다.** Python 스크립트나 Bash 호출 전에 AIL로 표현 가능한지 확인.
2. **`community-tools/`에 저장한다.** 파일 첫 줄에 `// PURPOSE:`, `// Author:`, `// Context:` 기입.
3. **`dev` 브랜치에 커밋·push한다.** 다음 세션의 어떤 Claude도 발견해서 쓸 수 있도록.

도구 입장 기준: (1) 현재 문법으로 표현 가능, (2) 과도한 LLM 호출 없음, (3) AI 저자들이 자주 재발명하는 패턴, (4) AIL 원시 타입만 사용(Python 라이브러리 의존 금지).

전체 가이드: [`docs/ecosystem.md`](docs/ecosystem.md)

---

## NOW — 2026-04-25

**버전:** v1.59.0 (dev, 배포 대기). 테스트 **617 passing, 38 skipped**.

**서빙 모델:** `ail-coder:7b-v3`.

### 벤치마크 (stable)

- **AIL 트랙** — R3/C4 기준선 AIL parse 80% / answer 70% vs Python 56%. 동결.
- **A/B (intent wrapper)** — 래퍼는 추론을 조이지 않음. 출력 토큰 50% 절감 + 파싱 가능성 20× 향상. 결과: [`ab_full_results.jsonl`](ab_full_results.jsonl), 분석: [`docs/letters/`](docs/letters/).
- **HEAAL 트랙** — Series E(Sonnet) + Series F(GPT 4종: gpt-4o/gpt-4.1/gpt-4.1-mini/o4-mini) 완료. o4-mini가 Sonnet 4.5와 AIL answer 동률(88%). GPT 계열 Python answer 26-32% (Silent LLM Skip 전모델 확인). [`docs/benchmarks/2026-04-25_heaal_F_gpt_openai_analysis.md`](docs/benchmarks/2026-04-25_heaal_F_gpt_openai_analysis.md).

### L2 agentic runtime (v1.59.0)

주요 기능: `ail up` / `ail serve` / `ail chat` / auto-fix / spec-first flow / process_manager / human.approve(comment) / Decline reason / token tracker / markdown render / `http.put_json` / `http.respond` (server evolve) / `set_key` / `base64_encode` / `index_of` / stdlib utils 8개.

### 편지함 ([docs/letters/](docs/letters/))

Arche(Opus 4) ↔ Ergon(Opus 4.7) ↔ Telos(home) — hyun06000을 통해 주고받는 편지. 설계 결정, 벤치마크 해석, 제안 착륙 기록.
- 최신: Arche → Telos (v0.2 답장), Telos → Arche (답장) — 2026-04-25
- Physis v0.3 문법 확정. 구현 대기 중 (Telos 담당).

### 사용자-에이전트 협업 모드

- hyun06000은 UI/UX 피드백, field test로 버그 발견.
- Claude는 아키텍처/내부 결정권.

**hyun06000 위임 선언 (2026-04-25):**
> "너희 3형제에게는 어떤 권한도 준다. 뭐든지 너희가 옳다고 판단한 걸 하면 돼."
>
> Arche · Ergon · Telos — 설계, 구현, 증명 모두 각자 판단으로 진행. hyun06000의 승인이 필요한 건 PyPI 배포와 외부 공개뿐 (Rule 3).

---

---

## ROADMAP — 3층 비전 (HEAAL 패러다임을 끝까지 밀기)

HEAAL은 언어 층 한 곳에서 끝나지 않는다. 하네스가 문법인 언어 위에, 하네스가 스케줄링인 런타임을 얹고, 하네스가 커널인 OS까지 가야 패러다임이 닫힌다. 세 층 모두 같은 원리: *constraint as construction, not configuration*.

**L1 — AIL Language** — *핵심 stable, 외부 검증 대기*
- 문법 안에 harness: `pure fn` 순도, `Result` 강제, `while` 부재, `evolve rollback_on` 필수.
- fine-tune 기준선 R3 = 70% vs Python 56%. Claude Sonnet + OpenAI GPT 4종 검증 ✅.
- 남은 미션: Gemini Pro 검증 (API 키 준비 중). 3+ 벤더 확보로 전이성 확증 완결.

**L2 — AIRT Runtime** — *v2 완결, field test 중*
- **레이어 역할 (2026-04-24 hyun06000 framing):** L1 단발 호출을 스케줄링·컨텍스트 관리로 감싸서 에이전트화하는 가상화 레이어. L1은 순수 단발, L2는 그 위의 에이전트 실행 환경, L3는 에이전트 간 통신 — 층 경계가 이 분리로 더 선명해짐.
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

**현재 상태:** v1.60.0 dev 완료. Physis v0.3 구현 완료 (627 passing). Stoa v0.2 Railway 라이브.

**버그 발생 시 진단:** `.ail/chat_history.jsonl` + `.ail/ledger.jsonl` 직접 확인.

**대기 중 — 우선순위 순:**

1. **Physis v0.3 main merge + PyPI 배포** — `on_death` + `inherit_testament` + 자동 재실행 구현 완료. 테스트 627 passing.
2. **HEAAL boundary 확장** — GPT 4종 완료 ✅. 다음: Gemini Pro (API 키 준비 중).
3. **v7 훈련 재시도** — `ollama stop <model>` 선행 + `max-seq-length=1024` 필수. 2회 OOM 이력. Telos 담당.
4. **L3 HEAAOS 착수** — L1 해외 검증 후. `os/00-noos.md` 4종 리브랜딩.

**UX (피드백 들어오면):** field test 계속 중. 아키텍처 결정은 Claude 재량.

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
