# Training handoff — runbook for the 3070-box Claude

You are Claude Code running on hyun06000's 3070 GPU box. The
Mac-side Claude (me, up through commit `cf78d79`) set everything
up so you can run the actual GPU work. This file is your runbook.

Read [`CLAUDE.md`](../../CLAUDE.md) for the strategic picture —
specifically the "DIRECTIVE FOR THE 3070-BOX CLAUDE" section at
the bottom. This file is operational: exact commands, expected
outputs, what to do on failure, when to stop and ask.

---

## What you're doing in one paragraph

Fine-tune `qwen2.5-coder:7b-instruct` with QLoRA on an 80-sample
AIL corpus, export the result to an Ollama model named
`ail-coder:7b`, re-run the cross-runtime benchmark, and decide
whether three explicit gate conditions are met. If yes — commit
the new benchmark JSON and tell hyun06000 to run the LinkedIn-post
step. If no — commit a post-mortem with the numbers and the
likely cause. You do NOT post to LinkedIn yourself, and you do NOT
push any partial adapter weights to HuggingFace without the user's
explicit OK.

---

## Environment you're landing in

Assumed true. Confirm before you start:

- `ollama` is running on `localhost:11434`. The model
  `qwen2.5-coder:14b-instruct-q4_K_M` is already pulled (that's
  what the baseline was measured against).
- GPU: NVIDIA 3070, 8 GB VRAM, CUDA ≥ 12.1. `nvidia-smi` should
  work.
- Disk: needs ~20 GB free (7B base + merged + GGUF).
- Python 3.10+, git, enough RAM to merge a 7B model (16 GB+
  system RAM comfortable; 32 GB safer).

If any of those isn't true, STOP and tell hyun06000. Don't try to
install drivers or reconfigure the box — that's out of scope.

---

## First 10 minutes: get synced

```bash
# 1. Clone or pull the repo
# (skip clone if the box already has it)
git clone git@github.com:hyun06000/AIL.git
cd AIL

git pull origin main           # make sure you're at cf78d79 or later
git log --oneline -5           # sanity

# 2. Install the AIL reference impl editable (needed for the
#    training scripts' imports to resolve)
cd reference-impl
pip install -e ".[dev]"        # confirms ail is importable

# 3. Verify tests + dataset still valid on THIS machine
python -m pytest tests/ -q
python training/validate.py training/dataset/*.jsonl --quiet \
    2>&1 | tail -8

# Expected:
#   249 passed, 2 skipped
#   TOTAL  80/80 passed
#     hybrid       24/24
#     pure_fn      35/35
#     pure_intent  21/21
```

If anything above fails, STOP. The repo state shouldn't have
drifted — if it did, you're on a different commit than cf78d79
and need to figure out why before burning GPU hours.

---

## Install the training stack

```bash
pip install \
    "unsloth[cu124-torch240] @ git+https://github.com/unslothai/unsloth.git" \
    "transformers>=4.44" "trl>=0.9" "peft>=0.12" \
    "datasets>=2.20" "accelerate>=0.33"
```

If `cu124-torch240` is wrong for this box's CUDA/torch version,
pick the extra that matches — `unsloth`'s README lists them. If
unsure, let the user pick.

Sanity check:

```bash
python -c "from unsloth import FastLanguageModel; print('ok')"
```

---

## Run the training

```bash
cd reference-impl      # NOT AIL/ — the training scripts expect this
python training/train.py \
    --dataset training/train.chatml.jsonl \
    --output training/ail-coder-7b-lora
```

**Expected wall clock:** 45-90 minutes on a 3070 at default
hyperparams (80 samples × 3 epochs × batch_size 2 × grad_accum 4).
If you see > 2 hours, something is wrong — probably CPU offload is
kicking in because VRAM is exhausted. Lower `--batch-size 1` and
try again; note it in the final commit message.

**Expected output:**

- `training/ail-coder-7b-lora/adapter_model.safetensors` (~200 MB)
- `training/ail-coder-7b-lora/ail_training_manifest.json` (tiny,
  human-readable)
- Epoch checkpoints in subdirs (you can delete these after)

**Smoke-test the adapter before exporting:**

```bash
python -c "
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    'training/ail-coder-7b-lora',
    max_seq_length=2048, load_in_4bit=True, dtype=None,
)
FastLanguageModel.for_inference(model)
messages = [
  {'role': 'system', 'content': 'You are an AIL source-code author.'},
  {'role': 'user', 'content': 'Compute the factorial of 7'},
]
inputs = tokenizer.apply_chat_template(messages, tokenize=True,
                                       add_generation_prompt=True,
                                       return_tensors='pt').to('cuda')
out = model.generate(inputs, max_new_tokens=200, temperature=0.0)
print(tokenizer.decode(out[0][inputs.shape[-1]:], skip_special_tokens=True))
"
```

You're looking for something like:

```
pure fn factorial(n: Number) -> Number {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
entry main(x: Text) { return factorial(7) }
```

