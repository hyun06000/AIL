"""Live harness: run every example against a real Claude model.

This is the script that turns AIL from a spec-with-a-mock into a
thing that actually executes on real infrastructure.

Usage:
    # Set your API key (directly or via .env at repo root)
    export ANTHROPIC_API_KEY=sk-ant-...

    # Run all examples and collect results:
    python examples/run_live.py

    # Run a single example with a specific input:
    python examples/run_live.py --only translate --input "Hello, how are you?"

    # Dump full traces as JSON to a directory:
    python examples/run_live.py --trace-dir ./live_results

Output format for each example:
    ──────────────────────────────────────────────
    EXAMPLE: <name>
    INPUT:   <input>
    ──────────────────────────────────────────────
    RESULT (confidence <N>): <value>

    [TRACE summary: N entries, M model calls]

The harness is defensive: any single example failing does not stop the
others. Failures are reported with the exception message and a short
tail of the trace to aid debugging.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

# Allow running from anywhere inside the repo
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))  # reference-impl/ on sys.path


@dataclass
class ExampleCase:
    name: str
    path: Path
    default_input: str
    description: str


EXAMPLES: list[ExampleCase] = [
    ExampleCase(
        name="hello",
        path=HERE / "hello.ail",
        default_input="세계",
        description="Simplest case — one intent, one entry",
    ),
    ExampleCase(
        name="translate",
        path=HERE / "translate.ail",
        default_input="Hello, how are you doing today?",
        description="Context inheritance with override; Korean formal translation",
    ),
    ExampleCase(
        name="classify",
        path=HERE / "classify.ail",
        default_input="I really enjoyed the film, but the ending dragged on.",
        description="Branch dispatch on a classifier's output",
    ),
    ExampleCase(
        name="ask_human",
        path=HERE / "ask_human.ail",
        default_input="I'm tired and hungry but unsure what I want",
        description="Low-confidence handler falls back to human (STDIN required)",
    ),
    ExampleCase(
        name="fizzbuzz",
        path=HERE / "fizzbuzz.ail",
        default_input="15",
        description="Pure fn — no LLM calls at all; proves AIL is a real language",
    ),
    ExampleCase(
        name="review_analyzer",
        path=HERE / "review_analyzer.ail",
        default_input="Great product!\nTerrible quality\nLoved it so much\nOkay I guess\nAwful",
        description="Hybrid fn+intent pipeline: parse+filter(fn) -> classify(intent) -> report(fn)",
    ),
]


def load_dotenv_if_present() -> None:
    """Load .env from the repo root if python-dotenv is not installed.

    Writes variables into os.environ. Only processes simple KEY=VALUE
    lines; does not handle export keyword, quoted values with escapes,
    or multiline values. For full dotenv semantics, install python-dotenv.
    """
    for candidate in (REPO_ROOT / ".env", HERE.parent / ".env", Path.cwd() / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


def run_one(case: ExampleCase, user_input: str | None,
            trace_dir: Path | None) -> tuple[bool, str]:
    """Run a single example. Returns (success, summary)."""
    from ail_mvp import run
    from ail_mvp.runtime.anthropic_adapter import AnthropicAdapter

    inp = user_input or case.default_input

    print("─" * 62)
    print(f"EXAMPLE: {case.name}")
    print(f"INPUT:   {inp}")
    print(f"NOTE:    {case.description}")
    print("─" * 62)

    try:
        adapter = AnthropicAdapter()
    except Exception as e:
        return False, f"Failed to construct AnthropicAdapter: {e}"

    # For ask_human, auto-decline interactive prompts for the non-interactive harness
    def non_interactive_human(q, *, expect="text"):
        print(f"  [harness auto-responded to human prompt: '{q[:80]}...']")
        if expect == "yes/no":
            return False
        return "(no human present; harness default)"

    try:
        result, trace = run(
            str(case.path), input=inp,
            adapter=adapter, ask_human=non_interactive_human,
        )
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"Execution raised {type(e).__name__}: {e}\n{tb}"

    # Summary
    conf = result.confidence
    val = str(result.value)
    if len(val) > 200:
        val_display = val[:200] + "…"
    else:
        val_display = val

    model_calls = sum(1 for e in trace.entries if e.kind == "model_response")
    print(f"\nRESULT (confidence {conf:.3f}):")
    print(f"  {val_display}")
    print(f"\n[trace: {len(trace.entries)} entries, {model_calls} model calls]")
    print()

    # Optionally dump trace
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        out_path = trace_dir / f"{case.name}.trace.json"
        out_path.write_text(trace.to_json(), encoding="utf-8")
        print(f"[trace written to {out_path}]")
        print()

    return True, f"ok — conf={conf:.3f}, value={val_display}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="Run just one example by name", default=None)
    parser.add_argument("--input", help="Override the input for the selected example", default=None)
    parser.add_argument("--trace-dir", help="Directory to dump full JSON traces", default=None)
    args = parser.parse_args()

    load_dotenv_if_present()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        print(
            "Set it in the environment or put it in a .env file at the repo root.",
            file=sys.stderr,
        )
        return 2

    # Filter cases
    if args.only:
        cases = [c for c in EXAMPLES if c.name == args.only]
        if not cases:
            names = ", ".join(c.name for c in EXAMPLES)
            print(f"Unknown example '{args.only}'. Available: {names}", file=sys.stderr)
            return 2
    else:
        cases = list(EXAMPLES)

    trace_dir = Path(args.trace_dir) if args.trace_dir else None

    successes: list[str] = []
    failures: list[tuple[str, str]] = []

    for case in cases:
        ok, summary = run_one(case, args.input, trace_dir)
        if ok:
            successes.append(f"{case.name}: {summary}")
        else:
            failures.append((case.name, summary))

    # Final summary
    print("═" * 62)
    print(f"SUMMARY: {len(successes)} ok, {len(failures)} failed")
    print("═" * 62)
    for s in successes:
        print(f"  ✓ {s}")
    for name, msg in failures:
        print(f"  ✗ {name}: {msg.splitlines()[0]}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
