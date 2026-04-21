# 5-Way Same-Size Benchmark — Analysis

**Date:** 2026-04-21
**Model size:** 7B (all conditions)
**Cases:** 50 prompts × 4 AIL conditions

---

## Experimental design

| Condition | AIL model | AIL prompt | Python model | Python baseline |
|---|---|---|---|---|
| C1 (base/nofs) | qwen2.5-coder:7b-base | default | qwen7b-base | ✅ fair |
| C2 (base/tut)  | qwen2.5-coder:7b-base | tutorial | qwen7b-base | ✅ fair |
| C3 (Py only)   | — | — | qwen7b-base | = C1 Python side |
| C4 (ft/nofs)   | ail-coder:7b-v3 | default | ail-coder:7b-v3 | ⚠️ degraded |
| C5 (ft/tut)    | ail-coder:7b-v3 | tutorial | ail-coder:7b-v3 | ⚠️ degraded |

> **Caveat on C4/C5 Python:** with only one GPU available, Python code was also authored on the fine-tune server. The fine-tuned model's Python authoring is degraded (parse 46% vs base 66%). The fair Python comparison line for C4/C5 AIL is **C1 Python side (56% answer)**.

---

## Overall results

### A. Answer correctness (`answer_ok_rate`)

| Condition | AIL | Python (same model) | Python baseline (C3) |
|---|---|---|---|
| C1 base/nofs | 42% | 56% | 56% |
| C2 base/tut  | 48% | 56% | 56% |
| C4 ft/nofs   | 48% | 38%⚠️ | 56% |
| C5 ft/tut    | **52%** | 38%⚠️ | 56% |

**Best combination: fine-tune + tutorial (C5)** — 42% → 52% (+10pp)
**Fair comparison:** best AIL (C5) 52% vs Python qwen7b-base 56% = **−4pp**

---

### B. Per-category accuracy

#### Category A — pure computation (fn only, 15 prompts)

```
xychart-beta
  title "Cat A (pure computation) accuracy"
  x-axis ["C1 base/nofs", "C2 base/tut", "C4 ft/nofs", "C5 ft/tut", "Py(C3)"]
  y-axis "accuracy %" 0 --> 100
  bar [47, 33, 40, 47, 73]
```

- Python qwen7b-base **73%** vs best AIL 47% — **Python leads by +26pp**
- Tutorial hurts AIL on Cat A (C1 47% → C2 33%): the tutorial nudges toward `intent` usage, which backfires on pure-fn problems
- Fine-tuning has little effect on Cat A

#### Category B — pure judgment (intent only, 15 prompts)

```
xychart-beta
  title "Cat B (pure judgment) accuracy"
  x-axis ["C1 base/nofs", "C2 base/tut", "C4 ft/nofs", "C5 ft/tut", "Py(C3)"]
  y-axis "accuracy %" 0 --> 100
  bar [53, 87, 60, 80, 7]
```

- **AIL dominates**: best AIL C2 87% vs Python 7%
- Python at 7% because the base model has no way to declare `intent` — it just writes Python functions without any LLM call and returns an empty response
- Tutorial effect is dramatic: base C1 53% → C2 87% (+34pp)
- Fine-tune effect: C1 53% → C4 60% (+7pp)

#### Category C — hybrid (fn + intent, 20 prompts)

```
xychart-beta
  title "Cat C (hybrid) accuracy"
  x-axis ["C1 base/nofs", "C2 base/tut", "C4 ft/nofs", "C5 ft/tut", "Py(C3)"]
  y-axis "accuracy %" 0 --> 100
  bar [30, 30, 45, 35, 80]
```

- Python qwen7b-base **80%** vs best AIL C4 45% — Cat C is AIL's biggest weakness right now
- **Fine-tune helps Cat C**: C1 30% → C4 45% (+15pp)
- Tutorial is neutral or slightly negative on Cat C

---

### C. Parse success rate

| Condition | AIL parse | Python parse |
|---|---|---|
| C1 base/nofs | 54% | 66% |
| C2 base/tut  | **60%** | 66% |
| C4 ft/nofs   | 58% | 46%⚠️ |
| C5 ft/tut    | 56% | 46%⚠️ |