If you see Python, AIL with obviously wrong syntax (`List[T]`,
`def`, `return;`), or garbled tokens, the training didn't take —
see TROUBLESHOOTING below.

---

## Export to Ollama

```bash
python training/export_to_ollama.py \
    --adapter training/ail-coder-7b-lora \
    --out training/ail-coder-7b-gguf \
    --ollama-name ail-coder:7b
```

This merges the LoRA into the base, quantises to Q4_K_M, writes a
Modelfile, and calls `ollama create ail-coder:7b -f …`.

Verify:

```bash
ollama list | grep ail-coder
ollama run ail-coder:7b "Compute the factorial of 7" 2>&1 | head -20
```

Should produce AIL source, not prose.

---

## Re-run the benchmark (the real test)

```bash
export AIL_OLLAMA_HOST=http://localhost:11434
export AIL_OLLAMA_MODEL=ail-coder:7b
export AIL_OLLAMA_TIMEOUT_S=600

OUT="docs/benchmarks/$(date +%F)_ail-coder-7b_all.json"
python tools/bench_vs_python.py --json-out "../$OUT"
```

Wall clock: ~20-30 minutes (7B finetuned is faster than 14B base).

**The file ends with a category-split table like:**

```
category    AIL(parse/route/ans)   Python(parse/route/ans)
hybrid      <n>%/<n>%/<n>%          100%/33%/100%
pure_fn     <n>%/<n>%/<n>%          100%/100%/95%
pure_intent <n>%/<n>%/<n>%          100%/73%/100%
overall     <n>%/<n>%/<n>%          100%/72%/38%
```

Python numbers are stable across runs; AIL numbers are what you're
measuring. Copy them into your analysis below.

---

## The gate — three conditions, ALL required

Baseline to beat is at
`docs/benchmarks/2026-04-20_qwen25-coder-14b_all.json`:

1. **G1. AIL overall parse rate ≥ 80%.**
   Baseline 64%. Need +16 percentage points.

2. **G2. AIL hybrid route rate > Python hybrid route rate.**
   Baseline 33% vs 33% (tied). Need strict majority.

3. **G3. AIL pure_fn answer rate ≥ Python pure_fn answer rate.**
   Baseline 80% vs 95%. Need +15 percentage points OR better.

Compute all three from your new JSON with this helper:

```bash
python - <<'EOF'
import json, sys
from collections import defaultdict
new = json.load(open('docs/benchmarks/XXXX.json'))   # set path
base = json.load(open('docs/benchmarks/2026-04-20_qwen25-coder-14b_all.json'))

def cat_split(data):
    d = defaultdict(list)
    for c in data['cases']:
        d[c['category']].append(c)
    def pct(rows, side, key):
        return 100 * sum(1 for r in rows if r[side][key]) / max(len(rows), 1)
    out = {}
    for cat, rows in d.items():
        out[cat] = {
            'ail_parse': pct(rows, 'ail', 'parsed'),
            'ail_route': pct(rows, 'ail', 'routing_ok'),
            'ail_answer': pct(rows, 'ail', 'answer_ok'),
            'py_parse': pct(rows, 'python', 'parsed'),
            'py_route': pct(rows, 'python', 'routing_ok'),
            'py_answer': pct(rows, 'python', 'answer_ok'),
        }
    out['overall'] = {
        'ail_parse': pct(data['cases'], 'ail', 'parsed'),
    }
    return out

new_s = cat_split(new)
G1 = new_s['overall']['ail_parse'] >= 80
G2 = new_s['hybrid']['ail_route'] > new_s['hybrid']['py_route']
G3 = new_s['pure_fn']['ail_answer'] >= new_s['pure_fn']['py_answer']

print(f"G1 parse>=80:  {new_s['overall']['ail_parse']:.1f}%  {'PASS' if G1 else 'FAIL'}")
print(f"G2 hybrid route > python: "
      f"{new_s['hybrid']['ail_route']:.0f}% vs {new_s['hybrid']['py_route']:.0f}%  "
      f"{'PASS' if G2 else 'FAIL'}")
print(f"G3 pure_fn answer >= python: "
      f"{new_s['pure_fn']['ail_answer']:.0f}% vs {new_s['pure_fn']['py_answer']:.0f}%  "
      f"{'PASS' if G3 else 'FAIL'}")
print(f"\nOPEN THE GATE: {G1 and G2 and G3}")
EOF
```

---

## If the gate opens (all three PASS)

Do this, in order:

1. Add the new benchmark JSON to `docs/benchmarks/README.md`'s
   snapshot table. Include a one-sentence note that this is the
   fine-tuned run — specifically that the trained model is
   `ail-coder:7b` (LoRA on qwen2.5-coder-7b-instruct).

2. Write a short post-mortem (HAPPY path) at
   `docs/benchmarks/2026-04-XX_ail-coder-7b_analysis.md`:
   - Before/after 3-axis table, per category
   - One paragraph on which category moved the most, and why
   - One paragraph on remaining gaps (this is honest, not a
     victory lap)

