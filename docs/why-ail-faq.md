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

**Short answer:** Against a naive "LLM-for-everything" agent (the default
LangChain pattern), AIL uses **~75% fewer LLM calls** at comparable or
better quality.

**Long answer — measured:**

50 prompts, three categories:

| Category | Shape | AIL LLM calls/task | Naive agent (est.) |
|---|---|---|---|
| A (15) | Pure computation | **0.07** (≈0) | ≥1 |
| B (15) | Pure judgment | 0.93 | ~1 |
| C (20) | Hybrid (compute + judge) | 1.10 | ≥3 |

**Across 50 tasks:** AIL uses 37 LLM calls total; a naive agent that
LLM-calls every subtask would use ~150.

**Cost (Claude Sonnet 4.6, ~500 tokens/call avg):**

- AIL: ~$0.14 per 50 tasks
- Naive agent: ~$0.59 per 50 tasks
- **Savings: ~76%**

**Why:** AIL separates `pure fn` (runs locally, 0 LLM calls) from
`intent` (delegates to LLM). The runtime executes the computation
directly; the LLM is called only where judgment is needed. Python has
no such distinction, so agents either hand-code the split (brittle) or
default to LLM-calling everything (expensive).

**Caveats:**
- AIL uses **more** LLM calls than the Python baseline in this
  benchmark (37 vs ~18). That's because Python silently skips LLM
  calls on judgment tasks — see Q3.
- Code-authoring cost (the fine-tuned 7B model running locally on a
  3070) is not counted here; it's effectively free.

---

## Q2. Is the output actually better?

**Yes. On the same model, by a 22 percentage-point margin.**

| Metric | AIL | Python |
|---|---|---|
| Final answer correctness (50 tasks) | **70%** | 48% |
| pure_intent answer rate (15 tasks) | **80%** | 13% |
| Parse success rate | **78%** | 54% |

The same fine-tuned 7B model, given a Python prompt, silently skips the
required LLM call on 14/50 (30%) of cases and hardcodes fake logic
(e.g. `if "love" in text: "positive"`). AIL won't let that happen —
you can't declare a judgment task as a `pure fn`, and you can't omit a
declared `intent` from the dispatch. The grammar refuses to let the
agent cut corners.

---

## Q3. What does "structurally safer than Python" mean concretely?

Three measured gaps:

| Risk | Python | AIL | Why |
|---|---|---|---|
| Error-handling omission (`to_number` etc.) | 44% | **0%** | `Result` type forces `is_ok()`/`unwrap()` |
| Infinite loops | Detected at runtime | **Impossible** | No `while` in the language |
| Hidden I/O in "pure" code | mypy can't catch | **Parse error** | `pure fn` body rejects `intent`/`perform` |

**The 44% → 0% gap is the harness headline.** The same model, on Python,
writes `int(x)` / `open(f)` / `json.loads(s)` without any error
handling 44% of the time. In AIL the number is **0% on every model
tier** — Sonnet 4.6, qwen14b, llama8b. The grammar enforces it, so
model quality is irrelevant.

The "just use a better model" objection fails here: Sonnet 4.6 is a
frontier model that routes LLM calls correctly 100% of the time, and
it **still** writes Python code that skips error handling on 70% of
failable operations. **Model upgrades don't close this gap. Only
grammatical guarantees do.**

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
- ✅ Your tasks mix computation with judgment (Category C: AIL's
  parse rate went 45% → 70% with fine-tune, while Python stays stuck
  on structural skip behaviour)
- ✅ You don't want to maintain external linters / pre-commit hooks to
  catch what the grammar could
- ✅ LLM call cost is a line item you care about (Q1)

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

**Prompt:** "Calculate BMI for height 175cm, weight 70kg, and assess
health."

**AIL output** (`ail-coder:7b-v3`, literal benchmark capture):

```ail
pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {
    return round(weight_kg / pow(height_cm / 100, 2), 2)
}
intent assess_health(bmi: Number) -> Text {
    goal: health_assessment
}
entry main(x: Text) {
    b = bmi(175, 70)
    return join([to_text(b), " ", assess_health(b)], "")
}
```

What happens:
1. `bmi` runs locally — **zero LLM calls** → 22.86
2. `assess_health` calls LLM **exactly once** → "normal range"
3. Result: "22.86 normal range"

**Same prompt in Python**, same model: either asks the LLM for the
BMI computation (wastes tokens) or hardcodes the assessment with
`if bmi < 25: "normal"` (wrong logic, silent fail). Both failure
modes are in the benchmark record.

**Token usage:** AIL = 1 LLM call. Computation runs locally.
Naive agent = 3 LLM calls (parse + compute + judge, each).

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

- Benchmark methodology & JSON snapshots: [`benchmarks/README.md`](benchmarks/README.md)
- v3 full analysis: [`benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md`](benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md)
- Language philosophy: [`why-ail.md`](why-ail.md)
- Raw numbers report: [`why-ail-numbers.md`](why-ail-numbers.md)
