# Training — AIL-specialised coder via QLoRA

The base-model baseline (see `docs/benchmarks/README.md`) established
the strategic finding: AIL's structural advantage is real, but the
gap to Python on parse rate is a training-distribution problem.
LLMs have seen orders of magnitude more Python than AIL. A small LoRA
on a pre-filtered AIL corpus should close the parse gap; the routing
and answer axes follow.

This directory holds the pipeline.

## Pipeline

```
dataset/*.jsonl          source samples — one JSON per line
  └─ validate.py         parses + purity-checks + runs every sample
                         (training never sees a sample the runtime
                         would reject at inference time)
  └─ to_chatml.py        converts validated samples → ChatML for
                         qwen-family tokenisers
  └─ train.py            unsloth QLoRA on qwen2.5-coder:7b-instruct
                         (runs on a 3070, ~1 hour for 100 samples × 3 epochs)
  └─ export_modelfile.py writes an Ollama Modelfile so the adapter
                         plugs into existing AIL tooling unchanged:
                         `AIL_OLLAMA_MODEL=ail-coder:7b ail ask "…"`
```

## Sample shape

Each line of a `dataset/*.jsonl` is one object with:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id`            | string | yes | unique per sample — used in validator output |
| `prompt`        | string | yes | the natural-language request as the user would type it |
| `ail_source`    | string | yes | the canonical AIL program that answers the prompt |
| `category`      | string | yes | `pure_fn` \| `pure_intent` \| `hybrid` |
| `expected`      | string | no  | expected program output (used only for pure_fn validation) |
| `input_text`    | string | no  | value bound to `entry main`'s first parameter during validation |
| `source_of_sample` | string | yes | `existing_example` \| `bench_canonical` \| `hand_written` — lets us track where the data came from and remove categories wholesale if one turns out to hurt |

## Validation

Every sample must pass FOUR gates before it enters the training set:

1. `compile_source(ail_source)` — parses cleanly
2. Purity checker — any `pure fn` in the sample obeys the contract
3. `run(ail_source, input=..., adapter=MockAdapter())` — executes without error
4. For `pure_fn` samples only: output equals `expected`

Samples that fail any gate are logged and excluded. The validator
prints a category-wise pass/fail table so we can see which kinds of
programs need more curation.

## Why three data sources

- `existing_example` — 15 programs from `reference-impl/examples/`,
  already shipped and verified.
- `bench_canonical` — one canonical AIL program per task in
  `bench_authoring.py`'s 50-task corpus. These are the programs we
  wish the author-model could produce; training on them targets the
  exact distribution the author-benchmark scores.
- `hand_written` — programs that fill gaps neither of the above
  covers (long recursion, nested Result handling, match with
  confidence, evolve declarations, etc.).

Category balance and feature coverage matter more than raw count.
Aiming for ~100 samples with every language feature appearing in
≥5 of them.

## Run

```bash
# 1. Validate
cd reference-impl
python training/validate.py training/dataset/*.jsonl

# 2. Produce training file
python training/to_chatml.py training/dataset/*.jsonl \
    --out training/train.chatml.jsonl

# 3. Train
python training/train.py \
    --dataset training/train.chatml.jsonl \
    --base qwen2.5-coder:7b-instruct \
    --output training/ail-coder-7b-lora

# 4. Export to Ollama
python training/export_modelfile.py \
    --lora training/ail-coder-7b-lora \
    --out training/ail-coder.Modelfile
ollama create ail-coder:7b -f training/ail-coder.Modelfile

# 5. Re-run the bench to see if the gate opened
AIL_OLLAMA_MODEL=ail-coder:7b \
    python tools/bench_vs_python.py \
    --json-out docs/benchmarks/$(date +%F)_ail-coder-7b_all.json
```

## Gate for the LinkedIn post

(Named explicitly so the commit trail can be re-read without extra
context.) All three must hold on the full 50-case `bench_vs_python`
run before declaring a win:

- AIL parse rate ≥ 80%
- AIL route rate > Python route rate on hybrid tasks
- AIL answer rate ≥ Python answer rate on pure_fn tasks

Baseline that needs to be beaten sits in
`docs/benchmarks/2026-04-20_qwen25-coder-14b_*.json`.
