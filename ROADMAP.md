# AIL Roadmap

No dates. This is a project with a direction, not a schedule.

---

## Current state (v1.8.3)

Language, runtime, benchmark, and fine-tune pipeline are all working.

- **Language:** `fn`, `pure fn`, `intent`, `attempt`, `match`, `evolve`, `Result`, provenance, calibration, implicit parallelism, effect system
- **Runtimes:** Python reference implementation (full feature set) + Go interpreter (core feature set)
- **Fine-tune:** `ail-coder:7b-v3` (qwen2.5-coder-7b + 244-sample QLoRA)
- **Benchmark:** 50 prompts, AIL vs Python, 4 measurement dimensions
- **Numbers:** AIL parse 78%, answer correctness 70% (Python 48%), error-handling omission 0%

---

## Next steps

### 1. G1 parse gate

AIL parse is currently 78%, one case short of the 80% target. All three remaining failures are Python-style `list[index]` subscript.

Options:
- **Parser sugar:** add `expr[index]` → `get(expr, index)` to both parsers. Small and targeted, but requires a `spec/10-proposals.md` entry first since the v1.8 grammar freeze is still in force. Land as v1.9.
- **Training samples:** add negative examples ("use `get(xs, i)`, never `xs[i]`") to the dataset and retrain.
- **Accept 78%:** G3 answer correctness (+22pp over Python) is the stronger headline. G1 was an internal gate, not a public promise.

### 2. Fairer G2 comparison

Current G2: AIL 60% vs Python 76% — Python wins. But the Python side was authored by the AIL-fine-tuned 7B, whose Python fluency has degraded. A fairer comparison:

- AIL side: `ail-coder:7b-v3` (60% routing — already measured)
- Python side: `qwen2.5-coder:14b` base (64% routing on the same corpus — already in JSON)

Run the benchmark with this configuration and add a row to `docs/benchmarks/README.md`.

### 3. One external user

The project has ~0 external users as of v1.8.3. The documentation and release are now in shape for a public introduction. Channels: X/Twitter demo video, GeekNews, direct outreach to AI researchers. This is a hyun06000 decision.

---

## v1.9 candidates

These features will be considered when the v1.8 grammar freeze lifts (conditions in `spec/09-stability.md`). None are committed work. All require a `spec/10-proposals.md` entry first.

- **`expr[index]` subscript** — `get(expr, index)` syntax sugar. Closes the G1 parse failures.
- **Per-symbol import** — `import classify from "stdlib/language"` currently imports the whole module. Should import only the named symbol.
- **Attempt + confidence threshold** — `attempt { try A with confidence > 0.8 }`. The parser reserves the syntax; the feature isn't implemented yet.

---

## Go runtime expansion

The Go interpreter covers: `fn`, `intent`, `entry`, control flow, `Result`, and `attempt`. Features still Python-only (provenance, purity checking, parallelism, calibration) can be brought to Go once the higher priorities above are resolved.

---

## Fine-tune v4 (conditional)

First, try to close the remaining G1 gap through prompt engineering alone. If the gap persists and the benchmark identifies AIL syntax unfamiliarity as the specific bottleneck, run a v4 fine-tune using the additional samples.

---

## What will NOT be done

- **No `while` loop.** Infinite loops are an AI code-generation failure mode. This decision does not change.
- **No classes / OOP / inheritance.** Outside the design scope.
- **No implicit effects.** Every effect is declared.
- **No silent evolution.** Every self-modification has a metric, bounds, and rollback.

---

## Proposing a change to this roadmap

Open an issue. Explain why the current order is wrong, what should come earlier, and what it enables that the current order does not.
