"""Turn a trained LoRA adapter into an Ollama model.

Flow:

    1. Merge the PEFT adapter into the base weights → a standalone
       HuggingFace model dir.
    2. Convert the merged HF dir → GGUF via llama.cpp's convert
       script (or unsloth's built-in save_pretrained_gguf if available).
    3. Quantise the GGUF to Q4_K_M so the 3070 can run inference.
    4. Write an Ollama Modelfile that points at the GGUF and
       carries the same system prompt used at training time.
    5. Run `ollama create ail-coder:7b -f <Modelfile>`.

Usage:

    python training/export_to_ollama.py \\
        --adapter training/ail-coder-7b-lora \\
        --out training/ail-coder-7b-gguf \\
        --ollama-name ail-coder:7b

Prerequisites on the host:
    - The same stack that `train.py` uses (transformers / peft / unsloth)
    - `llama.cpp` cloned somewhere, or unsloth installed (it vendors
      the conversion path)
    - `ollama` CLI

This script does NOT run fine-tuning — only conversion + registration.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).parent
SYSTEM_PROMPT_PATH = HERE / "to_chatml.py"   # canonical system prompt lives here


def _load_system_prompt() -> str:
    """Parse `to_chatml.py` for the AIL_SYSTEM_PROMPT literal so the
    Modelfile stays in sync without manual copy-paste."""
    src = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    # Grab everything between `AIL_SYSTEM_PROMPT = """` and the next `"""`.
    marker = 'AIL_SYSTEM_PROMPT = """\\\n'
    start = src.find(marker)
    if start < 0:
        # Fall back to the un-escaped form
        marker = 'AIL_SYSTEM_PROMPT = """'
        start = src.find(marker)
    if start < 0:
        raise RuntimeError("AIL_SYSTEM_PROMPT not found in to_chatml.py")
    start += len(marker)
    end = src.find('"""', start)
    return src[start:end].strip()


def _write_modelfile(gguf_path: Path, modelfile_path: Path) -> None:
    system = _load_system_prompt()
    # Ollama's Modelfile PARAMETER and SYSTEM directives are what the
    # runtime loads. The FROM line points at the GGUF file; the
    # template matches the ChatML format qwen uses natively.
    content = f"""\
FROM {gguf_path.resolve()}

PARAMETER temperature 0.0
PARAMETER num_ctx 4096

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"

SYSTEM \"\"\"{system}\"\"\"
"""
    modelfile_path.write_text(content, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter", type=Path, required=True,
                   help="Directory produced by train.py (contains "
                        "adapter_model.safetensors and the manifest)")
    p.add_argument("--out", type=Path, required=True,
                   help="Directory for the merged + GGUF artefacts")
    p.add_argument("--ollama-name", type=str, default="ail-coder:7b",
                   help="The name `ollama create` should register")
    p.add_argument("--quant", type=str, default="Q4_K_M",
                   help="llama.cpp quant level; Q4_K_M fits 7B in ~4.7GB")
    p.add_argument("--skip-merge", action="store_true",
                   help="If the merged-and-gguf artefacts already exist, "
                        "just write the Modelfile and run ollama create")
    args = p.parse_args()

    manifest_path = args.adapter / "ail_training_manifest.json"
    if not manifest_path.exists():
        print(f"adapter manifest not found: {manifest_path}\n"
              f"did you run train.py?", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text())
    base = manifest["base"]
    args.out.mkdir(parents=True, exist_ok=True)
    gguf_path = args.out / f"ail-coder.{args.quant}.gguf"

    if not args.skip_merge:
        try:
            from unsloth import FastLanguageModel
        except ImportError:
            print("unsloth not installed — required for merge+gguf step.",
                  file=sys.stderr)
            return 2

        print(f"[1/3] loading base {base} + adapter {args.adapter}",
              file=sys.stderr)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(args.adapter),
            max_seq_length=2048, load_in_4bit=True, dtype=None,
        )

        print(f"[2/3] merging and saving GGUF ({args.quant})", file=sys.stderr)
        # Unsloth's save_pretrained_gguf handles merge + quant in one call.
        model.save_pretrained_gguf(
            str(args.out),
            tokenizer,
            quantization_method=args.quant.lower(),
        )
        # unsloth writes a fixed filename — find and normalise it
        produced = list(args.out.glob("*.gguf"))
        if not produced:
            print("no .gguf produced by unsloth; check its version",
                  file=sys.stderr)
            return 3
        if produced[0] != gguf_path:
            shutil.move(str(produced[0]), str(gguf_path))

    else:
        if not gguf_path.exists():
            print(f"--skip-merge set but {gguf_path} does not exist",
                  file=sys.stderr)
            return 2

    modelfile = args.out / "Modelfile"
    print(f"[3/3] writing Modelfile → {modelfile}", file=sys.stderr)
    _write_modelfile(gguf_path, modelfile)

    print(f"  ollama create {args.ollama_name} -f {modelfile}",
          file=sys.stderr)
    r = subprocess.run(["ollama", "create", args.ollama_name, "-f",
                        str(modelfile)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("ollama create failed:\n" + r.stderr, file=sys.stderr)
        return r.returncode

    print(f"\nregistered {args.ollama_name}. Use with:", file=sys.stderr)
    print(f"  AIL_OLLAMA_MODEL={args.ollama_name} ail ask 'factorial of 7'",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
