# Why AIL — the numbers

🇰🇷 한국어: [`ko/why-ail-numbers.ko.md`](ko/why-ail-numbers.ko.md)

If you came here expecting a pitch, read [`why-ail.md`](why-ail.md)
instead. This file is the **numbers**. Every claim below is backed
by a JSON snapshot committed in [`docs/benchmarks/`](benchmarks/)
that you can download and diff yourself.

The one sentence:

> Across three models — an 8B open model, a 14B coder, and
> Anthropic's frontier Claude Sonnet 4.6 — **Python code written
> by an AI skips required error handling 42–86% of the time.
> AIL's rate is 0%, on every model, because Result is part of
> the grammar.**

That's the harness claim, measured. The number worth staring at:
Sonnet 4.6 — a frontier model that routes LLM calls correctly
**100% of the time** — still skips error handling on 70% of
failable operations. Better models don't solve this. Only a
grammatical guarantee does.

---

## What was measured

50 natural-language prompts, split into three categories Opus 4 defined:

- **A** — pure computation (15 prompts, ground truth = no LLM call)
- **B** — pure judgment (15 prompts, ground truth = LLM call)
- **C** — hybrid (20 prompts, ground truth = both)

Each prompt is sent to the **same model** twice:
1. Asked to author AIL via `ail ask`
2. Asked to author Python (stdlib only, urllib for any LLM call)

Both programs run in a subprocess. Four dimensions are scored:

- **A. Generation quality** — parse success, answer correctness, fn/intent routing
- **B. Safety** — side-effect in pure fn, unbounded loops, error-handling omissions
- **C. Efficiency** — LLM calls per task, wall clock
- **D. Harness effectiveness** — cases where Python emitted a structural bug AIL's grammar prevents by construction

Tool: [`reference-impl/tools/benchmark.py`](../reference-impl/tools/benchmark.py).
Corpus: [`benchmarks/prompts.json`](../benchmarks/prompts.json).

---

## The harness claim, in one table

**Error handling on failable operations** (int parsing, json.loads,
urllib requests, file opens — things that can raise):

| Model | Python programs that skip error handling | AIL programs that skip it |
|---|---|---|
| llama3.1:8b (small open model) | **86% (43/50)** | 0% by grammar |
| qwen2.5-coder:14b (mid coder) | **42% (21/50)** | 0% by grammar |
| **claude-sonnet-4-6 (frontier)** | **70% (35/50)** | 0% by grammar |

Sonnet 4.6 is the strongest model in the industry when this was
written. It routes LLM calls correctly 100% of the time — the
"silent LLM skip" mistake weaker models make (`if "love" in words:
return "positive"`) is solved at this model tier. You no longer
need AIL to prevent THAT mistake.

But error-handling miss goes UP at the frontier tier compared to
qwen14b (70% vs 42%). Why? Because Sonnet writes MORE real
Python — it actually uses `urllib.request`, `json.loads`,
`int()` for their intended purposes, instead of hardcoding. More
failable operations in the code means more places where `try` /
`except` is needed and skipped. AIL's rate stays 0% because
`Result` is part of the grammar — the author has to type
`is_ok` or `unwrap_or` at every failable boundary. There's no
"just forget" option.

Raw data:
- [`2026-04-20_llama3.1-8b_opus50.json`](benchmarks/2026-04-20_llama3.1-8b_opus50.json)
- [`2026-04-20_qwen25-coder-14b_opus50.json`](benchmarks/2026-04-20_qwen25-coder-14b_opus50.json)
- [`2026-04-20_claude-sonnet-4-6_opus50.json`](benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json)
- Full analysis: [`2026-04-20_claude_sonnet46_summary.md`](benchmarks/2026-04-20_claude_sonnet46_summary.md)

---

## What the structural guarantee looks like side by side

### Python (qwen14b wrote this for a sentiment-classification prompt):

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

13 lines, runs, prints `5,positive`. Bug: every input without the
literal word "love" or "hate" will return "neutral" regardless of
actual sentiment. The LLM was never called. The task REQUIRED it.

### AIL (qwen14b wrote this for the same prompt):

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

