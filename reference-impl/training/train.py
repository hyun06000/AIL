"""QLoRA fine-tune qwen2.5-coder-7b on the AIL dataset.

Runs on a single consumer GPU (the 3070 this file targets is 8 GB
VRAM — QLoRA with 4-bit base weights + adapters on attention layers
fits comfortably). Training time for ~80 samples × 3 epochs is
well under an hour on that hardware.

Not executed by this repo's CI or test suite — this is the offline
training step. The `bench_vs_python` and `bench_authoring` harnesses
are what measure success.

Prerequisites (install once on the training host):

    pip install \\
        "unsloth[cu124-torch240] @ git+https://github.com/unslothai/unsloth.git" \\
        "transformers>=4.44" "trl>=0.9" "peft>=0.12" \\
        "datasets>=2.20" "accelerate>=0.33"

Usage:

    python training/train.py \\
        --dataset training/train.chatml.jsonl \\
        --output training/ail-coder-7b-lora \\
        --base Qwen/Qwen2.5-Coder-7B-Instruct

The script intentionally has NO side effects outside `--output` so
it's safe to abort mid-run and restart.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True,
                   help="ChatML JSONL produced by to_chatml.py")
    p.add_argument("--output", type=Path, required=True,
                   help="Directory to write the LoRA adapter + "
                        "tokenizer + training logs")
    p.add_argument("--base", type=str,
                   default="Qwen/Qwen2.5-Coder-7B-Instruct",
                   help="HuggingFace model id (or local path) of the base")
    p.add_argument("--max-seq-length", type=int, default=2048)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=4,
                   help="gradient accumulation — effective batch = "
                        "batch_size × grad_accum")
    p.add_argument("--lr", type=float, default=2e-4,
                   help="LoRA learning rate — safe default for rank 16")
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=16)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--save-strategy", type=str, default="no",
                   choices=["no", "epoch", "steps"],
                   help="Trainer checkpoint cadence. Default 'no' to keep "
                        "the run single-save-at-end — under unsloth on an "
                        "8 GB card (e.g. 3070) the epoch-boundary save "
                        "spike OOMs. On a larger card switch to 'epoch'.")
    args = p.parse_args()

    # Imports live inside main() so `python train.py --help` works even
    # without the training stack installed.
    try:
        from unsloth import FastLanguageModel, is_bfloat16_supported
        from unsloth.chat_templates import get_chat_template
        from datasets import load_dataset
        from trl import SFTTrainer, SFTConfig
    except ImportError as e:
        print(f"missing training dependencies: {e}\n"
              f"see the install block at the top of this file.",
              file=sys.stderr)
        return 2

    print(f"[1/5] loading base {args.base} (4-bit QLoRA)", file=sys.stderr)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        dtype=None,   # unsloth picks bf16/fp16 based on GPU capability
    )

    print("[2/5] attaching LoRA adapters (attention + mlp)", file=sys.stderr)
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
        use_rslora=False,
    )

    # Qwen-family uses the ChatML template natively; confirm.
    tokenizer = get_chat_template(tokenizer, chat_template="chatml")

    print(f"[3/5] loading dataset {args.dataset}", file=sys.stderr)
    dataset = load_dataset("json", data_files=str(args.dataset), split="train")

    def formatting_func(example):
        # unsloth/TRL call this with either a single example (dict whose
        # "messages" is a list of dicts) during the warm-up probe, or a
        # batched dict-of-lists when the dataset map runs. Must always
        # return a list of rendered strings. Previously returned a bare
        # string which crashed on unsloth 2026.4 + trl ≥ 0.22 — captured
        # from the 2026-04-19 training attempt on the 3070 box.
        msgs = example["messages"]
        if msgs and isinstance(msgs[0], dict):
            return [tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=False,
            )]
        return [
            tokenizer.apply_chat_template(
                m, tokenize=False, add_generation_prompt=False,
            )
            for m in msgs
        ]

    print(f"[4/5] training — {args.epochs} epochs × {len(dataset)} samples",
          file=sys.stderr)
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        formatting_func=formatting_func,
        max_seq_length=args.max_seq_length,
        args=SFTConfig(
            output_dir=str(args.output),
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            optim="adamw_8bit",
            warmup_ratio=0.03,
            logging_steps=5,
            save_strategy=args.save_strategy,
            seed=args.seed,
            bf16=is_bfloat16_supported(),
            fp16=not is_bfloat16_supported(),
        ),
    )
    trainer.train()

    print("[5/5] saving adapter", file=sys.stderr)
    model.save_pretrained(str(args.output))
    tokenizer.save_pretrained(str(args.output))

    # Also write a tiny manifest so the deployment step knows what
    # base to combine the adapter with.
    manifest = {
        "base": args.base,
        "dataset": str(args.dataset),
        "samples": len(dataset),
        "epochs": args.epochs,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
    }
    (args.output / "ail_training_manifest.json").write_text(
        json.dumps(manifest, indent=2))

    print(f"done: adapter at {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
