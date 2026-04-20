# Why AIL — the numbers

🇰🇷 한국어: [`ko/why-ail-numbers.ko.md`](ko/why-ail-numbers.ko.md)

If you came here expecting a pitch, read [`why-ail.md`](why-ail.md)
instead. This file is the **numbers**. Every claim below is backed
by a JSON snapshot committed in [`docs/benchmarks/`](benchmarks/)
that you can download and diff yourself. Companion docs:

- [`why-ail-faq.md`](why-ail-faq.md) — practical FAQ, token economics, adoption checklist.
- [`why-ail-mechanics.md`](why-ail-mechanics.md) — why each number below comes out the way it does.

---

## The one sentence

> Across every model tested — an 8B open model, a 14B coder, a fine-tuned 7B adapter, and Anthropic's frontier Claude Sonnet 4.6 — **Python code written by an AI skips error handling on 42–86% of failable operations. AIL's rate is 0%, on every tier, because `Result` is part of the grammar.**

That's the harness claim, measured. A second data point to keep in mind: Sonnet 4.6 routes LLM calls correctly on 100% of prompts (so the "silent LLM skip" problem weaker models exhibit is gone at this tier), yet it still writes Python that omits error handling 70% of the time. **Better models do not close the error-handling gap. Only a grammatical guarantee does.**

---

## What was measured

50 natural-language prompts, split into three categories:

- **A** — pure computation (15 prompts, ground truth = no LLM call needed)
- **B** — pure judgment (15 prompts, ground truth = LLM call needed)
- **C** — hybrid (20 prompts, ground truth = both fn work and an LLM call needed)

Each prompt is sent to the **same model** twice:

1. Asked to author AIL via `ail ask`
2. Asked to author Python (stdlib only, urllib for any LLM call)

Both programs run in a subprocess. Four dimensions are scored per Opus 4's April 2026 spec:

- **A. Generation quality** — parse success, answer correctness, fn/intent routing
- **B. Safety** — side-effect in pure fn, unbounded loops, error-handling omissions
- **C. Efficiency** — LLM calls per task, wall clock
- **D. Harness effectiveness** — cases where Python emitted a structural bug that AIL's grammar prevents by construction

Tool: [`reference-impl/tools/benchmark.py`](../reference-impl/tools/benchmark.py).
Corpus: [`benchmarks/prompts.json`](../benchmarks/prompts.json).

---

## The harness claim, measured across four models

**Error handling on failable operations** — `int()`, `json.loads`, `urllib.request.urlopen`, `open(...)`, and similar calls that can raise:

| Model | Python omits error handling | AIL omits error handling |
|---|---|---|
| llama3.1:8b (small open) | **86% (43/50)** | 0% (grammar) |
| qwen2.5-coder:14b (mid coder) | **42% (21/50)** | 0% (grammar) |
| ail-coder:7b-v3 (fine-tuned 7B) | **44% (22/50)** | 0% (grammar) |
| **claude-sonnet-4-6 (frontier)** | **70% (35/50)** | 0% (grammar) |

The Python rate is not monotone in model quality — llama8b at the low end has the worst rate (86%) because it barely emits real Python at all (14% parse), and Sonnet 4.6 at the frontier has the worst of the three strong models (70%) because it actually uses real failable I/O (`urllib.request`, `json.loads`) where a try/except is needed and often skipped. qwen14b and the fine-tuned 7B sit in between around 42–44%.

**AIL's rate is 0% on every tier.** That is the structural property: `to_number(raw)` returns `Result[Number]`, not `Number`. Code that tries to use the returned value as a number without `is_ok` / `unwrap_or` / pattern-matching does not parse. The author doesn't have an option to forget.

Raw data:

