"""Tests for encode_json pure function and http.post_json effect.

These close the HEAAL gap surfaced by the 2026-04-23 promo-bot field test:
agents hand-rolling JSON strings via join([...]) shipped malformed bodies
that neither grammar nor runtime caught. encode_json / http.post_json
move the escaping responsibility into the runtime so the author cannot
get it wrong.
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


# ---------- encode_json ----------

def test_encode_json_flat_pair_list_becomes_object():
    out = _run('entry main(input: Text) {\n'
               '  r = encode_json([["name", "alice"], ["age", 30]])\n'
               '  if is_error(r) { return unwrap_error(r) }\n'
               '  return unwrap(r)\n'
               '}\n')
    assert json.loads(out) == {"name": "alice", "age": 30}


def test_encode_json_nested_pair_list():
    out = _run('entry main(input: Text) {\n'
               '  r = encode_json([\n'
               '    ["query", "mutation M"],\n'
               '    ["variables", [["title", "hi"], ["n", 42]]]\n'
               '  ])\n'
               '  if is_error(r) { return unwrap_error(r) }\n'
               '  return unwrap(r)\n'
               '}\n')
    parsed = json.loads(out)
    assert parsed == {
        "query": "mutation M",
        "variables": {"title": "hi", "n": 42},
    }


def test_encode_json_escapes_quotes_and_newlines():
    # The exact failure mode from the field test: embedded quotes and
    # newlines in LLM-generated body text must not break the wire format.
    out = _run('entry main(input: Text) {\n'
               '  r = encode_json([["body", input]])\n'
               '  if is_error(r) { return unwrap_error(r) }\n'
               '  return unwrap(r)\n'
               '}\n',
               inp='Hello "world"\nsecond line\\path')
    parsed = json.loads(out)
    assert parsed == {"body": 'Hello "world"\nsecond line\\path'}


def test_encode_json_plain_list_becomes_array():
    out = _run('entry main(input: Text) {\n'
               '  r = encode_json(["a", "b", "c"])\n'
               '  if is_error(r) { return unwrap_error(r) }\n'
               '  return unwrap(r)\n'
               '}\n')
    assert json.loads(out) == ["a", "b", "c"]


def test_encode_json_rejects_ok_result_wrapper():
    # Authors should unwrap() before encoding; wrapping a Result produces
    # {"_result": true, "ok": true, ...} which no API accepts. Refusing
    # up front surfaces the bug at the author's boundary.
    out = _run('entry main(input: Text) {\n'
               '  r = encode_json(ok("hi"))\n'
               '  if is_error(r) { return unwrap_error(r) }\n'
               '  return unwrap(r)\n'
               '}\n')
    assert "ok-Result" in out


def test_encode_json_rejects_error_result():
    out = _run('entry main(input: Text) {\n'
               '  r = encode_json(error("boom"))\n'
               '  if is_error(r) { return unwrap_error(r) }\n'
               '  return unwrap(r)\n'
               '}\n')
    assert "error-Result" in out


# ---------- http.post_json ----------

class _EchoHandler(BaseHTTPRequestHandler):
    """Echoes request method, path, headers, and body back as JSON."""

    received: list[dict] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        record = {
            "path": self.path,
            "content_type": self.headers.get("Content-Type", ""),
            "authorization": self.headers.get("Authorization", ""),
            "body": body,
        }
        self.__class__.received.append(record)
        if self.path == "/echo":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(record).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": false, "error": "not found"}')

    def log_message(self, format, *args):  # quiet test output
        pass


@pytest.fixture()
def echo_server():
    _EchoHandler.received = []
    srv = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    port = srv.server_port
    t = Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        srv.shutdown()
        srv.server_close()


def test_http_post_json_serializes_structured_body(echo_server):
    port = echo_server
    src = ('entry main(input: Text) {\n'
           f'  r = perform http.post_json("http://127.0.0.1:{port}/echo",\n'
           '    [["title", "hi"], ["body", input]])\n'
           '  return r.body\n'
           '}\n')
    out = _run(src, inp='line 1\nline "two"')
    parsed = json.loads(out)
    assert parsed["content_type"] == "application/json"
    assert json.loads(parsed["body"]) == {
        "title": "hi",
        "body": 'line 1\nline "two"',
    }


def test_http_post_json_rejects_text_body():
    out = _run('entry main(input: Text) {\n'
               '  r = perform http.post_json("http://127.0.0.1:1/", "{\\"a\\": 1}")\n'
               '  if is_error(r) { return unwrap_error(r) }\n'
               '  return "unexpected success"\n'
               '}\n')
    assert "body must be structured" in out
    assert "http.post" in out  # points author at the raw form


def test_http_post_json_auto_sets_content_type(echo_server):
    port = echo_server
    src = ('entry main(input: Text) {\n'
           f'  r = perform http.post_json("http://127.0.0.1:{port}/echo", [["k", "v"]])\n'
           '  return r.body\n'
           '}\n')
    out = _run(src)
    assert json.loads(out)["content_type"] == "application/json"


def test_http_post_json_preserves_caller_auth_header(echo_server):
    port = echo_server
    src = ('entry main(input: Text) {\n'
           f'  r = perform http.post_json("http://127.0.0.1:{port}/echo",\n'
           '    [["k", "v"]],\n'
           '    headers: [["Authorization", "Bearer tok123"]])\n'
           '  return r.body\n'
           '}\n')
    out = _run(src)
    assert json.loads(out)["authorization"] == "Bearer tok123"


def test_http_post_json_handles_error_status(echo_server):
    port = echo_server
    src = ('entry main(input: Text) {\n'
           f'  r = perform http.post_json("http://127.0.0.1:{port}/missing",\n'
           '    [["k", "v"]])\n'
           '  if r.ok { return "unexpected ok" }\n'
           '  return join([to_text(r.status), ": ", r.body], "")\n'
           '}\n')
    out = _run(src)
    assert out.startswith("404")
    assert "not found" in out
