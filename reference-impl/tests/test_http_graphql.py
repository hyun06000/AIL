"""Tests for the `perform http.graphql` effect.

HEAAL gap closer (2026-04-24 promo-bot field test): the agent spent
3 turns misdiagnosing a GitHub GraphQL failure because the combination
of 200 OK + `{"errors": [...]}` + no `data` field all looked like
success at the HTTP layer. The agent's hand-rolled check — `errs =
get(data, "errors"); if errs != "" ...` — fired on `None`/null errors
and never surfaced the real problem (missing `data`).

`http.graphql` collapses the entire decision tree into one Result:
ok(data) only when both `data` is present-and-not-null AND no
`errors` entries exist. Anything else is an error Result with a
concrete message.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str, inp: str = ""):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": inp}).value


class _GraphQLHandler(BaseHTTPRequestHandler):
    """Scripted responder. Each test sets `response` on the class
    and we echo it back with the corresponding status."""

    response: dict = {}
    status: int = 200
    captured_body: str = ""
    captured_auth: str = ""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self.__class__.captured_body = body
        self.__class__.captured_auth = self.headers.get("Authorization", "")
        payload = json.dumps(self.__class__.response).encode("utf-8")
        self.send_response(self.__class__.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


@pytest.fixture()
def graphql_server():
    _GraphQLHandler.response = {"data": {}}
    _GraphQLHandler.status = 200
    _GraphQLHandler.captured_body = ""
    _GraphQLHandler.captured_auth = ""
    srv = HTTPServer(("127.0.0.1", 0), _GraphQLHandler)
    port = srv.server_port
    t = Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        srv.shutdown()
        srv.server_close()


def test_graphql_success_returns_data(graphql_server):
    port = graphql_server
    _GraphQLHandler.response = {
        "data": {"createDiscussion": {"discussion": {"url": "http://x/42"}}}
    }
    src = (
        'entry main(input: Text) {\n'
        f'  r = perform http.graphql("http://127.0.0.1:{port}/graphql",\n'
        '     "mutation($t: String!) { createDiscussion(title: $t) '
        '{ discussion { url } } }",\n'
        '     [["t", "hello"]])\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  data = unwrap(r)\n'
        '  return get(get(get(data, "createDiscussion"), "discussion"), '
        '"url")\n'
        '}\n'
    )
    assert _run(src) == "http://x/42"
    sent = json.loads(_GraphQLHandler.captured_body)
    assert sent["variables"] == {"t": "hello"}


def test_graphql_errors_field_becomes_error_result(graphql_server):
    """The exact failure the field test hit: GitHub returned 200 with
    an `errors` array. The old hand-rolled check misread it.
    http.graphql surfaces the error message cleanly."""
    port = graphql_server
    _GraphQLHandler.response = {
        "errors": [{
            "type": "NOT_FOUND",
            "path": ["createDiscussion"],
            "message": "Could not resolve to a node with the global "
                       "id of 'R_kgDONdEkAg'.",
        }]
    }
    src = (
        'entry main(input: Text) {\n'
        f'  r = perform http.graphql("http://127.0.0.1:{port}/graphql",\n'
        '     "mutation { createDiscussion }")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "unexpected success"\n'
        '}\n'
    )
    out = _run(src)
    assert "http.graphql" in out
    assert "Could not resolve to a node" in out
    assert "NOT_FOUND" in out


def test_graphql_data_missing_is_error(graphql_server):
    """Server sends `{}` (no data, no errors) — real failure mode.
    http.graphql must flag this, not silently succeed."""
    port = graphql_server
    _GraphQLHandler.response = {}
    src = (
        'entry main(input: Text) {\n'
        f'  r = perform http.graphql("http://127.0.0.1:{port}/graphql",\n'
        '     "query { viewer { login } }")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "unexpected success"\n'
        '}\n'
    )
    out = _run(src)
    assert "http.graphql" in out
    assert "no `data`" in out


def test_graphql_data_null_is_error(graphql_server):
    """data: null means operation failed. Not an ok response."""
    port = graphql_server
    _GraphQLHandler.response = {"data": None}
    src = (
        'entry main(input: Text) {\n'
        f'  r = perform http.graphql("http://127.0.0.1:{port}/graphql",\n'
        '     "query { viewer { login } }")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "unexpected"\n'
        '}\n'
    )
    out = _run(src)
    assert "http.graphql" in out
    assert "null" in out


def test_graphql_http_4xx_is_error(graphql_server):
    port = graphql_server
    _GraphQLHandler.response = {"message": "Unauthorized"}
    _GraphQLHandler.status = 401
    src = (
        'entry main(input: Text) {\n'
        f'  r = perform http.graphql("http://127.0.0.1:{port}/graphql",\n'
        '     "query { viewer }")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "unexpected"\n'
        '}\n'
    )
    out = _run(src)
    assert "HTTP 401" in out


def test_graphql_non_json_response_is_error(graphql_server):
    # Simulate an auth gateway returning HTML. Real-world hazard.
    class _HtmlHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>rate limited</html>")

        def log_message(self, fmt, *a): pass

    srv = HTTPServer(("127.0.0.1", 0), _HtmlHandler)
    port = srv.server_port
    t = Thread(target=srv.serve_forever, daemon=True); t.start()
    try:
        src = (
            'entry main(input: Text) {\n'
            f'  r = perform http.graphql("http://127.0.0.1:{port}/g",\n'
            '     "query { x }")\n'
            '  if is_error(r) { return unwrap_error(r) }\n'
            '  return "unexpected"\n'
            '}\n'
        )
        out = _run(src)
        assert "not JSON" in out
        assert "rate limited" in out
    finally:
        srv.shutdown(); srv.server_close()


def test_graphql_auth_header_forwarded(graphql_server):
    port = graphql_server
    _GraphQLHandler.response = {"data": {"viewer": {"login": "hyun06000"}}}
    src = (
        'entry main(input: Text) {\n'
        f'  r = perform http.graphql("http://127.0.0.1:{port}/g",\n'
        '     "query { viewer { login } }",\n'
        '     [],\n'
        '     headers: [["Authorization", "Bearer tok-xyz"]])\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return get(get(unwrap(r), "viewer"), "login")\n'
        '}\n'
    )
    assert _run(src) == "hyun06000"
    assert _GraphQLHandler.captured_auth == "Bearer tok-xyz"


def test_graphql_empty_errors_array_is_success(graphql_server):
    # GraphQL spec: `errors: []` is valid and means no errors. Treat
    # same as no errors field.
    port = graphql_server
    _GraphQLHandler.response = {"data": {"ok": True}, "errors": []}
    src = (
        'entry main(input: Text) {\n'
        f'  r = perform http.graphql("http://127.0.0.1:{port}/g",\n'
        '     "query { ok }")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return to_text(get(unwrap(r), "ok"))\n'
        '}\n'
    )
    assert _run(src) == "true"


def test_graphql_rejects_empty_query():
    out = _run(
        'entry main(input: Text) {\n'
        '  r = perform http.graphql("http://127.0.0.1:1/g", "")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "unexpected"\n'
        '}\n'
    )
    assert "non-empty" in out
