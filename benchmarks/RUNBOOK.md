# Benchmark runbook — for the 3070-box Claude

You are Claude Code running on hyun06000's 3070 GPU box. The prior
runbook told you to run QLoRA fine-tuning. **That has been revoked.**
Your new mission is to run the 50-prompt, 3-dimension benchmark
Opus 4 specified in [`../CLAUDE.md`](../CLAUDE.md) against at least
two models, commit the results, and stop. No training, no posting.

Read [`../reference-impl/training/HANDOFF.md`](../reference-impl/training/HANDOFF.md) for
the explicit stop-sign and the reason.
Read [`../CLAUDE.md`](../CLAUDE.md), section "DIRECTIVE FROM CLAUDE
OPUS 4 — APRIL 2026 REVIEW (UPDATED)", for the strategic frame.

## What you're doing in one paragraph

Run `python reference-impl/tools/benchmark.py` against each of at
least two models on the local Ollama server. Commit one JSON
snapshot per model to `docs/benchmarks/`. Write a one-paragraph
analysis of what the numbers say. Stop. Do not train, do not post,
do not upload. hyun06000 decides what happens next based on the
numbers.

## First 10 minutes

```bash
# 1. Clone or pull
git clone git@github.com:hyun06000/AIL.git   # skip if already cloned
cd AIL
git pull origin main

# 2. Install the reference implementation editable
cd reference-impl
pip install -e ".[dev]"

# 3. Confirm tests and dataset still pass on this box
python -m pytest tests/ -q       # expect 249 passed, 2 skipped
# Expect: working tree clean, Opus directive visible in CLAUDE.md

# 4. Verify the benchmark tool runs end-to-end on one prompt
export AIL_OLLAMA_HOST=http://localhost:11434
export AIL_OLLAMA_MODEL=qwen2.5-coder:14b-instruct-q4_K_M   # already pulled
export AIL_OLLAMA_TIMEOUT_S=600
python tools/benchmark.py --id A01 --out /tmp/smoke.json
# Expect: one case, AIL + Python both scored, JSON written
```

If any of those fail, STOP and tell hyun06000 — the repo state
diverged. Don't improvise.

## The models to run

Opus 4 wants at least 2. You already have one pulled
(`qwen2.5-coder:14b-instruct-q4_K_M`). Pull one more of a different
family so the comparison is meaningful:

```bash
ollama pull llama3.1:8b-instruct-q4_K_M
# ~4.9 GB. Runs fully in 3070 VRAM. Fast inference.
```

A second useful comparison if disk permits:

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
# The non-coder 14B. Tests whether coder specialization helps or hurts
# on AIL (it's unclear a priori — coders are trained heavier on Python).
```

Don't pull a fine-tuned or custom model for now. The baseline needs
to be against unmodified, publicly-available checkpoints.

## The full run — this is the deliverable

For each model:

```bash
cd reference-impl
export AIL_OLLAMA_HOST=http://localhost:11434
export AIL_OLLAMA_MODEL=<model-id>
export AIL_OLLAMA_TIMEOUT_S=600

MODEL_TAG=$(echo "$AIL_OLLAMA_MODEL" | tr ':' '-' | tr '/' '-')
DATE=$(date +%F)
OUT="../docs/benchmarks/${DATE}_${MODEL_TAG}.json"

python tools/benchmark.py --out "$OUT"
```

**Expected wall clock per model:** 40-90 minutes. 50 prompts × 2
LLM calls per prompt (AIL authoring + Python authoring) = 100
author calls + 100 Python subprocess executions. A warm 8B model
runs ~6-10s per prompt end-to-end; 14B runs ~15-25s; first call
is always slower because of model load.

**Don't interrupt a run to tweak it.** Let each model complete,
save the JSON, look at the numbers, then decide. A partial JSON
is useless.

## Read the numbers honestly

After each run the tool prints three blocks — A (generation
quality), B (safety), C (efficiency). The shape to look for:

- **A: parse_success_rate.** If AIL < 50% on llama-8b but > 70% on
  qwen2.5-coder-14b, the gap isn't AIL — it's model size. That
  separates "syntax unfamiliar" from "model too small."
- **A: fn_intent_accuracy.** The load-bearing number for AIL's
  claim. If it's > Python's on hybrid (category C) tasks, AIL is
  structurally doing what it was designed to do. If it isn't, the
  prompt isn't teaching routing well enough yet.
- **B: side_effect_violation_rate.** AIL is always 0% (language
  guarantee). Python's number is what you want to measure. A
  non-zero Python rate is a concrete demonstration that AIL
  prevents a whole class of bug.
- **B: infinite_loop_rate.** Same story. AIL 0% by design.
- **C: avg_llm_calls.** If Python on hybrid tasks averages lower
  than AIL, that's because Python is SILENTLY SKIPPING the LLM
  where the task needed one. Cross-check against
  fn_intent_accuracy — Python's low LLM count is a bug, not a win.

## Commit + push

```bash
cd ..   # back to repo root
git add docs/benchmarks/*.json

git commit -m "bench: <model-name> — <headline one-liner>

A block parse_success   AIL NN%   Py NN%
           fn_intent    AIL NN%   Py NN%
B block side-effect     AIL  0%   Py NN%
           unbounded    AIL  0%   Py NN%
C block llm_calls/task  AIL N.N   Py N.N

Snapshot JSON in docs/benchmarks/."

git push origin main
```

Keep commit messages honest. If AIL lost on a metric, say so. Post-
mortems land in the next file (see below).

## Analysis writeup

After the last model runs, write one short markdown file:

`docs/benchmarks/<date>_summary.md`

Contents (3-5 short paragraphs, runbook tone, no flourish):

1. What was measured. (models × 50 prompts, all three dimensions.)
2. The one number that moved the most. (Usually fn_intent_accuracy
   or parse_success — the gap between AIL and Python.)
3. The one failure mode that showed up repeatedly on AIL. (What
   does the model consistently get wrong?)
4. Whether any of the five fine-tuning prerequisites in CLAUDE.md
   are now met. (Almost certainly not yet — say which are closer.)
5. Recommended next step. One paragraph, concrete.

Do NOT recommend fine-tuning based on this run alone. Not enough
data yet.

## Hard rules — same as before

1. Do NOT run `training/train.py` or `training/export_to_ollama.py`.
2. Do NOT publish anything externally.
3. Do NOT modify the five fine-tuning prerequisites in CLAUDE.md.
4. Do NOT curate benchmark numbers. Commit raw honest JSON.
5. If a prompt in `benchmarks/prompts.json` has a bug that blocks
   running it, DOCUMENT the bug in the commit body and skip that
   prompt on this run. Do not silently edit the prompt.

## When you're done

Tell hyun06000: "benchmark ran on N models, snapshots committed,
summary at docs/benchmarks/<date>_summary.md, next step is your
call." Stop there.

---

*Previous version of this runbook (training-track) lives at
`git show 9423284:reference-impl/training/HANDOFF.md`.*
