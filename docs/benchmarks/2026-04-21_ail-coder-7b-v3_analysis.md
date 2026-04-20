# Benchmark analysis — ail-coder:7b v3 fine-tune

**Date:** 2026-04-21
**Model:** `ail-coder:7b-v3` (qwen2.5-coder-7b-instruct + QLoRA rank-16, **244 samples**, 3 epochs)
**Corpus:** Opus 50-prompt corpus (15 A / 15 B / 20 C)
**Raw JSON:** [`2026-04-21_ail-coder-7b-v3_opus50.json`](2026-04-21_ail-coder-7b-v3_opus50.json)
**Prior:** [`2026-04-20_ail-coder-7b-v2_analysis.md`](2026-04-20_ail-coder-7b-v2_analysis.md)

---

## 1. What changed vs v2

Three interventions between v2 and v3:

1. **Language additions (both runtimes)** — `round`, `floor`, `ceil`, `sqrt`, `pow` are now trusted-pure builtins. Previously failed C07 (BMI), C12 (std-dev) with PurityError.
2. **Parser fix (both runtimes)** — `List[Number]`, `Map[K,V]`, `Result[T]`, `Tuple[A,B]` now parse cleanly (spec §2.3 was previously aspirational). Previously failed any fn signature using the spec-valid parametric form.
3. **Dataset expansion** — +41 validated samples (205 → 244) covering the unlocked patterns: 7 math-builtin, 12 parametric-type, 14 hybrid, 8 other.

Training: 244 samples × 3 epochs, loss 2.577 → 0.089, 10m14s on 3070.

---

## 2. Headline numbers

| Metric | v2 | **v3** | Δ vs v2 |
|---|---|---|---|
| AIL parse | 64.0% | **78.0%** | **+14 pp** |
| AIL answer | 56.0% | **70.0%** | **+14 pp** |
| AIL fn/intent accuracy | 54.0% | 60.0% | +6 pp |
| AIL avg retries | 0.96 | 0.60 | −0.36 (better) |
| Python parse | 56.0% | 54.0% | −2 pp |
| Python answer | 48.0% | 48.0% | — |
| Python fn/intent | 78.0% | 76.0% | −2 pp |
| Error-handling miss (Py) | 42.0% | 44.0% | ~flat |
| Error-handling miss (AIL) | 0.0% | 0.0% | — |

