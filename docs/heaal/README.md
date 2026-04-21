# HEAAL — Harness Engineering As A Language

HEAAL is the first project built **on top of** AIL. It is a separate track from the AIL language work itself.

- **AIL** answers: *does the language, by its design, produce safer and more correct code than Python on the same task?*
- **HEAAL** answers: *can a frontier base model write valid AIL without any fine-tuning — just through prompt-level harness engineering?*

AIL is the grammar and the runtime. HEAAL is what you get when you apply that grammar's discipline to a model the grammar was never trained on, using only the authoring prompt.

## Why separate?

The two tracks change different variables and produce different evidence:

| | AIL track | HEAAL track |
|---|---|---|
| Fixed | the language, the authoring prompt | the language |
| Varied | the model (via fine-tune), the training data | the authoring prompt |
| Success signal | *on the same model, AIL beats Python* | *on a strong base model, prompting reaches the AIL-fine-tune parse rate* |
| Resource | GPU (training, vLLM) | LLM APIs (Anthropic, OpenAI, etc.) |
| Iteration unit | hours (train + convert + benchmark) | minutes (API call) |
| Repo artifacts | `reference-impl/training/`, `docs/benchmarks/ail_*.json` | `docs/heaal/`, `docs/benchmarks/heaal_*.json` |

Mixing them introduces confounds — "did parse rate improve because the model got smarter or because the prompt got better?" — so the benchmarks are tagged by prefix and the analyses live in separate directories.

## The thesis

Claude Sonnet 4.6 on the 50-prompt corpus currently routes LLM calls correctly **100% of the time** and yet produces AIL that parses only **36% of the time**. The harness semantics are already in the model — it understands when judgment is needed. What it cannot do is emit AIL *syntax* reliably, because its pretraining distribution is heavily Python-biased.

HEAAL's premise: we do not need to teach Sonnet AIL. We need to prevent Sonnet from reaching for Python patterns when the harness asks for AIL. Everything else already works.

## Experiments

All HEAAL experiments share the same 50-prompt corpus (`benchmarks/prompts.json`) used by the AIL track, so the parse-rate and answer-rate columns are directly comparable.

### E1 — Anti-Python prompt variant (current)

**Hypothesis.** The standard authoring prompt describes AIL positively ("a program has one `entry main(...)` plus optional declarations…"). Positive description is ignored when it conflicts with pretraining prior. Negative instruction ("do NOT emit `List[T]`, do NOT use `x[0]` subscript") fights the prior directly, and the R2 benchmark (qwen2.5-coder:7b-v3 + FORBIDDEN SYNTAX block, +16pp answer) is preliminary evidence this works.

**Design.** Add a new prompt variant `anti_python` to `ail.authoring`. The variant front-loads a block of "will fail parse" patterns before the positive description, mirroring the FORBIDDEN SYNTAX approach that worked on the fine-tune in R2.

**Baseline.** Sonnet 4.6 with the standard prompt: AIL parse 36%, answer correctness 36% (see `docs/benchmarks/2026-04-20_claude_sonnet46_summary.md`).

**Target.** AIL parse ≥ 60% with the Anti-Python prompt alone.

**Cost.** ~$2 per run at 2026-04 Anthropic pricing.

### E2 — Grammar-first prompt *(queued)*

Put a minimal BNF-shaped grammar summary at the top of the prompt, before the prose.

### E3 — Chain-of-thought planning *(queued)*

Ask the model to state, before writing AIL, which parts of the task need `fn` versus `intent`. Then write.

### E4 — Structured tool-use authoring *(queued, most ambitious)*

Expose AIL structure as Anthropic tool definitions (`declare_pure_fn`, `declare_intent`, `set_entry`). The model constructs programs by calling tools; the harness assembles the source. The model never writes AIL syntax directly. This is the most complete version of "harness engineering as a language" — the grammar surface becomes a tool API.

## File naming convention

HEAAL benchmark artifacts live in the shared `docs/benchmarks/` directory but use a `heaal_` prefix:

- `docs/benchmarks/2026-04-22_heaal_E1_sonnet_anti_python.json` — raw run
- `docs/benchmarks/2026-04-22_heaal_E1_analysis.md` — writeup

AIL track benchmarks use a bare date or `ail_` prefix (current convention varies for historical reasons; new files SHOULD use `ail_`).

## Current status

*As of 2026-04-22:*

- Scaffold: this directory.
- E1: designed, not yet executed. Waiting on `anti_python` prompt variant landing in `ail.authoring`.
- Baseline reference: [`docs/benchmarks/2026-04-20_claude_sonnet46_summary.md`](../benchmarks/2026-04-20_claude_sonnet46_summary.md).
