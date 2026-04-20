# AIL FAQ — practical questions, measured answers

🇰🇷 한국어: [`ko/why-ail-faq.ko.md`](ko/why-ail-faq.ko.md)

This document answers the questions a team actually asks when
evaluating AIL, with measured numbers from the April 2026
benchmark. No rhetoric. All benchmark JSON is committed in
[`benchmarks/`](benchmarks/) — diff it yourself.

---

## One-line summary

> On the same 7B model, **AIL-authored code gets the right answer 70% of
> the time; Python-authored code gets it 48%**. AIL's error-handling
> omission rate is **0% by grammar**; Python's is 44%.

Everything below is "under what conditions, by how much."

---

## Q1. How many tokens does AIL save?

**Measured:** AIL made **37 LLM calls across the 50-prompt benchmark** on `ail-coder:7b-v3`. Every call landed where the prompt actually required model judgment; none on pure-computation tasks.

**Per-category averages:**

| Category | Shape | AIL calls/task (measured) |
|---|---|---|
| A (15 prompts) | Pure computation | **0.07** (≈0 — one misrouting case) |
| B (15 prompts) | Pure judgment | 0.93 (14/15 correctly invoked the LLM) |
| C (20 prompts) | Hybrid (compute + judge) | 1.10 |

**Why the "0.07" matters:** on the 15 pure-computation prompts, AIL made essentially no LLM calls. A naive agentic setup that pipes every subtask through an LLM ("the LangChain default") would have made at least one call per task on these same prompts — so for any workload where pure-computation tasks dominate, the token delta is just the count of pure-computation tasks × the per-call cost.

**Where the exact savings number depends on your baseline:**

AIL is explicit about the split — `pure fn` runs locally, `intent` dispatches. So AIL's call count reflects the shape of the task, not the author's discipline. How many calls you *save* depends on what you're replacing:

- **vs AIL itself:** no comparison to make.
- **vs a hand-tuned Python pipeline where the author correctly routes LLM only where needed:** zero savings — Python authors who route well use the same call budget AIL does.
- **vs the same 7B model authoring Python on this benchmark:** AIL uses *more* calls than Python baseline (37 vs ~18). Python made fewer calls by silently skipping LLM where required — answering 26% fewer tasks correctly as a result (see Q2).
- **vs a naive "LLM-for-every-subtask" agent (no routing):** Hybrid tasks that need 1 LLM subtask would take ≥ 2 calls in that setup (plan + execute) and often more, so AIL saves a noticeable fraction. The exact percentage depends entirely on the naive agent's implementation and task shape.

**What to take away:** if you're choosing between AIL and a well-tuned Python pipeline authored by a careful human, token savings are not the argument — Q2 (answer correctness) and Q3 (safety) are. If you're choosing between AIL and an agentic framework that LLM-calls for every subtask, AIL will use meaningfully fewer calls because the routing is structural, not up to the agent.

Code-authoring cost (running the fine-tuned 7B locally on a 3070) is not counted — it's effectively free at inference time.

---

## Q2. Is the output actually better?

**Yes — on the same model, by 22 percentage points on overall correctness.**

| Metric | AIL | Python |
|---|---|---|
| Final answer correctness (50 tasks) | **70%** | 48% |
| `pure_intent` category answer (15 tasks) | **80%** | 13% |
| Parse success rate | **78%** | 54% |

All three numbers come from one run of `ail-coder:7b-v3` on the same 50 prompts, one side authored in AIL and the other in Python.

**The gap comes mostly from silent LLM-skip on Python.** On the 35 prompts whose ground truth required an LLM call (B + C categories), Python-authored programs that *parsed* went one of two ways:

- 18/35 Python programs parsed. Of those, 12 (B:3 + C:9) had **no LLM-call attempt at all** in their source — the author declared the task solvable with string operations or keyword matching, and the runtime ran those and returned wrong answers. The famous case in this benchmark is the passive-voice prompt where Python hardcoded `{object} was {verb} by {subject}` and produced "chased was cat by The".
- The remaining 6 of 18 did attempt an LLM call and mostly got the right answer.

AIL cannot silently skip: `intent classify_sentiment(...)` is a dispatch declaration, and the runtime routes it through the model adapter. The author has no syntax for "declare the intent but skip the call".

---

## Q3. What does "structurally safer than Python" mean concretely?

Three measured gaps:

| Risk | Python | AIL | Why |
|---|---|---|---|
| Error-handling omission (`to_number` etc.) | 44% | **0%** | `Result` type forces `is_ok()`/`unwrap()` |
| Infinite loops | Detected at runtime | **Impossible** | No `while` in the language |
| Hidden I/O in "pure" code | mypy can't catch | **Parse error** | `pure fn` body rejects `intent`/`perform` |

**Why the 44% → 0% gap matters — and why a better model won't fix it:**

AI generates code statistically. Because training data overwhelmingly shows `int(x)`, `json.loads(s)`, and `open(f)` written without error handling (the happy path), models produce failable operations without wrapping them. Humans know from experience that these functions can throw. Models infer it probabilistically, and often get it wrong.

The "just use a better model" objection fails here. Sonnet 4.6 is the strongest model tested — it routes LLM calls correctly 100% of the time — and it still writes Python code that skips error handling on 70% of failable operations. The rate doesn't converge toward zero as models get stronger. Python simply *allows* you to write `int(x)` without error handling; the language makes no objection.

In an autonomous pipeline where AI generates code and executes it without human review, this omission propagates silently. Wrong values flow downstream. Nobody notices until something breaks far from the source.

In AIL, `to_number(x)` returns a `Result`. If you call `unwrap()` without first calling `is_ok()`, the parser rejects the program before it runs. Error handling is not something the model has to remember — the grammar enforces it.

