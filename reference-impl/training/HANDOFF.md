# 🟢 Training track resumed — 2026-04-20

You are Claude Code on hyun06000's 3070 box. A previous version of
this file said **⛔ STOP — training is paused**. As of 2026-04-20,
every one of Opus 4's five prerequisites is met and fine-tuning is
the correct next move. This file replaces the stop notice.

The prior "frozen" text is preserved at
`git show BEFORE_RESUME:reference-impl/training/HANDOFF.md` for
lineage. Do not restore it.

## Why this is now the right move

Opus 4's five fine-tuning preconditions (set 2026-04-20 and
re-stated at the top of [`../../CLAUDE.md`](../../CLAUDE.md)):

| # | Condition | Evidence |
|---|---|---|
| 1 | ≥ 2 base models benchmarked | 3: llama3.1:8b, qwen2.5-coder:14b, claude-sonnet-4-6 — snapshots in [`../../docs/benchmarks/`](../../docs/benchmarks/) |
| 2 | Prompt engineering exhausted | v1/v2/v3 prompt A/B on qwen14b all plateau — [`2026-04-20_prompt_ab_v3_analysis.md`](../../docs/benchmarks/2026-04-20_prompt_ab_v3_analysis.md) |
| 3 | Primary failure mode identified | Python-distribution contamination — Sonnet 4.6 parses AIL at 36% with 100% Python parse, same pattern at every model size. Full argument in [`2026-04-20_claude_sonnet46_summary.md`](../../docs/benchmarks/2026-04-20_claude_sonnet46_summary.md) |
| 4 | AIL spec frozen one version cycle | v1.8 frozen 2026-04-20, policy in [`../../spec/09-stability.md`](../../spec/09-stability.md) |
| 5 | ≥ 200 validated (prompt, AIL) pairs | 205 today, [`dataset/`](dataset/) |

All five hold. The training pipeline is no longer blind
optimization — there is a concrete measurable gap (AIL parse rate)
with a concrete diagnosed cause (training-distribution) and a
stable grammar target to train against.

## What to run

The canonical command (adjust `--base` for other targets):

```bash
python training/train.py \
    --dataset training/train.chatml.jsonl \
    --output training/ail-coder-7b-lora \
    --base Qwen/Qwen2.5-Coder-7B-Instruct \
    --max-seq-length 1024 \
    --batch-size 1 \
    --grad-accum 8 \
    --epochs 3
```

The `--max-seq-length 1024`, `--batch-size 1`, `--grad-accum 8`
defaults above are chosen to fit a 3070 (8 GB). The script's own
defaults (`2048` / `2` / `4`) aim at a larger card and will OOM on
a 3070 at the first checkpoint save.

### Known OOM gotcha — save_strategy at epoch boundaries

Training through epoch 1 and OOMing right at the epoch boundary
is the checkpoint-save VRAM spike under unsloth on an 8 GB card.
Mitigation options, in order of preference:

1. **Simplest** — set `save_strategy="no"` in `SFTConfig` inside
   `train.py`. The script already calls `model.save_pretrained`
   once at the very end, so you lose only mid-run checkpoints.
2. Cut `--max-seq-length 1024` → `512` if your dataset allows it
   (inspect with `wc -L train.chatml.jsonl`).
3. If both fail, profile `nvidia-smi` across the save boundary to
   confirm that's where the spike is before making bigger changes.

## After the run

1. Quick sanity — load the adapter and generate one AIL program
   for a held-out prompt. If it doesn't parse, something is very
   wrong (the training corpus is 100% parseable by construction).
2. Export via `export_to_ollama.py` — this merges the adapter into
   the base and produces a GGUF Ollama can serve.
3. Re-run the benchmark against the fine-tuned model:

       export BENCHMARK_BACKEND=ollama
       export AIL_OLLAMA_MODEL=ail-coder-7b:latest
       python tools/benchmark.py \
           --out docs/benchmarks/$(date +%F)_ail-coder-7b_opus50.json

4. Commit the snapshot. The numbers to watch against the baselines
   in [`../../docs/benchmarks/README.md`](../../docs/benchmarks/README.md):
   - AIL parse rate on all 50 prompts (baseline qwen14b: 42%,
     Sonnet: 36% — target: meaningfully higher)
   - fn/intent routing accuracy on hybrid prompts (baseline: 25%
     on qwen14b)

If parse rate improves and Python-side error-handling miss stays
at its 42–70% range, the harness thesis is validated end-to-end.

## Hard rules that still stand

1. Don't upload anything to HuggingFace / public hubs without
   hyun06000's explicit go.
2. Don't edit the Opus 4 directive or the prereq list to
   retroactively make a failed run count as success. Honest
   numbers only.
3. Don't train against a non-frozen grammar version. If
   `spec/09-stability.md` reports a freeze lift before you train,
   stop and confirm.
4. Don't delete the dataset. Every sample in `dataset/*.jsonl`
   was passed through `validate.py` — losing those is losing the
   ground-truth corpus.

## Read next

1. [`../../CLAUDE.md`](../../CLAUDE.md) — "DIRECTIVE FROM CLAUDE
   OPUS 4 — APRIL 2026 REVIEW (UPDATED)" still frames the project
   direction; only the training gate is now open.
2. [`../../spec/09-stability.md`](../../spec/09-stability.md) —
   what grammar you are training against and how the freeze lifts.
3. [`../../docs/benchmarks/2026-04-20_claude_sonnet46_summary.md`](../../docs/benchmarks/2026-04-20_claude_sonnet46_summary.md)
   — the evidence for prereq #3 (training-distribution as primary
   failure mode).
