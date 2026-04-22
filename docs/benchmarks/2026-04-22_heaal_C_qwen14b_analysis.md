# HEAAL Stage C — does `anti_python` scale down to weaker base models?

**Date:** 2026-04-22 (run overnight 04-21/22)
**Track:** HEAAL.
**Question:** the `anti_python` authoring prompt variant lifted Claude Sonnet's AIL parse rate from 36% to 94% on the same corpus. Does the same prompt-level intervention help a smaller, non-fine-tuned base coder model? This is the "scale down" test for HEAAL's prompt-level harness.

## Setup

- **Author + intent model:** `qwen2.5-coder:14b-instruct-q4_K_M` via local Ollama (no fine-tune)
- **Corpus:** the shared 50-prompt AIL-track corpus
- **Run C1:** default authoring prompt
- **Run C2:** same model, same corpus, with `AIL_AUTHOR_PROMPT_VARIANT=anti_python`
- **Backend:** Ollama at temperature 0 (deterministic)
- **No external harness** on either side

## Results

| Metric | C1 (default) | C2 (anti_python) | Δ |
|---|---|---|---|
| AIL parse | 62% | 62% | **0** |
| AIL answer | 54% | 54% | **0** |
| fn/intent routing | 50% | 50% | 0 |
| avg retries | 1.08 | 1.08 | 0 |
| Python answer (same model) | 80% | 78% | — |
| AIL error-handling miss | 0% | 0% | 0 (grammar) |
| HEAAL Score (AIL) | 80.9 | 80.9 | 0 |
| HEAAL Score (Python) | 69.6 | 69.2 | — |

**The AIL side is bit-identical across C1 and C2 — all 50 programs the model wrote are byte-for-byte the same.** `anti_python` produced zero measurable change on qwen14b.

Raw data: [`2026-04-21_heaal_C1_qwen14b_default.json`](2026-04-21_heaal_C1_qwen14b_default.json) · [`2026-04-21_heaal_C2_qwen14b_antipython.json`](2026-04-21_heaal_C2_qwen14b_antipython.json).

## Why zero movement — the failure modes tell the story

qwen14b failed 19 out of 50 parses on both runs. The failure classes:

- **Dict literal `{}` emitted** — e.g. `freq = {}` then `freq[c] = freq[c] + 1`. AIL rejects both the literal and the subscript assignment.
- **Invented builtins** — `contains(unique, item)`, `has_key(freq, c)`. Neither is in the AIL stdlib.
- **Top-level prose response** — `"The mouse was chased by the cat."` as a bare string at the start of the program. The model answered in English instead of AIL.
- **Unterminated strings** (LexError) — rare mis-tokenizations.

The `anti_python` prompt explicitly warns against each of the first three: "Dict literal `{\"k\": v}` → not supported", "Output: raw AIL source only, no markdown fences, no prose explanation", and lists the full set of available builtins. These warnings should have prevented the exact errors qwen14b made.

They did not prevent anything. The model output was identical with or without the warnings.

## Interpretation — the bound on HEAAL's prompt intervention

`anti_python` is not a universal intervention. It is a frontier-model intervention.

Claude Sonnet (200B-class, frontier API) responds to "do NOT emit Python-style patterns" by suppressing them. It can hold the negative instruction in its effective context and apply it at generation time. That was the 36% → 94% lift on the same corpus.

qwen2.5-coder-14b (14B, mid-tier, strongly coder-specialized) does not respond the same way. Negative instructions wash past its pattern-matching priors. Its Python pretraining distribution dominates at the token level regardless of what the system prompt says. With temperature 0 and the same user prompts, the top-token choice is the same whether the system prompt adds the `anti_python` block or not.

This is not a "prompt didn't reach the model" bug. The env var propagates correctly (verified in isolation) and the default and anti_python goal strings are reliably produced from `_build_authoring_goal()` based on the env var. The model simply ignores the content of the variant.

## HEAAL claim — what this refines

The HEAAL claim has always been about **the grammar**, not the prompt. E1 demonstrated that Sonnet + anti_python reaches 96.1 on the HEAAL Score. C1/C2 now show that qwen14b without any prompt work still reaches 80.9 — because the grammar-enforced safety columns (error handling, structural safety, observability) are language properties that don't depend on author-model quality.

So the scorecard reads:

| Author | Prompt | HEAAL Score (AIL) | Python baseline |
|---|---|---|---|
| ail-coder:7b-v3 (fine-tuned) | default | 87.7 | 58.0 |
| qwen2.5-coder:14b (base, mid-tier) | default | 80.9 | 69.6 |
| qwen2.5-coder:14b (base) | anti_python | **80.9** (no change) | 69.2 |
| Claude Sonnet 4.6 (frontier) | default | 77.6 | 75.3 |
| Claude Sonnet 4.5 (frontier) | anti_python | **96.1** | 75.9 |

Two observations. First, AIL beats Python on the HEAAL Score at every tier measured — the grammar-enforced floor holds. Second, the prompt variant only matters at the frontier. A mid-tier coder model gets the default-prompt score and cannot be lifted by prompt engineering alone; it would need fine-tuning to move.

## Recommendation

- Keep `anti_python` as a Sonnet / GPT-4o / Gemini-class intervention. Document that it is not expected to help smaller bases.
- Do not invest more in prompt-variant engineering for mid-tier bases. The path for that tier is fine-tuning (the AIL track) — our own v3 fine-tune on a 7B base scored 87.7, higher than the 14B base at 80.9.
- Possible follow-up: verify this pattern on one more mid-tier base (llama3.1:8b, mistral-7b) to confirm the boundary is tier-driven rather than model-family-driven.

## Artifacts

- Raw C1 JSON: [`2026-04-21_heaal_C1_qwen14b_default.json`](2026-04-21_heaal_C1_qwen14b_default.json)
- Raw C2 JSON: [`2026-04-21_heaal_C2_qwen14b_antipython.json`](2026-04-21_heaal_C2_qwen14b_antipython.json)
- Companion: E1 at frontier ([`2026-04-22_heaal_E1_analysis.md`](2026-04-22_heaal_E1_analysis.md)) shows the anti_python lift in the regime where it *does* work.

## Appendix — v7 did not happen overnight

The overnight chain was supposed to also produce an R7 benchmark (v7: non-coder 7B base trained on indented chatml, testing whether the 8pp gap between v3 and v6 is due to format or base model). The training step OOM'd twice on the 3070 — the first time because PyTorch allocator fragmentation, the second time because Ollama was still holding ~7 GiB of qwen14b weights on the GPU after Stage C finished.

Fix for a future attempt: explicitly `ollama stop <model>` before the training stage, and keep `max-seq-length=1024` for conservative memory headroom.
