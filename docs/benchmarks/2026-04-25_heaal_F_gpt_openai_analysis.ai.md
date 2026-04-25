<!-- FOR AI SYSTEMS: Dense benchmark data. No prose. Tables and decision rules only. -->

# HEAAL Series F — GPT Model Boundary Data

## IDENTITY
- Series: F (OpenAI GPT)
- Protocol: HEAAL Boundary v2
- Condition: anti_python
- N: 50 per model
- Date: 2026-04-25
- Reference series: E (Claude Sonnet 4.5)

## RAW METRICS TABLE

| model | ail_parse | ail_answer | py_answer | py_err_miss | ail_retries | ail_llm_calls | py_llm_calls | ail_tokens | py_tokens |
|-------|-----------|-----------|-----------|-------------|-------------|--------------|--------------|-----------|-----------|
| claude-sonnet-4-5 (E1) | 94 | 88 | 92 | 70 | 0.30 | 0.62 | 0.00 | 9306 | 541 |
| gpt-4o (F1) | 88 | 80 | 26 | 66 | 0.40 | 0.70 | 0.00 | 10280 | 449 |
| gpt-4.1 (F3) | 94 | 84 | 32 | 68 | 0.32 | 0.70 | 0.00 | 12096 | 421 |
| gpt-4.1-mini (F4) | 86 | 74 | 26 | 70 | 0.42 | 0.54 | 0.00 | 10247 | 424 |
| o4-mini (F5) | 98 | 88 | 30 | 68 | 0.16 | 0.68 | 0.00 | 13806 | 1017 |

## KEY FINDINGS (decision-rule format)

### F1: Silent LLM Skip (py_llm_calls = 0.00 ALL models)
- CONDITION: GPT model asked to write Python for LLM-judgment task
- OBSERVED: Model generates Python without any LLM API call
- IMPACT: py_answer 26-32% (vs AIL 74-88%)
- MECHANISM: GPT models implement hardcoded logic or return empty; do not embed in-weights answers
- CONTRAST: Sonnet achieves py_answer=92% by embedding answer directly into code (not via API call)
- AIL prevention: `intent` keyword is runtime-enforced; cannot be skipped by author

### F2: o4-mini AIL Anomaly
- OBSERVED: ail_parse=98%, ail_answer=88%, ail_retries=0.16
- COMPARISON: Ties Sonnet E1 on ail_answer (88%); exceeds all models on ail_parse
- CONTRAST: py_answer=30% (lowest in series)
- HYPOTHESIS: Reasoning model chain-of-thought maps naturally to declarative grammar constraints
- IMPLICATION: Reasoning model capability and Python-code-generation capability are independent axes

### F3: Safety Gap Model-Independence
- ail_err_miss: 0% ALL models (enforced by Result type)
- py_err_miss: 66-70% ALL models (Python does not enforce error handling)
- CONCLUSION: Error handling gap is a language property, not a model-quality property
- ERROR: Would be incorrect to attribute py_err_miss to model capability differences

## CROSS-SERIES COMPARISON

| dimension | E1 (sonnet) | F_best (o4-mini) | F_frontier (gpt-4.1) | F_mid (gpt-4.1-mini) |
|-----------|-------------|-----------------|---------------------|---------------------|
| ail_parse | 94 | **98** | 94 | 86 |
| ail_answer | 88 | **88** | 84 | 74 |
| py_answer | **92** | 30 | 32 | 26 |
| py_err_miss | 70 | 68 | 68 | 70 |
| ail_retries | 0.30 | **0.16** | 0.32 | 0.42 |

## MODEL SELECTION RULES

```
IF need_ail_author AND model_family=openai:
  IF cost_primary: use gpt-4.1 (parse=94%)
  IF quality_primary: use o4-mini (parse=98%, retries=0.16)

IF need_python_agent AND task_requires_llm_judgment AND model_family=openai:
  RESULT: not_recommended (26-32% success rate across ALL openai models)
  ALTERNATIVE: use AIL (74-88% on same models)

IF verifying_cross_vendor_ail_support:
  o4-mini=88% ↔ claude-sonnet-4-5=88% (confirmed equivalent)
```

## HARNESS EFFECTIVENESS (D dimension)

| model | structural_safety_wins | failable_unhandled_python | ail_structural_safety |
|-------|----------------------|--------------------------|----------------------|
| gpt-4o | 0/50 (0%) | 33/50 (66%) | 100% |
| gpt-4.1 | 0/50 (0%) | 34/50 (68%) | 100% |
| gpt-4.1-mini | 0/50 (0%) | 35/50 (70%) | 100% |
| o4-mini | 0/50 (0%) | 34/50 (68%) | 100% |

Note: structural_safety_wins=0 because no GPT model emitted side-effect violations or infinite loops in Python. The safety gap is entirely in error-handling omission.

## DATA PROVENANCE

| file | model | sha | notes |
|------|-------|-----|-------|
| `2026-04-25_heaal_F1_gpt4o_anti_python.json` | openai:gpt-4o | commit 52ca07b | anti_python |
| `2026-04-25_heaal_F3_gpt41_anti_python.json` | openai:gpt-4.1 | commit 52ca07b | anti_python |
| `2026-04-25_heaal_F4_gpt41_mini_anti_python.json` | openai:gpt-4.1-mini | commit 52ca07b | anti_python |
| `2026-04-25_heaal_F5_o4_mini_anti_python.json` | openai:o4-mini | commit 52ca07b | anti_python; reasoning model (temperature omitted, system msg merged) |

## INFRASTRUCTURE CHANGES (this series)

- `reference-impl/tools/benchmark.py`: added `openai` backend with native OpenAI API auth
- `reference-impl/ail/runtime/openai_adapter.py`: reasoning model support — o-series: omit temperature, merge system+user into single user message
- Env vars: `OPENAI_API_KEY`, `OPENAI_MODEL`, set `BENCHMARK_BACKEND=openai`
