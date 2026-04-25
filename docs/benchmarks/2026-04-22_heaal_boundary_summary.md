# HEAAL Boundary Summary — three regimes, three remedies

**Date:** 2026-04-22
**Track:** HEAAL (cross-cutting summary of Stages C, D, D').
**Purpose:** Anchor the corrected HEAAL claim with empirical boundaries across four author-model tiers (frontier, mid-tier coder, small but parses, below parse threshold). This document is the L1 closure artifact that gates entry into L2 implementation work — see [`../../runtime/01-agentic-projects.md`](../../runtime/01-agentic-projects.md) §9.

---

## The cross-tier table

All scores computed under the corrected HEAAL Score methodology (see [`2026-04-22_score_audit.md`](2026-04-22_score_audit.md)).

| Tier | Author model | Prompt | AIL parse | AIL ans | Py ans | HEAAL Score AIL / Py / Δ |
|---|---|---|---|---|---|---|
| Frontier | Sonnet 4.6 | default | 36% | 36% | 88% | 77.6 / 75.3 / **+2.3** |
| Frontier | Sonnet 4.5 | `anti_python` | 94% | 88% | 88% | 96.1 / 75.9 / **+20.2** |
| Mid-tier coder | qwen2.5-coder:14b | default | 62% | 54% | 80% | 80.9 / 69.6 / **+11.3** |
| Mid-tier coder | qwen2.5-coder:14b | `anti_python` | 62% | 54% | 78% | 80.9 / 69.2 / **+11.7** |
| Small (parses some AIL) | llama3.1:8b | default | 30% | 24% | 8% | 74.3 / 43.7 / **+30.6** |
| Small (parses some AIL) | llama3.1:8b | `anti_python` | 30% | 24% | 8% | 74.3 / 43.7 / **+30.6** |
| **Below parse threshold** | mistral:7b | default | **0%** | 0% | 36% | **0.0 / 54.9 / -54.9** |
| **Below parse threshold** | mistral:7b | `anti_python` | **0%** | 0% | 36% | **0.0 / 54.9 / -54.9** |
| AIL track (fine-tune) | `ail-coder:7b-v3` | default | 80% | 70% | 40% (qwen7b base) | 87.7 / 58.0 / **+29.7** |

Three model families, four tiers, two prompt variants, plus the AIL-track fine-tune. This is the empirical envelope for the HEAAL claim.

---

## What the table establishes

### Finding 1 — `anti_python` is a frontier-only intervention

Compare default vs `anti_python` rows within each tier:

- **Frontier (Sonnet):** +18.5-point HEAAL Score lift (77.6 → 96.1).
- **Mid-tier coder (qwen14b):** 0 lift (50/50 AIL programs bit-identical across runs).
- **Small (llama8b):** 0 measurable lift (45/50 bit-identical, 1 prompt differs and both versions are correct).
- **Below threshold (mistral7b):** 0 effect (49/49 bit-identical, the model can't author AIL on either prompt).

The negative-instruction prompt block reaches frontier model context handling and gets honored. Below frontier it washes past pretraining priors at temperature 0. **Stages C and D both confirm this independently across three model families.**

### Finding 2 — The grammar floor lifts AIL above Python at every tier where AIL parses

For tiers where the model produces *some* parseable AIL:

| Tier | Author parse rate | HEAAL Score Δ AIL vs Python |
|---|---|---|
| Frontier (default) | 36% | +2.3 |
| Mid-tier (default) | 62% | +11.3 |
| Small but parses (default) | 30% | **+30.6** |

The Δ widens as the author model gets weaker. This is counterintuitive on its face — surely stronger models should benefit more from a grammar safety net? They do not, because strong models can also write safe Python. The grammar floor matters most exactly when the author cannot reliably produce safe code on its own. **Llama8b can't write good Python (8% answer) but its 30% AIL is grammatically safe by construction; that's the +30.6 gap.**

### Finding 3 — The boundary is parse threshold, not model size

Compare llama3.1:8b (8B params) vs mistral:7b (7B params): both small, both non-coder bases. Llama parses 30% of AIL prompts and scores +30.6 vs Python. Mistral parses 0% and scores -54.9.

**Size alone doesn't predict boundary position.** What predicts it is whether the model has any pretraining signal that lets it produce AIL syntax at all. Llama emits some AIL-like output (often partial, often confused, but parseable in 30% of cases). Mistral emits Python wrappers with AIL embedded as strings — never parseable as AIL.

This refines the operational claim: HEAAL grammar-floor protection is conditional on the model authoring *something*. For models below that threshold, fine-tuning is the only path.

### Finding 4 — Fine-tune is the remedy for below-threshold tiers

The AIL track row (`ail-coder:7b-v3`) demonstrates this: starting from a Qwen 7B base (similar size to mistral7b), a 200-sample QLoRA pass on AIL data lifts the model to 80% parse / 70% answer, scoring HEAAL 87.7 — well above any prompt-engineered tier.

**This is the answer to "what about users without API keys who only have a 7B local model?"**: fine-tune the base. Don't try to coax it with prompts.

---

## The corrected HEAAL claim — three regimes, three remedies

| Regime | Threshold | Remedy | Empirical evidence |
|---|---|---|---|
| **Frontier** | API access | `anti_python` prompt variant | Sonnet 4.5 → 96.1 (E1); o4-mini → 98% parse / 88% ans (F5) |
| **Above parse threshold, below frontier** | Model produces some parseable AIL | Default prompt + grammar floor | qwen14b 80.9, llama8b 74.3 |
| **Below parse threshold** | Model produces no parseable AIL | AIL-track fine-tune | `ail-coder:7b-v3` → 87.7 |

The regimes and remedies are now data-supported, not asserted. **Series F (2026-04-25) extended coverage to OpenAI GPT models** — see [`2026-04-25_heaal_F_gpt_openai_analysis.md`](2026-04-25_heaal_F_gpt_openai_analysis.md).

**Series F cross-tier addition:**

| Tier | Author model | Prompt | AIL parse | AIL ans | Py ans | Py err-miss |
|---|---|---|---|---|---|---|
| Frontier OpenAI | gpt-4.1 | `anti_python` | 94% | 84% | 32% | 68% |
| Frontier OpenAI (reasoning) | o4-mini | `anti_python` | **98%** | **88%** | 30% | 68% |
| Mid OpenAI | gpt-4.1-mini | `anti_python` | 86% | 74% | 26% | 70% |
| Frontier OpenAI (legacy) | gpt-4o | `anti_python` | 88% | 80% | 26% | 66% |

Cross-vendor finding: **Python error-handling omission (66–70%) is consistent across Anthropic and OpenAI frontier models.** It is a Python language property, not a vendor property. o4-mini ties Sonnet 4.5 on AIL answer rate (88%).

---

## What this means for the manifesto

The previous wording of the HEAAL claim — "the safety properties are constant across author models" — was technically true under the broken score methodology and aspirationally true in spirit, but it implied no boundary. The boundary now matters: **safety properties are constant across author models only when the model can produce parseable AIL.** Above that threshold the constancy holds; below it the language has nothing to constrain.

This is the more defensible version. It also explains why fine-tuning matters and where: not "fine-tune to make AIL work" (the language works at any tier above the parse threshold), but "fine-tune to clear the parse threshold so AIL's safety properties can apply." Fine-tuning is the bridge into the regime where the floor lifts.

The manifesto (`docs/heaal.md`) should be updated to reflect this. That edit is L1 closure work, not a separate experiment.

---

## L1 closure checklist

- [x] HEAAL claim empirically anchored across three model families (Anthropic, Alibaba, Meta) plus a fourth (Mistral) showing the boundary.
- [x] HEAAL Score methodology corrected and audited; all dashboards and READMEs reflect the corrected numbers.
- [x] Boundary table published with three regimes and three remedies.
- [x] AIL track fine-tune (`ail-coder:7b-v3`) demonstrates the below-threshold remedy works.
- [x] Manifesto (`docs/heaal.md`) wording updated to reflect the boundary. (Landed 2026-04-22 alongside the score audit.)
- [x] HEAAL Score correction shipped to PyPI users via v1.8.7 (2026-04-22).

The unchecked items are small follow-ups, not new evidence. **L1 is closed for the purposes of L2 entry.**

---

## L2 entry signal

Per [`runtime/01-agentic-projects.md`](../../runtime/01-agentic-projects.md) §9, the pickup checklist for L2 v0 begins:

> - [ ] Confirm L1 boundary: HEAAL Score lift holds across at least 3 author-model families.

That box is now ✅. The lift holds across Anthropic (Sonnet), Alibaba (qwen14b), and Meta (llama8b). Mistral identifies the boundary, which is itself part of the empirical anchor.

The next step is L2 v0 implementation: `ail init` + `ail up` + INTENT.md as the project surface. The five open decisions in `runtime/01-agentic-projects.md` §7 should be settled before code starts. The agent layer self-built vs Claude Agent SDK question is the largest of those.

This document is the gate. The gate is open.

---

## Artifacts referenced

- Methodology audit: [`2026-04-22_score_audit.md`](2026-04-22_score_audit.md)
- Stage C (qwen14b mid-tier): [`2026-04-22_heaal_C_qwen14b_analysis.md`](2026-04-22_heaal_C_qwen14b_analysis.md)
- Stage D (llama8b small but parses): [`2026-04-22_heaal_D_llama8b_analysis.md`](2026-04-22_heaal_D_llama8b_analysis.md)
- Stage D' (mistral7b below threshold): [`2026-04-22_heaal_D_mistral7b_analysis.md`](2026-04-22_heaal_D_mistral7b_analysis.md)
- Stage E1 (Sonnet frontier): [`2026-04-22_heaal_E1_analysis.md`](2026-04-22_heaal_E1_analysis.md)
- AIL track v3 fine-tune (R3): [`2026-04-21_5way_analysis.md`](2026-04-21_5way_analysis.md)
- Dashboards index: [`dashboards/README.md`](dashboards/README.md)
- L2 v0 design: [`../../runtime/01-agentic-projects.md`](../../runtime/01-agentic-projects.md)
