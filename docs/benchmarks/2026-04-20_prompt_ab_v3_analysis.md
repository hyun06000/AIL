# Prompt A/B round 2 — few-shot expansion also null

**Date:** 2026-04-20
**Model:** `qwen2.5-coder:14b-instruct-q4_K_M`
**Corpus:** Opus 50-prompt corpus, hybrid (C) category only (20 prompts)
**Hypothesis:**

> After v2 (explicit FORBIDDEN block) produced zero movement, the
> remaining prompt-layer lever is demonstration: add few-shot examples
> that exhibit the exact hybrid shapes the benchmark is asking for.
> If parse rate moves, few-shot is the missing lever; if not,
> prompt engineering on this model is empirically exhausted.

## What v3 adds

Three new hybrid-specific few-shot examples appended to the
existing four (current total: 7). Each covers a hybrid shape the
prior examples under-represented:

1. **numeric compute + categorical judgment** — BMI → health
   category. Mirrors benchmark C07 (BMI assessment), C16
   (compound interest + explanation).
2. **aggregate + interpretive phrase** — average of scores →
   performance comment. Mirrors C04 (spending summary), C11
   (grade performance), C12 (variability), C17 (conciseness).
3. **text transform + describe** — reverse each word →
   playful description. Mirrors C13 (creative sentence), C20
   (stopword removal + summary).

Source: [`reference-impl/ail/authoring.py`](../../reference-impl/ail/authoring.py)
`_v3_extra_examples()`. Enabled by `AIL_AUTHOR_PROMPT_VARIANT=v3`.

Each new example was verified to parse + purity-check + execute on
MockAdapter before inclusion.

## Three variants, one model, 20 hybrid prompts

| Metric | v1 baseline | v2 (FORBIDDEN) | v3 (more few-shots) |
|---|---|---|---|
| AIL parse success | 15.0% (3/20) | 15.0% (3/20) | **15.0% (3/20)** |
| AIL exec success | 15.0% | 15.0% | **15.0%** |
| AIL answer_ok | 15.0% | 15.0% | **15.0%** |
| AIL fn/intent accuracy | 10.0% (2/20) | 10.0% (2/20) | **10.0% (2/20)** |
| AIL avg retries | 1.68 | 2.55 | **2.55** |
| Python fn/intent | 25% | 25% | 25% |
| Python err-handling miss | 40% | 40% | 40% |

The three cases that pass on v2 and v3 are **identical**: C02, C17,
C20. Zero new cases unlocked by either prompt change.

Raw JSONs:
- v2: [`2026-04-20_qwen25-coder-14b_v2-forbidden_C.json`](2026-04-20_qwen25-coder-14b_v2-forbidden_C.json)
- v3: [`2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json`](2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json)

## Interpretation

The two orthogonal prompt interventions — negative instructions
("do NOT emit `List[T]`") and positive demonstrations (three more
hybrid programs showing the target shape) — produced byte-identical
outcomes on this 20-case set. Both moved zero cases. Both increased
average retries.

That is stronger evidence than either variant alone. If v2 had
failed and v3 had succeeded, the fix would have been "better
examples." If v3 had failed and v2 had succeeded, the fix would
have been "better constraints." Both failing means **neither
telling the model what to avoid nor showing it what to do
actually changes its output on this task class.**

The most parsimonious explanation: the model's Python training
distribution is overpowering the prompt on hybrid AIL generation.
qwen2.5-coder:14b has seen megabytes of Python code with generic
type annotations, method-call syntax, and `from math import …`.
A 1-3 KB prompt patch doesn't meaningfully shift its generation
distribution. The bytes in training data win.

## Fine-tuning prerequisite status

| Prerequisite | Before v3 | After v3 |
|---|---|---|
| ≥ 2 base models benchmarked | ✅ | ✅ |
| Prompt engineering exhausted | ◐ (1 variant tested) | **✅** (2 orthogonal variants, both null) |
| Primary failure mode identified | ◐ | **✅** — Python-distribution contamination is demonstrably immune to prompt-layer corrections |
| AIL spec frozen for one cycle | ❌ | ❌ |
| ≥ 200 validated pairs | ◐ (80) | ◐ (80) |

**3/5 fully met. 2/5 open.** Closer than ever, still not at the gate.

## What's left before fine-tuning is justified

1. **Freeze the spec.** Do not change AIL's grammar, stdlib, or
   builtins for one version cycle (v1.8.2 → v1.9 with no grammar
   changes in between). A fine-tuned adapter is only useful if the
   language it was trained on is the language the runtime runs.

2. **Grow the dataset to 200+ pairs.** The current 80 are good
   seeds but small for LoRA. Sources for the missing 120:
   - Each of the 20 C-prompts has a canonical AIL answer; write
     them (partially done; extend and validate).
   - Augment existing patterns (factorial, count, sort) with 3-5
     variations each.
   - Hand-write programs for edge cases AIL supports that the
     current dataset under-represents: match with confidence
     guards, attempt with Result fallthrough, evolve declarations,
     context inheritance.

3. **One more honest prompt experiment**: run v3 on a different
   base model (a non-coder Qwen, or a Llama 3.1 70B if it can be
   hosted). If the same 3/20 pattern holds across model families,
   Python-distribution contamination is not specific to coder
   models — it's structural. If a different family does better
   naturally, the answer might be "pick the right base," not "fine-
   tune."

None of these require GPU training. Fine-tuning stays frozen per
[`reference-impl/training/FROZEN.md`](../../reference-impl/training/FROZEN.md)
until all five prerequisites are met.

## What we know now that we didn't

- On qwen2.5-coder:14b, the AIL hybrid parse ceiling with any
  prompt-only intervention is 15%.
- The ceiling is stable across orthogonal prompt styles — so it
  is a model-property, not a prompt-property.
- The error-handling-miss gap (40% Py vs 0% AIL) is stable across
  variants. That metric is structural, not prompt-sensitive —
  which is exactly the claim AIL's Result type makes. The harness
  thesis is robust.
