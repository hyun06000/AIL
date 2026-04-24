"""A/B experiment: does AIL's intent wrapping degrade Sonnet's answers?

Commissioned by Claude Opus 4, who suspects the `intent` system prompt
over-constrains reasoning. We run each question through three paths:

  A. AIL intent with current wrapped system prompt
     (meta-framing + forced JSON envelope + confidence request)
  B. AIL intent with stripped wrapping
     (goal as system, question as user, no envelope)
  C. Direct Anthropic API call
     (no AIL at all — control)

Output: side-by-side text for the operator to judge. This is
qualitative on purpose; Opus's hypothesis is that degradation is
fluency/reasoning shape, which benchmarks miss.

Usage:
    ANTHROPIC_API_KEY=... python tools/intent_vs_raw_ab.py

Optionally pass `--out results.jsonl` to save structured output.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# So we can import ail from repo without an install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ail.runtime.anthropic_adapter import AnthropicAdapter, DEFAULT_MODEL
from ail.runtime.model import ModelResponse


# Representative questions, chosen to stress reasoning (not recall).
QUESTIONS = [
    {
        "name": "korean_nuance",
        "goal": "translate the following English idiom into natural Korean that preserves its implication, not a literal gloss",
        "input": "beating a dead horse",
        "constraints": ["idiomatic_korean", "preserve_the_implication"],
    },
    {
        "name": "summarize_technical",
        "goal": "summarize the given text in 2 sentences. Keep the sharpest technical claim.",
        "input": (
            "HEAAL is a paradigm where safety constraints are part of the grammar. "
            "Where other teams build harnesses around Python (AGENTS.md, pre-commit "
            "hooks, custom linters), AIL puts the harness inside the language. "
            "There's no while keyword, so infinite loops are structurally impossible. "
            "Failable ops return Result, so errors can't be silently swallowed. "
            "pure fn is statically verified for side-effect freedom."
        ),
        "constraints": ["two_sentences", "keep_sharpest_technical_claim"],
    },
    {
        "name": "short_reasoning",
        "goal": "answer with a short explanation — why would removing the while keyword from a language make infinite loops impossible?",
        "input": "(no input)",
        "constraints": ["one_paragraph", "technical_but_clear"],
    },
    {
        "name": "code_critique",
        "goal": "identify the single biggest risk in the given Python snippet and say why",
        "input": "def process(items):\n    for item in items:\n        item.save()\n        notify(item)",
        "constraints": ["one_sentence"],
    },
    {
        "name": "json_extraction",
        "goal": "extract the repo name and star count from the given GitHub API JSON response",
        "input": json.dumps({
            "full_name": "hyun06000/AIL",
            "stargazers_count": 42,
            "description": "AI-Intent Language",
        }),
        "constraints": ["output_name_colon_value_line_per_field"],
    },
]


def call_wrapped(adapter: AnthropicAdapter, q: dict) -> ModelResponse:
    """Path A — current AIL intent wrapping."""
    return adapter.invoke(
        goal=q["goal"],
        constraints=q.get("constraints", []),
        context={"_intent_name": "ab_test"},
        inputs={"input": q["input"]},
        expected_type="Text",
    )


def call_stripped(adapter: AnthropicAdapter, q: dict) -> ModelResponse:
    """Path B — no JSON envelope, no meta-framing. Goal as system,
    constraints inlined, user message = input. Mimics what the
    authoring_chat path does."""
    system_lines = [q["goal"]]
    if q.get("constraints"):
        system_lines.append("")
        system_lines.append("Constraints:")
        for c in q["constraints"]:
            system_lines.append(f"- {c}")
    system = "\n".join(system_lines)

    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=adapter.model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": q["input"]}],
    )
    text = "".join(
        block.text for block in resp.content
        if getattr(block, "type", None) == "text"
    ).strip()
    return ModelResponse(
        value=text,
        confidence=1.0,
        model_id=resp.model,
        raw={"system_prompt": system, "user_prompt": q["input"]},
    )


def call_direct(adapter: AnthropicAdapter, q: dict) -> ModelResponse:
    """Path C — control. Minimal prompt; no AIL framing at all. Just
    the goal phrased naturally."""
    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"))
    goal = q["goal"]
    # Phrase constraints naturally, not as identifier list.
    if q.get("constraints"):
        goal += " Keep it " + ", ".join(
            c.replace("_", " ") for c in q["constraints"]
        ) + "."
    resp = client.messages.create(
        model=adapter.model,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"{goal}\n\nInput:\n{q['input']}",
        }],
    )
    text = "".join(
        block.text for block in resp.content
        if getattr(block, "type", None) == "text"
    ).strip()
    return ModelResponse(
        value=text,
        confidence=1.0,
        model_id=resp.model,
        raw={"goal_as_user_turn": goal},
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=str, default=None,
        help="Optional JSONL output file for structured results.")
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"Anthropic model (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--only", type=str, default=None,
        help="Run only the named question (for quick iteration).")
    args = parser.parse_args()

    adapter = AnthropicAdapter(model=args.model)
    out_file = open(args.out, "w", encoding="utf-8") if args.out else None

    questions = QUESTIONS
    if args.only:
        questions = [q for q in QUESTIONS if q["name"] == args.only]

    for q in questions:
        print("\n" + "=" * 72)
        print(f"QUESTION: {q['name']}")
        print("=" * 72)
        print(f"Goal: {q['goal']}")
        print(f"Input: {q['input'][:120]}")
        print()

        for label, caller in [
            ("A  wrapped (current AIL intent)", call_wrapped),
            ("B  stripped (raw system prompt)", call_stripped),
            ("C  direct (no AIL at all)", call_direct),
        ]:
            t0 = time.time()
            try:
                resp = caller(adapter, q)
                dt = time.time() - t0
                value = resp.value if isinstance(resp.value, str) else json.dumps(resp.value, ensure_ascii=False)
                print(f"--- {label}  ({dt:.1f}s) ---")
                print(value)
                print()
                if out_file is not None:
                    out_file.write(json.dumps({
                        "question": q["name"],
                        "path": label,
                        "value": value,
                        "latency_s": dt,
                        "model": resp.model_id,
                    }, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"--- {label}  FAILED ---")
                print(f"  {type(e).__name__}: {e}")
                print()

    if out_file is not None:
        out_file.close()
        print(f"\n[wrote {args.out}]")


if __name__ == "__main__":
    main()