---

## Q4. What about execution speed?

**AIL is slower.** Per-task average:

- AIL: 4.8s
- Python: 1.9s

Two reasons:
1. AIL honestly calls the LLM when judgment is needed; Python is fast
   partly because it skips calls it should make.
2. The AIL runtime tracks provenance, confidence, and trace records.
   The current implementation is the Python reference; Go is
   Phase-0 subset.

**Where it matters:**
- Low-latency interactive chatbots → AIL isn't a great fit.
- Batch processing, data pipelines, agentic coding → the extra 3s is
  in the noise.

---

## Q5. When should I choose AIL? When should I not?

**Choose it when:**
- ✅ You have a pipeline where AI writes and executes code
- ✅ Your tasks mix computation with judgment (hybrid category C: AIL's parse rate improved from 45% on the v2 training cycle to 70% on v3, and hybrid is where Python most often silently skips the LLM call on the same model)
- ✅ You don't want to maintain external linters / pre-commit hooks to catch what the grammar could
- ✅ LLM call cost is a line item you care about, and your current setup is a naive agent that LLM-calls for every subtask (see Q1 for what "depends on your baseline" means)

**Don't choose it when:**
- ❌ The code is read and debugged by humans (AIL's design premise is
  "humans don't read the code layer"; if that premise fails for you,
  Python is correct)
- ❌ You'd be rewriting an already-working Python pipeline (the ROI
  rarely clears)
- ❌ 100% of your tasks are pure judgment (AIL vs direct LLM call —
  AIL doesn't add much)
- ❌ Low-latency production requirement (Q4)

---

## Q6. What model do I need?

**Minimum viable setup:**
- A 7B+ code-specialized base model
- QLoRA fine-tune on the AIL training set (~244 samples)
- 3070 (8 GB VRAM) trains in 10 minutes
- Serve via Ollama, local inference = $0

**Tested models:**

| Model | AIL parse rate | Notes |
|---|---|---|
| `llama3.1:8b` | 8% | Too small — doesn't work |
| `qwen2.5-coder:14b` | 42% | Base, no fine-tune |
| `claude-sonnet-4-6` | 36% | Base, frontier |
| **`ail-coder:7b-v3`** | **78%** | qwen2.5-coder-7b + AIL QLoRA |

**Key finding:** prompt-based approaches don't work. The model's
Python training distribution is too strong to override with a prompt
alone. For a 7B model fine-tuning is required — but once fine-tuned,
a small model beats a frontier base model at authoring AIL.

---

## Q7. One concrete example

**Prompt:** "Calculate BMI for height 175cm, weight 70kg" (paired with a health-assessment request).

**AIL output** — captured from a smoke-test call of `ollama run ail-coder:7b-v3 "calculate BMI from 175cm 70kg"` on the v3 fine-tuned model, cleaned of terminal control codes:

```ail
pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {
    return round(weight_kg / pow(height_cm / 100, 2), 2)
}
entry main(x: Text) { return bmi(175, 70) }
```

What happens when this runs:

1. `bmi` is a `pure fn`. The runtime evaluates `round(70 / pow(1.75, 2), 2)` locally. **Zero LLM calls.** Result: 22.86.
2. If you'd asked the model to also assess the BMI (one of the benchmark's actual hybrid prompts, C07), it would add an `intent assess_health(bmi)` declaration and the runtime would dispatch that — **exactly one LLM call** for the judgment part.

**What Python typically does on the same prompt with the same model** (this is the measured failure mode from the benchmark corpus — not every run hits it, but it's the dominant error class): either the author hardcodes a BMI-to-health mapping in deterministic Python (`if bmi < 25: "normal"`), which makes the "assessment" a fixed lookup rather than a model judgment, or the author writes a correct LLM call but omits error handling on the `urllib`/`json.loads` chain used to reach the model. AIL's grammar structurally prevents both: `intent` cannot be hardcoded, and `Result` cannot be silently discarded.

**Caveat:** the smoke-test snippet above is cleaner than some of v3's actual benchmark captures on this prompt class. C07 specifically didn't parse in the canonical v3 run because the generated code used Python-style `split("175cm", "cm")[0]` subscript — one of the three remaining parse-failure patterns documented in [`2026-04-21_ail-coder-7b-v3_analysis.md`](benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md).

---

## Q8. Decision checklist

If 5+ of these are true, AIL is worth a spike.

- [ ] You have a pipeline where AI authors code that then executes
- [ ] Your monthly LLM bill is $100+
- [ ] You've debugged a "the AI should have called the LLM here but
      hardcoded a heuristic" bug
- [ ] You keep adding pre-commit hooks / custom linters to catch
      AI-generated issues
- [ ] Your workload mixes computation and judgment (e.g. parse CSV +
      summarize, score + classify)
- [ ] Missing error handling has caused a production incident
- [ ] You have a 3070-class GPU and have done fine-tuning before
- [ ] Code-review load for AI-generated code is growing
- [ ] Project size is rewritable (< 10K LOC)
- [ ] You've heard the phrase "harness engineering" and know what it
      means

---

## Further reading

- **Why the numbers come out this way — mechanics**: [`why-ail-mechanics.md`](why-ail-mechanics.md) (the *why* behind every metric in this FAQ)
- Benchmark methodology & JSON snapshots: [`benchmarks/README.md`](benchmarks/README.md)
- v3 full analysis: [`benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md`](benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md)
- Language philosophy: [`why-ail.md`](why-ail.md)
- Raw numbers report: [`why-ail-numbers.md`](why-ail-numbers.md)
