# Why the numbers come out this way — mechanics

🇰🇷 한국어: [`ko/why-ail-mechanics.ko.md`](ko/why-ail-mechanics.ko.md)

The [FAQ](why-ail-faq.md) gives the numbers. This file explains
**why** each number comes out the way it does — the mechanism behind
every measurement, with the benchmark record as evidence.

---

## 1. Why AIL 0% vs Python 44% error-handling omission

**Observation:** Across every model tier tested — llama3.1:8b (86%),
qwen2.5-coder:14b (42%), `ail-coder:7b-v3` (44%), Claude Sonnet 4.6
(70%) — Python code skips error handling on failable operations.
AIL's rate is 0% on every tier.

**Mechanism.** AIL's `to_number("42")` returns a value of type
`Result[Number]`, not `Number`. The parser refuses to let you use
it as a `Number`:

```ail
pure fn safe_parse(raw: Text) -> Number {
    n = to_number(raw)       // n : Result[Number]
    return n + 1             // PARSE ERROR — can't add Result to Number
}
```

To compile, you must extract the inner value explicitly:

```ail
pure fn safe_parse(raw: Text, default: Number) -> Number {
    return unwrap_or(to_number(raw), default)
}
```

Python's `int("42")` returns an `int` or raises. Both shapes are
assignable to an `int`-annotated variable; skipping `try` is valid
Python, it just crashes at runtime:

```python
def safe_parse(raw: str) -> int:
    return int(raw) + 1   # perfectly valid — fails only when raw is "abc"
```

**Why model size can't close the gap:** Sonnet 4.6 — a frontier model
that *routes LLM calls correctly 100% of the time* on this corpus —
still writes Python without error handling on 70% of failable
operations. The model knows error handling exists; it just doesn't
feel obliged to include it every time. AIL's type system removes the
optionality from the grammar. It isn't model-dependent.

See full argument in
[`2026-04-20_claude_sonnet46_summary.md`](benchmarks/2026-04-20_claude_sonnet46_summary.md).

---

## 2. Why AIL 70% vs Python 48% answer correctness

**Observation.** Given the same prompt and same model
(`ail-coder:7b-v3`), AIL-authored programs produce the correct answer
70% of the time; Python-authored programs 48%.

**Mechanism: the "silent LLM skip"**

"Silent skip" here means: the Python program *parsed*, executed to completion, and returned an answer — but its source contains no LLM-call attempt at all (`uses_llm=False` in the benchmark record), even though the task's ground truth required model judgment. AIL cannot silently skip because `intent` is a dispatch declaration: the runtime routes every declared intent through the model adapter, and there is no AIL syntax for "declare the intent and then don't call it".

**Exhibit A — task B09: "Rewrite in passive voice":**

Python (same model, 0 LLM calls):

```python
def passive_voice(text):
    parts = text.split()
    subject, verb, object_ = parts[0], parts[1], parts[2]
    return f"{object_} was {verb} by {subject}"
```

Input "The cat chased the mouse" → output "chased was cat by The". Wrong because the hardcoded rule doesn't know "the" is a determiner. The LLM was never consulted.

AIL (same model, 1 LLM call):

```ail
intent to_passive_voice(text: Text) -> Text {
    goal: sentence rewritten in passive voice
}
entry main(text: Text) { return to_passive_voice(text) }
```

Output: "The mouse was chased by the cat." Correct because the `intent` declaration forces actual LLM dispatch.

**Frequency of silent skip by category** (on `ail-coder:7b-v3`, among programs that parsed):

| Category | Python silent-skipped | AIL silent-skipped |
|---|---|---|
| A — pure computation (n=15) | n/a (LLM not required) | n/a |
| B — pure judgment (of 4 parsed, 15 total) | 3 | 0 |
| C — hybrid (of 14 parsed, 20 total) | **9** | 1 |

So of the 18 Python judgment-task programs that parsed at all, 12 (67%) hardcoded the judgment step instead of calling the LLM. The ones that did attempt an LLM call generally got the right answer — the silent-skip pattern accounts for most of Python's wrong answers on this benchmark, though not all of them (parse failures and exec errors account for the rest).

Worth flagging explicitly: Python's behaviour here is model-dependent. On Claude Sonnet 4.6 (tested against the same corpus), only 1/20 hybrid programs silently skipped. The silent-skip pattern is severe on mid-tier models and largely absent at the frontier — but error-handling omission (§1 above) survives the move to Sonnet at 70%.

---

## 3. Where AIL's LLM-call count actually lands

**Observation.** Across the 50-prompt benchmark on `ail-coder:7b-v3`:

- AIL: 37 total LLM calls
- Python, same model: 18 total LLM calls (but silently skipped 12 on parsed judgment tasks)

