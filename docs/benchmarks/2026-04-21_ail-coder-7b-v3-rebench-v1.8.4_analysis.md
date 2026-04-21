# ail-coder:7b-v3 re-bench under v1.8.4 — G1 cleared

**Date:** 2026-04-21
**Model:** `ail-coder:7b-v3` (unchanged from the v3 fine-tune released in v1.8.3)
**Runtime:** v1.8.4 (`EXPR[INDEX]` subscript sugar landed)
**Corpus:** Opus 50-prompt, all categories
**Snapshot:** [`2026-04-21_ail-coder-7b-v3-rebench-v1.8.4_opus50.json`](2026-04-21_ail-coder-7b-v3-rebench-v1.8.4_opus50.json)

## Why this run exists

The v3 fine-tune missed the G1 ≥ 80% AIL parse gate by exactly one
case (78%). Three of the remaining parse failures used Python-style
`list[index]` subscript instead of the canonical `get(list, index)`.
Issue [#1](https://github.com/hyun06000/AIL/issues/1) proposed
fixing this with a parser-level desugar — `EXPR[INDEX]` →
`get(EXPR, INDEX)` — rather than retraining the model. v1.8.4
shipped that change. This run measures what the fine-tune now
scores against the same 50 prompts, with the model and adapter
untouched.

## Headline

**G1 cleared at exactly 80%.** The v3 model went from 78% AIL
parse rate (under v1.8.3) to **80%** (under v1.8.4) without a
single byte of model retraining. The language change carried the
gate.

This is a meaningful project precedent: when the failure mode is a
syntactic one the model produces consistently, a parser change is
strictly cheaper than dataset growth + retraining.

## Numbers

| Dimension | v3 under v1.8.3 (prior) | v3 under v1.8.4 (this) | Δ |
|---|---|---|---|
| AIL parse | 78% | **80%** ✅ | +2pp |
| AIL exec | 78% | 80% | +2pp |
| AIL answer | 70% | 70% | 0 |
| AIL fn/intent accuracy | 60% | 60% | 0 |
| Python parse | 54% | 50% | -4pp* |
| Python answer | 48% | 46% | -2pp* |
| AIL err-handling miss | 0% | **0%** | 0 |
| Python err-handling miss | 44% | 44% | 0 |

\* Python rates moved within model nondeterminism (same prompt,
different sampling). Not attributable to the parser change since
v1.8.4 doesn't touch Python authoring.

The two metrics that should have moved did, in the right
direction. The two metrics that shouldn't have moved (err-handling,
fn/intent accuracy) didn't.

## What the remaining 10 parse failures look like

Failure modes in the 10 cases that still don't parse, by class:

| Class | Count | Example | Root cause |
|---|---|---|---|
| **Invented fn called from `pure fn`** | 3 | `has(...)`, `mean(...)`, `pop(...)` not trusted-pure builtins | Model invents helpers without writing them as `pure fn` first. PurityError fires correctly. |
| **Python control-flow / literal leak** | 4 | dict literal `{...}`, set comprehension `{... for ...}`, `for x of y`, `&` operator | Python prior the parser still rejects. |
| **Stray comma / paren** | 2 | `B15`, `A08` | Tokenization-level slips. |
| **Internal harness bug** | 1 | `A09` `int(None)` raised inside calibration code | Not a model output problem; benchmark.py crash. Track separately. |

Notice `list[index]` is **not on this list anymore** — the
subscript desugar caught all instances of that pattern in the
50-prompt corpus.

## Implication for the next training cycle

Of the 9 model-attributable failures (excluding A09), 3 are
"invented helper not declared as `pure fn`" and 4 are "Python
literal/operator the parser correctly rejects". A v5 fine-tune
shouldn't try to brute-force these:

- The "invented helper" pattern is learnable from a small dataset
  expansion that shows the model declaring the helper as a
  separate `pure fn` before calling it. ~5 samples should move
  the needle.
- The Python literal/operator class (4 cases) is the same
  training-distribution problem the project has been working
  against from the start. Two paths: either grow the dataset
  with the rejected patterns rewritten in canonical AIL, or
  desugar more Python shapes the way `[index]` was desugared
  here. The desugar path has just demonstrated its value; we
  should be aggressive about it.

## What this run does NOT measure

- A v4 fine-tune. The model is byte-identical to v3.
- The G2 routing gate. v3's routing accuracy stayed at 60% —
  unchanged because nothing in v1.8.4 touched fn/intent
  classification.
- The G3 answer gate. v3's answer rate stayed at 70% vs Python
  46% — same +24pp gap, slightly wider than the +22pp from
  v1.8.3 only because Python's rate moved down.

## Reproduction

```bash
ssh homeblack
cd ~/AIL && git pull   # must be at v1.8.4 or later
export OLLAMA_HOST=10.0.0.1:11434 \
       AIL_OLLAMA_MODEL=ail-coder:7b-v3 \
       BENCHMARK_BACKEND=ollama \
       AIL_OLLAMA_TIMEOUT_S=600
~/venv/labs/bin/python reference-impl/tools/benchmark.py \
    --out docs/benchmarks/$(date +%F)_$YOUR-LABEL.json
```

~5 minutes on the 3070 with the model warm. A cold-start adds
~30s for Ollama to load the GGUF.

## Related

- [`2026-04-21_ail-coder-7b-v3_analysis.md`](2026-04-21_ail-coder-7b-v3_analysis.md) — the original v3 analysis (G1 missed by one case)
- [Issue #1](https://github.com/hyun06000/AIL/issues/1) — the subscript-sugar proposal that this run validates
- [v1.8.4 CHANGELOG entry](../../CHANGELOG.md#v184--2026-04-21)
- [`spec/09-stability.md` §3](../../spec/09-stability.md) — the additive-parser-desugaring policy that made shipping this in a patch release legal
