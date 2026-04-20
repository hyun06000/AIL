# Benchmarks — AIL vs Python + LLM SDK

This directory holds periodic snapshots of the head-to-head benchmark
comparing AIL to the "Python + direct-HTTP LLM call" baseline.

The benchmark lives at
[`reference-impl/tools/bench_vs_python.py`](../../reference-impl/tools/bench_vs_python.py).
For a single task it:

1. Asks the same LLM model to write an **AIL** program (via `ail ask`).
2. Asks the same model to write a **Python** program — stdlib only, any
   judgment subtask is a direct `urllib.request` POST to the Ollama
   server — then executes it in a subprocess.

It scores each side on three independent axes:

| Axis | Meaning |
|---|---|
| **parse** | Did the program actually run? |
| **route** | Did it call the LLM when the task needed judgment (intent) and skip the LLM when it didn't (fn)? |
| **answer** | For `pure_fn` tasks only — is the output numerically/textually correct? |

The "route" axis is the important one. Every Python solution that
hardcodes a heuristic (e.g. `if "love" in words: return "positive"`)
gets **parse ✓ / route ✗**: it runs, it prints something, but the
author silently replaced a required LLM judgment with a brittle
keyword lookup. This is exactly the failure mode AIL was designed to
structurally prevent — and it shows up in the numbers.

---

## Running one

```bash
export AIL_OLLAMA_HOST=http://your.ollama.host:11434
export AIL_OLLAMA_MODEL=<model_name>
export AIL_OLLAMA_TIMEOUT_S=600

cd reference-impl
python tools/bench_vs_python.py \
    --category hybrid \
    --limit 5 \
    --json-out ../docs/benchmarks/$(date +%F)_<model-tag>_hybrid.json
```

Wall clock on a 3070 with `qwen2.5-coder:14b-q4_K_M`: ~60s per case.

---

## Snapshots so far

