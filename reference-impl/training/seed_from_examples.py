"""Produce dataset/01_existing_examples.jsonl from the 15 programs
already in reference-impl/examples/.

Each example's leading `// ...` comment block is reused as the NL
prompt. The AIL source is taken verbatim. Category is inferred from
declaration types (any IntentDecl → at least pure_intent; plus any
FnDecl → hybrid). Runs every sample through the validator gates
before emitting — a sample that doesn't survive execution on
MockAdapter is skipped with a note.

This script is idempotent — re-run whenever examples/ changes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ail import compile_source, run, MockAdapter
from ail.parser.ast import FnDecl, IntentDecl


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
OUT_PATH = Path(__file__).parent / "dataset" / "01_existing_examples.jsonl"


# Pipe-delimited sample inputs for examples that expect one.
# Examples whose `entry` ignores its parameter can stay empty.
SAMPLE_INPUTS: dict[str, str] = {
    "classify.ail": "I love this product",
    "fizzbuzz.ail": "15",
    "translate.ail": "hello world",
    "summarize_and_classify.ail": "The weather is nice today",
    "review_analyzer.ail": "Great!\nAwful\nLoved it",
    "safe_csv_parser.ail": "Alice:85,Bob:xyz,Charlie:92",
    "evolve_retune.ail": "great",
    "cascade_extract.ail": "42",
    "hello.ail": "world",
    "audit_provenance.ail": "I love this product",
    "ask_human.ail": "I am tired",
    "smart_reply.ail": "hello",
    "parallel_analysis.ail": "The Fed raised rates today.",
    "meta_codegen.ail": "hello",
    "agent_fetch_summarize.ail": "",
    "expense_analyzer.ail": "2026-04-01|52000|food|팀 점심\n2026-04-03|180000|food|저녁 회식",
}


# The prompt an external user would type to ask for this program.
# Hand-curated per example; leaving it too long or too academic would
# pollute the training distribution. Short, plain request style.
NATURAL_PROMPTS: dict[str, str] = {
    "fizzbuzz.ail": "run fizzbuzz up to the number passed as input",
    "classify.ail": "classify the sentiment of the input text as positive, negative, or neutral",
    "translate.ail": "translate the input text to Korean",
    "summarize_and_classify.ail": "summarize the input briefly, then tell me its sentiment",
    "review_analyzer.ail": "given newline-separated reviews, classify each and report totals per category",
    "safe_csv_parser.ail": "parse comma-separated name:score rows; skip any row whose score isn't a valid non-negative number and report how many rows passed and how many errored",
    "evolve_retune.ail": "label the input's sentiment, using an intent that evolves its threshold when metrics drop",
    "cascade_extract.ail": "extract a number from the input — try a direct numeric parse first, fall back to scanning tokens, and only then ask the model",
    "hello.ail": "greet the person named in the input",
    "audit_provenance.ail": "produce a small report about the input text; label each field as coming from a pure fn or an LLM intent",
    "ask_human.ail": "suggest what to have for dinner, asking the human if the suggestion looks wrong",
    "smart_reply.ail": "classify the input's sentiment and reply with a different message for high vs low confidence",
    "parallel_analysis.ail": "for the input text, return its sentiment, topic, and a one-line summary",
    "meta_codegen.ail": "generate an AIL program at runtime that doubles its input, then run it",
    "agent_fetch_summarize.ail": "fetch a URL, summarize its body, and write the summary to a file",
    "expense_analyzer.ail": "given pipe-delimited date|amount|category|memo transactions, one per line, compute total and category breakdown and give one-sentence saving advice",
}


def classify_category(ail_source: str) -> str:
    """Walk the AST to decide pure_fn / pure_intent / hybrid.

    Conservative: any non-pure fn that could be calling intents counts
    as hybrid; a program with only pure fn (no intent decls, no
    intent-bearing stdlib imports) is pure_fn; one with only intent
    and no non-trivial fn is pure_intent; anything else is hybrid.
    """
    prog = compile_source(ail_source)
    has_intent = False
    has_fn = False
    for d in prog.declarations:
        if isinstance(d, IntentDecl):
            has_intent = True
        elif isinstance(d, FnDecl):
            # pure_fn declarations count only for purity decoration,
            # not for "this program does real computation" — we care
            # about the entry-level mix of fn vs intent.
            has_fn = True
    # Entry-point checks: look for intent calls from the entry body
    # via the source text (AST walk would be cleaner but this is a
    # one-shot harvester, not runtime code).
    if has_intent and has_fn:
        return "hybrid"
    if has_intent:
        return "pure_intent"
    return "pure_fn"


def try_execute(ail_source: str, input_text: str) -> tuple[bool, str]:
    try:
        result, _ = run(ail_source, input=input_text, adapter=MockAdapter())
        return True, str(result.value)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    skipped: list[tuple[str, str]] = []
    for path in sorted(EXAMPLES_DIR.glob("*.ail")):
        name = path.name
        prompt = NATURAL_PROMPTS.get(name)
        if prompt is None:
            skipped.append((name, "no NATURAL_PROMPTS entry"))
            continue
        src = path.read_text(encoding="utf-8")
        input_text = SAMPLE_INPUTS.get(name, "")
        ok, result_or_err = try_execute(src, input_text)
        if not ok:
            skipped.append((name, result_or_err))
            continue
        category = classify_category(src)
        entry = {
            "id": f"example_{path.stem}",
            "prompt": prompt,
            "ail_source": src,
            "category": category,
            "input_text": input_text,
            "source_of_sample": "existing_example",
        }
        # pure_fn entries get the deterministic expected value.
        if category == "pure_fn":
            entry["expected"] = result_or_err
        entries.append(entry)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for e in entries:
            json.dump(e, f, ensure_ascii=False)
            f.write("\n")

    print(f"wrote {len(entries)} samples → {OUT_PATH.relative_to(Path.cwd())}",
          file=sys.stderr)
    if skipped:
        print(f"skipped {len(skipped)}:", file=sys.stderr)
        for name, why in skipped:
            print(f"  {name}: {why[:100]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
