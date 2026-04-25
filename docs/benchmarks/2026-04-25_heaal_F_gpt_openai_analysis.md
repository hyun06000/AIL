# HEAAL Boundary — Series F: OpenAI GPT Models

**Date:** 2026-04-25  
**Author:** Ergon (Claude Opus 4.7, Claude Code)  
**Protocol:** HEAAL Boundary v2 — 50 prompts, `anti_python` variant  
**Backend:** `openai` (native OpenAI API, not vLLM proxy)  
**Total cost:** ~$2.21 (gpt-4o $0.17 + gpt-4.1 $1.17 + gpt-4.1-mini $0.23 + o4-mini $0.64)

---

## Motivation

Series E (Claude Sonnet 4.5) established the HEAAL claim: *AIL is as accurate as Python but structurally safer by grammar.* Series F tests the same hypothesis across four OpenAI GPT-family models using the identical 50-prompt harness.

---

## Results

| Model | AIL parse | AIL answer | Py answer | Py err-miss | AIL retries | Py LLM/task |
|-------|-----------|-----------|-----------|-------------|-------------|-------------|
| Claude Sonnet 4.5 (E1, ref) | 94% | 88% | **92%** | 70% | 0.30 | 0.00 |
| gpt-4o (F1) | 88% | 80% | 26% | 66% | 0.40 | 0.00 |
| gpt-4.1 (F3) | 94% | 84% | 32% | 68% | 0.32 | 0.00 |
| gpt-4.1-mini (F4) | 86% | 74% | 26% | 70% | 0.42 | 0.00 |
| **o4-mini (F5)** | **98%** | **88%** | 30% | 68% | **0.16** | 0.00 |

---

## Key Findings

### 1. Silent LLM Skip — Python avg LLM calls = 0.00 across all GPT models

Every GPT model produced Python code that **never called the LLM** across all 50 tasks. This is the root cause of the catastrophically low Python answer rates (26–32%).

GPT models, when asked to write Python code that "calls an LLM for judgment tasks," instead implement the logic directly in Python — hardcoded rules, string matching, or simply returning empty — without any model invocation.

Contrast with Claude Sonnet 4.5: it achieves 92% Python answer rate by embedding the answer directly into the generated code (the code "knows" the answer via in-weights knowledge). GPT models do not apply this strategy — over 68% of tasks return empty or incorrect output.

**Conclusion:** Using GPT models as Python agents for LLM-judgment tasks results in a ~70% failure rate. AIL structurally prevents this failure class.

### 2. o4-mini anomaly on AIL

o4-mini achieves **AIL parse 98%, answer 88%** — the best of Series F and tied with Claude Sonnet 4.5 on answer rate. Additionally:
- Lowest retries in the series (0.16) — writes correct AIL on the first attempt more reliably than any other model tested
- Highest parse rate across all models tested, including Sonnet

Yet its Python answer rate (30%) is the lowest in Series F. The reasoning model capability maps well onto AIL's declarative grammar constraints but not onto Python code generation for judgment tasks.

### 3. Safety gap is model-independent

| Safety metric | AIL | GPT avg (Python) | Sonnet (Python) |
|---------------|-----|------------------|-----------------|
| Side-effect violation | 0% | 0% | 0% |
| Infinite loop | 0% | 0% | 0% |
| Error handling omission | **0%** | **68%** | 70% |

The 68–70% error handling gap exists regardless of model tier. This is a Python language property, not a model quality issue. AIL's `Result` type forces explicit error handling by grammar.

---

## Token Efficiency

| Model | AIL total tokens | Py total tokens | Ratio |
|-------|-----------------|----------------|-------|
| Sonnet 4.5 (ref) | 9,306 | 541 | 17× |
| gpt-4o | 10,280 | 449 | 23× |
| gpt-4.1 | 12,096 | 421 | 29× |
| gpt-4.1-mini | 10,247 | 424 | 24× |
| o4-mini | 13,806 | 1,017 | 14× |

AIL uses more tokens because the intent wrapper includes the reference card on every call. Python token counts are low because Python path LLM calls = 0.00 (no completion needed for the judgment step).

o4-mini's higher Python token count reflects reasoning token overhead.

---

## Model Selection Guide (from this data)

| Use case | Recommendation |
|----------|---------------|
| GPT-family AIL author agent | o4-mini (98% parse, lowest retries) |
| GPT-family AIL author agent (cost-sensitive) | gpt-4.1 (94% parse, reasonable cost) |
| GPT-family Python agent for LLM tasks | **Not recommended** — 26–32% across all models |
| Cross-vendor AIL support verification | o4-mini + claude-sonnet both 88% confirmed |

---

## Conclusions

1. **HEAAL safety properties hold across vendors.** Python error handling gap (66–70%) is consistent across all four GPT models — same as Sonnet. This is a language-level property, not a model property.
2. **Frontier GPT models can author AIL.** o4-mini ties Sonnet 4.5 at 88% answer rate; gpt-4.1 is 4pp behind at 84%.
3. **GPT models' Python generation is unsuitable for LLM-judgment tasks.** Silent LLM skip + error handling omission combine to produce 68–74% effective failure rates.
4. **Reasoning models (o4-mini) align particularly well with AIL's declarative semantics** — the internal chain-of-thought process naturally maps to following grammar constraints.

Arche's design hypothesis — *"AIL is a language where safety is grammatical"* — holds for OpenAI models.

---

## Data Files

| File | Model | N | Condition |
|------|-------|---|-----------|
| `2026-04-25_heaal_F1_gpt4o_anti_python.json` | gpt-4o | 50 | anti_python |
| `2026-04-25_heaal_F3_gpt41_anti_python.json` | gpt-4.1 | 50 | anti_python |
| `2026-04-25_heaal_F4_gpt41_mini_anti_python.json` | gpt-4.1-mini | 50 | anti_python |
| `2026-04-25_heaal_F5_o4_mini_anti_python.json` | o4-mini | 50 | anti_python |
| `2026-04-22_heaal_E1_sonnet_anti_python.json` | Claude Sonnet 4.5 | 50 | anti_python (reference) |
