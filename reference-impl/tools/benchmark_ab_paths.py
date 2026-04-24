"""A/B/C path comparison on the full 50-prompt benchmark corpus.

Commissioned by Arche (Claude Opus 4) on 2026-04-24: the 5-prompt smoke
test suggested wrapped does not degrade reasoning, but 5 is a hypothesis
check — 50 is proof. Corpus: ``benchmarks/prompts.json`` (A=pure_fn,
B=pure_intent, C=hybrid).

Three paths per prompt:
  A_wrapped  — current AIL intent (meta-framing + JSON envelope + confidence)
  B_stripped — goal as system, question as user, no envelope
  C_direct   — no AIL framing at all, raw user turn

Output: JSONL with every response plus full prompt bytes sent to the
model (from the instrumented adapter). Scoring is separate — prompts
with ``expected`` are matched here; judgment items are flagged for
later LLM-as-judge.

Usage:
    ANTHROPIC_API_KEY=... python tools/benchmark_ab_paths.py \\
        --out ../ab_full_results.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ail.runtime.anthropic_adapter import AnthropicAdapter, DEFAULT_MODEL
from ail.runtime.model import ModelResponse


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = REPO_ROOT / "benchmarks" / "prompts.json"


def call_wrapped(adapter: AnthropicAdapter, prompt: dict) -> ModelResponse:
    return adapter.invoke(
        goal=prompt["text"],
        constraints=[],
        context={"_intent_name": "benchmark_ab"},
        inputs={},
        expected_type="Text",
    )


def call_stripped(adapter: AnthropicAdapter, prompt: dict) -> ModelResponse:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=adapter.model,
        max_tokens=2048,
        system=prompt["text"],
        messages=[{"role": "user", "content": "(proceed)"}],
    )
    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()
    return ModelResponse(
        value=text, confidence=1.0, model_id=resp.model,
        raw={"system_prompt": prompt["text"], "user_prompt": "(proceed)"},
    )


def call_direct(adapter: AnthropicAdapter, prompt: dict) -> ModelResponse:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=adapter.model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt["text"]}],
    )
    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()
    return ModelResponse(
        value=text, confidence=1.0, model_id=resp.model,
        raw={"user_prompt": prompt["text"]},
    )


def score_expected(value, expected: str) -> dict:
    """Objective scoring for prompts with ground truth.

    Returns {"match": bool, "kind": str} — 'exact', 'substring', 'miss'.
    Wrapped path value may be non-string (JSON parsed); normalize.
    """
    if expected is None:
        return {"match": None, "kind": "no_ground_truth"}
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    s_norm = s.strip().lower()
    exp_norm = str(expected).strip().lower()
    if s_norm == exp_norm:
        return {"match": True, "kind": "exact"}
    if exp_norm in s_norm:
        return {"match": True, "kind": "substring"}
    return {"match": False, "kind": "miss"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--model", type=str, default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None,
                    help="Run only first N prompts (smoke)")
    ap.add_argument("--only-category", type=str, default=None,
                    choices=["A", "B", "C"])
    args = ap.parse_args()

    corpus = json.load(open(CORPUS))["prompts"]
    if args.only_category:
        corpus = [p for p in corpus if p["category"] == args.only_category]
    if args.limit:
        corpus = corpus[: args.limit]

    print(f"Corpus: {len(corpus)} prompts × 3 paths = {len(corpus)*3} calls")
    adapter = AnthropicAdapter(model=args.model)

    paths = [
        ("A_wrapped", call_wrapped),
        ("B_stripped", call_stripped),
        ("C_direct", call_direct),
    ]

    with open(args.out, "w", encoding="utf-8") as f:
        for i, prompt in enumerate(corpus):
            print(f"\n[{i+1}/{len(corpus)}] {prompt['id']} [{prompt['category']}]: {prompt['text'][:70]}")
            for path_name, caller in paths:
                t0 = time.time()
                try:
                    resp = caller(adapter, prompt)
                    dt = time.time() - t0
                    value = resp.value if isinstance(resp.value, str) else json.dumps(resp.value, ensure_ascii=False)
                    score = score_expected(resp.value, prompt.get("expected"))
                    print(f"  {path_name:12s} {dt:4.1f}s  {score['kind']:13s}  {value[:80]}")
                    f.write(json.dumps({
                        "prompt_id": prompt["id"],
                        "category": prompt["category"],
                        "text": prompt["text"],
                        "expected": prompt.get("expected"),
                        "path": path_name,
                        "value": value,
                        "confidence": resp.confidence,
                        "latency_s": round(dt, 2),
                        "model": resp.model_id,
                        "score": score,
                    }, ensure_ascii=False) + "\n")
                    f.flush()
                except Exception as e:
                    dt = time.time() - t0
                    print(f"  {path_name:12s} {dt:4.1f}s  FAILED: {type(e).__name__}: {e}")
                    f.write(json.dumps({
                        "prompt_id": prompt["id"],
                        "category": prompt["category"],
                        "path": path_name,
                        "error": f"{type(e).__name__}: {e}",
                    }, ensure_ascii=False) + "\n")
                    f.flush()

    print(f"\n[wrote {args.out}]")


if __name__ == "__main__":
    main()
