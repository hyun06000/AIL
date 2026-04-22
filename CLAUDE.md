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
- 현재 게시: 1.8.0–1.8.6. 다음은 최소 1.8.7.

---

## NOW — 2026-04-22

**버전:** v1.8.6 (main + PyPI). 서빙 모델: `ail-coder:7b-v3`.

**트랙 분리됨** (상세: [`docs/heaal/README.md`](docs/heaal/README.md)):
- **AIL 트랙** — 언어 자체. 기준선 R3/C4: AIL parse 80% / answer 70% vs Python 56%. 이미 Python 돌파.
- **HEAAL 트랙** — frontier가 훈련 없이 안전한 AIL 쓰게 하는 harness-as-language 증명. E1/E2 target 초과 (Sonnet+anti_python parse 94% / ans 88% / error-omission 0%).

**최신 발견** (Stage C): `anti_python`은 frontier-only intervention. mid-tier(`qwen2.5-coder:14b`)에서는 default와 anti_python 출력이 bit-identical. 그래도 문법 강제로 HEAAL Score 80.9 vs Py 69.6 유지.

**PyPI 미배포 변경:** 없음. dev = main = PyPI 동기화됨.

---

## NEXT — 선택지 (긴급도 순 아님, hyun06000 지시 대기)

1. **dev → main 머지 + v1.8.6 태그.** 쌓인 변경을 안정화. `--save-source`, HEAAL 대시보드, `ail_parse_check`, parse_json이 아직 PyPI에 없음.
2. **v7 훈련 재시도** — 비-coder base + indented format으로 v3(70%) vs v6(62%)의 8pp 격차 분리. **주의:** 과거 2회 OOM. 반드시 `ollama stop <model>` 선행 + `max-seq-length=1024`.
3. **HEAAL boundary 확인** — `llama3.1:8b`, `mistral-7b`로 anti_python 동작 재확인. 14B-specific인지 mid-tier 전반인지 결정.
4. **Frontier 이식** — GPT-4o, Gemini Pro에 anti_python 적용. 모델-가족 전이성.
5. **E1'** — Sonnet 4.5로 default 프롬프트 재측정 (apples-to-apples, ~$2).

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
