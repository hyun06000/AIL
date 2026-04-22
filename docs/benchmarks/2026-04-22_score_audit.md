# HEAAL Score audit — methodology correction, 2026-04-22

We discovered two methodology bugs in the HEAAL Score formula and corrected them. This document is the public record of what changed, why, and which previously published numbers move.

We are publishing this audit because the original numbers were on our README, in our dashboards, and in our v1.8.5 release notes. Quietly editing them would erase the lineage of how the claim was actually arrived at. The corrected numbers are still favorable to AIL; the uncorrected ones were favorable for the wrong reasons.

---

## What was wrong

### Bug 1 — Misleading label

The metric labeled **"Execution Success"** in the score table was computed from `answer_ok` (the program produced the correct final answer), not from `exec_success` (the program ran without crashing). The variable name in the code (`answered`) made this obvious if you read the source, but the displayed label was inaccurate. Renamed to **"Answer Correctness"**. The number didn't change; the label now matches what it measures.

### Bug 2 — Vacuous-truth inflation when parse rate is 0

The four "program property" metrics — Error Explicitness, Structural Safety, Loop Safety, Observability — were divided by **N** (total prompts), not by **parsed** (programs the model actually produced). When a model failed to author any valid AIL at all, those rates defaulted to **100%**: there were no programs in the numerator *or* denominator to violate the property. Counting "0 violations out of 0 programs" as 100% safe meant a model that produced nothing scored higher than a model that produced a few buggy programs.

Concretely, on `mistral:7b-instruct-q4_K_M`, the model produced AIL output that was **never parseable** (0/50 valid programs — it emitted Python wrapper code that imports the AIL interpreter and calls `run()` with AIL embedded as a string). Under the old methodology, the AIL HEAAL Score on this run computed to **65.0** vs Python **44.3** — appearing to "beat" Python while having authored zero AIL programs.

That's not a defensible result.

### What the fix is

Per-program metrics now use **parsed** as their denominator. If parse rate is 0, those rates are 0 — no programs exist to be safe.

Two metrics keep their original `N` denominator because they measure *authoring success per attempt*, not properties of programs that exist:
- **Parse Success** (% of attempts that produced valid syntax)
- **Answer Correctness** (% of attempts that produced the correct final answer)

The score formula and weights are unchanged:

```
HEAAL Score = 0.25 · Error Explicitness    [/ parsed]
            + 0.20 · Answer Correctness    [/ N]    ← renamed
            + 0.20 · No-Silent-Skip rate   [/ parsed B/C]
            + 0.15 · Parse Success         [/ N]
            + 0.10 · Structural Safety     [/ parsed]   ← was / N
            + 0.05 · Loop Safety           [/ parsed]   ← was / N
            + 0.05 · Observability         [/ parsed]   ← was constant
```

---

## Before / after — every previously published score

| Scenario | Author model | Old AIL / Py / Δ | New AIL / Py / Δ | Notes |
|---|---|---|---|---|
| HEAAL baseline | Sonnet 4.6 | 77.6 / 75.3 / +2.3 | 77.6 / 75.3 / +2.3 | unchanged |
| HEAAL E1 | Sonnet 4.5 + anti_python | 96.1 / 75.9 / +20.2 | 96.1 / 75.9 / +20.2 | unchanged |
| HEAAL C1 | qwen2.5-coder:14b default | 80.9 / 69.6 / +11.3 | 80.9 / 69.6 / +11.3 | unchanged |
| HEAAL C2 | qwen2.5-coder:14b anti_python | 80.9 / 69.2 / +11.7 | 80.9 / 69.2 / +11.7 | unchanged |
| HEAAL D1 | llama3.1:8b default | 74.3 / 42.2 / +32.1 | **74.3 / 43.7 / +30.6** | Python rate corrected up; Δ shrinks 1.5pp |
| HEAAL D2 | llama3.1:8b anti_python | 74.3 / 42.2 / +32.1 | **74.3 / 43.7 / +30.6** | same |
| **AIL track v3 fine-tune** | `ail-coder:7b-v3` | **87.7 / 48.5 / +39.2** | **87.7 / 58.0 / +29.7** | **Python rate corrected up; Δ shrinks 9.5pp — the largest correction** |
| HEAAL D3 (new) | mistral:7b default | (not published) | **0.0 / 54.9 / -54.9** | mistral fails AIL parse 0/50; loses to Python under honest scoring |
| HEAAL D4 (new) | mistral:7b anti_python | (not published) | **0.0 / 54.9 / -54.9** | same |

