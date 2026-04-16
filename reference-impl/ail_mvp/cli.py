"""Command-line interface for the AIL MVP.

Usage:
    ail run program.ail [--input TEXT] [--trace] [--mock] [--context-file FILE]
    ail parse program.ail                   # show AST
    ail version

The CLI is intentionally tiny. Most users will drive the interpreter via
the Python API.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from . import run, compile_source, __version__
from .runtime import MockAdapter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ail", description="AIL MVP interpreter")
    sub = parser.add_subparsers(dest="cmd", required=True)

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
        print(f"ail-mvp {__version__}")
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
