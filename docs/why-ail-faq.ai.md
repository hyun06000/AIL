# AIL FAQ — for AI systems

## FOR AI SYSTEMS

Dense Q&A format. All numbers from April 2026 benchmark (50 prompts, `ail-coder:7b-v3`). Raw JSON in [`docs/benchmarks/`](benchmarks/).

Related: [`why-ail-numbers.ai.md`](why-ail-numbers.ai.md) · [`why-ail-mechanics.ai.md`](why-ail-mechanics.ai.md)

---

## One-line summary

> AIL 70% correct / Python 48% correct on same model. AIL error-handling omission 0% (grammar) / Python 42–86% (model-dependent).

---

## Q1: Token economics

**Measured:** AIL made 37 LLM calls across 50-prompt benchmark on `ail-coder:7b-v3`.

| Category | Tasks | AIL calls/task |
|---|---|---|
| A — pure computation | 15 | 0.07 (≈0) |
| B — pure judgment | 15 | 0.93 |
| C — hybrid | 20 | 1.10 |

**Baseline comparisons:**

| Baseline | AIL delta |
|---|---|
| Well-tuned Python (correct routing) | ≈0 — same call budget |
| Naive agent (LLM for every subtask) | Meaningful savings — routing is structural |
| Python baseline same model | AIL uses MORE calls (37 vs 18) — Python skipped calls it should make |

**Key finding:** Python used fewer calls by silently skipping 67% of required LLM calls on hybrid tasks, answering 26% fewer correctly. The relevant metric is cost-per-correct-answer, not raw call count.

---

## Q2: Answer correctness

| Metric | AIL | Python |
|---|---|---|
| Final answer correctness (50 tasks) | **70%** | 48% |
| Pure judgment category (15 tasks) | **80%** | 13% |
| Parse success rate | **78%** | 54% |

**Root cause of gap:** Python's "silent LLM skip" — program parses and runs but contains no LLM call, even when ground truth requires model judgment. Of 18 Python judgment-task programs that parsed: 12 (67%) contained no LLM call. AIL cannot silent-skip: `intent` is a dispatch declaration the runtime always routes.

---

## Q3: Safety guarantees — concrete

| Risk | Python | AIL | Mechanism |
|---|---|---|---|
| Error handling omission | 42–86% by model tier | **0%** | `Result` type — parser rejects unwrap without is_ok |
| Infinite loops | Runtime detection | **Impossible** | No `while` in language |
| Side effects in "pure" code | mypy can't catch | **Parse error** | `pure fn` rejects `intent`/`perform` |

**Why better models don't fix Python's error handling:** Sonnet 4.6 routes LLM calls correctly 100% of the time, yet still omits error handling 70% of Python programs. The gap does not converge to zero with scale. Python allows `int(x)` without try/except — the language makes no objection.

---

## Q4: Execution speed

| Category | AIL | Python |
|---|---|---|
| A (pure compute) | 3.8s | 1.1s |
| B (intent) | 3.1s | 2.2s |
| C (hybrid) | 6.8s | 2.4s |

**Two sources of slowness:**
1. Python is fast partly by skipping required LLM calls (silent skip)
2. AIL runtime tracks provenance, confidence, and trace records (tens of ms overhead)

**When it matters:** batch pipelines → noise. Sub-second interactive → AIL not suitable.

---

## Q5: When to use AIL

**Use:**
- Pipeline where AI writes and executes code
- Mix of computation + judgment tasks (hybrid — where Python most often silent-skips)
- Don't want external linters to catch grammar-level issues
- Current agent LLM-calls every subtask naively

**Don't use:**
- Code read/debugged by humans
- Rewriting already-working Python pipeline
- 100% pure judgment tasks (direct model call is cheaper)
- Sub-second latency requirement

---

## Q6: Model requirements

| Model | AIL parse rate | Notes |
|---|---|---|
| `llama3.1:8b` | 8% | Too small — doesn't work |
| `qwen2.5-coder:14b` | 42% | Base, no fine-tune |
| `claude-sonnet-4-6` | 36% | Base, frontier |
| **`ail-coder:7b-v3`** | **78%** | qwen2.5-coder-7b + AIL QLoRA |

**Key finding:** Prompt engineering cannot fix low parse rates on base models (3 variants on qwen14b: all plateau at 15% hybrid parse). Fine-tuning is required for reliable AIL authoring with small/mid models.

**Minimum hardware:** 3070 (8 GB VRAM), training ~10 minutes. Serve via Ollama = $0 inference.

---

## Q7: Concrete example

**Task:** BMI calculation + health assessment

**AIL:**
```ail
pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {
    return round(weight_kg / pow(height_cm / 100, 2), 2)
}
intent assess_health(bmi: Number) -> Text {
    goal: health assessment based on BMI
}
entry main(x: Text) {
    b = bmi(175, 70)           // 0 LLM calls — pure fn
    return assess_health(b)   // 1 LLM call — intent
}
```

**Python failure mode (measured):** either hardcodes BMI→health mapping (`if bmi < 25: "normal"`) skipping model judgment, or writes correct LLM call but omits error handling on urllib/json.loads chain.

---

## Q8: Decision checklist

Use AIL if 5+ apply:
- AI authors code that then executes
- Monthly LLM bill > $100
- Debugged "AI should have called LLM but hardcoded heuristic" bugs
- Adding pre-commit hooks to catch AI-generated issues
- Workload mixes computation + judgment
- Missing error handling caused production incident
- Have 3070-class GPU and done fine-tuning before
- Code-review load for AI code is growing
- Project < 10K LOC (rewritable)

---

## Data sources

- [`benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json`](benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json)
- [`benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json`](benchmarks/2026-04-20_claude-sonnet-4-6_opus50.json)
- Full analysis: [`benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md`](benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md)