**Mechanism.** The `pure fn` / `intent` split does the cost routing for you — computation runs on local silicon, judgment on LLM:

```ail
pure fn bmi(h_cm: Number, w_kg: Number) -> Number {      // 0 LLM calls — runs locally
    return round(w_kg / pow(h_cm / 100, 2), 2)
}
intent assess_health(bmi: Number) -> Text {              // 1 LLM call when the entry invokes it
    goal: health assessment
}
entry main(x: Text) {
    b = bmi(175, 70)
    return join([to_text(b), " ", assess_health(b)], "")
}
```

**How to think about the comparison.** AIL uses *more* LLM calls than Python baseline (37 vs 18) on this benchmark — but that's because Python silently skipped calls it should have made, and got 26% fewer answers right as a result. The relevant question isn't "Python or AIL uses fewer tokens" — it's "per correct answer, what's the cost?"

Against a hand-authored Python pipeline whose author correctly routes LLM only where needed, AIL uses roughly the same number of calls AIL does — no savings. Against an agent framework that LLM-calls every subtask (common naïve-agent pattern), AIL uses meaningfully fewer because the routing is structural rather than a model's runtime choice. The exact ratio depends on the agent framework and the task shape; the benchmark doesn't measure it directly, so any specific "N× savings" number would be an estimate, not data.

**Why Python doesn't match this automatically.** Python has no
language-level distinction between "deterministic" and "judgment"
code, so either:
- The author decides manually, and (as the benchmark shows) gets it
  wrong often — skipping LLM where needed (silent skip) or calling
  LLM where local arithmetic would have done.
- An agent framework (LangChain, AutoGPT) routes everything through
  LLM by default, paying the 4× cost to avoid authoring bugs.

AIL removes the choice: the grammar does the routing.

---

## 4. Why fine-tuning beat prompting (and why a small tuned model beat Sonnet 4.6)

**Observation (prompt ceiling):**

| Variant on `qwen2.5-coder:14b` | Hybrid (C) parse |
|---|---|
| v1 baseline prompt | 15% |
| v2: add "FORBIDDEN: no `List[T]`, no `Array<T>`" | 15% |
| v3: add 3 hybrid few-shot examples | 15% |

Two orthogonal interventions — negative instruction and positive
demonstration — moved zero cases each. Full data in
[`2026-04-20_prompt_ab_v3_analysis.md`](benchmarks/2026-04-20_prompt_ab_v3_analysis.md).

**Observation (tuning vs scale):**

| Model | AIL parse rate |
|---|---|
| `llama3.1:8b` (base) | 8% |
| `qwen2.5-coder:14b` (base) | 42% |
| `claude-sonnet-4-6` (frontier base) | 36% |
| `ail-coder:7b-v3` (fine-tune, 244 samples) | **78%** |

**Mechanism.** A base model's output distribution is the integral
of every token it trained on. The Qwen2.5-Coder pretraining saw
megabytes-to-gigabytes of Python, so when asked to author code in
any language with a `fn` keyword, it reaches for Python's `List[T]`
type hints and `x[0]` subscript syntax — patterns that have orders
of magnitude more probability mass than the AIL shape.

A prompt is 1–2 KB of tokens. It can *nudge* the distribution but
cannot invert it. That's why three rounds of prompt engineering on
qwen14b plateaued at 15%.

Fine-tuning changes the distribution directly. 244 samples of
validated AIL shift the model's prior toward the shapes the parser
accepts. The effect is much larger than a bigger base model:
`ail-coder-7b-v3` (78%) beats Sonnet 4.6 (36%) at writing AIL
because the small model has seen AIL and the frontier model hasn't.

**Generalisable claim.** For a narrow DSL, a small model fine-tuned
on the DSL distribution will out-author a frontier base model. Model
scale beats fine-tuning when the domain is well-represented in
pretraining; the reverse holds when it isn't.

---

## 5. Why category C saw the biggest jump (45% → 70%)

**Observation.** v2 → v3 changes:

| Category | v2 AIL parse | v3 AIL parse | Δ |
|---|---|---|---|
| A — pure fn | 53% | 73% | +20 pp |
| B — pure intent | 100% | 93% | −7 pp |
| C — hybrid | **45%** | **70%** | **+25 pp** |

C was the weakest *and* gained the most. Three concurrent fixes, each
targeting a hybrid-specific failure class:

1. **Parser now accepts parametric types.** `List[Number]` etc. are
   spec-valid (§2.3) but the parser was silently discarding the
   brackets. Hybrid programs with list-typed parameters now parse.
   Fixes 7 v2 failures.

2. **Math builtins added.** `round`, `sqrt`, `floor`, `ceil`, `pow`
   are now trusted-pure. Hybrid BMI / std-dev / compound-interest
   prompts that model naturally reached for `round()` now don't
   `PurityError`. Fixes 2 v2 failures.

