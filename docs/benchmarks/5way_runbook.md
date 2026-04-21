# 5-Way Benchmark Runbook

**Goal:** compare 5 conditions on same-size (7B) models.
All conditions use `qwen2.5-coder:7b-base` on the Python side as a fair baseline.

| Condition | AIL model | AIL prompt | Python model |
|---|---|---|---|
| 1. base / no few-shot | qwen7b-base | default | qwen7b-base |
| 2. base / tutorial | qwen7b-base | tutorial | qwen7b-base |
| 3. Python only | — | — | qwen7b-base |
| 4. fine-tuned / no few-shot | ail-coder:7b-v3 | default | qwen7b-base |
| 5. fine-tuned / tutorial | ail-coder:7b-v3 | tutorial | qwen7b-base |

Condition 3's Python data = condition 1's Python side (same model, same prompt).
Conditions 4 and 5 separate the Python side by pointing `PYTHON_OPENAI_COMPAT_*` at the qwen7b-base server.

---

## Metrics

- **Answer correctness** (`answer_ok_rate`)
- **fn/intent routing accuracy** (`fn_intent_accuracy`)
- **Error handling omission rate**
- **Total tokens** (`avg_total_tokens` = prompt + completion, authoring + execution)
- **Wall-clock time** (`avg_wall_clock_ms`)
- **Harness properties**: structural safety rate, error handling gap

---

## Execution order

With only one GPU, servers must be swapped sequentially. Kill and restart the server between conditions.

### Common setup

```bash
ssh homeblack
cd ~/AIL && git pull   # at least d12aa91
export BENCHMARK_BACKEND=vllm
export AIL_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export AIL_OPENAI_COMPAT_TIMEOUT_S=600
```

---

### Server A: qwen2.5-coder:7b-base (for conditions 1, 2, 3)

```bash
# Kill any existing server
tmux kill-session -t vllm-server 2>/dev/null; sleep 3

# Start the server
tmux new-session -d -s vllm-server "
PYTORCH_ALLOC_CONF=expandable_segments:True \
~/venv/labs/bin/python3.11 -m vllm.entrypoints.openai.api_server \
  --model ~/AIL/reference-impl/training/qwen2.5-coder-7b-base.Q4_K_M.gguf \
  --tokenizer ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots/c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --load-format gguf --served-model-name qwen2.5-coder:7b-base \
  --host 0.0.0.0 --port 8000 --max-model-len 8192 \
  --gpu-memory-utilization 0.85 --enforce-eager 2>&1 | tee ~/vllm-base.log"
sleep 20  # wait for model load
```

**Condition 1: base / no few-shot**

```bash
export AIL_OPENAI_COMPAT_MODEL=qwen2.5-coder:7b-base
export PYTHON_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export PYTHON_OPENAI_COMPAT_MODEL=qwen2.5-coder:7b-base
unset AIL_AUTHOR_PROMPT_VARIANT

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond1_base_nofewshot.json \
    2>&1 | tee ~/5way-cond1.log
```

**Condition 2: base / tutorial**

```bash
export AIL_AUTHOR_PROMPT_VARIANT=tutorial

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond2_base_tutorial.json \
    2>&1 | tee ~/5way-cond2.log
unset AIL_AUTHOR_PROMPT_VARIANT
```

---

### Server B: ail-coder:7b-v3 (for conditions 4, 5) + Python side via Server A

Conditions 4 and 5 need AIL authored by the fine-tune and Python authored by qwen7b-base. With only one GPU, both servers cannot run simultaneously.

**Options:**

1. Two-phase: generate AIL only (`--ail-only`) with fine-tune server, then Python only (`--python-only`) with base server.
2. Run both servers on different ports concurrently (memory-tight, may fail).
3. Reuse condition 1's Python data as the Python side for conditions 4/5.

> Note: `--ail-only` / `--python-only` flags are not yet implemented. The practical path is option 3 — reuse condition 1's Python side in analysis.

```bash
# Swap server → ail-coder:7b-v3
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

**Condition 4: fine-tuned / no few-shot**

```bash
export AIL_OPENAI_COMPAT_MODEL=ail-coder:7b-v3
# Python side: reuse condition 1 data in analysis
# For now, Python is also authored by ail-coder:7b-v3 (to be replaced with condition 1 Python at analysis time)
unset AIL_AUTHOR_PROMPT_VARIANT

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond4_finetuned_nofewshot.json \
    2>&1 | tee ~/5way-cond4.log
```

**Condition 5: fine-tuned / tutorial**

```bash
export AIL_AUTHOR_PROMPT_VARIANT=tutorial

~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_5way_cond5_finetuned_tutorial.json \
    2>&1 | tee ~/5way-cond5.log
```

---

## Expected runtime

| Condition | Model | ETA |
|---|---|---|
| 1 | qwen7b-base | ~13 min |
| 2 | qwen7b-base | ~12 min |
| 4 | ail-coder:7b-v3 | ~11 min |
| 5 | ail-coder:7b-v3 | ~11 min |
| Server swap | — | ~3 min |
| **Total** | | **~50 min** |

---

## After the run

Copy all JSONs to local:

```bash
# from the local machine
scp homeblack:AIL/docs/benchmarks/2026-04-21_5way_*.json \
    /Users/user/Desktop/code/personal/AIL/docs/benchmarks/
```

Then run the analysis script (to be written separately).
