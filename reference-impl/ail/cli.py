"""Command-line interface for the AIL MVP.

Usage:
    ail ask "what I want to know"           # the primary interface
    ail run program.ail [--input TEXT] [--trace] [--mock]
    ail parse program.ail                   # show AST
    ail version

`ask` is the AI-native interface: you write a plain-language prompt, an
LLM writes AIL to answer it, the runtime executes, you get the answer.
The other subcommands are the programming-language-shaped fallback —
useful for debugging, learning the syntax, or running a program someone
else wrote.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from . import run, compile_source, ask, AuthoringError, __version__
from .runtime import MockAdapter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ail", description="AIL MVP interpreter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ask = sub.add_parser("ask",
        help="Ask AIL in natural language — the AI writes AIL and runs it for you")
    p_ask.add_argument("prompt", help="Natural-language request")
    p_ask.add_argument("--show-source", action="store_true",
                       help="Also print the AIL source the author produced (stderr)")
    p_ask.add_argument("--retries", type=int, default=3,
                       help="Max retries if the author emits invalid AIL (default 3)")

    p_run = sub.add_parser("run", help="Run an AIL program")
    p_run.add_argument("file", help="Path to .ail source file")
    p_run.add_argument("--input", default=None, help="Input to the entry's first parameter")
    p_run.add_argument("--trace", action="store_true", help="Print execution trace")
    p_run.add_argument("--trace-json", action="store_true", help="Print trace as JSON")
    p_run.add_argument("--mock", action="store_true",
                       help="Use mock adapter (no model calls)")

    p_parse = sub.add_parser("parse", help="Parse and print AST")
    p_parse.add_argument("file", help="Path to .ail source file")

    sub.add_parser("version", help="Print version")

    args = parser.parse_args(argv)

    if args.cmd == "version":
        print(f"ail {__version__}")
        return 0

    if args.cmd == "ask":
        try:
            result = ask(args.prompt, max_retries=args.retries)
        except AuthoringError as e:
            print(f"AuthoringError: {e}", file=sys.stderr)
            if e.partial is not None and args.show_source:
                print("--- last attempt ---", file=sys.stderr)
                print(e.partial.ail_source, file=sys.stderr)
                print("--- errors ---", file=sys.stderr)
                for err in e.partial.errors:
                    print(f"  {err}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        # The human sees only the answer by default.
        print(result.value)
        if args.show_source:
            print("--- AIL ---", file=sys.stderr)
            print(result.ail_source, file=sys.stderr)
            print(
                f"--- confidence={result.confidence:.3f} "
                f"retries={result.retries} author={result.author_model} ---",
                file=sys.stderr,
            )
        return 0

    if args.cmd == "parse":
        source = Path(args.file).read_text(encoding="utf-8")
        program = compile_source(source)
        print(f"Program with {len(program.declarations)} declarations:")
        for d in program.declarations:
            # Different declaration types have different name fields
            label = _declaration_label(d)
            print(f"  {type(d).__name__}: {label}")
        return 0

    if args.cmd == "run":
        adapter = MockAdapter() if args.mock else None
        try:
            result, trace = run(args.file, input=args.input, adapter=adapter)
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1

        print("=" * 60)
        print("RESULT")
        print("=" * 60)
        print(f"value: {result.value}")
        print(f"confidence: {result.confidence:.3f}")

        if args.trace_json:
            print()
            print("=" * 60)
            print("TRACE (JSON)")
            print("=" * 60)
            print(trace.to_json())
        elif args.trace:
            print()
            print("=" * 60)
            print("TRACE")
            print("=" * 60)
            print(trace.pretty())

        return 0

    return 0


def _declaration_label(d) -> str:
    """Return a human-friendly label for each declaration type."""
    # Each declaration kind has its own primary-name field
    if hasattr(d, "name"):
        return d.name
    if hasattr(d, "intent_name"):   # EvolveDecl
        return f"for {d.intent_name}"
    if hasattr(d, "source"):        # ImportDecl
        sym = getattr(d, "symbol", "")
        return f"{sym} from {d.source!r}" if sym else d.source
    return "?"


if __name__ == "__main__":
    sys.exit(main())