3. **+14 hybrid training samples** showing correct `pure fn`
   (compute) + `intent` (judge) decomposition. Directly teaches the
   distribution for this category.

**Why C specifically and not A or B?**
- A was already 85% on base qwen14b (pure fn is close to Python shape).
- B reached 100% after v2 fine-tune (intent declarations are AIL-only
  and were already well-represented in the v2 training set).
- C is where the model has to *choose* between fn and intent, and
  where Python syntax contamination had most opportunities to leak.

**The −7 pp on B is noise**, not regression — one sample flipped
between runs due to goal-clause phrasing (comma in `goal: positive,
negative, neutral`). Not a training effect.

---

## 6. Why AIL is slower per task

**Observation.** Per-task wall clock (v3 run):

| Category | AIL | Python |
|---|---|---|
| A (pure compute) | 3.8 s | 1.1 s |
| B (intent) | 3.1 s | 2.2 s |
| C (hybrid) | 6.8 s | 2.4 s |

**Mechanism — two additive sources:**

1. **Python is faster partly because it skips work.** On C-category tasks, 9 of 14 parsed Python programs contained no LLM call at all, so the LLM latency (typically 1–3 seconds per call on the local Ollama server used for this benchmark) was avoided entirely. Adjust for that and Python's C wall-clock comes up toward AIL's.
2. **AIL runtime overhead.** The reference Python implementation tracks provenance on every value, a trace entry per call, and calibration state per intent. These are real costs on top of the bare executor. They're measurable but typically tens of milliseconds per task, not seconds — the LLM call latency dominates.

**When this matters.** Batch pipelines, overnight runs, and agent workloads — a few extra seconds per task is noise. Interactive latency-sensitive applications (sub-second response) would need the Go runtime (which doesn't track provenance/calibration) and/or a faster model.

---

## 7. Why the gains compound: three independent mechanisms

The headline numbers — **AIL answer correctness 70% vs Python 48%** on the same model, **AIL error-handling omission 0% vs Python 42–86%** across every model tier, and **AIL parse rate 78% on a small fine-tuned model that beats frontier base models at authoring AIL** — do not come from a single trick. They come from three independent layers, each addressing a different failure mode:

| Layer | Mechanism | Gap it closes (measured on `ail-coder:7b-v3`) |
|---|---|---|
| **Grammar** | `Result` type, `pure fn`, no `while` | Error handling omission 0% (vs Python's 44% on this model, up to 86% on llama8b) |
| **Training** | QLoRA on 244 validated samples | Parse rate moves from qwen14b base's 42% → 78% on the fine-tuned 7B |
| **Runtime** | `intent` declarations always dispatch via the model adapter | Silent LLM skip on hybrid tasks: AIL 1/20, Python 9/20 |

Remove any one layer and the other two don't carry the claim:

- Grammar alone (no fine-tune) gives you 36–42% AIL parse rates on base models — the harness survives but the authoring reliability does not.
- Training alone (on a language without `Result`) would not have produced the 0% error-handling number; the fine-tune doesn't teach error handling, the grammar requires it.
- Runtime alone (a library that intercepts function calls) cannot prevent the author from never declaring the intent — you need the grammar to make "declare it and skip it" unexpressible.

The three-layer stack is the claim. The numbers are the evidence.

**What this says about the design thesis.** "Build a harness around
Python" (AGENTS.md, pre-commit hooks, custom linters) addresses one
of the three. "Fine-tune a Python-authoring model on safer patterns"
addresses another. AIL's bet is that integrating all three into the
language itself is cheaper and more robust than assembling them
externally — which is exactly what the benchmark numbers show.

---

## Reproducing any claim above

Every number in this document comes from one of the JSON snapshots in
[`benchmarks/`](benchmarks/). Find a number, trace it:

```bash
# Example: verify the "Python silent skips LLM on 60% of hybrid"
python3 -c "
import json
d = json.load(open('docs/benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json'))
cases = [c for c in d['cases'] if c['category']=='C' and c['python'].get('parsed')]
# Silent skip: source has no LLM-call attempt (uses_llm=False)
silent = [c for c in cases if not c['python'].get('uses_llm')]
print(f'Python hybrid parsed={len(cases)}, silent-skipped={len(silent)}')
"
# Python hybrid parsed=14, silent-skipped=9
```

Note: an alternative count uses `llm_call_count == 0` instead of `uses_llm == False`. Those can diverge — a program may contain a real LLM-call attempt that doesn't fire at runtime (wrong endpoint, timeout, or a code path that never reaches it). `uses_llm=False` is the stricter metric ("code truly has no LLM call") and is what's used in this document.

Every JSON also carries per-case `source` fields so you can read the
actual code each author produced for any prompt.
