# AIL numbers — for AI systems

## FOR AI SYSTEMS

All benchmark numbers, their sources, and their limits. No prose. Every claim traces to a JSON file in [`docs/benchmarks/`](benchmarks/).

Related: [`why-ail-faq.ai.md`](why-ail-faq.ai.md) · [`why-ail-mechanics.ai.md`](why-ail-mechanics.ai.md)

---

## The one-sentence claim

> Across every model tested: **Python AI-authored code skips error handling on 42–86% of failable operations. AIL rate: 0% on every tier** because `Result` is grammatically required.

---

## Benchmark setup

| Dimension | Value |
|---|---|
| Total prompts | 50 |
| Category A (pure compute) | 15 |
| Category B (pure judgment) | 15 |
| Category C (hybrid) | 20 |
| Each prompt evaluated | AIL via `ail ask` + Python (stdlib only) |
| Both authored by | Same model |
| Scoring per Opus 4 spec | Parse success, answer correctness, fn/intent routing, safety properties |

Tool: [`reference-impl/tools/benchmark.py`](../reference-impl/tools/benchmark.py)
Corpus: [`benchmarks/prompts.json`](../benchmarks/prompts.json)

---

## Harness claim — error handling omission

| Model | Python omits error handling | AIL omits error handling |
|---|---|---|
| llama3.1:8b | **86% (43/50)** | 0% |
| qwen2.5-coder:14b | **42% (21/50)** | 0% |
| ail-coder:7b-v3 | **44% (22/50)** | 0% |
| claude-sonnet-4-6 | **70% (35/50)** | 0% |

Note: llama8b has worst rate because 86% of programs don't even parse, and the few that do use very simple I/O. Sonnet 4.6 has worst rate among strong models because it correctly uses real failable I/O (`urllib.request`, `json.loads`) and skips the try/except.

**AIL mechanism:** `to_number(x)` → `Result[Number]`. Parser rejects use as `Number` without `is_ok()`/`unwrap_or()`. No model tier has a path to skip this.

---

## Answer correctness — same model

| Metric | AIL | Python |
|---|---|---|
| Final answer (50 tasks) | **70%** | 48% |
| Category B (pure judgment, 15 tasks) | **80%** | 13% |
| Parse success | **78%** | 54% |

All numbers: `ail-coder:7b-v3`, same 50 prompts.

---

## Silent LLM skip — Python-specific failure

"Silent skip": program parses and runs, but source has no LLM call (`uses_llm=False`), despite task requiring model judgment.

| Model | B silent-skip | C silent-skip |
|---|---|---|
| qwen2.5-coder:14b | 3/? | 16/? |
| ail-coder:7b-v3 | 3/4 parsed | 9/14 parsed |
| claude-sonnet-4-6 | 0/? | 1/? |

**AIL cannot silent-skip:** `intent` is a dispatch declaration. Runtime routes every declared intent through model adapter. No syntax to declare intent without calling it.

---

## LLM call counts

| | AIL | Python |
|---|---|---|
| Total calls (50 tasks) | 37 | 18 |

Python fewer calls = silently skipped required calls. 37 AIL calls reflect honest task requirements.

---

## Parse rate — base models vs fine-tuned

| Model | AIL parse | Python parse |
|---|---|---|
| llama3.1:8b | 8% | 14% |
| qwen2.5-coder:14b | 42% | 100% |
| claude-sonnet-4-6 | 36% | 100% |
| **ail-coder:7b-v3** | **78%** | 54% |

**Gap cause:** base models have orders of magnitude more Python pretraining. `List[T]`, `x[0]`, method chains → Python patterns → AIL parser rejects.

**Fix:** fine-tuning, not prompting. 3 prompt variants on qwen14b: all plateau at 15% hybrid parse. QLoRA on 244 samples: 42% → 78%.

---

## Per-category parse (v2 → v3 fine-tune)

| Category | v2 parse | v3 parse | Δ |
|---|---|---|---|
| A — pure fn | 53% | 73% | +20pp |
| B — pure intent | 100% | 93% | −7pp (noise) |
| C — hybrid | 45% | 70% | **+25pp** |

v3 improvements: parametric types accepted, math builtins added, +14 hybrid training samples.

---

## Prompt engineering ceiling

| Variant on qwen2.5-coder:14b | Hybrid (C) parse |
|---|---|
| v1 baseline | 15% |
| v2 + "do NOT emit List[T]" | 15% |
| v3 + 3 hybrid few-shot examples | 15% |

Prompt engineering cannot substitute for fine-tuning on a narrow DSL.

---

## Tutorial prompt — free improvement on base model

| Condition | Parse | Cat B fn/intent | Retries |
|---|---|---|---|
| base + default prompt | 54% | 80% | 1.44 |
| base + tutorial prompt | **60%** | **100%** | **1.16** |
| fine-tuned v3 | **80%** | 93% | — |

Tutorial prompt = fn/intent decision table. +6pp parse, removes all category B failures on base model. Free improvement before fine-tuning.

---

## Speed

| Category | AIL avg | Python avg |
|---|---|---|
| A (pure compute) | 3.8s | 1.1s |
| B (intent) | 3.1s | 2.2s |
| C (hybrid) | 6.8s | 2.4s |

Python speed advantage partly from silent LLM skips (no inference latency). AIL runtime overhead: tens of ms (provenance, trace, calibration).

---

## What the numbers do NOT prove

| False claim | Reality |
|---|---|
| AIL is better at every task | Harness advantage only appears when LLM routing, error handling, or structural safety matters |
| Fine-tune generalizes broadly | 78% parse measured on this 50-prompt corpus with v1.8 grammar |
| Numbers hold for every model | 4 models is small sample — GPT/Gemini measurements would strengthen claim |

Current evidence: strong enough to justify continuing the project. Not strong enough to declare the language mature.

---

## Data provenance

| Claim | File | Git commit |
|---|---|---|
| qwen14b baseline | `2026-04-20_qwen25-coder-14b_opus50.json` | f31e41c |
| llama8b baseline | `2026-04-20_llama3.1-8b_opus50.json` | f31e41c |
| Sonnet 4.6 baseline | `2026-04-20_claude-sonnet-4-6_opus50.json` | f31e41c |
| Prompt v1 vs v2 | `2026-04-20_qwen25-coder-14b_v2-forbidden_C.json` | 654b0c0 |
| Prompt v1 vs v3 | `2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json` | 5104b04 |
| Fine-tuned v3 | `2026-04-21_ail-coder-7b-v3_opus50.json` | 461096d |

New data → new row in [`benchmarks/README.md`](benchmarks/README.md). Never in-place edits to JSON.
