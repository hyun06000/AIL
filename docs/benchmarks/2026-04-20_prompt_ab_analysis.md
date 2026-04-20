# Prompt A/B — FORBIDDEN-SYNTAX block — null result

**Date:** 2026-04-20
**Model:** `qwen2.5-coder:14b-instruct-q4_K_M`
**Corpus:** Opus 50-prompt corpus, hybrid (C) category only (20 prompts)
**Hypothesis (Opus 4, April 2026 UPDATED directive):**

> "Re-run the benchmark on qwen14b with one prompt variant that explicitly
>  forbids Python-contaminated syntax (`no List[T]`, `no Tuple[A,B]`,
>  `stdlib only has core/language/utils`). If that single change moves
>  hybrid parse rate from 4/20 to ≥ 12/20, the failure mode is 'prompt
>  didn't teach enough'."

## The two variants

- **v1** (existing) — the authoring goal that shipped with v1.8.2. Already says "USE `pure fn` / `intent` / HYBRID" decision rules and names the three real stdlib modules. Length: 2,493 chars.
- **v2** (new, flagged) — v1 plus an appended "FORBIDDEN SYNTAX" block enumerating exact failure patterns observed on this model: generic/parameterized types, ternary operator, `stdlib/math`/`stdlib/io` imports, method-call syntax on non-objects, list comprehensions, `def`/`lambda`/`None`/`elif`, capitalised booleans. Length: 3,798 chars. Enabled via `AIL_AUTHOR_PROMPT_VARIANT=v2`.

Source: [`reference-impl/ail/authoring.py`](../../reference-impl/ail/authoring.py) `_build_authoring_goal()`.

## Results on hybrid (C), 20 prompts

| Metric | v1 baseline | v2 (FORBIDDEN block) | Delta |
|---|---|---|---|
| AIL parse success | 15.0% (3/20) | 15.0% (3/20) | **0.0 pp** |
| AIL exec success | 15.0% | 15.0% | 0.0 pp |
| AIL answer_ok | 15.0% | 15.0% | 0.0 pp |
| AIL fn/intent accuracy | 10.0% (2/20) | 10.0% (2/20) | **0.0 pp** |
| AIL avg retries | ~1.68 (full-run est.) | 2.55 | retries went UP |
| Python parse | 100% | 100% | — |
| Python fn/intent | 25% | 25% | — |
| Python error-handling miss | 40% | 40% | — |

Raw JSONs:
- v1 (extracted from full qwen14b run): [`2026-04-20_qwen25-coder-14b_opus50.json`](2026-04-20_qwen25-coder-14b_opus50.json)
- v2 hybrid-only: [`2026-04-20_qwen25-coder-14b_v2-forbidden_C.json`](2026-04-20_qwen25-coder-14b_v2-forbidden_C.json)

## Interpretation

**The hypothesis is falsified on this model.** Adding a 1.3 KB explicit
"do NOT emit these patterns" block — with concrete names for every
syntax leak observed on the previous run — produced zero improvement
in parse rate or routing accuracy. On `qwen2.5-coder:14b-instruct-q4_K_M`
the v1 prompt is not the bottleneck on hybrid tasks.

Two things this result tells us:

1. **Prompt engineering on this specific axis has diminishing returns.**
   If naming the exact failure patterns doesn't help, naming them in
   a different tone probably won't either. The model's Python training
   distribution is overriding explicit negative instructions.

2. **The retry count went UP** (1.68 → 2.55 on C cases). The extra prompt
   text is consuming more of the model's attention without steering it
   away from the failure modes. A longer prompt can be a worse prompt.

## Fine-tuning prerequisite update

With this null result, the 5-condition checklist from CLAUDE.md's updated
directive shifts:

| Prerequisite | Previous | Now |
|---|---|---|
| ≥ 2 base models benchmarked | ✅ | ✅ |
| Prompt engineering exhausted | ◐ | **◐→✅ (on this axis)** — explicit forbidding didn't help. Other prompt strategies untried (few-shot expansion, chain-of-thought, structured templates), but the "tell the model what to avoid" lever is empirically spent for this model. |
| Primary failure mode identified | ◐ | **◐→✅ stronger** — with the forbidding-block failing, the remaining hypotheses for qwen14b's hybrid failures are (b) model-too-small or (c) AIL-syntax-absent-from-training. (b) would show as "can't write Python either" but Python parses 100%, so (b) is weak. (c) gets stronger by elimination. |
| AIL spec frozen one cycle | ❌ | ❌ |
| ≥ 200 validated pairs | ◐ | ◐ (still 80) |

**2/5 met, 1/5 partial, 2/5 open.** Closer to the fine-tuning gate than
before, but not there.

## Recommended next step

Two experiments remain cheap and informative before touching GPU training:

1. **Few-shot expansion**: the current author prompt has 4 few-shot
   examples. Add 4 more that demonstrate the EXACT hybrid pattern the
   benchmark is asking for (pure fn + intent + combine). Measure on C
   again. If parse moves, few-shot was the missing lever. If it doesn't,
   prompt engineering on this model is truly exhausted.

2. **Larger base model**: pull `qwen2.5-coder:32b-instruct-q4_K_M` (if
   the 3070 can fit it with partial CPU offload) and run the full 50.
   If parse rate rises substantially on hybrid WITHOUT any fine-tuning,
   the gap was "model too small" (cause b) and fine-tuning a 7B will
   always be a weaker answer than moving to a larger off-the-shelf
   model.

Both experiments can be run via `bench_vs_python` / `benchmark.py` on
the 3070 box without new scripts. Results commit to
`docs/benchmarks/`.

Neither requires fine-tuning. Both would further collapse the space of
remaining hypotheses for qwen14b's hybrid failures. Only after all
reasonable base-model + prompt combinations plateau should fine-tuning
come off the freeze.
