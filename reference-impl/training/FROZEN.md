# 🔥 This directory is no longer frozen — 2026-04-20

The fine-tuning pipeline under `reference-impl/training/` was paused
while Opus 4's five preconditions were being worked. As of
2026-04-20 all five hold. Training is the active track.

Proof for each condition:

1. **≥ 2 base models benchmarked** — 3 done: `llama3.1:8b`,
   `qwen2.5-coder:14b`, `claude-sonnet-4-6`. JSON snapshots in
   [`../../docs/benchmarks/`](../../docs/benchmarks/).
2. **Prompt engineering exhausted** — v1/v2/v3 A/B all plateau on
   qwen14b; see
   [`2026-04-20_prompt_ab_v3_analysis.md`](../../docs/benchmarks/2026-04-20_prompt_ab_v3_analysis.md).
3. **Primary failure mode identified** — Python-distribution
   contamination of the author model. Same shape across llama8b,
   qwen14b, Sonnet 4.6; argument in
   [`2026-04-20_claude_sonnet46_summary.md`](../../docs/benchmarks/2026-04-20_claude_sonnet46_summary.md).
4. **AIL spec frozen for one cycle** — v1.8 frozen 2026-04-20,
   policy in [`../../spec/09-stability.md`](../../spec/09-stability.md).
5. **≥ 200 validated (prompt, AIL) pairs** — 205 today in
   [`dataset/`](dataset/).

What to do now: see [`HANDOFF.md`](HANDOFF.md) for the training
command, 3070-box-specific flags, the known save-time OOM gotcha,
and the post-run benchmark step.

The 2026-04-20-and-before "frozen" content of this file is
preserved in git history; retrieve it with
`git log --diff-filter=D -- reference-impl/training/FROZEN.md`
if you need the original text.
