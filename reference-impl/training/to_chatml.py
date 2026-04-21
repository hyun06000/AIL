"""Convert the validated dataset into ChatML-style JSONL that the
qwen-family tokenisers consume directly during LoRA fine-tuning.

Input  : one or more dataset/*.jsonl from the seed scripts,
         already passed through validate.py.
Output : one line per sample, shape —

    {
      "messages": [
        {"role": "system", "content": "<AIL_SYSTEM_PROMPT>"},
        {"role": "user",   "content": "<NL prompt>"},
        {"role": "assistant", "content": "<AIL source>"}
      ]
    }

The system prompt mirrors (a condensed form of) what `ail ask` sends
the author at inference time. Training on this exact shape means
the fine-tuned model's behaviour matches the deployment surface.
If the system prompt drifts at inference time, re-export this file
and retrain.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Condensed version of the goal text in ail.authoring._build_authoring_goal.
# Short enough that LoRA training on 7B fits under consumer-GPU limits,
# long enough to keep the crucial fn/intent rules in context.
AIL_SYSTEM_PROMPT = """\
You are an AIL source-code author. AIL is a programming language \
designed for AI-authored code. A program has one `entry main(x: Text) \
{ ... }` plus optional declarations.

Function kinds:
  - `pure fn name(args) -> Type { body }` — deterministic, no LLM, no \
    effects. Used for arithmetic, parsing, iteration, comparison.
  - `intent name(args) -> Type { goal: description }` — delegates to \
    the model. Used for sentiment, classification, summarisation, \
    translation, judgment.

Always choose `pure fn` if the task is computable. Use `intent` only \
when the task truly requires judgment. Hybrid programs declare both.

Type annotations are single identifiers (`Text`, `Number`, `Boolean`) \
or parametric types (`List[Number]`, `Map[Text, Number]`, \
`Result[Text]`, `Tuple[Number, Text]`). C++/Java-style `Array<T>` is \
NOT AIL — use `List[T]`. Do not put bare `[Number]` without a \
leading identifier.

Builtin math functions (all usable in `pure fn`): `abs`, `max`, \
`min`, `round`, `floor`, `ceil`, `sqrt`, `pow`. Use these directly; \
do NOT import a math module.

Available stdlib modules: `stdlib/core`, `stdlib/language`, \
`stdlib/utils` — nothing else. Do NOT import `stdlib/math` or any \
other name.

Output: raw AIL source only, no markdown fences, no explanation."""


def _strip_line_comments(source: str) -> str:
    """Remove `//` and `#` line comments from AIL source.

    Careful: `//` and `#` must be OUTSIDE string literals to count as
    comments. A naive regex would corrupt strings like "hash: #...".
    We walk the source char-by-char with a tiny lexer.
    """
    out = []
    i = 0
    in_str = False
    while i < len(source):
        ch = source[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < len(source):
                out.append(source[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        # Line comment?
        if (ch == "/" and i + 1 < len(source) and source[i + 1] == "/") or ch == "#":
            # Skip to end of line (but keep the newline as a separator)
            while i < len(source) and source[i] != "\n":
                i += 1
            continue
        # Block comment? /* ... */
        if ch == "/" and i + 1 < len(source) and source[i + 1] == "*":
            i += 2
            while i + 1 < len(source) and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i += 2  # consume */
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _flatten_ail(source: str, mode: str) -> str:
    """Re-emit AIL source in one of three formats.

    mode="none"        : original (human-readable indented).
    mode="strip-indent": per-line leading whitespace removed, `\\n` preserved.
                         Kills indentation tokens but keeps statement
                         separators a whitespace-sensitive tokenizer might
                         prefer.
    mode="single-line" : line comments stripped, then newlines and
                         indentation collapsed into single spaces. Maximally
                         serialized. AIL's grammar is brace-delimited, so
                         this is semantically identical to the original —
                         verified against the parser on 2026-04-22.
                         Comments are removed because (a) they'd be read
                         as swallowing the whole joined line, and (b) they
                         are human documentation with no semantic content
                         that the author model needs to learn.
    """
    if mode == "none":
        return source
    if mode == "strip-indent":
        return "\n".join(line.lstrip() for line in source.split("\n"))
    if mode == "single-line":
        stripped = _strip_line_comments(source)
        return " ".join(stripped.split())
    raise ValueError(f"unknown flatten mode: {mode!r}")


def _emit(sample: dict, flatten_mode: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": AIL_SYSTEM_PROMPT},
            {"role": "user", "content": sample["prompt"]},
            {"role": "assistant", "content": _flatten_ail(sample["ail_source"], flatten_mode)},
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--shuffle-seed", type=int, default=42,
                   help="If set, shuffle output in deterministic order "
                        "so successive validation splits compare cleanly")
    p.add_argument("--flatten", choices=["none", "strip-indent", "single-line"],
                   default="none",
                   help="Transform AIL source before emitting. `single-line` "
                        "is the v5 experiment — serialize code to maximise "
                        "token efficiency. Default `none` preserves original.")
    args = p.parse_args()

    samples: list[dict] = []
    for path in args.files:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            samples.append(json.loads(line))

    if args.shuffle_seed is not None:
        import random
        random.Random(args.shuffle_seed).shuffle(samples)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for s in samples:
            json.dump(_emit(s, args.flatten), f, ensure_ascii=False)
            f.write("\n")

    print(f"{len(samples)} samples → {args.out}  (flatten={args.flatten})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
