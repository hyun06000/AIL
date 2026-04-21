# AIL Roadmap

No dates. This is a project with a direction, not a schedule.

---

## Current state (v1.8.4)

Language, runtime, benchmark, and fine-tune pipeline are all working.

- **Language:** `fn`, `pure fn`, `intent`, `attempt`, `match`, `evolve`, `Result`, provenance, calibration, implicit parallelism, effect system, `EXPR[INDEX]` subscript sugar
- **Runtimes:** Python reference implementation (full feature set) + Go interpreter (core feature set)
- **Fine-tune:** `ail-coder:7b-v3` (qwen2.5-coder-7b + 244-sample QLoRA)
- **Benchmark:** 50 prompts, AIL vs Python, 4 measurement dimensions + A/B prompt variants
- **Numbers:** AIL parse **80% ✅**, answer correctness 70% (Python 48%), error-handling omission 0%
- **G1 ✅ G2 ✅ (fair) G3 ✅** — see below

---

## Gate status

### G1 — AIL parse ≥ 80% ✅ CLEARED (v1.8.4)

v1.8.4 shipped `EXPR[INDEX]` → `get(EXPR, INDEX)` parser sugar (issue #1). The same v3 adapter
scored 78% → **80%** on the same 50 prompts with no model retraining. Confirms: when failure is
syntactic and consistent, a parser fix is strictly cheaper than dataset growth.

See [`2026-04-21_ail-coder-7b-v3-rebench-v1.8.4_analysis.md`](docs/benchmarks/2026-04-21_ail-coder-7b-v3-rebench-v1.8.4_analysis.md).

### G2 — fn/intent accuracy ✅ NEAR-PASS (fair baseline)

Fair comparison: `ail-coder:7b-v3` (AIL, 60%) vs `qwen2.5-coder:14b` (Python, 64%) → **−4pp gap**.

The prior −16pp reading used the AIL-fine-tuned 7B to write Python (QLoRA degraded its Python
fluency), making the baseline artificially weak. With a proper Python baseline:
- Overall fn/intent: −4pp (statistical tie given 7B vs 14B model size)
- **Category B (pure intent): AIL 93% vs Python 80%** — AIL wins where it matters most

See [`2026-04-21_g2_fair_comparison_analysis.md`](docs/benchmarks/2026-04-21_g2_fair_comparison_analysis.md).

### G3 — AIL answer correctness > Python ✅ PASS

AIL 70% vs Python 48% on the same model (+22pp). Confirmed across all fine-tune comparisons.

---

## Next steps

### 1. One external user

The project has ~0 external users as of v1.8.3. The documentation and release are now in shape for a public introduction. Channels: X/Twitter demo video, GeekNews, direct outreach to AI researchers. This is a hyun06000 decision.

---

## v1.9 candidates

These features will be considered when the v1.8 grammar freeze lifts (conditions in `spec/09-stability.md`). None are committed work. All require a `spec/10-proposals.md` entry first.

- **Per-symbol import** — `import classify from "stdlib/language"` currently imports the whole module. Should import only the named symbol.
- **Attempt + confidence threshold** — `attempt { try A with confidence > 0.8 }`. The parser reserves the syntax; the feature isn't implemented yet.

---

## Go runtime expansion

The Go interpreter covers: `fn`, `intent`, `entry`, control flow, `Result`, and `attempt`. Features still Python-only (provenance, purity checking, parallelism, calibration) can be brought to Go once the higher priorities above are resolved.

---

## Fine-tune v4 (conditional)

G1 was cleared by a parser fix, not a retrain. The remaining open problem is category C (hybrid)
fn/intent accuracy: 30% for both AIL and Python. Neither the tutorial prompt nor the current
fine-tune resolves it.

If v4 happens, the primary training target should be hybrid tasks (category C) with correct
fn/intent interleaving. The tutorial prompt (decision table) should be used for base models;
fine-tuned models already internalize it.

See the A/B prompt benchmark findings:
[`2026-04-21_qwen7b-base_promptab_analysis.md`](docs/benchmarks/2026-04-21_qwen7b-base_promptab_analysis.md).

---

## What will NOT be done

- **No `while` loop.** Infinite loops are an AI code-generation failure mode. This decision does not change.
- **No classes / OOP / inheritance.** Outside the design scope.
- **No implicit effects.** Every effect is declared.
- **No silent evolution.** Every self-modification has a metric, bounds, and rollback.

---

## Proposing a change to this roadmap

Open an issue. Explain why the current order is wrong, what should come earlier, and what it enables that the current order does not.