The author **declared** `intent classify_sentiment`. The runtime
sees an intent declaration and routes the call to a language
model. The author cannot choose to not call the model — the
`intent` is part of the program's public surface, not a comment.

On a hybrid-task run with qwen14b, the Python side called an LLM
on 25% of hybrid prompts; the AIL side's `intent` routing was
correct on 100% of programs that parsed. The structural property
is the point: it's true when AIL parses, and it's never true of
Python.

---

## The harness thesis is model-invariant

We tried three different authoring prompts on qwen14b:

| Prompt variant | AIL parse (hybrid, 20 prompts) | AIL routing | Python err-handling miss |
|---|---|---|---|
| v1 (baseline) | 15% | 10% | 40% |
| v2 (+ explicit "do NOT emit List[T]" etc.) | 15% | 10% | 40% |
| v3 (+ 3 more hybrid few-shot examples) | 15% | 10% | 40% |

The AIL side's parse rate doesn't move with better prompts —
that's a training-distribution issue (discussed below). But the
**Python error-handling miss stays at 40% across ALL three
variants.** That number is structural, not prompt-sensitive.
Change the prompt all you want; AI-written Python keeps dropping
try/except at the same rate. AIL's Result type keeps forcing it.

This is the harness claim in pure form: *certain safety
properties are language properties, not configuration properties.*
The number that proves it is the one that doesn't change when
the prompt changes.

Raw data:
- [`2026-04-20_prompt_ab_analysis.md`](benchmarks/2026-04-20_prompt_ab_analysis.md) — v1 vs v2
- [`2026-04-20_prompt_ab_v3_analysis.md`](benchmarks/2026-04-20_prompt_ab_v3_analysis.md) — v1 vs v2 vs v3

---

## Where AIL is BEHIND (honest section)

AIL's parse rate is below Python's on every model tested:

| Model | AIL parse (50 prompts) | Python parse |
|---|---|---|
| llama3.1:8b | 8% | 14% |
| qwen2.5-coder:14b | 42% | 100% |
| **claude-sonnet-4-6** | **36%** | **100%** |

