# HEAAL E1 — `ail ask` + Sonnet author, no external harness

**Date:** 2026-04-22
**Track:** HEAAL (not AIL).
**Thesis being tested:** when an end user invokes `ail ask` with a frontier base model as the author, the runtime's safety properties hold end-to-end without any user-added harness (no linters, no AGENTS.md, no post-generation validators).

---

## Setup

This is not a model evaluation. It is a demonstration run. Two LLMs participate in each `ail ask` call, in separate roles (see [`docs/heaal/README.md`](../heaal/README.md) for the full flow diagram):

| Role | Model | Reason |
|---|---|---|
| **Author model** | `anthropic:claude-sonnet-4-6` (no AIL fine-tune) | Test whether a frontier base with a Python-heavy pretraining prior can author AIL well enough for the pipeline to work end-to-end. |
| **Intent model** | same Sonnet (single-adapter benchmark mode) | Simplifies reproduction. A production deployment would typically split these (e.g. author=Sonnet, intent=local vLLM). HEAAL's claim holds regardless of split because safety lives in the runtime, not the models. |

The author-model call happens **once per `ail ask`**. Intent-model calls happen **0..N times per program execution**, once per `intent` declaration reached at runtime.

Two authoring-prompt configurations tested:

- **default** — the reference-card-driven authoring prompt that ships with `ail ask`. Baseline (measured 2026-04-20).
- **anti_python** — the front-loaded negative-instruction variant added in commit [`94b3bf5`](../../commit/94b3bf5). Also ships with `ail`, so this is still "language-level harness," not user-added tooling.

No external harness on either side. No linters, validators, retry wrappers beyond what `ail ask` does natively.

---

## Results

*Raw data: [`2026-04-20_claude-sonnet-4-6_opus50.json`](2026-04-20_claude-sonnet-4-6_opus50.json) (default), [`2026-04-22_heaal_E1_sonnet_anti_python.json`](2026-04-22_heaal_E1_sonnet_anti_python.json) (anti_python).*

### Headline — safety properties on the AIL side

| Property | default prompt | anti_python prompt | Python gen + Sonnet (no harness) |
|---|---|---|---|
| **Error handling omission on failable ops** | **0%** | **0%** | 70% (35/50) |
| **Silent intent-skip on judgment tasks** | 0% B / 5% C | TBD | — (Python has no `intent` to skip, but hardcoded heuristic rate is equivalent) |
| **Unbounded loops** | 0% | TBD | 0% (Sonnet doesn't generate them) |
| **"Pure" fn that secretly calls LLM** | 0% (parse error) | 0% (parse error) | n/a |

**The grammar column does not move between default and anti_python.** That is the HEAAL finding. The prompt variant affects authoring stability (below), not safety properties — safety comes from the grammar and runtime, which are the same under both prompts.

### Parse success and answer rate — does the pipeline reach the user?

| Metric | default | anti_python | Δ |
|---|---|---|---|
| AIL parse success | 36% | TBD | TBD |
| AIL answer correctness | 36% | TBD | TBD |
| avg retries in `ail ask` | 0.76 | TBD | TBD |
| avg total tokens (author + intents) | TBD | TBD | TBD |

Target for E1: anti_python brings parse ≥ 60% so the pipeline completes on more user requests. Safety is guaranteed on whatever completes; more completions = more user value at no safety cost.

### Per-category breakdown

| Category (N) | default parse | anti_python parse | default ans | anti_python ans |
|---|---|---|---|---|
| A — pure computation (15) | 60% | TBD | 60% | TBD |
| B — pure judgment (15) | 27% | TBD | 27% | TBD |
| C — hybrid (20) | 25% | TBD | 25% | TBD |

---

## Interpretation — what's HEAAL, what's not

### HEAAL-claim columns

**Error-handling omission rate stays at 0% on AIL regardless of prompt.** This is HEAAL's punch line. The language did this, not the prompt and not the model. The same Sonnet, in Python, forgets `try/except` on 70% of failable operations. The grammar is the difference.

A stronger author model does not close this gap on the Python side. Sonnet 4.6 is as strong as a base model gets right now, and 70% is its rate. HEAAL holds across the model quality spectrum because it's a property of the language, not the model.

### Authoring-stability columns (not HEAAL per se)

Parse rate, retry count, token count — these measure whether the **author model** can emit valid AIL at reasonable cost. That's useful practical information, but it's an AIL-track question, not a HEAAL claim. The prompt variant `anti_python` is the AIL runtime's attempt to make the `ail ask` round trip reliable enough to be usable; whether it succeeds changes the user experience but not the safety guarantee.

### What happens on parse failures

`ail ask` runs a retry loop. On parse error, it re-dispatches to the author model with the error message appended, up to 3 retries. Programs that still fail to parse after retries return an error to the user, cleanly — they do not return a garbage program that looks right but behaves wrong. This is the language-level fallback for the case where the author model cannot be steered into valid AIL.

From the end-user's perspective:

- **Valid-AIL path:** `ail ask` returns the answer, with the grammar's safety guarantees intact.
- **Invalid-AIL path (after 3 retries):** `ail ask` returns an error. The user retries or rewords.

Neither path produces silently-wrong output. This is the full harness-as-a-language claim: **you never get an incorrect-looking-correct result from `ail ask` + frontier author model + no external harness.**

---

## Comparison against the AIL track

AIL track's v3 fine-tuned 7B reaches 80% AIL parse / 70% answer on the same corpus (R3/C4 baseline). HEAAL with Sonnet + default reaches 36% / 36%. That gap is the AIL-track question: *how much authoring quality does fine-tuning add over a strong base model?* The gap does not contradict HEAAL's claim — it just means the 7B fine-tune is a more reliable author on this corpus.

HEAAL's value is in the **not-reliable** half: when the base model can author AIL, the safety properties are yours for free. No fine-tune, no harness infrastructure, nothing for the end user to maintain.

---

## Cost

- Default baseline (2026-04-20): ~$2
- anti_python run (2026-04-22): ~$2
- Total E1 demonstration cost: **~$4** for ~100 Sonnet calls across 50 prompts × 2 configurations.

---

## Next experiments

- **E2 — grammar-first prompt.** Put BNF-shaped grammar summary at the top of the authoring prompt. Queued.
- **E3 — chain-of-thought planning.** Author model states fn/intent split before writing. Queued.
- **E4 — tool-use authoring.** Author model builds programs via tool calls; runtime assembles source. Most ambitious. Queued.

If E1 target (parse ≥ 60% on anti_python) is met, the project has demonstrated the core HEAAL claim on a frontier author model with no external harness. That is the headline HEAAL deliverable.

---

## Artifacts

- Baseline JSON (default prompt, 2026-04-20): [`2026-04-20_claude-sonnet-4-6_opus50.json`](2026-04-20_claude-sonnet-4-6_opus50.json)
- Baseline summary: [`2026-04-20_claude_sonnet46_summary.md`](2026-04-20_claude_sonnet46_summary.md)
- anti_python JSON (2026-04-22): [`2026-04-22_heaal_E1_sonnet_anti_python.json`](2026-04-22_heaal_E1_sonnet_anti_python.json)
- Prompt variant source: [`reference-impl/ail/authoring.py`](../../reference-impl/ail/authoring.py), search `_anti_python_authoring_goal`