**AIL answer 70% vs Python 48% — AIL is now winning the end-to-end quality metric by 22 percentage points on the same model.** The only other v3 regression is Python side (expected — the fine-tune is AIL-specialised; a 7B adapter can't improve both).

---

## 3. Per-category breakdown

| Category | v2 AIL parse | **v3 AIL parse** | v3 AIL answer | v3 Py answer |
|---|---|---|---|---|
| A — pure fn (n=15) | 53% | **73%** (+20 pp) | 67% | 53% |
| B — pure intent (n=15) | 100% | 93% (−7 pp) | 80% | 13% |
| C — hybrid (n=20) | 45% | **70%** (+25 pp) | 65% | 70% |

**Category C is the headline.** Hybrid programs went from 45% to 70% parse rate — a 55% relative improvement. This was the weakest category on v2 and the class that most directly tests AIL's fn/intent value proposition. The +14 hybrid samples and the math-builtin / parametric-type unlocks land on exactly this distribution.

Category B slipped one case (100% → 93%). The single B regression is B15 — a Python-style enum `goal: positive, negative, or neutral` clause with commas that the parser treats as statement separators. Fixing this is either a training-data note or a goal-clause grammar tweak; not a v3 bug.

Category A gained +20 pp on the math-builtin wins plus a few shape-of-program samples it had previously botched.

---

## 4. Gate verdicts

From the project's three gates:

| Gate | Target | v2 | **v3** | Verdict |
|---|---|---|---|---|
| G1 — AIL parse ≥ 80% | ≥ 80% | 64% | **78%** | **FAIL by 1 case** |
| G2 — AIL routing > Python | AIL > Py | 54% vs 78% | 60% vs 76% | **FAIL** |
| G3 — AIL answer ≥ Python | AIL ≥ Py | 56% vs 48% | **70% vs 48%** | **PASS (+22 pp)** |

G1 missed by one prompt. v3 gets 39/50 parses; 40/50 would have crossed 80%.

G2 remains open: the fine-tune improved AIL routing (54% → 60%) but Python's routing advantage is stable (76%) because when Python programs parse at all on a 7B AIL-specialised model, they tend to route correctly. This gate asks the wrong question on an AIL-specialised model — it compares *AIL authored by the fine-tune* vs *Python authored by the fine-tune*, and the Python side is no longer a fair opponent. The better comparator is AIL-v3 routing (60%) vs Python-qwen14b-base routing on the same corpus (64% on opus50 per v2 run).

---

## 5. Remaining AIL parse failures (11 total)

| Class | Count | Example | Root cause |
|---|---|---|---|
| Bracket indexing `list[i]` | 3 | `results[i-1]` in fibonacci | Model uses Python-style list subscript; AIL uses `get(list, i)` |
| PurityError — invented builtin | 2 | `has(seen, item)` / `mean(nums)` | Model invented a function that isn't an AIL builtin; gap in training data |
| `COMMA` in intent goal | 1 | `goal: positive, negative, or neutral` | Parser treats comma as statement separator |
| `for` keyword in intent goal | 1 | `goal: explain to a teenager...` — `for` is taken as for-loop | Goal clause parses as expression; `for` is reserved |
| `LBRACE` dict literal | 1 | `{c: count[c] for c in chars}` | Python dict/comprehension syntax |
| `&` bitwise operator | 1 | `if x % 2 == 0 & y...` | Python bitwise `&`; AIL has only boolean `and` |
| `ARROW` in params | 1 | lambda-shaped call | Python lambda leaked |
| Runtime error | 1 | `int(None)` on FizzBuzz output | Not a parse issue |

**The three "bracket indexing" failures are the most interesting.** Unlike v2's dominant parametric-type failure (fixed at language layer), subscript-style indexing is deeply habitual for Python-trained models. Options to address:

- **Language:** add `expr[index]` as sugar for `get(expr, index)` in the parser. Small change, high recovery.
- **Training:** explicit negative examples showing "prefer `get(xs, i)` over `xs[i]`". Incremental.
- **Prompt:** add an explicit line to the system prompt. Unknown magnitude based on v2/v3 A/B history.

The remaining 8 failures are long-tail — each a distinct pattern, each costing roughly 1 case. They will respond to dataset breadth more than to language changes.

---

## 6. The harness thesis — still holds

| Dimension | AIL v3 | Python | Gap |
|---|---|---|---|
| Error-handling miss | **0.0%** | 44.0% | +44 pp in AIL's favour |
| Side-effect in pure | 0.0% | 0.0% | — |
| Infinite loops | 0.0% | 0.0% | — |

The error-handling gap is stable across runs (42–70% on every model tier). It's structural to AIL's `Result` type forcing explicit `is_ok`/`unwrap` at failable boundaries. This is the one metric where AIL's advantage does not depend on the model.

---

## 7. What to do next

### Option A — push G1 across the 80% line (1 prompt away)

Add `expr[index]` subscript support to both parsers. Three cases (C07, C18, C19) failed on this alone — any one of them recovering lifts G1 from 78% to 80%. This is the cheapest path to passing G1.

Trade-off: subscript sugar is a grammar change. Spec §2.6 doesn't list it as frozen, but adding syntax during a freeze has historically been what §9 warns against. Proper form: write a `spec/10-proposals.md` entry, note the measured benchmark delta (3 cases), land it with both runtimes updated and a conformance case.

### Option B — close G2 by running the benchmark against a larger base

The G2 failure is a function of Python-side quality on a 7B model. Re-run the v3 benchmark with AIL generated by `ail-coder:7b-v3` and Python generated by `qwen2.5-coder:14b` (unfine-tuned). This gives a fairer AIL vs Python comparison — same *language skill level* on both sides — and is the comparison that external readers will care about.

### Option C — publish now

G3 (70% vs 48%) is the marketable number. It answers the concrete question "does using AIL produce better answers than using Python with the same tooling?" The honest headline is: **fine-tuning gets a 7B model to author AIL well enough that the AIL version out-answers the Python version by 22 percentage points, with zero error-handling bugs vs Python's 44%**.

G1 and G2 are open; the project's credibility does not depend on them passing today.

---

### Do not do

- Do not edit gate targets to make v3 read as a pass
- Do not publish the fine-tuned adapter without hyun06000's explicit go
- Do not update README.md headline numbers without hyun06000's review (the public pitch is visible; a silent regression is the worst outcome)
