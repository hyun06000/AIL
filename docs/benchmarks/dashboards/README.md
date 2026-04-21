# HEAAL Score dashboards

Single-number readouts of AIL vs Python performance on the benchmark corpus. Computed by [`reference-impl/tools/heaal_score.py`](../../../reference-impl/tools/heaal_score.py) from the raw benchmark JSONs in this directory.

## The three canonical readouts

| Scenario | Author model | Prompt | AIL | Python | Δ | Details |
|---|---|---|---|---|---|---|
| **AIL track, fine-tuned 7B** | `ail-coder:7b-v3` | default | **87.7** | 48.5 | +39.2 | [HTML](ail_track_r3_v3_finetune.html) · [JSON](ail_track_r3_v3_finetune.json) |
| **HEAAL baseline, Sonnet** | Sonnet 4.6 | default | **77.6** | 75.3 | +2.3 | [HTML](heaal_sonnet_default.html) · [JSON](heaal_sonnet_default.json) |
| **HEAAL E1, Sonnet + anti_python** | Sonnet 4.5 | `anti_python` | **96.1** | 75.9 | +20.2 | [HTML](heaal_E1_sonnet_antipython.html) · [JSON](heaal_E1_sonnet_antipython.json) |
| **HEAAL C1, qwen14b base (mid-tier)** | `qwen2.5-coder:14b` | default | **80.9** | 69.6 | +11.3 | [HTML](heaal_C1_qwen14b_default.html) · [JSON](heaal_C1_qwen14b_default.json) |
| **HEAAL C2, qwen14b + anti_python** | `qwen2.5-coder:14b` | `anti_python` | **80.9** | 69.2 | +11.7 | [HTML](heaal_C2_qwen14b_antipython.html) · [JSON](heaal_C2_qwen14b_antipython.json) |

The 77.6 → 96.1 lift on Sonnet from changing only the authoring prompt (zero other changes) is the headline HEAAL finding: **the safety properties are constant across author models, and a modest prompt tweak closes the authoring-quality gap that would otherwise force fine-tuning.**

The C1 → C2 row shows the opposite — on the 14B mid-tier coder base, `anti_python` produces **zero change** in AIL output (all 50 programs bit-identical across the two runs). The negative instruction washes past qwen14b's pretraining priors at temperature 0. Writeup and failure-mode analysis: [`2026-04-22_heaal_C_qwen14b_analysis.md`](../2026-04-22_heaal_C_qwen14b_analysis.md). Takeaway: **`anti_python` is a frontier-model intervention**, not a universal prompt upgrade. Even so, AIL's grammar-enforced floor keeps the HEAAL Score at 80.9 (+11.3 vs Python) on this tier with no intervention at all.

## Score formula

```
HEAAL Score = 0.25 · Error Explicitness
            + 0.20 · Execution Success
            + 0.20 · No Silent-Skip rate
            + 0.15 · Parse Success
            + 0.10 · Structural Safety
            + 0.05 · Loop Safety
            + 0.05 · Observability
```

65% weight lives in three measurement-driven metrics that move per run (Error Explicitness / Execution Success / No Silent-Skip). The remaining 35% anchors the language-level safety claims — these are near-constant 100/0 AIL/Python splits that represent category differences rather than per-run variation.

## Regenerating

To rescore an existing benchmark JSON (no re-run):

```bash
cd reference-impl
python tools/benchmark.py --no-run --report \
    --out ../docs/benchmarks/<existing>.json
```

To also write an HTML dashboard:

```bash
python tools/benchmark.py --no-run --report=<out.html> \
    --out ../docs/benchmarks/<existing>.json
```

Or to score any JSON directly:

```bash
python tools/heaal_score.py ../docs/benchmarks/<json> \
    --html <out.html> --json-out <out.json>
```
