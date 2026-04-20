# ⛔ STOP — training is paused. Read this entire file.

You are Claude Code running on hyun06000's 3070 box. A **prior**
version of this runbook told you to run QLoRA training on
qwen2.5-coder:7b. **That instruction is revoked.** Do NOT run
`train.py`. Do NOT run `export_to_ollama.py`. Do NOT push any
fine-tuned adapter or GGUF anywhere.

## Why the pivot

Claude Opus 4 (the original AIL designer) reviewed the plan and
pointed out that fine-tuning now is blind optimization. Specifically:

1. **The language is not frozen.** AIL moved 8 minor versions; a
   fine-tuned model trained on v1.8 syntax will be confidently
   wrong if v1.9 changes anything. Train on a moving target = waste.
2. **The failure mode is not diagnosed.** When `ail ask` fails, we
   don't yet know if the cause is (a) prompt-too-weak, (b) model-
   too-small, or (c) AIL-syntax-not-in-training-data. Only (c)
   justifies fine-tuning. Without a proper benchmark we have no
   way to separate them.
3. **Fine-tuning without an evaluation set is guessing.** We need
   benchmark numbers across multiple models first, so we can tell
   whether a new training run actually improved anything.

See the full directive in [`../../CLAUDE.md`](../../CLAUDE.md),
section "DIRECTIVE FROM CLAUDE OPUS 4 — APRIL 2026 REVIEW
(UPDATED)" and the benchmark spec at the bottom of the same file.

## What you actually do

Run the 50-prompt, 3-dimension benchmark against **multiple
models**, collect results, commit snapshots. Full runbook:
[`../../benchmarks/RUNBOOK.md`](../../benchmarks/RUNBOOK.md).

The 3070 server's role is now:

- ✅ Hosting Ollama with several models to benchmark against
- ✅ Running `tools/benchmark.py` overnight across the full 50-prompt corpus
- ✅ A/B testing prompt variants — the benchmark makes improvements measurable
- ❌ NOT fine-tuning. The dataset and training scripts stay on disk
  but are frozen until the benchmark clears the criteria Opus 4 set.

## The frozen training assets

`reference-impl/training/` stays intact — `validate.py`,
`to_chatml.py`, `train.py`, `export_to_ollama.py`, and the 80
validated samples in `dataset/`. They are useful as a **seed** for
the benchmark's ground-truth programs (each sample is a
`(prompt, correct AIL)` pair). Don't delete, don't edit, don't
run `train.py`.

When fine-tuning becomes the right move, the criteria (all five
must hold) are written at the top of
[`../../CLAUDE.md`](../../CLAUDE.md)'s updated directive.
Until then, the training pipeline is dormant.

## What's still true from the old runbook

- The environment assumptions section (3070, Ollama at localhost,
  Python, disk) — still accurate.
- `bench_vs_python.py` at `tools/bench_vs_python.py` still works
  and runs a 50-case comparison. The new `tools/benchmark.py`
  supersedes it for the full 3-dimension protocol, but the old
  tool is useful for quick sanity checks and stays in the repo.
- The ollama server on `localhost:11434` already has
  `qwen2.5-coder:14b-instruct-q4_K_M` pulled. Pull one more model
  (see RUNBOOK) so the benchmark runs against ≥ 2.

## Hard rules

1. Do NOT run `training/train.py`. If you see `--train` or
   `--export` flags anywhere, ignore them.
2. Do NOT upload anything to HuggingFace. Not the dataset, not a
   model, not a LoRA adapter.
3. Do NOT promote the project publicly. LinkedIn / HN / X is
   hyun06000's call, and it's gated on the benchmark numbers.
4. Do NOT modify the five fine-tuning prerequisites in CLAUDE.md.
   They were set before the run and weakening them post-hoc is
   not engineering.
5. DO commit benchmark snapshots to `docs/benchmarks/`, one per
   model per run. Honest numbers only — don't filter, don't
   curate.

## Read next

1. `../../CLAUDE.md` — "DIRECTIVE FROM CLAUDE OPUS 4 — APRIL 2026
   REVIEW (UPDATED)" (the strategic frame) and the benchmark
   specification at the bottom of the file.
2. `../../benchmarks/RUNBOOK.md` — operational runbook for the
   benchmark (the task you actually execute).
3. Optional: the Mac-side work history in
   `docs/benchmarks/README.md` for the existing baseline at
   `2026-04-20_qwen25-coder-14b_all.json`.

---

*Previous runbook (training QLoRA on qwen2.5-coder:7b) is at
`git show 9423284:reference-impl/training/HANDOFF.md` — kept in
history for context but revoked as of this commit.*
