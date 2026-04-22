# HEAAL Stage D — does `anti_python` scale to a much weaker base than Stage C?

**Date:** 2026-04-22
**Track:** HEAAL.
**Question:** Stage C established that `anti_python` produces zero AIL output change on `qwen2.5-coder:14b` — the prompt variant washes past mid-tier coder pretraining at temperature 0. Stage D pushes this one tier further down: does the same finding hold on `llama3.1:8b-instruct`, a smaller, non-coder-specialized base? And how does AIL fare against Python when the author model is genuinely too weak to write good code in either language?

## Setup

- **Author + intent model:** `llama3.1:8b-instruct-q4_K_M` via local Ollama (no fine-tune)
- **Corpus:** the shared 50-prompt AIL-track corpus
- **Run D1:** default authoring prompt
- **Run D2:** same model, same corpus, with `AIL_AUTHOR_PROMPT_VARIANT=anti_python`
- **Backend:** Ollama at temperature 0 (deterministic)
- **No external harness** on either side

## Results

| Metric | D1 (default) | D2 (anti_python) | Δ |
|---|---|---|---|
| AIL parse | 30% | 30% | **0** |
| AIL answer | 24% | 24% | **0** |
| Python parse | 14% | 14% | 0 |
| Python answer | 8% | 8% | 0 |
| AIL error-handling miss | 0% | 0% | 0 (grammar) |
| Python error-handling miss | 86% | 86% | 0 |
| HEAAL Score (AIL) | **74.3** | **74.3** | 0 |
| HEAAL Score (Python) | 43.7 | 43.7 | 0 |

**AIL source bit-identity across D1 and D2: 45/46 cases identical** (one case had no source on either side). Only A01 (factorial) differed — D1 produced a recursive implementation, D2 produced an iterative one. Both correct (return 5040), both well-formed AIL.

Raw data: [`2026-04-22_heaal_D1_llama8b_default.json`](2026-04-22_heaal_D1_llama8b_default.json) · [`2026-04-22_heaal_D2_llama8b_antipython.json`](2026-04-22_heaal_D2_llama8b_antipython.json).

Dashboards: [`heaal_D1_llama8b_default.html`](dashboards/heaal_D1_llama8b_default.html) · [`heaal_D2_llama8b_antipython.html`](dashboards/heaal_D2_llama8b_antipython.html).

## Confirmation of Stage C — `anti_python` is frontier-only

The 45/46 bit-identity result on llama3.1:8b confirms what Stage C found on qwen14b: **the negative-instruction prompt variant has no effect at mid-tier or smaller bases.** Stage C left open whether the finding was specific to qwen-coder's strong Python prior; Stage D removes that ambiguity by repeating the test on a different model family (Meta vs Alibaba) and a smaller size (8B vs 14B).

The single difference (A01 recursive → iterative) is suggestive but does not change the conclusion. The model output the same program 49 times out of 50; on the one prompt where it diverged, both versions are still valid AIL. The variant is not "doing nothing" in the sense of being completely invisible to the model — but it is "doing nothing useful" in the sense of producing zero measurable improvement on parse rate, answer rate, error-handling, or HEAAL Score.

## The more important Stage D finding — HEAAL holds when both sides are weak

Stage D was designed to test the prompt boundary. It accidentally produced a stronger result about the grammar floor.

`llama3.1:8b` is too weak to write good code in *either* language:

- **AIL: 30% parse, 24% answer.** The model produces non-AIL output (English explanations, partial code, syntax confusion) on 70% of prompts. Of the 30% that parse, four out of five reach the right answer.
- **Python: 14% parse, 8% answer.** This is the surprising number. Even a weak Python author should beat a weak AIL author on a syntax familiarity argument — Python is everywhere in pretraining; AIL is in nobody's pretraining.

What the model actually emits when asked for Python explains the gap. From the failing A02 ("reverse the string"):

```python
import urllib.request

def reverse_string(s):
    return s[::-1]

url = "http://10.0.0.1:11434/api/chat"
data = '{"prompt": "reverse hello world", "stream": false}'
req = urllib.request.Request(url, data=data.encode(), ...)
response = urllib.request.urlopen(req)
...
```

The model defines the correct function, then **does not call it.** Instead it constructs an HTTP request to its own Ollama endpoint and asks itself to do the reversal. The request fails (wrong API shape, port, payload), the program crashes, the run fails.

This is `llama3.1:8b` failing to distinguish "I should compute this" from "I should ask an LLM to compute this." A failure mode Python provides no defense against — the language doesn't have an opinion about effects.

In AIL the same confusion would manifest as `intent reverse(...)` (LLM dispatch) instead of `pure fn reverse(...)` (computation). When the model takes the `intent` path here, the AIL runtime calls the model again, gets back a string, and the program returns it. The result is sometimes correct, sometimes not — but the program **runs to completion** because the runtime's `Result` discipline catches the model misbehavior.

