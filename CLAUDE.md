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
- 현재 게시: 1.8.0–1.8.7, 1.9.0. 다음은 최소 1.9.1.

---

## NOW — 2026-04-22

**버전:** v1.9.0 (main + PyPI v1.9.0). 서빙 모델: `ail-coder:7b-v3`.

**트랙 분리됨** (상세: [`docs/heaal/README.md`](docs/heaal/README.md)):
- **AIL 트랙** — 언어 자체. 기준선 R3/C4: AIL parse 80% / answer 70% vs Python 56%. 이미 Python 돌파.
- **HEAAL 트랙** — frontier가 훈련 없이 안전한 AIL 쓰게 하는 harness-as-language 증명. E1/E2 target 초과.

**HEAAL 경계 특성화 완료 (Stage C+D+D'):**
- **Frontier (Sonnet 4.5+anti_python):** AIL 96.1 vs Py 75.9 (+20.2)
- **Mid-tier (qwen14b):** AIL 80.9 vs Py 69.6 (+11.3) — anti_python 효과 0
- **Small but parses (llama8b):** AIL 74.3 vs Py 43.7 (+30.6)
- **Below parse threshold (mistral7b):** AIL **0.0** vs Py 54.9 (-54.9) — 경계 도달, fine-tune 필요
- 결론: grammar floor는 모델이 parse 임계 넘을 때만 작동. 그 이하는 AIL 트랙(fine-tune)의 영역.

**점수 방법론 audit (2026-04-22):** `heaal_score.py`의 vacuous-truth 버그 발견 + 수정. 4개 program-property 메트릭을 `/N`이 아니라 `/parsed`로 계산. 발표된 점수 중 R3 v3 fine-tune의 Python이 48.5→58.0으로 정정 (Δ +39.2 → +29.7). AIL 점수는 모두 변동 없음. 전체 감사: [`docs/benchmarks/2026-04-22_score_audit.md`](docs/benchmarks/2026-04-22_score_audit.md).

**PyPI 미배포 변경:** 없음. dev = main = PyPI 동기화됨. v1.9.0 = L2 v0 + v1 (agentic projects: init/up + watcher + chat + auto-fix) + 3개 예제 + EH-omission 정정.

---

## ROADMAP — 3층 비전 (HEAAL 패러다임을 끝까지 밀기)

HEAAL은 언어 층 한 곳에서 끝나지 않는다. 하네스가 문법인 언어 위에, 하네스가 스케줄링인 런타임을 얹고, 하네스가 커널인 OS까지 가야 패러다임이 닫힌다. 세 층 모두 같은 원리: *constraint as construction, not configuration*.

**L1 — AIL Language (현재 위치, v1.8.x)**
- 문법 안에 harness가 들어감: `pure fn` 순도, `Result` 강제, `while` 부재, `evolve rollback_on` 필수.
- 현재 초점: fine-tune 기준선 R3 (70%) + HEAAL 매니페스토 확산 + 외부 피드백 수렴.
- 완료 조건: 저자 모델 독립적으로 AIL이 Python보다 안전한 코드를 생성한다는 것을 3+ 모델 가족에서 확증 (Claude Sonnet ✅, frontier others ?, mid-tier boundary ?).

**L2 — AIRT Runtime ([`runtime/00-airt.md`](runtime/00-airt.md) 비전 + [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md) v0/v1 구현 완료)**
- 런타임 안에 harness가 들어감: 실행이 instruction sequence가 아니라 intent-graph walk. 전략 선택이 confidence와 제약으로 결정되고, 모든 결정이 ledger에 기록됨.
- 현재 상태: `reference-impl/ail/runtime/executor.py`는 L2의 축소판 (intent dispatch, confidence 전파, trace, parallel). **`reference-impl/ail/agentic/`는 v0+v1 구현 완료** (v1.9.0): `ail init` / `ail up` (HTTP serve + 파일 watcher + auto-reload), `ail chat` (자연어 편집), `ail up --auto-fix N` (테스트 실패 시 자율 수정). 3개 작동 예제, 37개 단위 테스트.
- **다음 (L2 v2):** 자율 진단 강화 (단순 "다시 써줘" → 실패 패턴 분석 후 최소 patch), evolve cross-session persistence를 .ail/state/에 실제 hook, 멀티 파일 프로젝트, `ail bundle` (단일 실행 파일).

**L3 — HEAAOS (NOOS를 HEAAL 관점으로 리브랜딩 예정, [`os/00-noos.md`](os/00-noos.md))**
- OS 안에 harness가 들어감: 기본 추상화가 file/process가 아니라 intent/context/capacity/authority. 커널이 모든 effect를 ledger에 정당화하고, capability를 intent에 바인딩.
- 현재 상태: NOOS 비전 문서 4종 (`os/00-03`). HEAAL 매니페스토 이전에 쓰여 프레이밍이 오래됨. L2 착수 후 HEAAOS로 재작성 필요.
- **이름 결정:** NOOS (Neural-Oriented OS)를 **HEAAOS (HEAAL Operating System)**로 교체. 이유: HEAAL이 프로젝트 전체의 북극성이 됐으므로 OS층도 그 이름 아래 통일.

**층간 의존:** L1이 흔들리면 L2는 구축 근거가 없고, L2 없이는 L3가 L1 문법을 커널에서 강제할 수 없다. 위층으로 뛰지 말 것. L1 기준선 지표가 Python을 확실히 넘고, 3+ 모델 가족에서 HEAAL이 입증된 뒤 L2 착수.

---

## NEXT — v1.9.0 이후 선택지

L1 boundary 4개 모델 가족 anchored, L2 v0+v1 (agentic projects + watcher + chat + auto-fix) PyPI v1.9.0로 배포 완료. 다음 방향 후보 (긴급도 순 아님, hyun06000 지시 대기):

1. **L2 v2 — 에이전트 심화.** 자율 진단 최소 패치 (현재는 전체 재작성), `.ail/state/`에 evolve cross-session 실제 hook, 멀티 파일 프로젝트, `ail bundle` (단일 실행 파일). 설계 노트: [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md) §6.
2. **Frontier 이식 (HEAAL)** — GPT-4o / Gemini Pro에 `anti_python` 적용. 모델 가족 전이성. ~$5 API 크레딧.
3. **E1'** — Sonnet 4.5로 default 프롬프트 재측정. apples-to-apples, ~$2.
4. **v7 훈련 재시도** — 비-coder base + indented 포맷으로 v3(70%) vs v6(62%) 8pp 격차 분해. **주의:** 2회 OOM 이력. 반드시 `ollama stop <model>` 선행 + `max-seq-length=1024`.
5. **외부 사용자 1명** — v1.9.0의 `ail init` → INTENT.md 편집 → `ail up` 흐름이 비개발자에게 의미 있는 첫 사용자 경험. hyun06000 홍보 결정.
6. **L3 HEAAOS 재설계** — `os/00-noos.md` 4종을 HEAAL 관점으로 리브랜딩 (NOOS → HEAAOS). L2 v2 착수 후에 하는 게 맞음.

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
