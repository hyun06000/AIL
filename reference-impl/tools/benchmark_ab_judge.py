"""LLM-as-judge for A/B/C responses on judgment prompts.

For each prompt WITHOUT objective ground truth, present the three
responses (labels randomized) to a judge model and ask: which response
best satisfies the original request? Rank + one-line reason.

Judge: Sonnet 4.6 (cheaper than Opus, still strong). Each prompt =
1 judge call. Randomization prevents position bias.

Usage:
    ANTHROPIC_API_KEY=... python tools/benchmark_ab_judge.py \\
        --results ../ab_full_results.jsonl \\
        --out ../ab_judgments.jsonl
"""
from __future__ import annotations
import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

JUDGE_MODEL = "claude-sonnet-4-6"

JUDGE_SYSTEM = """You are an impartial judge evaluating three responses to the same request.

Rank them best → worst based on how well each satisfies the ORIGINAL REQUEST.
Criteria: correctness, directness, absence of unnecessary verbosity, constraint compliance.

Output ONLY this JSON, nothing else:
{"ranking": ["X", "Y", "Z"], "reason": "one short sentence", "best_quality": "<brief>"}

where X/Y/Z are the labels shown to you."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    # Group responses by prompt_id, skip prompts with expected ground truth.
    by_prompt = defaultdict(dict)
    prompt_meta = {}
    for line in open(args.results):
        r = json.loads(line)
        if "error" in r:
            continue
        pid = r["prompt_id"]
        by_prompt[pid][r["path"]] = r
        prompt_meta[pid] = {
            "category": r["category"],
            "text": r["text"],
            "expected": r.get("expected"),
        }

    # Only judge prompts without expected (LLM judge for subjective items).
    # Prompts WITH expected are scored objectively — no need for judge.
    to_judge = [pid for pid, meta in prompt_meta.items() if not meta["expected"]]
    print(f"Judging {len(to_judge)} prompts (subjective / no ground truth)")

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    with open(args.out, "w") as f:
        for i, pid in enumerate(to_judge):
            responses = by_prompt[pid]
            if len(responses) != 3:
                print(f"  {pid}: missing path, skipping")
                continue
            paths = ["A_wrapped", "B_stripped", "C_direct"]
            labels = ["X", "Y", "Z"]
            order = paths[:]
            rng.shuffle(order)
            label_to_path = dict(zip(labels, order))

            meta = prompt_meta[pid]
            user_msg_parts = [
                f"ORIGINAL REQUEST: {meta['text']}",
                "",
                "THREE RESPONSES:",
                "",
            ]
            for lbl, path in label_to_path.items():
                user_msg_parts.append(f"--- {lbl} ---")
                user_msg_parts.append(responses[path]["value"])
                user_msg_parts.append("")

            resp = client.messages.create(
                model=JUDGE_MODEL,
                max_tokens=512,
                system=JUDGE_SYSTEM,
                messages=[{"role": "user", "content": "\n".join(user_msg_parts)}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
            try:
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:].strip()
                judgment = json.loads(text)
                ranked_paths = [label_to_path[lbl] for lbl in judgment["ranking"]]
            except Exception as e:
                print(f"  {pid}: parse failed ({e}); raw: {text[:100]}")
                ranked_paths = None
                judgment = {"raw": text, "parse_error": str(e)}

            record = {
                "prompt_id": pid,
                "category": meta["category"],
                "text": meta["text"],
                "label_to_path": label_to_path,
                "judgment": judgment,
                "ranked_paths": ranked_paths,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            winner = ranked_paths[0] if ranked_paths else "?"
            print(f"  [{i+1}/{len(to_judge)}] {pid}: winner={winner}")

    print(f"\n[wrote {args.out}]")


if __name__ == "__main__":
    main()