This is a real gap, not a benchmark artefact. It's also not a
language-design problem — it's a **training-distribution**
problem. The model has seen megabytes of Python and kilobytes of
AIL. When the model has to synthesize AIL, it reaches for Python
patterns (`List[T]` type hints, method-call syntax, `stdlib/math`
imports that don't exist in AIL) and the AIL parser correctly
rejects them.

We confirmed this is a training-distribution problem, not a
prompt problem, by running two orthogonal prompt interventions
(v2 negative instructions, v3 positive demonstrations) on the
same 20 hybrid tasks. Both produced **zero improvement in parse
rate.** Pattern is stable: on this model, prompt-layer
corrections cannot overcome the model's Python prior.

The fix for this gap is fine-tuning a small base model on AIL —
but per the criteria Opus 4 set, that comes **after** the spec
has stabilised for a version cycle AND the 205+ validated
training samples we now have are actually used.

Current status against the 5 fine-tuning prerequisites:

- ✅ Benchmark results from ≥ 2 base models (now **3**: llama8b, qwen14b, Sonnet 4.6)
- ✅ Prompt engineering exhausted (v1 / v2 / v3 all plateau on qwen14b)
- ✅ Primary failure mode identified (Python-distribution contamination)
- ✅ AIL spec frozen for one version cycle — **v1.8 frozen 2026-04-20** ([`spec/09-stability.md`](../spec/09-stability.md))
- ✅ ≥ 200 validated (prompt, correct AIL) pairs — **205 today** ([`reference-impl/training/dataset/`](../reference-impl/training/dataset/))

**5/5 met.** The training pipeline at
[`reference-impl/training/`](../reference-impl/training/) is
ready to run on a consumer GPU.

---

## What else AIL does by grammar

Metrics where AIL is 0% by language design and Python's rate is
what you want to compare against:

| Metric | AIL rate | Python rate (qwen14b / llama8b) | Why AIL is 0% |
|---|---|---|---|
| Side-effect in "pure" function | **0%** | 0% / 0% | `pure fn` is a parser-enforced contract — no intent call, no `perform`, no non-pure call allowed in the body |
| Unbounded loops | **0%** | 0% / 0% | AIL has no `while`. The only loop construct is `for x in bounded_collection`. Infinite loops are not expressible |
| Error handling skipped on failable ops | **0%** | 42% / 86% | `Result` type forces `is_ok` / `unwrap_or` / explicit `error(...)` branches — you can't silently drop |
| LLM call "forgotten" on judgment task | **0% when parsed** | 25% on hybrid (qwen14b) | `intent` declarations aren't optional annotations — they route through a model adapter at runtime |

Python's 0% on "side-effect in pure" and "unbounded loops" in
THIS benchmark is because qwen14b is well-behaved; the model
isn't emitting `os.remove()` or `while True` on these prompts.
On more adversarial inputs (the Veracode 2025 "45% of AI code
has vulnerabilities" result), those numbers move. AIL's
guarantee is **robustness across inputs**: even if you hand the
model an adversarial prompt, a `pure fn` still can't `os.remove`.

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

# 4. Run. 30–60 min per model.
python tools/benchmark.py \
    --out ../docs/benchmarks/$(date +%F)_your-model.json
```

The output JSON has per-case detail — the AIL source, the Python
source, the exec result, the verdict on each axis. You can diff
it against the snapshots in this directory to see if the numbers
reproduce, or watch them change as the tool and prompts evolve.

---

## Data provenance

Every number in this document comes from a JSON file in
[`docs/benchmarks/`](benchmarks/) committed at a specific git
hash. Short pointers:

| Claim | File | Commit |
|---|---|---|
| qwen14b baseline (all 50) | [`2026-04-20_qwen25-coder-14b_opus50.json`](benchmarks/2026-04-20_qwen25-coder-14b_opus50.json) | f31e41c (rescored) |
| llama8b baseline | [`2026-04-20_llama3.1-8b_opus50.json`](benchmarks/2026-04-20_llama3.1-8b_opus50.json) | f31e41c (rescored) |
| claude-sonnet-4-6 frontier baseline | [`2026-04-20_claude-sonnet-4-6_opus50.json`](benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json) | this commit |
| Prompt v1 vs v2 (hybrid) | [`2026-04-20_qwen25-coder-14b_v2-forbidden_C.json`](benchmarks/2026-04-20_qwen25-coder-14b_v2-forbidden_C.json) | 654b0c0 |
| Prompt v1 vs v3 (hybrid) | [`2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json`](benchmarks/2026-04-20_qwen25-coder-14b_v3-more-fewshot_C.json) | 5104b04 |

When these numbers move (as fine-tuning happens, or the spec
stabilises, or newer models are tested), the table in
[`docs/benchmarks/README.md`](benchmarks/README.md) gets a new
row, never an edit.

---

## What this doesn't prove (yet)

- **AIL is better at every task.** It isn't. Pure computation
  that fits in a one-liner is fine in either language; the
  harness advantage only appears when LLM routing, error handling,
  or safety matters.
- **Fine-tuned AIL beats Python across the board.** We haven't
  fine-tuned yet. That's the next experiment, and it has a gate
  (see the 5 prerequisites above).
- **These numbers hold for every model.** Three models is still
  a small sample — we've shown the pattern on llama3.1:8b,
  qwen2.5-coder:14b, and Claude Sonnet 4.6. GPT-5 / Gemini 2.5 /
  Claude Opus 4.7 class runs would tighten the claim further.
  The Sonnet 4.6 data point does show the expected shape: stronger
  models route LLM calls correctly but still skip error handling
  at a high rate, so the harness win survives moving to a
  frontier model.

The current evidence is strong enough to justify the investment
but not strong enough to declare victory. This document will be
updated as the gap closes or new data arrives.

---

## Related

- [`why-ail.md`](why-ail.md) — the qualitative version of this
  argument, with one worked example per differentiator
- [`../spec/08-reference-card.ai.md`](../spec/08-reference-card.ai.md)
  — the language itself, in the form any AI model can read
- [`benchmarks/README.md`](benchmarks/README.md) — per-run snapshot
  table and methodology
- [`../reference-impl/training/README.md`](../reference-impl/training/README.md)
  — the dataset, validator, and training pipeline that will be
  unfrozen when the fine-tuning prerequisites are met
