"""Tests for the optional `headers` kwarg on `perform http.get/post`.

Uses http.server in a background thread so we can inspect what headers
the HTTP effect actually sent over the wire — the goal is to verify
Bearer tokens and custom Content-Types land on the request exactly as
the AIL program passed them."""
from __future__ import annotations

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from ail import run


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _HeaderEchoHandler(BaseHTTPRequestHandler):
    """Echo each request's headers as a JSON-ish body so AIL can
    read them back. Used only in tests."""

    received: list[dict] = []

    def log_message(self, fmt, *args):  # quiet
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self.__class__.received.append({
            "headers": {k: v for k, v in self.headers.items()},
            "body": body,
        })
        resp = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


def _start_server():
    port = _find_free_port()
    _HeaderEchoHandler.received = []
    server = HTTPServer(("127.0.0.1", port), _HeaderEchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Give the accept loop a moment to be ready.
    time.sleep(0.05)
    return server, port


def test_http_post_sends_authorization_header(tmp_path):
    server, port = _start_server()
    try:
        src = f"""
entry main(input: Text) {{
    r = perform http.post(
        "http://127.0.0.1:{port}/",
        "payload",
        headers: [["Authorization", "Bearer secret-token-abc"]]
    )
    if r.ok {{ return "ok" }}
    return "fail"
}}
"""
        result, _ = run(str(_write(tmp_path, src)), input="")
        assert result.value == "ok"
        received = _HeaderEchoHandler.received[-1]
        assert received["headers"]["Authorization"] == "Bearer secret-token-abc"
        assert received["body"] == "payload"
    finally:
        server.shutdown()


def test_http_post_merges_user_agent_with_custom_headers(tmp_path):
    server, port = _start_server()
    try:
        src = f"""
entry main(input: Text) {{
    r = perform http.post(
        "http://127.0.0.1:{port}/",
        "x",
        headers: [["Content-Type", "application/json"]]
    )
    return "done"
}}
"""
        run(str(_write(tmp_path, src)), input="")
        received = _HeaderEchoHandler.received[-1]["headers"]
        assert received["Content-Type"] == "application/json"
        # default User-Agent still present
        assert "ail-http-effect" in received.get("User-Agent", "")
    finally:
        server.shutdown()


def test_http_post_works_without_headers_kwarg(tmp_path):
    # Backward compatibility: existing programs pass only (url, body).
    server, port = _start_server()
    try:
        src = f"""
entry main(input: Text) {{
    r = perform http.post("http://127.0.0.1:{port}/", "plain")
    return to_text(r.status)
}}
"""
        result, _ = run(str(_write(tmp_path, src)), input="")
        assert result.value == "200"
    finally:
        server.shutdown()


def _write(tmp_path, src: str):
    p = tmp_path / "app.ail"
    p.write_text(src, encoding="utf-8")
    return p