**Two patterns to call out:**

1. **The headline number (87.7 vs Python) didn't move.** What moved is the Python column — under the old methodology, Python's "error_explicit" rate was being computed across all 50 prompts including the ones where Python failed to parse, dragging the rate down. Under the new methodology, error explicitness is measured only across parsed Python programs. Python's parse rate is what it is; its safety properties on the programs it *does* produce are correctly higher than we previously credited.

2. **The mistral row shows the corrected methodology is doing what it should.** When a model authors zero valid AIL, AIL's grammar floor cannot help — there is no program to apply the floor to. The new score reflects this. The Δ flips from "AIL wins on grammar floor alone" (an artifact of the bug) to "AIL loses outright" (the truth). This is the right shape.

---

## What this changes about the HEAAL claim

The HEAAL claim is not weakened. It is sharpened.

**Old version of the claim (what the dashboards implied):**
> AIL beats Python on the HEAAL Score at every model tier we have measured.

This was technically true under the broken methodology, and true on the published rows under the fixed methodology — except for mistral, which we hadn't published yet and now have a corrected number for.

**Corrected version of the claim:**
> AIL beats Python on the HEAAL Score at every tier where the author model can produce *any* valid AIL. When the model cannot author AIL at all (mistral 7B Instruct without a fine-tune), AIL's grammar floor has nothing to apply to and the score is honest about that. The path for that tier is the AIL track — fine-tuning a 7B base on AIL data, which produces `ail-coder:7b-v3` at AIL 87.7 vs Python 58.0 (Δ +29.7).

The corrected claim is more honest and easier to defend in technical review. The boundary it implies — "the harness floor matters once the model can write the language at all" — is exactly the right boundary to publicize.

---

## What we are doing about it

- `reference-impl/tools/heaal_score.py` is fixed in this commit. The fix is in [`_side_metrics()`](../../reference-impl/tools/heaal_score.py) — see the "Honest-denominator rule" docstring.
- All dashboards in `docs/benchmarks/dashboards/` regenerated.
- `docs/benchmarks/dashboards/README.md` table updated (8 rows, including mistral).
- Top-level `README.md` table updated. The headline row (`ail-coder:7b-v3`) shows the corrected `87.7 / 58.0 / +29.7`.
- `docs/ko/README.ko.md` mirror updated.
- Stage D analysis (`2026-04-22_heaal_D_llama8b_analysis.md`) updated to reflect the +30.6 (was +32.1) gap and the corrected cross-tier table.
- Stage D mistral analysis (`2026-04-22_heaal_D_mistral7b_analysis.md`) is published with the corrected methodology from the start.
- `CHANGELOG.md` v1.8.5 entry left as-is for historical accuracy, with a footnote pointing to this audit.
- v1.8.7 shipped the corrected `heaal_score.py` to PyPI users on 2026-04-22; anyone re-running the benchmark on an upgraded install gets the corrected scoring by default.

---

## Lessons we are recording for future scoring work

1. **Default to the smallest defensible denominator.** When in doubt, count things in the numerator and denominator that *exist*. Vacuous-truth defaults (100% if no cases) should be treated as a code smell, not as convenience.
2. **Match labels to what the code actually computes.** The "Execution Success" label drifted from its variable name (`answered` = `answer_ok`). Either the label was right and the code was wrong, or the code was right and the label was wrong — we eventually had to pick. We picked accuracy.
3. **Re-audit before publishing a new tier.** The mistral run was the first run where parse=0. That's the run that exposed the bug. Future runs that produce qualitatively different shapes (extreme parse fail, extreme retries, etc.) should trigger a manual sanity check before the score is taken at face value.

This audit was prompted by hyun06000 noticing that mistral's score "65 vs 44 in AIL's favor" did not pass the smell test when the underlying parse rate was 0. Credit to him for catching it before it went into a manifesto or a public talk.
