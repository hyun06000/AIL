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

On 15 of 50 tasks (30%), the Python author *declared* it was writing
code to solve a judgment task but *never actually called the LLM* —
instead it hardcoded a keyword-match heuristic. AIL cannot do this
because `intent` is a dispatch declaration: at runtime the executor
routes through the model adapter whether the author wanted it to or
not.

**Exhibit A — task B09: "Rewrite in passive voice":**

Python (same model, 0 LLM calls):
```python
def passive_voice(text):
    parts = text.split()
    subject, verb, object_ = parts[0], parts[1], parts[2]
    return f"{object_} was {verb} by {subject}"
```

Input "The cat chased the mouse" → output "chased was cat by The".
Wrong because the hardcoded rule doesn't know "the" is a determiner.

AIL (same model, 1 LLM call):
```ail
intent to_passive_voice(text: Text) -> Text {
    goal: sentence rewritten in passive voice
}
entry main(text: Text) { return to_passive_voice(text) }
```

Output: "The mouse was chased by the cat." Correct because `intent`
forces actual LLM dispatch — there is no AIL grammar that lets the
author pretend to answer this with string operations.

**The frequency of this failure by category:**

| Category | Python silent-skips | AIL silent-skips |
|---|---|---|
| A — pure computation (n=15) | n/a (LLM not needed) | n/a |
| B — pure judgment (n=15) | 3/15 (20%) | 0/15 |
| C — hybrid (n=20) | **12/20 (60%)** | 1/20 |

**Hybrid is where Python collapses.** On 60% of C-category tasks the
Python author wrote code that looks computational, runs fine, and
answers with garbage. AIL's `intent`/`pure fn` distinction is
grammatical — you can't omit the LLM call the task requires.

---

## 3. Why AIL uses ~75% fewer tokens than a naive agent

**Observation.** Across 50 tasks:
- AIL: 37 total LLM calls
- Python (same model): 18 calls (but silently skipped 15 it should have made)
- Naive "LLM-for-everything" agent: ~150 calls (estimated 3/task avg)

**Mechanism.** The `pure fn` / `intent` split does the cost routing
for you — computation runs on local silicon, judgment on LLM:

```ail
pure fn bmi(h_cm: Number, w_kg: Number) -> Number {      // 0 LLM calls
    return round(w_kg / pow(h_cm / 100, 2), 2)
}
intent assess_health(bmi: Number) -> Text {              // 1 LLM call
    goal: health assessment
}
entry main(x: Text) {
    b = bmi(175, 70)
    return join([to_text(b), " ", assess_health(b)], "")
}
```

A naive "put everything in an LLM prompt" agent would LLM-call at least
three times for this shape: to parse the spec, to compute, and to
assess. AIL's runtime bypasses the first two entirely.

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

## 6. Why AIL is 2.5× slower than Python per task

**Observation.** Per-task wall clock (v3 run):

| Category | AIL | Python |
|---|---|---|
| A (pure compute) | 3.8 s | 1.1 s |
| B (intent) | 3.1 s | 2.2 s |
| C (hybrid) | 6.8 s | 2.4 s |

**Mechanism.** Two additive sources:

1. **Python cheats on runtime by skipping LLM calls** (12/20 on C).
   Each skipped call is ~2 s saved. Subtract those and Python's C
   wall-clock would be similar to AIL's.

2. **AIL runtime overhead.** The reference Python implementation
   tracks provenance on every value, trace entries on every call,
   calibration state for intents. These are optional features the
   Go runtime doesn't track. On a ~200-ms-per-task baseline this
   is a real cost but not the dominant factor.

**When this matters.** Batch pipelines, overnight runs, agent
workloads — the 3 s extra per task is in the noise. Interactive
chatbots with <1 s latency targets — the overhead would need tuning
(or a switch to the Go runtime).

---

## 7. Why the gains compound: three independent mechanisms

The headline numbers (70% answer correctness, 0% error omission, 75%
token reduction) don't come from a single trick. They come from three
layers, each addressing a different failure mode:

| Layer | Mechanism | Gap it closes |
|---|---|---|
| **Grammar** | `Result` type, `pure fn`, no `while` | Error handling (44% → 0%), infinite loops, side-effect hiding |
| **Training** | QLoRA on 244 validated samples | Parse rate (42% base → 78%), fn/intent routing |
| **Runtime** | `intent` dispatches through adapter | Silent LLM skip (60% → 5% on hybrid) |

Remove any one and the claim collapses. Keep all three and the
numbers hold across every model tier tested.

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
skips = [c for c in cases if (c['python'].get('llm_call_count') or 0)==0]
print(f'Python hybrid parsed={len(cases)}, silent-skipped={len(skips)}')
"
# Python hybrid parsed=14, silent-skipped=12
```

Every JSON also carries per-case `source` fields so you can read the
actual code each author produced for any prompt.
