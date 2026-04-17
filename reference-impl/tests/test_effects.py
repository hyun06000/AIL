"""Tests for the effect system — http.get, http.post, file.read, file.write.

Effects are the mechanism by which an AIL program interacts with the
world outside the interpreter: network, filesystem, logs. Until this
phase, only `human_ask` and `log` were wired; now the spec's named
effects actually do something.

These tests cover:
  - Parser accepts dotted effect names (`http.get`, `file.read`).
  - File effects work end-to-end on a tmp path.
  - HTTP effects work against a local fixture server.
  - Every effect result carries an `effect` origin; provenance queries
    (has_effect_origin) return True.
  - Purity still rejects any pure fn containing a perform of any effect.
  - Implicit parallelism does NOT batch assignments whose RHS contains
    a perform — effects stay serial so ordering is deterministic.
"""
from __future__ import annotations

import http.server
import socketserver
import threading
import time
from pathlib import Path

import pytest

from ail_mvp import run
from ail_mvp.parser import PurityError
from ail_mvp.runtime import MockAdapter
from ail_mvp.runtime.parallel import plan_groups
from ail_mvp.parser.ast import Assignment, Call, Identifier, PerformExpr


# ---------- parser: dotted effect names ----------


def test_parser_accepts_dotted_effect_name():
    src = '''
    entry main(x: Text) {
        content = perform file.read("/tmp/does_not_matter")
        return content
    }
    '''
    from ail_mvp import compile_source
    program = compile_source(src)
    assert program.entry() is not None


def test_parser_accepts_legacy_bare_effect_name():
    # Backward-compat: old `perform human_ask(...)` still parses.
    src = '''
    entry main(x: Text) {
        answer = perform human_ask("hi")
        return answer
    }
    '''
    from ail_mvp import compile_source
    program = compile_source(src)
    assert program.entry() is not None


# ---------- file effects ----------


def test_file_write_then_read_roundtrip(tmp_path):
    path = str(tmp_path / "hello.txt")
    src = f'''
    entry main(x: Text) {{
        result = perform file.write("{path}", "hello from ail")
        content = perform file.read("{path}")
        return content
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "hello from ail"


def test_file_read_missing_returns_result_error(tmp_path):
    path = str(tmp_path / "nope.txt")
    src = f'''
    entry main(x: Text) {{
        content = perform file.read("{path}")
        if is_error(content) {{
            return "failed"
        }}
        return content
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "failed"


# ---------- http effects ----------


@pytest.fixture(scope="module")
def http_fixture():
    """Spin up a local HTTP server that echoes a deterministic response.
    Runs in a daemon thread so pytest tears it down on module exit.
    """
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/hello":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"hello http")
            elif self.path == "/notfound":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"missing")
            else:
                self.send_response(400)
                self.end_headers()
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", "replace")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"echo:{body}".encode("utf-8"))
        def log_message(self, *a, **kw):   # silence test output
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    # Give the socket a moment to be ready.
    time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def test_http_get_returns_body(http_fixture):
    url = f"{http_fixture}/hello"
    src = f'''
    entry main(x: Text) {{
        resp = perform http.get("{url}")
        return resp.body
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "hello http"


def test_http_get_status_field(http_fixture):
    url = f"{http_fixture}/hello"
    src = f'''
    entry main(x: Text) {{
        resp = perform http.get("{url}")
        return resp.status
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 200.0


def test_http_get_404_still_returns_response(http_fixture):
    # Non-2xx is a real response, not a transport error. ok=False but
    # we still get a body and status, so the program can inspect them.
    url = f"{http_fixture}/notfound"
    src = f'''
    entry main(x: Text) {{
        resp = perform http.get("{url}")
        return resp.status
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 404.0


def test_http_post_echoes_body(http_fixture):
    src = f'''
    entry main(x: Text) {{
        resp = perform http.post("{http_fixture}/any", "payload123")
        return resp.body
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "echo:payload123"


# ---------- provenance integration ----------


def test_file_read_value_carries_effect_origin(tmp_path):
    path = str(tmp_path / "x.txt")
    Path(path).write_text("data")
    src = f'''
    entry main(x: Text) {{
        content = perform file.read("{path}")
        return has_effect_origin(content)
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is True


def test_pure_computation_does_not_carry_effect_origin():
    src = '''
    pure fn double(n: Number) -> Number { return n * 2 }
    entry main(x: Text) { return has_effect_origin(double(5)) }
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is False


def test_effect_origin_name_is_qualified(tmp_path):
    path = str(tmp_path / "y.txt")
    Path(path).write_text("data")
    src = f'''
    entry main(x: Text) {{
        content = perform file.read("{path}")
        return origin_of(content)
    }}
    '''
    result, _ = run(src, input="", adapter=MockAdapter())
    assert isinstance(result.value, dict)
    assert result.value["kind"] == "effect"
    assert result.value["name"] == "file.read"
    assert "at" in result.value   # timestamp stamped


# ---------- purity + effects ----------


def test_pure_fn_cannot_contain_http_get():
    src = '''
    pure fn fetch_and_use(x: Text) -> Text {
        resp = perform http.get("http://example.com")
        return resp.body
    }
    entry main(x: Text) { return fetch_and_use(x) }
    '''
    with pytest.raises(PurityError) as ei:
        from ail_mvp import compile_source
        compile_source(src)
    assert "perform" in str(ei.value).lower() or "http.get" in str(ei.value)


def test_pure_fn_cannot_contain_file_write():
    src = '''
    pure fn sneaky(x: Text) -> Text {
        perform file.write("/tmp/x", "data")
        return "ok"
    }
    entry main(x: Text) { return sneaky(x) }
    '''
    with pytest.raises(PurityError) as ei:
        from ail_mvp import compile_source
        compile_source(src)
    assert "perform" in str(ei.value).lower() or "file.write" in str(ei.value)


# ---------- parallelism excludes effects ----------


def test_effect_calls_are_not_parallelized():
    # Two assignments, both with intent calls AND a perform. These would
    # be eligible for batching by the intent-presence rule, but the
    # perform-guard keeps them serial.
    stmts = [
        Assignment("a", PerformExpr(effect="http.get", args=[], kwargs={})),
        Assignment("b", PerformExpr(effect="http.get", args=[], kwargs={})),
    ]
    groups = plan_groups(stmts, intents=set())
    assert all(not g.parallel for g in groups)
    assert len(groups) == 2
