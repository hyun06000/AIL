# 🟢 Training track — v3 adapter shipping (2026-04-21)

This file was the runbook for resuming fine-tuning after the five
Opus 4 preconditions were met on 2026-04-20. Two tune runs have now
happened (v2, v3); the v3 adapter is serving as `ail-coder:7b-v3`
in v1.8.3. This update replaces the "go run the canonical command"
version of this file. The prior text is in git history — `git show
4215d6e~1:reference-impl/training/HANDOFF.md` recovers it.

## Current state

| Artefact | Location | Purpose |
|---|---|---|
| v2 adapter | `~/AIL/reference-impl/training/ail-coder-7b-lora/` on homeblack | Preserved for rollback; 205 samples, 3 epochs |
| **v3 adapter** | `~/AIL/reference-impl/training/ail-coder-7b-lora-v3/` on homeblack | **Active**; 244 samples, 3 epochs, loss 2.58→0.09 |
| v3 merged fp16 | `~/AIL/reference-impl/training/ail-coder-7b-v3-merged/` | 15 GB intermediate, deletable |
| v3 f16 GGUF | `~/AIL/reference-impl/training/ail-coder-7b-v3.f16.gguf` | 15 GB intermediate, deletable |
| v3 Q4_K_M GGUF | `~/AIL/reference-impl/training/ail-coder-7b-v3.Q4_K_M.gguf` | **4.4 GB, Ollama's `FROM` target** |
| v3 Modelfile | `~/AIL/reference-impl/training/Modelfile.ail-coder-7b-v3` | Baked-in SYSTEM prompt (matches `to_chatml.py::AIL_SYSTEM_PROMPT`) |
| Ollama registration | `ail-coder:7b-v3` @ `10.0.0.1:11434`, ID `06e5e7ce2c72` | Served by the running Ollama |
| Benchmark JSON | [`../../docs/benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json`](../../docs/benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json) | 50-prompt run, 78% parse / 70% answer |

All Opus 4 preconditions still hold as of v1.8.3 — the training
track is open and will stay open as long as the v1.8 freeze is in
force.

## How v3 was produced (for reproduction)

Each step below was run from `~/AIL/reference-impl/` on homeblack.

### 1. Dataset expansion

```bash
# new seed covering v2 failure classes (math builtins, parametric types, hybrids)
PYTHONPATH=. ~/venv/labs/bin/python training/seed_v3_fixes.py

# re-validate full dataset (244 pass, 2 pre-existing failures unrelated)
PYTHONPATH=. ~/venv/labs/bin/python training/validate.py --quiet training/dataset/*.jsonl \
    > training/validated.jsonl 2>&1

# regenerate chatml training file from the validated set
PYTHONPATH=. ~/venv/labs/bin/python training/to_chatml.py training/validated.jsonl \
    --out training/train.chatml.jsonl
rm training/validated.jsonl
```

### 2. Train (~10 min on the 3070)

```bash
tmux new-session -d -s ail-train-v3 "cd ~/AIL/reference-impl && \
  ~/venv/labs/bin/python training/train.py \
    --dataset training/train.chatml.jsonl \
    --output training/ail-coder-7b-lora-v3 \
    --base Qwen/Qwen2.5-Coder-7B-Instruct \
    --max-seq-length 1024 \
    --batch-size 1 \
    --grad-accum 8 \
    --epochs 3 \
    --save-strategy no 2>&1 | tee ~/ail-train-v3.log"
```