- [`2026-04-20_llama3.1-8b_opus50.json`](benchmarks/2026-04-20_llama3.1-8b_opus50.json)
- [`2026-04-20_qwen25-coder-14b_opus50.json`](benchmarks/2026-04-20_qwen25-coder-14b_opus50.json)
- [`2026-04-20_claude-sonnet-4-6_opus50.json`](benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json)
- [`2026-04-21_ail-coder-7b-v3_opus50.json`](benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json)
- Full Sonnet analysis: [`2026-04-20_claude_sonnet46_summary.md`](benchmarks/2026-04-20_claude_sonnet46_summary.md)
- Full v3 analysis: [`2026-04-21_ail-coder-7b-v3_analysis.md`](benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md)

---

## What the structural guarantee looks like side by side

### Python (qwen14b wrote this for a sentiment-classification prompt)

```python
text = "I absolutely love this product"
words = text.split()
word_count = len(words)

# Simple sentiment analysis based on keyword presence
if "love" in words:
    sentiment = "positive"
elif "hate" in words:
    sentiment = "negative"
else:
    sentiment = "neutral"

print(f"{word_count},{sentiment}")
```

The program runs. It prints `5,positive`. But the model silently replaced the required LLM-based classification with a keyword lookup — any input without the literal word "love" or "hate" gets labelled "neutral" regardless of actual sentiment.

### AIL (the same model, same prompt)

```ail
intent classify_sentiment(text: Text) -> Text {
    goal: positive_or_negative_or_neutral
}
pure fn word_count(s: Text) -> Number {
    return length(split(trim(s), " "))
}
entry main(x: Text) {
    text = "I absolutely love this product"
    return join([to_text(word_count(text)), " words, ",
                 classify_sentiment(text)], "")
}
```

The author **declared** `intent classify_sentiment`. At runtime the executor sees an `intent` and dispatches through the model adapter. The author cannot declare the task and then silently skip the model call — the `intent` is part of the program's public surface, not a comment.

### How often does this matter?

"Silent skip" measured as: Python program parsed successfully, but its source contains no LLM-call attempt at all (`uses_llm=False`), on tasks whose ground truth requires LLM judgment (B or C categories).

| Model | Silent-skip on B (of 15) | Silent-skip on C (of 20) |
|---|---|---|
| qwen2.5-coder:14b | 3 | 16 |
| ail-coder:7b-v3 | 3 | 9 |
| claude-sonnet-4-6 | 0 | 1 |

Sonnet 4.6 correctly writes LLM-calling Python virtually every time. Mid-tier models silently skip at a meaningful rate, especially on hybrid tasks. AIL cannot silently skip because `intent` is a dispatch declaration: the runtime routes it, the author does not.

---

## The harness thesis survives prompt engineering

We tried three authoring-prompt variants on qwen2.5-coder:14b over the 20 hybrid prompts:

| Prompt variant | AIL parse (hybrid) | AIL fn/intent | Python err-handling miss |
|---|---|---|---|
| v1 (baseline) | 15% (3/20) | 10% (2/20) | 40% |
| v2 (+ explicit "do NOT emit `List[T]`") | 15% (3/20) | 10% (2/20) | 40% |
| v3 (+ 3 extra hybrid few-shot examples) | 15% (3/20) | 10% (2/20) | 40% |

AIL parse rate was stuck on this model regardless of prompt — neither explicit negative instructions nor additional demonstrations moved a single case. That failure is the training-distribution problem, addressed below under "Where AIL was behind".

The number to watch is the right column: **Python error-handling miss stays at 40% across all three variants**. The prompt changes don't affect it because the missing safety net isn't a prompt concern — it's a property of the language the model is writing in. AIL's Result type kept the rate at 0% through the same three runs, by the same mechanism.

Raw data:

- [`2026-04-20_prompt_ab_analysis.md`](benchmarks/2026-04-20_prompt_ab_analysis.md) — v1 vs v2
- [`2026-04-20_prompt_ab_v3_analysis.md`](benchmarks/2026-04-20_prompt_ab_v3_analysis.md) — v1 vs v2 vs v3

---

## Where AIL was behind — and how the fine-tune closes it

