"""Minimal HTTP server for an agentic AIL project.

POST /  with raw text body  →  runs entry main(input=body), returns the value.
GET  /healthz                →  200 ok.

Uses Python's stdlib `http.server`. Not production-grade; v0 is meant
for local development and small-traffic demos. Production hardening
(concurrency, timeouts, auth) is L2 v1+ work.
"""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from .. import run as ail_run
from .agent import _looks_like_error
from .project import Project


def _render_value(value):
    """Format an entry main() return value for HTTP response.

    AIL programs that signal success-or-error with Result return a dict
    shape; collapse it to the inner value (or error message) so HTTP
    clients see plain text instead of language internals.
    """
    if isinstance(value, dict) and value.get("_result"):
        if value.get("ok"):
            return value.get("value", "")
        return value.get("error", "error")
    if isinstance(value, str) and value.startswith("UNWRAP_ERROR:"):
        # Surface the inner message without the runtime sentinel prefix.
        return value[len("UNWRAP_ERROR:"):].strip()
    return value


def _make_handler(project: Project):
    """Build a request handler closed over a specific Project. Done as
    a factory so each project can have its own handler without globals."""

    class _Handler(BaseHTTPRequestHandler):
        # Suppress default per-request stderr logging — we record to ledger.
        def log_message(self, fmt, *args):  # noqa: N802 — stdlib name
            return

        def do_GET(self):  # noqa: N802 — stdlib name
            if self.path in ("/healthz", "/health"):
                body = b"ok\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._send_text(404, "POST / with the input as the body, "
                                 "or GET /healthz\n")

        def do_POST(self):  # noqa: N802 — stdlib name
            if self.path != "/":
                self._send_text(404, "POST / only\n")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8") if length else ""

            try:
                result, _trace = ail_run(str(project.app_path), input=body)
                value = result.value
                if _looks_like_error(value):
                    rendered = _render_value(value)
                    project.append_ledger({
                        "event": "request",
                        "path": "/",
                        "input_chars": len(body),
                        "ok": False,
                        "value_preview": str(rendered)[:200],
                    })
                    self._send_text(500, str(rendered) + "\n")
                    return
                rendered = _render_value(value)
                response = (str(rendered) + "\n").encode("utf-8")
                project.append_ledger({
                    "event": "request",
                    "path": "/",
                    "input_chars": len(body),
                    "ok": True,
                    "value_preview": str(value)[:200],
                })
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                project.append_ledger({
                    "event": "request",
                    "path": "/",
                    "input_chars": len(body),
                    "ok": False,
                    "error": err,
                })
                self._send_text(500, err + "\n")

        def _send_text(self, code: int, text: str) -> None:
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def serve_project(project: Project, *, port: int, host: str = "127.0.0.1") -> int:
    """Block, serving the project until SIGINT. Returns exit code."""
    handler = _make_handler(project)
    try:
        server = HTTPServer((host, port), handler)
    except OSError as e:
        # Port collision is the common case. Fail loud, don't reassign.
        print(f"could not bind {host}:{port} — {e}\n"
              f"another `ail up` on the same port? change `## Deployment` "
              f"in INTENT.md or pass --port to ail up.",
              file=sys.stderr)
        return 3

    project.append_ledger({
        "event": "serve_start", "host": host, "port": port,
    })
    print(f"[{project.root.name}] serving on http://{host}:{port}/  "
          f"(POST text body, Ctrl-C to stop)", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{project.root.name}] shutting down", file=sys.stderr)
    finally:
        server.server_close()
        project.append_ledger({"event": "serve_stop"})
    return 0
