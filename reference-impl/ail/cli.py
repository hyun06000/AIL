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


def _find_free_port(preferred: int = 8080) -> int:
    """Return `preferred` if available, otherwise the next free port.
    Scans up to 64 ports above `preferred` to avoid wandering to weird
    high numbers; falls back to an OS-assigned port if that exhausts."""
    import socket
    for p in range(preferred, preferred + 64):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            s.close()
            continue
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _try_open_browser(url: str) -> None:
    """Best-effort open the URL in the user's default browser. Silent
    on failure — the URL is already printed to stdout."""
    try:
        import webbrowser
        webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        pass


def _write_source(dest: str, source: str) -> None:
    """Write AIL source text to `dest`. `-` writes to stdout.

    Parent directories are created if missing. Contents are written with a
    trailing newline so the file is friendly to line-counting tools. Prints
    a one-line confirmation to stderr when the destination is a real file.
    """
    if dest == "-":
        print(source, end="\n" if not source.endswith("\n") else "")
        return
    path = Path(dest).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = source if source.endswith("\n") else source + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"--- AIL saved to {path} ---", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ail", description="AIL MVP interpreter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ask = sub.add_parser("ask",
        help="Ask AIL in natural language — the AI writes AIL and runs it for you")
    p_ask.add_argument("prompt", help="Natural-language request")
    p_ask.add_argument("--show-source", action="store_true",
                       help="Also print the AIL source the author produced (stderr)")
    p_ask.add_argument("--save-source", metavar="PATH", default=None,
                       help="Save the AIL source the author produced to the "
                            "given file path (answer still goes to stdout). "
                            "Use '-' to write to stdout instead.")
    p_ask.add_argument("--retries", type=int, default=3,
                       help="Max retries if the author emits invalid AIL (default 3)")

    p_run = sub.add_parser("run", help="Run an AIL program")
    p_run.add_argument("file", help="Path to .ail source file")
    p_run.add_argument("--input", default=None, help="Input to the entry's first parameter")
    p_run.add_argument("--trace", action="store_true", help="Print execution trace")
    p_run.add_argument("--trace-json", action="store_true", help="Print trace as JSON")
    p_run.add_argument("--mock", action="store_true",
                       help="Use mock adapter (no model calls)")
    p_run.add_argument("--raw", action="store_true",
                       help="Print only the return value on a single line "
                            "(no header, no confidence, no trace). "
                            "Matches the Go runtime's default output shape, "
                            "enabling shell-level conformance comparison.")

    p_parse = sub.add_parser("parse", help="Parse and print AST")
    p_parse.add_argument("file", help="Path to .ail source file")

    p_init = sub.add_parser("init",
        help="Scaffold a new AIL project AND launch the authoring chat "
             "UI in a browser. Talk to the agent in plain language; it "
             "writes INTENT.md and app.ail incrementally. Replaces the "
             "old 'edit INTENT.md manually then run ail up' flow.")
    p_init.add_argument("name",
        help="Project directory name. The folder is created in the cwd.")
    p_init.add_argument("--port", type=int, default=None,
        help="Port for the authoring server (default 8080, or next "
             "free port if occupied).")
    p_init.add_argument("--no-chat", action="store_true",
        help="Scaffold and exit — skip launching the chat UI. For "
             "scripted / CI use.")
    p_init.add_argument("--no-open", action="store_true",
        help="Don't auto-open the chat URL in the default browser.")

    p_up = sub.add_parser("up",
        help="Read INTENT.md, author/load app.ail, run tests, serve HTTP")
    p_up.add_argument("path", nargs="?", default=".",
        help="Project directory (default: current directory)")
    p_up.add_argument("--port", type=int, default=None,
        help="Override the port from INTENT.md ## Deployment")
    p_up.add_argument("--no-serve", action="store_true",
        help="Author + run tests, then exit. Don't start the HTTP server.")
    p_up.add_argument("--no-watch", action="store_true",
        help="Skip the file-watch background loop. By default `ail up` "
             "polls INTENT.md and app.ail for edits and re-runs the "
             "declared tests on change without restarting the server.")
    p_up.add_argument("--retries", type=int, default=3,
        help="Max retries if the author emits invalid AIL (default 3)")
    p_up.add_argument("--auto-fix", type=int, default=0, metavar="N",
        help="If declared tests fail, hand the failures to the chat "
             "backend and retry up to N times. Costs LLM calls — "
             "default 0 (off).")
    p_up.add_argument("--log", choices=["friendly", "compact"],
        default="friendly",
        help="Output style. `friendly` (default) is for end users; "
             "`compact` is the original v1.9.0 dev-style one-liners "
             "useful for scripts and CI.")

    p_serve = sub.add_parser("serve",
        help="Run a project's programs WITHOUT the authoring chat. "
             "This is the 'independent execution' mode per "
             "PRINCIPLES.md §5 — the chat session can be closed; the "
             "server keeps schedule.every ticks firing and the "
             "view.html dashboard accessible at /run. Run in a "
             "separate terminal (or tmux) from `ail up`; both can "
             "coexist on different ports against the same project.")
    p_serve.add_argument("path", nargs="?", default=".",
        help="Project directory (default: current directory)")
    p_serve.add_argument("--port", type=int, default=8090,
        help="Port to serve on (default 8090, distinct from ail up's "
             "default 8080 so both can run side-by-side).")
    p_serve.add_argument("--host", default="127.0.0.1",
        help="Host to bind (default 127.0.0.1). Use 0.0.0.0 to expose "
             "on the LAN for field-testing.")

    p_chat = sub.add_parser("chat",
        help="Edit an agentic project in natural language. The AI updates "
             "INTENT.md and/or app.ail to match your request, then re-runs "
             "the declared tests.")
    p_chat.add_argument("path", help="Project directory")
    p_chat.add_argument("request", help="Natural-language edit request "
                                        "(quoted on the command line)")
    p_chat.add_argument("--no-rerun", action="store_true",
        help="Skip re-running the declared tests after the edit lands.")

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
            if e.partial is not None and (args.show_source or args.save_source):
                src = e.partial.ail_source or ""
                if args.save_source:
                    _write_source(args.save_source, src)
                if args.show_source:
                    print("--- last attempt ---", file=sys.stderr)
                    print(src, file=sys.stderr)
                    print("--- errors ---", file=sys.stderr)
                    for err in e.partial.errors:
                        print(f"  {err}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        # The human sees only the answer by default.
        print(result.value)
        if args.save_source:
            _write_source(args.save_source, result.ail_source)
        if args.show_source:
            print("--- AIL ---", file=sys.stderr)
            print(result.ail_source, file=sys.stderr)
            print(
                f"--- confidence={result.confidence:.3f} "
                f"retries={result.retries} author={result.author_model} ---",
                file=sys.stderr,
            )
        return 0

    if args.cmd == "init":
        from .agentic import Project
        try:
            proj = Project.init(args.name)
        except FileExistsError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        print(f"Initialized AIL project at {proj.root}")

        if args.no_chat:
            print(f"  edit:  {proj.intent_path}")
            print(f"  then:  ail up {args.name}")
            return 0

        # Launch the authoring chat UI. The server auto-detects the
        # fresh state and serves the chat page on GET /.
        from .agentic.server import serve_project
        port = args.port or _find_free_port(8080)
        url = f"http://127.0.0.1:{port}/"
        print(f"  chat:  {url}")
        if not args.no_open:
            _try_open_browser(url)
        print(f"  (Ctrl+C to stop)\n")
        return serve_project(proj, port=port, host="127.0.0.1", watch=True)

    if args.cmd == "up":
        from .agentic import Project, bring_up
        try:
            proj = Project.at(args.path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return bring_up(
            proj,
            max_retries=args.retries,
            serve=not args.no_serve,
            port_override=args.port,
            watch=not args.no_watch,
            auto_fix_attempts=args.auto_fix,
            log_style=args.log,
        )

    if args.cmd == "serve":
        from .agentic import Project
        from .agentic.server import serve_project
        try:
            proj = Project.at(args.path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Serving {proj.root.name} on http://{args.host}:{args.port}/run")
        print(f"  (chat UI disabled — independent execution mode)")
        print(f"  (Ctrl+C to stop)\n")
        return serve_project(
            proj, port=args.port, host=args.host, watch=False,
            serve_only=True,
        )

    if args.cmd == "chat":
        from .agentic import Project, chat_apply
        try:
            proj = Project.at(args.path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        try:
            result = chat_apply(proj, args.request, rerun_tests=not args.no_rerun)
        except Exception as e:
            print(f"chat failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        if not result["changed"]:
            print("(no files changed)")
        else:
            print(f"changed: {', '.join(result['changed'])}")
        if result.get("summary"):
            print(f"summary: {result['summary']}")
        if "tests" in result:
            t = result["tests"]
            print(f"tests: {t['passed']}/{t['total']} passed")
            if t["passed"] < t["total"]:
                return 2
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

        if args.raw:
            # Value only — matches go-impl's default output shape so
            # the two runtimes can be compared byte-for-byte. Python
            # floats print as `5040.0`; Go prints whole-valued numbers
            # without the trailing `.0`. Normalize Python output to
            # match so conformance cases agree across runtimes.
            print(_format_value_raw(result.value))
            return 0

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


def _format_value_raw(value) -> str:
    """Render a ConfidentValue.value for `ail run --raw` in a shape
    that matches go-impl's default printer.

    - Floats that happen to be whole numbers (5040.0) drop the `.0`
      and print as integers. This reconciles the two runtimes on the
      common case without changing runtime semantics — Number in AIL
      is still float-backed in Python.
    - Everything else falls through to the default str() so lists,
      dicts, booleans, and non-integer floats are unchanged.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


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