| File | Model | Category | Cases | AIL parse | AIL route | Python parse | Python route | Note |
|---|---|---|---|---|---|---|---|---|
| `2026-04-20_qwen25-coder-14b_hybrid.json` | qwen2.5-coder:14b-instruct-q4_K_M | hybrid | 5 | 40% | 20% | 100% | 40% | **Initial baseline.** Python runs every time but 3 of 5 programs hardcoded the judgment subtask. |
| `2026-04-20_qwen25-coder-14b_all.json` | qwen2.5-coder:14b-instruct-q4_K_M | all 50 | 50 | **64%** | 60% | 100% | 72% | **Full baseline to beat.** Bench_authoring corpus. By category: hybrid parse 46% / route 33%, pure_fn parse 85% / answer 80%, pure_intent parse 53%. Python on hybrid routes through the LLM only 33% of the time — the other 67% are silent LLM-skips. |
| `2026-04-20_qwen25-coder-14b_opus50.json` | qwen2.5-coder:14b-instruct-q4_K_M | Opus 50 all 4 dims | 50 | 42% | 40% (fn/intent accuracy) | 100% | 64% | **Opus 50-prompt corpus, canonical bench.** Python wins A (generation) across the board; AIL wins error_handling_miss by 42 percentage points. No Python side-effect or infinite-loop bugs emerged (qwen is "nice"); the harness win is the error-handling gap. See [`2026-04-20_opus50_summary.md`](2026-04-20_opus50_summary.md). |
| `2026-04-20_llama3.1-8b_opus50.json` | llama3.1:8b-instruct-q4_K_M | Opus 50 all 4 dims | 50 | 8% | 8% (fn/intent accuracy) | 14% | 80%* | **Model-capability floor.** llama3.1:8b fails to author both languages — 14% Python parse rate means the model is below the threshold for either. Python error-handling miss: 86%. The 80% routing is a scoring artefact (model couldn't emit Python so "no LLM call" got credit on fn_only prompts). |
| `2026-04-20_claude-sonnet-4-6_opus50.json` | anthropic:claude-sonnet-4-6 | Opus 50 all 4 dims | 50 | 36% | 36% (fn/intent accuracy) | 100% | 100% | **Frontier-model data point.** Sonnet 4.6 routes LLM calls 100% correctly (the "silent LLM skip" problem qwen14b has is solved at this model tier). Yet Python still skips required error handling on **70%** of failable ops vs AIL's 0% by grammar. See [`2026-04-20_claude_sonnet46_summary.md`](2026-04-20_claude_sonnet46_summary.md). |
| `2026-04-20_ail-coder-7b-v2_opus50.json` | ail-coder:7b (qwen2.5-coder-7b + QLoRA 205 samples 3 epochs) | Opus 50 all 4 dims | 50 | **64%** | 54% (fn/intent accuracy) | 56% | 78% | **Fine-tuned model v2.** First run where AIL parse (64%) > Python parse (56%). Category B (pure intent) reached 100% AIL parse. G1 FAIL (64% < 80%), G2 FAIL (54% < 78%), G3 PASS (AIL answer 56% > Python 48%). Primary remaining failure: Python type-annotation syntax (`List[T]`, `Array<T>`) bleeding into fn bodies. See [`2026-04-20_ail-coder-7b-v2_analysis.md`](2026-04-20_ail-coder-7b-v2_analysis.md). |

**Note — 2026-04-20 rescore.** All three opus50 JSONs above were
re-scored on this date after discovering that the
`python_side_effect_in_pure` regex flagged `os.environ["..."]`
reads as a harmful side effect. `os.environ` is a legitimate read
used for API-key auth; the check was narrowed to
`os.system` / `os.remove` / `os.unlink` / ... (mutation / IO
verbs). The rescored JSONs carry a `rescored_note` field. Per-case
`side_effect_violation` flags and the Dimension D summary are the
only affected fields; parse / route / answer / error-handling
metrics are unchanged.

---

## Reading a snapshot

Each JSON report contains:

```json
{
  "summary": {
    "model": "...",
    "total": N,
    "ail":    {"parsed": [n,N,pct], "routing_ok": [n,N,pct], "answer_ok": [n,N,pct]},
    "python": {"parsed": [n,N,pct], "routing_ok": [n,N,pct], "answer_ok": [n,N,pct]}
  },
  "cases": [
    {
      "name": "...", "prompt": "...", "category": "hybrid",
      "ail":    {"parsed": true, "routing_ok": false, "used_llm": true, "value": "...", "source": "<ail source>", ...},
      "python": {"parsed": true, "routing_ok": false, "used_llm": false, "value": "...", "source": "<python source>", ...}
    },
    ...
  ]
}
```

The `source` field contains the exact code each side produced — useful
for diffing across prompt changes, fine-tuned models, etc.

---

## Why this benchmark matters

The previous author-side benchmark (`bench_authoring.py`) measures
whether AIL can be authored well by an LLM. It tells you how good the
AIL pipeline is at its job.

This benchmark asks a different question: **given the same task and
the same model, does AIL produce measurably better code than a
reasonable Python+SDK alternative?** "Better" is decomposed into three
axes so a win on one doesn't hide a loss on another.

Today's answer, from the one baseline we have:

- On hybrid tasks AIL's parse rate lags Python's (40% vs 100%) —
  expected: the model is trained on Python, not AIL.
- On hybrid tasks AIL's routing rate (when it parses) is behind
  Python's, but Python's 40% means **60% of Python programs quietly
  skipped the LLM the task required**. That skip is the design flaw
  AIL prevents — you can't hardcode a judgment subtask in AIL because
  `intent` is a declaration the runtime enforces, not a comment the
  model can ignore.

The strategic implication (and the point of tracking this over time):
**the gap to close is AIL's parse rate, not AIL's structural
advantage.** Parse rate is a training-distribution problem. The fix
that makes the biggest difference is a model fine-tuned on AIL — and
every future snapshot in this directory will measure how close we are.
