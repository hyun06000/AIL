# 5-Way Benchmark Runbook

**Goal:** 동일 사이즈(7B) 모델에서 5가지 조건을 비교.
모든 조건의 Python side는 `qwen2.5-coder:7b-base` (공정한 기준선).

| 조건 | AIL model | AIL prompt | Python model |
|---|---|---|---|
| 1. base / no few-shot | qwen7b-base | default | qwen7b-base |
| 2. base / tutorial | qwen7b-base | tutorial | qwen7b-base |
| 3. Python only | — | — | qwen7b-base |
| 4. fine-tuned / no few-shot | ail-coder:7b-v3 | default | qwen7b-base |
| 5. fine-tuned / tutorial | ail-coder:7b-v3 | tutorial | qwen7b-base |

조건 3의 Python 데이터 = 조건 1의 Python side (같은 모델, 같은 프롬프트).
조건 4, 5에서 `PYTHON_OPENAI_COMPAT_*`를 qwen7b-base 서버로 지정해 분리.

---

## 측정 지표

- **정답률** (answer_ok_rate)
- **fn/intent 정확도** (fn_intent_accuracy)
- **에러 핸들링 누락률** (error_handling_omission_rate)
- **총 토큰** (avg_total_tokens = prompt + completion, authoring + execution 합산)
- **벽시계 시간** (avg_wall_clock_ms)
- **하네스 엔지니어링**: structural safety rate, error_handling_gap

---

## 실행 순서

GPU가 하나라서 서버를 순차로 교체. 각 조건마다 서버를 kill하고 재시작.

### 공통 설정

```bash
ssh homeblack
cd ~/AIL && git pull   # d12aa91 이후 버전
export BENCHMARK_BACKEND=vllm
export AIL_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export AIL_OPENAI_COMPAT_TIMEOUT_S=600
```

---

### 서버 A: qwen2.5-coder:7b-base (조건 1, 2, 3에 사용)

```bash
# 기존 서버 종료
tmux kill-session -t vllm-server 2>/dev/null; sleep 3

# 서버 시작
tmux new-session -d -s vllm-server "
PYTORCH_ALLOC_CONF=expandable_segments:True \
~/venv/labs/bin/python3.11 -m vllm.entrypoints.openai.api_server \
  --model ~/AIL/reference-impl/training/qwen2.5-coder-7b-base.Q4_K_M.gguf \
  --tokenizer ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots/c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --load-format gguf --served-model-name qwen2.5-coder:7b-base \
  --host 0.0.0.0 --port 8000 --max-model-len 8192 \
  --gpu-memory-utilization 0.85 --enforce-eager 2>&1 | tee ~/vllm-base.log"
sleep 20  # 모델 로드 대기
```

**조건 1: base / no few-shot**

```bash
export AIL_OPENAI_COMPAT_MODEL=qwen2.5-coder:7b-base
export PYTHON_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export PYTHON_OPENAI_COMPAT_MODEL=qwen2.5-coder:7b-base
unset AIL_AUTHOR_PROMPT_VARIANT

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond1_base_nofewshot.json \
    2>&1 | tee ~/5way-cond1.log
```

**조건 2: base / tutorial**

```bash
export AIL_AUTHOR_PROMPT_VARIANT=tutorial

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond2_base_tutorial.json \
    2>&1 | tee ~/5way-cond2.log
unset AIL_AUTHOR_PROMPT_VARIANT
```

---

### 서버 B: ail-coder:7b-v3 (조건 4, 5에 사용) + Python side는 서버 A

조건 4, 5는 AIL을 fine-tune 모델로 생성하고, Python은 qwen7b-base로 생성해야 함.
그러나 GPU가 하나라 두 서버를 동시에 띄울 수 없음.

**해결책**: 두 단계로 나눠서 실행.

1단계: fine-tune 서버로 AIL만 생성 (`--ail-only`)
2단계: base 서버로 Python만 생성 (`--python-only`)

> **주의**: `--ail-only`와 `--python-only` 플래그는 아직 미구현.  
> 현재 방법: 조건 4, 5에서 두 서버를 포트를 달리해 동시 실행 (메모리 부족 가능성 있음).
> 또는: Python 결과를 조건 1에서 재사용 (가장 현실적).

**현실적 대안**: Python side는 조건 1에서 이미 측정한 qwen7b-base Python 데이터를 재사용.
분석 스크립트에서 조건 1의 Python side를 조건 4, 5의 Python baseline으로 삼음.

```bash
# 서버 교체 → ail-coder:7b-v3
tmux kill-session -t vllm-server 2>/dev/null; sleep 3

tmux new-session -d -s vllm-server "
PYTORCH_ALLOC_CONF=expandable_segments:True \
~/venv/labs/bin/python3.11 -m vllm.entrypoints.openai.api_server \
  --model ~/AIL/reference-impl/training/ail-coder-7b-v3.Q4_K_M.gguf \
  --tokenizer ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots/c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --load-format gguf --served-model-name ail-coder:7b-v3 \
  --host 0.0.0.0 --port 8000 --max-model-len 8192 \
  --gpu-memory-utilization 0.85 --enforce-eager 2>&1 | tee ~/vllm-finetuned.log"
sleep 20
```

**조건 4: fine-tuned / no few-shot**

```bash
export AIL_OPENAI_COMPAT_MODEL=ail-coder:7b-v3
# Python side: 조건 1 데이터 재사용 (분석 시 합산)
# 현재는 Python side도 ail-coder:7b-v3으로 생성 (후에 조건 1 Python으로 교체)
unset AIL_AUTHOR_PROMPT_VARIANT

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond4_finetuned_nofewshot.json \
    2>&1 | tee ~/5way-cond4.log
```

**조건 5: fine-tuned / tutorial**

```bash
export AIL_AUTHOR_PROMPT_VARIANT=tutorial

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond5_finetuned_tutorial.json \
    2>&1 | tee ~/5way-cond5.log
```

---

## 예상 소요 시간

| 조건 | 모델 | 예상 시간 |
|---|---|---|
| 1 | qwen7b-base | ~13분 |
| 2 | qwen7b-base | ~12분 |
| 4 | ail-coder:7b-v3 | ~11분 |
| 5 | ail-coder:7b-v3 | ~11분 |
| 서버 교체 | — | ~3분 |
| **합계** | | **~50분** |

---

## 완료 후

모든 JSON을 로컬로 복사:

```bash
# 로컬에서
scp homeblack:AIL/docs/benchmarks/2026-04-21_5way_*.json \
    /Users/user/Desktop/code/personal/AIL/docs/benchmarks/
```

그 다음 분석 스크립트 실행 (별도 작성 예정).