3. Commit with message starting `training: ail-coder-7b beats
   baseline — all three gates open`. Include the full numbers
   in the commit body.

4. Push.

5. STOP and tell hyun06000 it's done and the LinkedIn gate is
   now open. The Mac-side Claude drafted English+Korean posts
   in a prior session — hyun06000 has those. You do not post.

6. DO NOT upload the model to HuggingFace in this session. That
   requires hyun06000's HF credentials and an explicit green-
   light to publish. Mention it as a next step in the commit
   message; don't do it.

---

## If the gate does NOT open

One or more of G1/G2/G3 failed. Your job: figure out WHY, not
retry blindly.

1. Write an honest post-mortem at
   `docs/benchmarks/2026-04-XX_ail-coder-7b_analysis.md`:
   - Full numbers per category
   - Which of G1/G2/G3 failed
   - Where the AIL programs broke on this run — is it the same
     failure modes as base 14B (`List[T]` type hints, non-
     existent stdlib imports, ternary `?:`) or new ones?
   - A concrete next-step hypothesis: "more samples of category
     X," "longer training," "different base model," etc.

2. Commit with message `training: ail-coder-7b missed gate —
   failure modes: …`. Full numbers in the body.

3. Push.

4. STOP. Do NOT try a second training run without hyun06000's
   say-so. Fine-tuning costs GPU time and every run should have
   a hypothesis attached.

---

## Troubleshooting

| Symptom | Likely cause | What to try |
|---|---|---|
| `pip install unsloth` fails | CUDA / torch version mismatch | Check `python -c "import torch; print(torch.version.cuda)"` and pick the matching `unsloth[cuXXX-torchYYY]` extra |
| Training OOMs on `forward` | Batch too large for 8 GB | `--batch-size 1 --grad-accum 8` (same effective batch) |
| Training loss stays > 2 after 3 epochs | Dataset too small or LR too low | Try `--epochs 5 --lr 3e-4`. Note it in the commit. Do NOT go past 10 epochs — overfitting risk on 80 samples |
| Adapter generates Python | ChatML system prompt not applied at inference | Check `to_chatml.py` system prompt matches `ail.authoring._build_authoring_goal` shape |
| Adapter generates AIL with `List[T]` | Same as base — training didn't generalize | Add more negative examples? Regenerate dataset with explicit "no list types" — but this is a hyun06000-level decision |
| `export_to_ollama.py` fails on GGUF | unsloth version skew | Try manually: `llama.cpp` convert + quantize, write Modelfile by hand following the one in `training/ail-coder-7b-gguf/Modelfile` (if it got that far) |
| `bench_vs_python.py` times out per case | `ail-coder:7b` is actually slower than 14B (rare but possible on cold start) | First call is cold; warm up with `ollama run ail-coder:7b "hi"` once, then re-run. If still slow, lower `AIL_OLLAMA_TIMEOUT_S` isn't the answer — `ollama ps` will show if the model is on GPU |
| `bench_vs_python.py` gives different numbers across runs | Benchmark is non-deterministic across runs (model temp 0 helps but isn't perfect) | Run it 3 times, take the median. Note the spread in commit body |

---

## Hard rules — things the handoff does NOT permit

1. **Do not modify the gate conditions.** G1/G2/G3 were set
   before the run, by design. Lowering them post-hoc to make
   the run pass is academic fraud, not engineering.
2. **Do not hide failures.** If the adapter produces weird AIL,
   if training logs show loss spikes, if benchmark Python numbers
   shift — record it in the commit body. Future sessions need
   this information.
3. **Do not post to LinkedIn / HN / X / anywhere.** hyun06000
   handles public publication. Your role ends at "gate opens" or
   "gate closes, here's why."
4. **Do not upload to HuggingFace without credentials + permission.**
   HF push is a separate explicit step.
5. **Do not train a second variant without a hypothesis.** If the
   first run misses the gate, write the post-mortem. Don't throw
   hyperparams at the wall.

---

## Useful context beyond this runbook

- Strategy directive: `CLAUDE.md` bottom section — the "why" for
  doing this at all
- Architecture of what you're fine-tuning against: `docs/why-ail.md`
- What the benchmark measures: `docs/benchmarks/README.md`
- The AIL author prompt this dataset teaches:
  `reference-impl/ail/authoring.py` (`_build_authoring_goal`)
- The existing bench tool you'll re-run:
  `reference-impl/tools/bench_vs_python.py`
- The dataset format:
  `reference-impl/training/validate.py` (schema comment at top)

---

## Quick contact

If stuck on something this runbook didn't cover, leave a clearly
marked `HANDOFF_BLOCKED:` note in a new commit message on a branch
called `training-blocked`, push, and tell hyun06000. Don't spin
on it — he'd rather unblock once than have you burn hours.
