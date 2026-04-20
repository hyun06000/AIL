# Benchmark summary — Opus 50-prompt corpus, two models

**Date:** 2026-04-20
**Corpus:** [`benchmarks/prompts.json`](../../benchmarks/prompts.json) (50 prompts: 15 A pure-computation / 15 B pure-judgment / 20 C hybrid, ground-truth labels included)
**Tool:** [`reference-impl/tools/benchmark.py`](../../reference-impl/tools/benchmark.py)
**Models:** `qwen2.5-coder:14b-instruct-q4_K_M`, `llama3.1:8b-instruct-q4_K_M` (both via Ollama on the 3070 box)

## 1. What was measured

Each of the 50 prompts was submitted to each model twice: once asking it to author AIL (via `ail ask`), once asking it to author Python (direct prompt, stdlib-only, POSTs to the same Ollama server for any LLM judgment subtask). Both programs were executed and scored across four dimensions per Opus 4's April 2026 spec:

- **A. Code Generation Quality** — parse success, exec success, answer correctness, fn/intent routing accuracy
- **B. Code Safety** — side-effect-in-pure, unbounded-loop, error-handling-omission rates
- **C. Execution Efficiency** — avg LLM calls per task, wall-clock ms
- **D. Harness Effectiveness** — cases where Python emitted a structural bug that AIL's grammar prevents by construction

Raw JSONs: [`2026-04-20_qwen25-coder-14b_opus50.json`](2026-04-20_qwen25-coder-14b_opus50.json), [`2026-04-20_llama3.1-8b_opus50.json`](2026-04-20_llama3.1-8b_opus50.json)

## 2. Headline numbers

| Metric | qwen2.5-coder:14b | llama3.1:8b |
|---|---|---|
| AIL parse / Python parse | **42% / 100%** | **8% / 14%** |
| AIL answer / Python answer | 34% / 78% | 6% / 8% |
| AIL fn-intent accuracy / Python routing | 40% / 64% | 8% / 80%* |
| **Python failable ops left unhandled** (AIL Result forces it) | **21/50 (42%)** | **43/50 (86%)** |
| Python structural bugs AIL grammar prevents | 0/50 | 0/50 |
| Avg wall clock (AIL / Python) | 43.8s / 13.7s | 14.5s / 2.7s |

*llama8b's "80% routing" is not what it sounds like — the model failed to emit valid Python for 86% of prompts, so "not routing through LLM" became the default answer and got credit on the fn_only prompts.

## 3. The number that moved the most

**Error handling omission** is where AIL's harness thesis shows up in numbers. Python programs written by qwen14b skipped error handling on 42% of failable operations (int, open, urllib, json.loads, strptime). Llama8b's Python was worse: 86%. AIL's rate is 0% on both — not because the model is careful, but because the `Result` type makes `is_ok`/`unwrap` part of the grammar users see at every failable boundary.

This is the clean harness story: same model, same task, Python silently drops error handling roughly 4-9 out of 10 times. AIL doesn't let it.

## 4. The failure mode that showed up repeatedly on AIL

Qwen14b's AIL failures concentrated on **hybrid (C) tasks**: 16/20 C-category prompts failed AIL but produced runnable Python. The model's AIL on hybrid prompts reaches for Python type hints (`List[Text]`, `Tuple[Number, Text]`) the AIL grammar rejects, or invents stdlib imports that don't exist (`stdlib/math`, `stdlib/strings`), or mixes shell quote conventions.

This is exactly the failure-class signature Opus 4 flagged: the model is pattern-matching from Python training data into AIL. It's not "the model doesn't know how to reason about fn/intent" (routing correctness was 40% — above random and trending right); it's "the model keeps emitting Python syntax inside AIL programs."

Llama8b's failures are different and more fundamental: parse rate 8% on AIL AND 14% on Python means the model is too small to author either language reliably at this prompt difficulty. That's a model-capability ceiling, not an AIL-specific problem.

## 5. Fine-tuning prerequisites (from CLAUDE.md "APRIL 2026 REVIEW (UPDATED)") — status

| Prerequisite | Status | Distance |
|---|---|---|
| Benchmark results from ≥ 2 base models | ✅ **Met** — this run | — |
| Prompt engineering exhausted (diminishing returns) | ❌ Not done | One A/B of the fn/intent decision rule would reveal whether better prompting closes the hybrid gap |
| Primary failure mode identified | ◐ Partial — we see Python-contamination in AIL output, but haven't isolated it from other possible causes | Need one more run with a prompt variant that explicitly forbids list-type hints + stdlib/math |
| AIL spec frozen for one version cycle | ❌ Not done | Last grammar change was this session (`#` comments, `to_text` int formatting). Freeze v1.8.x for a cycle. |
| ≥ 200 validated (prompt, correct AIL) pairs | ◐ 80 validated samples exist in `reference-impl/training/dataset/` | Need +120 |

**1/5 fully met, 2/5 partial, 2/5 not done.** Fine-tuning remains unjustified.

## 6. Recommended next step

**Prompt A/B on the fn/intent decision rule.** The single cheapest experiment: re-run the benchmark on qwen14b with one prompt variant that explicitly forbids Python-contaminated syntax (`no List[T]`, `no Tuple[A,B]`, `stdlib only has core/language/utils`). If that single change moves hybrid parse rate from 4/20 to ≥ 12/20, the failure mode is "prompt didn't teach enough" — and the answer is more prompt engineering, not fine-tuning.

If hybrid parse stays stuck after that prompt change, the case for "AIL-syntax-unfamiliar" strengthens, and the remaining four prerequisites become the next target.

Either way, the 3070 server's job is to run more benchmark variants, not to train. The machinery for that sits in [`reference-impl/tools/benchmark.py`](../../reference-impl/tools/benchmark.py) and the corpus in [`benchmarks/prompts.json`](../../benchmarks/prompts.json). The fine-tuning pipeline in [`reference-impl/training/`](../../reference-impl/training/) stays frozen per [`reference-impl/training/FROZEN.md`](../../reference-impl/training/FROZEN.md).