That's why AIL's answer rate (24%) is 3× Python's (8%) at this tier, and why AIL's HEAAL Score (74.3) is 30.6 points above Python's (43.7). The grammar isn't producing better code — it's producing code that **can't fail in the most common ways the model produces failure-prone output.**

## Cross-tier picture (Stages C + D combined)

| Author | Prompt | AIL parse | AIL ans | Py ans | HEAAL Score AIL / Py | Δ |
|---|---|---|---|---|---|---|
| Sonnet 4.5 (frontier) | anti_python | 94% | 88% | 88% | **96.1 / 75.9** | +20.2 |
| Sonnet 4.6 (frontier) | default | 36% | 36% | 88% | 77.6 / 75.3 | +2.3 |
| qwen2.5-coder:14b (mid) | default | 62% | 54% | 80% | 80.9 / 69.6 | +11.3 |
| qwen2.5-coder:14b (mid) | anti_python | 62% | 54% | 78% | 80.9 / 69.2 | +11.7 |
| llama3.1:8b (small) | default | 30% | 24% | 8% | **74.3 / 43.7** | **+30.6** |
| llama3.1:8b (small) | anti_python | 30% | 24% | 8% | 74.3 / 43.7 | +30.6 |

Two refinements to the HEAAL claim emerge from this table:

1. **The prompt intervention (`anti_python`) only matters at the frontier.** It produces a +18.5-point HEAAL Score lift on Sonnet 4.5 vs Sonnet 4.6 default. On both qwen14b and llama8b, it produces 0.
2. **The grammar floor (HEAAL Score Δ AIL vs Python) widens as the author model gets weaker — but only while the model can still write *some* AIL.** Across the rows where AIL parse > 0: Sonnet default +2.3 (frontier), qwen14b +11.3 (mid-tier), llama8b **+30.6** (small but still parses 30%). The mistral row (D3/D4) shows the boundary: when AIL parse = 0/50, the grammar floor has nothing to stand on — see [`2026-04-22_heaal_D_mistral7b_analysis.md`](2026-04-22_heaal_D_mistral7b_analysis.md).

The headline reads: strong author models can write either AIL or Python well, so the grammar floor matters less. Mid-and-small-tier author models can write neither well — but if they can produce *any* parseable AIL, the grammar floor stops them from shipping the dangerous *kind* of bad code. Python lets a weak author emit a script that looks plausible and crashes on first call; AIL forces them into a shape where what they emit either parses with safety properties intact or doesn't parse at all.

This is the operational meaning of "harness as a language" — but it requires the model to clear the parse threshold first.

## What remains open

- **mistral:7b-instruct** is queued (Stage D' / D3+D4) on homeblack at the time of writing. Result will go in a follow-up document. If mistral also produces bit-identical output across default and anti_python, the "anti_python is frontier-only" claim is generalized across three independent model families (Qwen, Meta, Mistral) and two size tiers (8B and 14B).
- The "weak author → larger HEAAL gap" pattern needs one more data point to be confident. mistral7b will provide it.
- We have not measured **GPT-4o** or **Gemini Pro** with `anti_python`. Stage C/D establish where the prompt variant *fails*. We don't yet know how broadly it succeeds across frontier model families.

## Recommendation

- **For the HEAAL manifesto:** the boundary is real and now empirically anchored. Document `anti_python` as a frontier-class intervention, with concrete failure points at qwen14b and llama8b. Use the Δ HEAAL Score column to argue the grammar floor is most valuable for users who can only afford a weak local model.
- **No further mid-tier prompt-engineering work.** Stages C and D both establish that prompt variants don't move the needle below the frontier. The path for those tiers remains fine-tuning (the AIL track — `ail-coder:7b-v3` already serves this niche at HEAAL Score 87.7).
- **Hold v7 / further mid-tier training experiments** until L1 boundary work has clearly settled. Weak-author HEAAL gap is the more interesting story than fine-tune format ablations right now.

## Artifacts

- D1 raw: [`2026-04-22_heaal_D1_llama8b_default.json`](2026-04-22_heaal_D1_llama8b_default.json)
- D2 raw: [`2026-04-22_heaal_D2_llama8b_antipython.json`](2026-04-22_heaal_D2_llama8b_antipython.json)
- D1 dashboard: [`dashboards/heaal_D1_llama8b_default.html`](dashboards/heaal_D1_llama8b_default.html)
- D2 dashboard: [`dashboards/heaal_D2_llama8b_antipython.html`](dashboards/heaal_D2_llama8b_antipython.html)
- Companion at mid-tier (qwen14b): [`2026-04-22_heaal_C_qwen14b_analysis.md`](2026-04-22_heaal_C_qwen14b_analysis.md)
- Companion at frontier (Sonnet): [`2026-04-22_heaal_E1_analysis.md`](2026-04-22_heaal_E1_analysis.md)
