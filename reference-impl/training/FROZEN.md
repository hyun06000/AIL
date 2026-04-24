# ⛄ This directory is frozen

All files in `reference-impl/training/` were built to enable a
fine-tuning pipeline for AIL. That pipeline is **paused**, not
deleted.

## Why

Claude Opus 4 (the AIL designer) reviewed the plan and flagged
that fine-tuning now is premature. The five conditions that must
ALL hold before fine-tuning becomes the right move are:

1. Benchmark results from at least 2 base models
2. Prompt engineering has been exhausted (diminishing returns
   confirmed)
3. The primary failure mode is identified as "model doesn't know
   AIL syntax" (not prompt issues, not model-too-small)
4. The AIL spec has been frozen for at least one version cycle
5. At least 200 validated `(prompt, correct AIL)` pairs for
   training/eval split

Full rationale is in `../../CLAUDE.md`, section "DIRECTIVE FROM
CLAUDE OPUS 4 — APRIL 2026 REVIEW (UPDATED)".

## What's still valid

- `dataset/*.jsonl` — 80 validated samples. These stay useful as
  seed ground-truth programs for the benchmark, and as training
  data when/if the criteria above are met.
- `validate.py` — the 4-gate validator. Still runs; used when
  adding new dataset entries.
- `seed_from_*.py` — the harvesters that produced the dataset.
  Deterministic, re-runnable.
- `to_chatml.py`, `train.py`, `export_to_ollama.py` — the
  training-side scripts. Tested that they `--help` without
  errors; not exercised end-to-end. Kept for when the freeze
  lifts.

## What changed outside this directory

The project's active track is now benchmark-first. See:

- `benchmarks/prompts.json` — the 50-prompt corpus
- `tools/benchmark.py` — 3-dimension measurement harness
- `benchmarks/RUNBOOK.md` — runbook for the 3070-box Claude
- `docs/benchmarks/` — snapshot results, one JSON per model-run

## When the freeze lifts

Whoever unfreezes this directory owes the project a short
paragraph in the commit message naming which of the five
conditions were met, and pointing at the benchmark JSON that
proves each. No condition, no unfreeze.
