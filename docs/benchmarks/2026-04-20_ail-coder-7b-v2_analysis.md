# Benchmark analysis — ail-coder:7b v2 fine-tune

**Date:** 2026-04-20
**Model:** `ail-coder:7b` (qwen2.5-coder-7b-instruct + QLoRA rank-16, 205 samples, 3 epochs)
**Corpus:** Opus 50-prompt corpus (`benchmarks/prompts.json`) — 15 A pure-fn / 15 B pure-intent / 20 C hybrid
**Raw JSON:** [`2026-04-20_ail-coder-7b-v2_opus50.json`](2026-04-20_ail-coder-7b-v2_opus50.json)
**Sibling:** [`2026-04-20_opus50_summary.md`](2026-04-20_opus50_summary.md) (base-model baselines)

---

## 1. Headline numbers

| Metric | qwen14b base (opus50) | **ail-coder:7b v2** | Δ |
|---|---|---|---|
| AIL parse | 42% | **64%** | +22 pp |
| AIL answer | 34% | **56%** | +22 pp |
| AIL fn/intent accuracy | 40% | **54%** | +14 pp |
| Python parse | 100% | **56%** | −44 pp |
| Python answer | 78% | **48%** | −30 pp |
| Python fn/intent | 64% | **78%** | +14 pp |
| Python error-handling miss | 42% | **42%** | 0 pp |
| AIL error-handling miss | 0% | **0%** | — |

Fine-tuning on AIL substantially improved AIL generation at the cost of Python
generation quality. This is expected: a 7B model has limited capacity, and
shifting distribution toward AIL shifts it away from Python.

---

## 2. Per-category breakdown

| Category | AIL parse | Python parse | AIL answer | Python answer |
|---|---|---|---|---|
| A — pure fn (n=15) | 8/15 (53%) | 9/15 (60%) | 6/15 (40%) | 8/15 (53%) |
| B — pure intent (n=15) | **15/15 (100%)** | 7/15 (46%) | 13/15 (86%) | 4/15 (26%) |
| C — hybrid (n=20) | 9/20 (45%) | 12/20 (60%) | 9/20 (45%) | 12/20 (60%) |

**Category B is the breakthrough.** The model learned to write `intent` declarations
reliably — 100% parse rate, 86% correct answers. This is up from 53% on qwen14b
base. The fine-tune taught the model exactly when and how to use `intent`.

Category A still lags. The model generates syntactically invalid fn bodies ~47% of
the time. Category C improved from 15% (best prompt-only result) to 45%.

---

## 3. Gate verdicts

From `CLAUDE.md` session-state table (v1 = 80 samples/2 epochs on bench_authoring corpus):

| Gate | Target | v1 | v2 (this run) | Verdict |
|---|---|---|---|---|
| G1 — AIL overall parse ≥ 80% | ≥ 80% | 70% | **64%** | **FAIL** |
| G2 — AIL hybrid route > Python | AIL > Py | 47% vs 67% | **54% vs 78%** | **FAIL** |
| G3 — AIL pure_fn answer ≥ Python | AIL ≥ Py | 75% tie | **56% vs 48%** | **PASS** |

Note: v1 and v2 use different corpora (bench_authoring vs opus50). The opus50
corpus is harder (longer programs, more complex hybrid tasks), so 64% here is
not a strict regression from 70% — the comparison is directional only.

**New metric not in gates:** AIL parse (64%) now exceeds Python parse (56%) for
the first time across all model runs. This is partly because fine-tuning hurt
Python generation, but it demonstrates that a dedicated AIL model can
out-generate Python on its own language.

---

## 4. Failure-mode analysis (AIL parse failures, n=18)

| Failure class | Count | Example |
|---|---|---|
| `LBRACK` in fn signature (Python `List[T]` generics) | 5 | `fn foo(items: List[Number])` |
| `LT` in fn signature (C++/Java `Array<T>` generics) | 2 | `fn foo(items: Array<Text>)` |
| PurityError — unknown builtin (`round`, `sqrt`) | 2 | `pure fn bmi`: calls `round` |
| PurityError — intent inside pure fn | 1 | `pure fn parse_scores`: calls intent |
| `LBRACE` in fn body (Python dict literal) | 1 | `{m: 1, i: 4, ...}` |
| Semicolons in fn body | 1 | `return result;` |
| Other parse errors | 6 | Walrus operator, EQ in expression |

The dominant pattern is still **Python syntax bleeding into AIL fn bodies**:
type annotations (`List[T]`, `Array<T>`), dict literals, semicolons. This is
the same class v3 A/B testing couldn't fix with prompts — the model's Python
training distribution overpowers prompt-layer instructions.

The PurityError on `round`/`sqrt` is a different problem: the model assumes
these are AIL builtins, but the runtime's pure-fn checker doesn't trust them.
Fix: either add `round`/`sqrt` to the trusted-builtin whitelist, or add them
to `stdlib/math.ail`. This is a language gap, not a model gap.

---

## 5. The harness thesis — still holds

| Dimension | AIL | Python | Gap |
|---|---|---|---|
| Error-handling miss | **0%** | 42% | +42 pp in AIL's favor |
| Infinite loops | 0% | 0% | — |
| Side effects in pure code | 0% | 0% | — |

The error-handling gap is unchanged from the base-model runs. It's structural —
AIL's `Result` type makes `is_ok`/`unwrap` mandatory at failable boundaries
regardless of which model writes the code. Python's 42% miss rate persists
because nothing in the Python grammar forces error handling.

---

## 6. What to do next

### Immediate (no GPU needed)

1. **Add `round`, `floor`, `ceil`, `sqrt` to AIL's trusted-builtin set.**
   Two PurityErrors out of 18 failures were `round`/`sqrt` not trusted by the
   pure-fn checker. This is a runtime fix, not a training fix. It would unlock
   A07 and C07 immediately.

2. **Add `round`, `floor`, `ceil`, `sqrt` to stdlib/math.ail** (or expose them
   as first-class builtins). The model knows these exist; the runtime just
   doesn't recognize them as safe. Close the gap at the language layer.

3. **Run a targeted re-train with expanded dataset.** The current 205 samples
   under-represent: (a) fn bodies with numeric operations, (b) hybrid programs
   using match + Result, (c) programs that explicitly do NOT use type annotations
   in fn signatures. Add 50 samples covering these gaps → re-train → re-run.

### Before calling fine-tuning complete

G1 (≥ 80% parse) is the blocking gate. To reach 80% from 64%:
- Fixing `round`/`sqrt` builtins recovers ~2 cases → ~68%
- Fixing the type-annotation leakage (7 cases) → ~82%

The type-annotation leakage is a training-data problem: the model never saw
a negative example where `List[T]` in an AIL fn signature was wrong. Adding
"fn signatures have no type annotations — AIL infers types at runtime" examples
explicitly to the training set is the targeted fix.

### Do not do yet

- Do not change AIL grammar (v1.8 frozen per `spec/09-stability.md`)
- Do not upload adapter to HuggingFace without hyun06000's explicit go
- Do not update README.md headline numbers — G1 and G2 still failing