`--save-strategy no` avoids the 8 GB-VRAM checkpoint OOM at epoch
boundaries. The script calls `model.save_pretrained()` once at the
end regardless, so you only lose mid-run checkpoints (which you
don't need on a 10-min run).

### 3. Manual GGUF pipeline (because `export_to_ollama.py` is broken)

`export_to_ollama.py` calls into unsloth's GGUF save path, which
internally tries `sudo apt-get install` for build tools. The 3070
box has no passwordless sudo, so it blocks forever. The working
pipeline uses llama.cpp directly:

```bash
# 3.1 merge LoRA into the base, save as HF dir (~10 min on CPU)
~/venv/labs/bin/python - << 'EOF'
from pathlib import Path
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = "Qwen/Qwen2.5-Coder-7B-Instruct"
ADAPTER = Path.home() / "AIL/reference-impl/training/ail-coder-7b-lora-v3"
OUT = Path.home() / "AIL/reference-impl/training/ail-coder-7b-v3-merged"

base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype="float16")
model = PeftModel.from_pretrained(base, str(ADAPTER)).merge_and_unload()
OUT.mkdir(parents=True, exist_ok=True)
model.save_pretrained(str(OUT), safe_serialization=True)
AutoTokenizer.from_pretrained(BASE).save_pretrained(str(OUT))
EOF

# 3.2 HF → f16 GGUF (~15 sec)
~/venv/labs/bin/python ~/llama.cpp/convert_hf_to_gguf.py \
    ~/AIL/reference-impl/training/ail-coder-7b-v3-merged \
    --outfile ~/AIL/reference-impl/training/ail-coder-7b-v3.f16.gguf \
    --outtype f16

# 3.3 f16 → Q4_K_M (~1 min)
LD_LIBRARY_PATH=~/llama.cpp/build/bin \
    ~/llama.cpp/build/bin/llama-quantize \
        ~/AIL/reference-impl/training/ail-coder-7b-v3.f16.gguf \
        ~/AIL/reference-impl/training/ail-coder-7b-v3.Q4_K_M.gguf \
        Q4_K_M
```

### 4. Register with Ollama

Write a Modelfile with `FROM` pointing at the Q4_K_M and a `SYSTEM`
prompt that matches what the training data's system role used
(keep these two in sync — see `training/to_chatml.py::AIL_SYSTEM_PROMPT`):

```bash
cat > ~/AIL/reference-impl/training/Modelfile.ail-coder-7b-v3 << 'EOF'
FROM /home/david/AIL/reference-impl/training/ail-coder-7b-v3.Q4_K_M.gguf
PARAMETER temperature 0.0
PARAMETER num_ctx 4096
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>
"""
SYSTEM """<paste contents of to_chatml.py::AIL_SYSTEM_PROMPT>"""
EOF

OLLAMA_HOST=10.0.0.1:11434 ollama create ail-coder:7b-v3 \
    -f ~/AIL/reference-impl/training/Modelfile.ail-coder-7b-v3
```

### 5. Run the benchmark

```bash
tmux new-session -d -s ail-bench-v3 "cd ~/AIL/reference-impl && \
  export BENCHMARK_BACKEND=ollama AIL_OLLAMA_HOST=http://10.0.0.1:11434 \
         AIL_OLLAMA_MODEL=ail-coder:7b-v3 AIL_OLLAMA_TIMEOUT_S=600 && \
  ~/venv/labs/bin/python tools/benchmark.py \
    --out ~/AIL/docs/benchmarks/$(date +%F)_ail-coder-7b-v3_opus50.json \
    2>&1 | tee ~/ail-bench-v3.log"
```

50 prompts × 2 languages, ~8–12 min with the v3 model warm on the
GPU. Then score against the three gates and write an analysis file
alongside the JSON.

## When to run v4

Re-train only when one of these is true:

- The dataset gains ≥ 20 more validated samples covering a failure
  class v3 still misses (e.g. `list[i]` subscript handling, currently
  the dominant remaining parse failure — 3 cases).
- The grammar changes in a way that invalidates v3's training
  (currently forbidden by the freeze, but check `spec/09-stability.md`
  for freeze status before assuming).
- A new base model is worth trying (the current setup is hardcoded
  to `Qwen/Qwen2.5-Coder-7B-Instruct`; swap via `--base`).

Don't re-train just to chase a better loss curve. The loss number
is not the bench score. The bench JSON is the bench score.

## Hard rules (still in force)

1. No HuggingFace push without hyun06000's explicit go.
2. Don't edit gate targets or prereq lists to flatter a result.
3. Don't commit adapter / GGUF / checkpoint files. They're in
   `.gitignore` — keep it that way.
4. Don't train against a non-frozen grammar. If `spec/09-stability.md`
   reports a freeze lift, stop and confirm with hyun06000.
5. The v2 adapter dir (`ail-coder-7b-lora/`) is intentionally
   preserved. Don't delete it; v3 writes to its own v3 dir.

## Read next

1. [`../../CLAUDE.md`](../../CLAUDE.md) — SESSION STATE 2026-04-21
   block has the current open-work list and environment quirks.
2. [`../../spec/09-stability.md`](../../spec/09-stability.md) — the
   grammar surface you must train against.
3. [`../../docs/benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md`](../../docs/benchmarks/2026-04-21_ail-coder-7b-v3_analysis.md)
   — the v3 result breakdown, including which three cases would move
   G1 from 78% to 80%+ if fixed.
