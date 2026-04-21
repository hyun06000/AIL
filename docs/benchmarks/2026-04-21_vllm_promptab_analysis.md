# vLLM A/B Prompt Benchmark — tutorial variant on ail-coder:7b-v3

**Date:** 2026-04-21
**Model:** `ail-coder:7b-v3` (QLoRA fine-tune, Q4_K_M GGUF via vLLM)
**Backend:** vLLM 0.19.1, enforce-eager, max-model-len 8192
**Corpus:** Opus 50-prompt, all categories

## Why this run exists

Two goals:

1. Measure whether the `tutorial` prompt variant (decision table + intent-goal
   syntax constraints added to the authoring prompt) improves parse rate over
   the default variant on a fine-tuned model.

2. Establish vLLM as a faster alternative to Ollama for benchmark runs.

## Speed result (the headline)

| Backend | Model | Wall clock (50 prompts) |
|---|---|---|
| Ollama (llama.cpp) | qwen2.5-coder:14b Q4_K_M | **41 min** |
| vLLM 0.19.1 (enforce-eager) | ail-coder:7b-v3 Q4_K_M | **11 min** |

**3.7× faster.** GPU utilization under vLLM: ~100% sustained. Under Ollama:
burst to 99% with idle gaps between requests.

Note: the two benchmarks use different models (14b vs 7b), so absolute
numbers are not directly comparable. The speed ratio is the valid takeaway.

## A/B prompt comparison

| Metric | BASELINE | TUTORIAL | Δ |
|---|---|---|---|
| AIL parse rate | 58% | 56% | −2pp |
| AIL answer OK | 48% | 52% | +4pp |
| AIL fn/intent accuracy | 54% | 54% | 0 |
| AIL avg retries | 1.2 | 1.2 | 0 |
| Python parse rate | 46% | 46% | 0 |
| Python answer OK | 38% | 38% | 0 |
| Python error-handling miss | 50% | 50% | 0 |

## Interpretation

The tutorial variant has **no meaningful effect on ail-coder:7b-v3**. All
deltas are within noise (±2pp). This is expected:

- ail-coder:7b-v3 was fine-tuned on 244 AIL samples. It already knows AIL
  syntax. The tutorial prompt's fn/intent decision table adds no information
  the model hasn't already internalized.
- The +4pp answer improvement is within model nondeterminism.

**The tutorial variant is designed to help base models that have never seen
AIL.** The right test is qwen2.5-coder:14b (base, no fine-tune). That
benchmark would show whether the decision table and intent-goal constraints
reduce the "model writes wrong fn/intent" error class.

## Why qwen14b was not used for vLLM

The qwen2.5-coder:14b Q4_K_M GGUF is 8.99 GB. Loading it with vLLM requires:
- 8.99 GB weights + KV cache overhead > 8 GB VRAM (RTX 3070)

Ollama's llama.cpp backend loads it at 7.0 GB through more aggressive memory
optimization. For vLLM to serve qwen14b, the 3070 is insufficient.

## Setup

```bash
ssh homeblack
# Start vLLM server
PYTORCH_ALLOC_CONF=expandable_segments:True \
~/venv/labs/bin/python3.11 -m vllm.entrypoints.openai.api_server \
  --model ~/AIL/reference-impl/training/ail-coder-7b-v3.Q4_K_M.gguf \
  --tokenizer ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots/c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --load-format gguf --served-model-name ail-coder:7b-v3 \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 8192 --gpu-memory-utilization 0.85 --enforce-eager

# Run benchmarks
export AIL_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export AIL_OPENAI_COMPAT_MODEL=ail-coder:7b-v3
export BENCHMARK_BACKEND=vllm

# Baseline
cd ~/AIL && ~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_vllm_ail-coder-7b-v3_promptab_baseline.json

# Tutorial variant
export AIL_AUTHOR_PROMPT_VARIANT=tutorial
~/venv/labs/bin/python -u reference-impl/tools/benchmark.py \
    --out docs/benchmarks/2026-04-21_vllm_ail-coder-7b-v3_promptab_tutorial.json
```

## What to do next for the tutorial prompt

To get a meaningful A/B result, run against a base model that has never seen
AIL. Two options within 8 GB VRAM:

1. **qwen2.5-coder:7b base** — download GGUF from HuggingFace, serve with
   vLLM the same way. Model has no AIL knowledge → tutorial prompt should show
   a larger effect.
2. **llama3.1:8b** — already in Ollama, can be re-run with vLLM GGUF.

The qwen14b Ollama baseline (parse 60%) remains the best single data point
for the tutorial prompt effect on a strong base model, but it requires an
Ollama run (no vLLM path on 8 GB VRAM for 14B).

## Related

- [`2026-04-21_qwen14b_promptab_baseline.json`](2026-04-21_qwen14b_promptab_baseline.json) — Ollama qwen14b baseline (60% parse, 41 min)
- [`openai_adapter.py`](../../reference-impl/ail/runtime/openai_adapter.py) — new adapter added this session
