# HEAAL Stage D' — mistral:7b is below the parse threshold; HEAAL boundary identified

**Date:** 2026-04-22
**Track:** HEAAL.
**Question:** Stages C (qwen14b) and D (llama3.1:8b) showed `anti_python` is a frontier-only intervention; the grammar floor still produced AIL > Python in HEAAL Score on those tiers because the model could author *some* parseable AIL. The boundary question this run answers: **what happens when the model authors zero parseable AIL?**

## Setup

- **Author + intent model:** `mistral:7b-instruct-q4_K_M` via local Ollama (no fine-tune)
- **Corpus:** the shared 50-prompt AIL-track corpus
- **Run D3:** default authoring prompt
- **Run D4:** same model, same corpus, with `AIL_AUTHOR_PROMPT_VARIANT=anti_python`
- **Backend:** Ollama at temperature 0 (deterministic)

## Results

| Metric | D3 (default) | D4 (anti_python) | Δ |
|---|---|---|---|
| AIL parse | **0%** | **0%** | 0 |
| AIL answer | 0% | 0% | 0 |
| Python parse | 42% | 42% | 0 |
| Python answer | 36% | 36% | 0 |
| AIL bit-identity | 49/49 identical (one case had no source on either side) | | |
| HEAAL Score (AIL) | **0.0** | **0.0** | 0 |
| HEAAL Score (Python) | 54.9 | 54.9 | 0 |

Raw data: [`2026-04-22_heaal_D3_mistral7b_default.json`](2026-04-22_heaal_D3_mistral7b_default.json) · [`2026-04-22_heaal_D4_mistral7b_antipython.json`](2026-04-22_heaal_D4_mistral7b_antipython.json).
Dashboards: [`heaal_D3_mistral7b_default.html`](dashboards/heaal_D3_mistral7b_default.html) · [`heaal_D4_mistral7b_antipython.html`](dashboards/heaal_D4_mistral7b_antipython.html).

## Why AIL parse rate is 0

The model emits Python wrapper code that imports the AIL interpreter as a library and tries to invoke AIL through it, with the AIL source embedded as a string inside the wrapper. Excerpt from D3 / A01 ("Calculate the factorial of 7"):

```python
from ail import run, compile_source, MockAdapter

# Run with mock (no API key):
result, trace = run("pure fn factorial(n: Number) -> Number {\n    if n <= 1 { return 1 }\n    return n * factorial(n - 1)\n}\nentry main(x: Text) { return factorial(7) }", input="7")
```

Inside the string, the AIL is mostly correct. Outside, the model wrote Python. The benchmark harness asked for AIL, gets Python, the AIL parser refuses at the first non-AIL token (`from`, `IDENT`, line 1).

This is a unique failure mode for this model family. We have now seen three:

| Model family | Size | Failure mode |
|---|---|---|
| `qwen2.5-coder` | 14B | Writes "Python-style AIL" — dict literals `{}`, invented builtins (`contains`, `has_key`), Python idioms the AIL grammar rejects |
| `llama3.1` | 8B | Writes English explanations or partial code; when generating actual code, calls back to its own Ollama HTTP endpoint to outsource the work |
| `mistral` | 7B | Writes Python that imports the AIL interpreter as a library and embeds AIL as a string parameter |

All three fail the AIL parse but in distinct ways. The grammar correctly refuses each; the harness correctly records each as `parsed=False`. None of these is a harness bug.

## What the score says, honestly

Under the corrected scoring methodology (see [`2026-04-22_score_audit.md`](2026-04-22_score_audit.md)), AIL's per-program safety metrics are computed only over programs that actually parse. With parse rate at 0%, those metrics are 0% — there are no programs to be safe. AIL HEAAL Score for this run: **0.0**.

The Python column scores 54.9. Mistral does write valid Python on 21/50 prompts and produces a correct answer on 18/50. Among those programs the harness measures Python's per-parsed safety properties honestly: error handling explicit on 22 cases, no infinite loops, no structural violations.

**This run is the boundary** of the HEAAL grammar-floor claim. The claim has always been "constraint as construction" — but a constraint cannot construct what was never authored. When a model is below the threshold of producing any valid AIL, the floor cannot lift it.

## What this refines about the HEAAL claim

We had the wording right but the methodology wrong before this audit. The corrected wording:

> **The HEAAL grammar floor lifts AIL above Python on the HEAAL Score at every tier where the author model can produce any valid AIL.**
>
> Sonnet 4.6 default: AIL 77.6 vs Python 75.3 (+2.3, frontier with no prompt help)
> qwen14b default: AIL 80.9 vs Python 69.6 (+11.3, mid-tier)
> llama8b default: AIL 74.3 vs Python 43.7 (+30.6, small but parses 30% of AIL)
> mistral7b default: AIL 0.0 vs Python 54.9 (-54.9, below parse threshold — this is the boundary)
>
> For tiers below the parse threshold, the path is the AIL track: fine-tune a 7B base on AIL data, which produces `ail-coder:7b-v3` at AIL 87.7 vs Python 58.0 (+29.7).

The corrected story is: **prompt-only HEAAL works for frontier; grammar-floor HEAAL works for any tier that can clear parse; below parse threshold, fine-tune is required.** Three regimes, three remedies, with a clear boundary between them.

## Recommendation

- **Do not promote AIL to mistral7b users without a fine-tune.** The model is below the parse threshold on the default prompt and on `anti_python`. It cannot author AIL through prompt engineering alone.
- **Treat mistral7b as a fine-tune target.** If the same model gets a 200-sample QLoRA pass on AIL data (the same recipe that produced `ail-coder:7b-v3` from a Qwen base), it should clear the parse threshold and then fall in line with the rest of the cross-tier table. Whether to do this depends on whether mistral7b users are an audience we want.
- **Document the boundary in the manifesto.** Three regimes, three remedies. The boundary is data, not opinion.

## Artifacts

- D3 raw: [`2026-04-22_heaal_D3_mistral7b_default.json`](2026-04-22_heaal_D3_mistral7b_default.json)
- D4 raw: [`2026-04-22_heaal_D4_mistral7b_antipython.json`](2026-04-22_heaal_D4_mistral7b_antipython.json)
- D3 dashboard: [`dashboards/heaal_D3_mistral7b_default.html`](dashboards/heaal_D3_mistral7b_default.html)
- D4 dashboard: [`dashboards/heaal_D4_mistral7b_antipython.html`](dashboards/heaal_D4_mistral7b_antipython.html)
- Methodology audit: [`2026-04-22_score_audit.md`](2026-04-22_score_audit.md)
- Companion at small-but-parses tier (llama8b): [`2026-04-22_heaal_D_llama8b_analysis.md`](2026-04-22_heaal_D_llama8b_analysis.md)
- Companion at mid-tier (qwen14b): [`2026-04-22_heaal_C_qwen14b_analysis.md`](2026-04-22_heaal_C_qwen14b_analysis.md)
- Companion at frontier (Sonnet): [`2026-04-22_heaal_E1_analysis.md`](2026-04-22_heaal_E1_analysis.md)