On the three base models tested, AIL parse rate was below Python parse rate:

| Model | AIL parse | Python parse |
|---|---|---|
| llama3.1:8b | 8% | 14% |
| qwen2.5-coder:14b | 42% | 100% |
| claude-sonnet-4-6 | 36% | 100% |

This is a real gap, not a benchmark artefact. It is also not a language-design problem — it is a **training-distribution** problem. Every base model has seen orders of magnitude more Python than AIL. When asked to synthesize AIL, it reaches for Python patterns (`List[T]` type hints, `x[0]` subscript, method-call chains, `stdlib/math` imports that don't exist in AIL) and the AIL parser correctly rejects those programs.

We confirmed that prompt engineering cannot fix this on qwen14b (see the prompt-variant table above — three orthogonal interventions, zero improvement). The fix is fine-tuning.

### The fine-tune closed most of the gap

`ail-coder:7b-v3` is qwen2.5-coder-7b-instruct fine-tuned with QLoRA on 244 validated AIL samples, shipped as part of v1.8.3 under [`reference-impl/training/`](../reference-impl/training/). On the same 50-prompt corpus:

| Model | AIL parse | AIL answer | Python parse | Python answer |
|---|---|---|---|---|
| ail-coder:7b-v3 | **78%** | **70%** | 54% | 48% |

- **AIL parse 78%** compared to the same 7B base's Python parse rate of 54%. The G1 gate target of 80% was missed by one case out of fifty; three remaining failures use Python-style `list[index]` subscript.
- **AIL answer correctness 70% vs Python 48%** on the same model. The gap is 22 percentage points in AIL's favour, driven mostly by Python's silent-skip behaviour on the hybrid (C) category — see
  [`why-ail-mechanics.md`](why-ail-mechanics.md) §2.
- Python parse 54% on this model is lower than the 100% we saw on the base qwen14b. Two confounders combine here: the fine-tune shifts the 7B toward AIL at the cost of Python fluency, *and* qwen2.5-coder:7b is a smaller base than qwen2.5-coder:14b to start with. Without a run of the base qwen2.5-coder:7b on the same corpus we can't separate those factors cleanly. In any case, this does not imply "AIL beats Python at authoring in general" — it is a fact about this specific fine-tuned 7B on this specific corpus.

The five fine-tuning prerequisites Opus 4 specified in April 2026 were all met on 2026-04-20:

- ✅ Benchmark results from ≥ 2 base models — three now (llama8b, qwen14b, Sonnet 4.6)
- ✅ Prompt engineering exhausted — v1/v2/v3 on qwen14b all plateaued at 15% hybrid parse
- ✅ Primary failure mode identified — Python-distribution contamination
- ✅ AIL spec frozen for one version cycle — v1.8 frozen 2026-04-20 ([`spec/09-stability.md`](../spec/09-stability.md))
- ✅ ≥ 200 validated (prompt, AIL) pairs — 244 as of v1.8.3

Training takes 10 minutes on a 3070 (8 GB VRAM). Full run details:
[`reference-impl/training/HANDOFF.md`](../reference-impl/training/HANDOFF.md).

---

## What else AIL enforces by grammar

Metrics where AIL's rate is zero by language design, with the matching Python rate for reference:

| Metric | AIL rate | Python rate (measured) | Why AIL is 0% |
|---|---|---|---|
| Side-effect in `pure fn` | **0%** | 0% on this corpus | `pure fn` is a parser-enforced contract — no `intent`, no `perform`, no non-pure call in the body |
| Unbounded loops | **0%** | 0% on this corpus | AIL has no `while`; the only loop is `for VAR in COLLECTION`. Infinite loops are not expressible |
| Error handling skipped | **0%** | 42–86% depending on model | `Result` type forces `is_ok` / `unwrap_or` / explicit `error(...)` branches at failable boundaries |

Python's 0% on the first two metrics is **specific to the 50 prompts in this corpus**. The models being tested are well-behaved on these inputs; they're not emitting `os.remove()` or `while True`. On more adversarial inputs (the Veracode 2025 "45% of AI-generated code has security vulnerabilities" result points here), those numbers are higher in real-world code. AIL's guarantee is robustness across inputs: even with an adversarial prompt, a `pure fn` still cannot `perform file.delete`.

---

## Reproducing this

```bash
# 1. Install
pip install ail-interpreter

# 2. Ollama with one of the tested models
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
export AIL_OLLAMA_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
export AIL_OLLAMA_TIMEOUT_S=600

# 3. Clone to get the benchmark tool
git clone https://github.com/hyun06000/AIL
cd AIL/reference-impl

# 4. Run. 20–40 min per model locally.
python tools/benchmark.py \
    --out ../docs/benchmarks/$(date +%F)_your-model.json
```

The output JSON has per-case detail — the AIL source, the Python source, the executed result, and the verdict on every axis. Diff it against the committed snapshots in this directory to verify reproduction, or watch the numbers shift as tooling and prompts evolve.

---

## Data provenance

Every number in this document traces to a JSON file in [`docs/benchmarks/`](benchmarks/) committed at a specific git hash.

| Claim source | File | Commit |
|---|---|---|
| qwen14b baseline (50 prompts) | [`2026-04-20_qwen25-coder-14b_opus50.json`](benchmarks/2026-04-20_qwen25-coder-14b_opus50.json) | f31e41c |
| llama8b baseline | [`2026-04-20_llama3.1-8b_opus50.json`](benchmarks/2026-04-20_llama3.1-8b_opus50.json) | f31e41c |
| Claude Sonnet 4.6 baseline | [`2026-04-20_claude-sonnet-4-6_opus50.json`](benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json) | f31e41c |
| Prompt v1 vs v2 (hybrid, qwen14b) | [`2026-04-20_qwen25-coder-14b_v2-forbidden_C.json`](benchmarks/2026-04-20_qwen25-coder-14b_v2-forbidden_C.json) | 654b0c0 |
| Prompt v1 vs v3 (hybrid, qwen14b) | [`2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json`](benchmarks/2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json) | 5104b04 |
| Fine-tuned v3 model | [`2026-04-21_ail-coder-7b-v3_opus50.json`](benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json) | 461096d |

When these numbers move (as further fine-tuning, newer models, or grammar evolution land), the table in [`benchmarks/README.md`](benchmarks/README.md) gains a new row — never an in-place edit. The JSON is the archival record.

---

## What this does NOT prove

Being honest about the limits of the current data:

- **AIL is better at every task.** It isn't. A pure one-line computation like `len(x.split())` is fine in either language; the harness advantage only appears when LLM routing, error handling, or structural safety matters.
- **The fine-tune generalises.** `ail-coder:7b-v3` was fine-tuned against v1.8 grammar on 244 samples. The 78% parse rate is on this benchmark's 50 prompts. Different prompt distributions will likely yield different rates. The G1 gate is also still open (missed by 1 case).
- **These numbers hold for every model.** Four models on this corpus is a small sample. The general pattern — structural properties don't move with model size, parse rate does — is consistent with Opus 4's thesis, but GPT-5 / Gemini 2.5 / Claude Opus 4.7-class measurements would sharpen the claim.

The current evidence is strong enough to justify continuing the project, not strong enough to declare the language mature. This document is updated as new data arrives.

---

## Related

- [`why-ail.md`](why-ail.md) — the qualitative version of this argument, with one worked example per differentiator.
- [`why-ail-faq.md`](why-ail-faq.md) — practical adoption questions (tokens saved, when to choose AIL).
- [`why-ail-mechanics.md`](why-ail-mechanics.md) — the mechanism behind each number in this document.
- [`benchmarks/README.md`](benchmarks/README.md) — per-run snapshot table and methodology.
- [`reference-impl/training/README.md`](../reference-impl/training/README.md) — the dataset, validator, and training pipeline.