- Tutorial improves AIL parse (C1 54% → C2 60%, +6pp)
- Python parse drops from 66% to 46% on the fine-tuned model — the fine-tune has specialized toward AIL syntax

---

### D. fn/intent routing accuracy

| Condition | AIL fn/intent | Python fn/intent |
|---|---|---|
| C1 base/nofs | 48% | 72% |
| C2 base/tut  | 52% | 72% |
| C4 ft/nofs   | **54%** | 80% |
| C5 ft/tut    | **54%** | 80% |

- Fine-tune consistently improves fn/intent routing on AIL (+6pp)
- Python still leads on routing accuracy because qwen7b-base was simply trained on more Python

---

### E. Harness properties (language-level)

| Metric | AIL (all conditions) | Python qwen7b-base |
|---|---|---|
| Error handling omission | **0%** | **40–50%** |
| Infinite loops | **0%** | 0% (this run) |
| Structural safety | **100% (grammar)** | 0% (requires external tooling) |

- These numbers come from **language design**, not model or prompt — they don't change when conditions change.
- Python 40–50% error-handling omission: `try/except` dropped on failable operations.

---

### F. Token and time efficiency

| Condition | AIL total tokens | Python total tokens | AIL wall time (ms) | Python wall time (ms) |
|---|---|---|---|---|
| C1 | 4,261 | 327 | 14,092 | 1,633 |
| C2 | 4,537 | 327 | 12,891 | 1,594 |
| C4 | 4,126 | 334 | 11,501 | 1,810 |
| C5 | 4,398 | 334 | 13,629 | 1,775 |

- AIL uses **~13× more tokens** than Python — most of the authoring prompt is the reference card.
- AIL wall time is **~7–8× slower** — authoring LLM call is the bottleneck.
- Fine-tune improves wall time: C1 14,092ms → C4 11,501ms (−18%).

---

## Key findings

### Where AIL wins

| Metric | AIL | Python |
|---|---|---|
| **Cat B (pure intent)** | **87%** (C2) | 7% |
| **Error handling** | **0% miss** | 40–50% miss |
| **Structural safety** | **100%** (grammar guaranteed) | 0% |

Cat B shows a **12× gap** (87% vs 7%). The Python base model has no way to declare `intent`, so it skips LLM calls entirely.

### Where Python wins

| Metric | Python | Best AIL |
|---|---|---|
| **Cat A (pure computation)** | 73% | 47% |
| **Cat C (hybrid)** | 80% | 45% |
| **Overall answer rate** | 56% | 52% |
| **Tokens per task** | 327 | 4,261 |
| **Wall time** | 1,633ms | 11,501ms |

### Improvement trajectory

| Condition | AIL answer rate | vs Python (C3) |
|---|---|---|
| C1 base/nofs (starting point) | 42% | −14pp |
| C2 base/tut | 48% | −8pp |
| C4 ft/nofs | 48% | −8pp |
| **C5 ft/tut (best)** | **52%** | **−4pp** |

Fine-tune + tutorial narrowed the gap from −14pp to −4pp. **Cat B has already flipped in AIL's favor.**

---

## Next priorities

### 1. Cat A and Cat C are where the gap is

- Cat A (fn): AIL stuck at 47%. Analyze failure cases around loop / arithmetic generation inside `fn`.
- Cat C (hybrid): 30–45%. Python wins Cat C (80%) by reducing hybrid problems to pure-fn solutions. AIL should add hybrid few-shot examples to the base (non-tutorial) prompt.

### 2. Token efficiency

- Most of the ~4,000 prompt tokens is the reference card. Consider compressing or loading selectively.

### 3. Cat C samples for v4 fine-tune

- HANDOFF.md criterion: retrain when ≥20 Cat C failure cases are collected.

---

*Generated from:*
- `2026-04-21_5way_cond1_base_nofewshot.json`
- `2026-04-21_5way_cond2_base_tutorial.json`
- `2026-04-21_5way_cond4_finetuned_nofewshot.json`
- `2026-04-21_5way_cond5_finetuned_tutorial.json`
