"""Tests for the agentic HTTP server helpers.

Focuses on the small pure functions in server.py that don't need a
bound socket to exercise. Full end-to-end request/response is covered
by test_agentic_web_ui.py's serve_project test."""
import json
import socket
import threading
import time
import urllib.error
import urllib.request

from ail.agentic.project import Project
from ail.agentic.server import (
    _diagnose_from_trace, _http_reason_hint, _render_value, serve_project,
)


# ---------- _render_value: dict / list formatting ----------


def test_render_value_passes_text_through():
    assert _render_value("hello") == "hello"


def test_render_value_passes_numbers_through():
    assert _render_value(42) == 42


def test_render_value_collapses_result_ok():
    v = {"_result": True, "ok": True, "value": "inner"}
    assert _render_value(v) == "inner"


def test_render_value_collapses_result_error():
    v = {"_result": True, "ok": False, "error": "boom"}
    assert _render_value(v) == "boom"


def test_render_value_collapses_result_containing_dict_to_json():
    # Result wrapping a record: the wrapper collapses, but the inner
    # record still gets pretty-printed so the user sees readable JSON
    # rather than Python repr `{'key': 'value'}`.
    inner = {"a": 1, "b": [1, 2]}
    v = {"_result": True, "ok": True, "value": inner}
    out = _render_value(v)
    assert isinstance(out, str)
    assert json.loads(out) == inner


def test_render_value_pretty_prints_dict():
    v = {"name": "Alice", "score": 92}
    out = _render_value(v)
    assert isinstance(out, str)
    # Pretty-printed — not Python repr (`'Alice'` would fail json parse).
    assert json.loads(out) == v
    assert "\n" in out  # indent=2 adds newlines


def test_render_value_pretty_prints_list():
    v = [1, 2, {"k": "v"}]
    out = _render_value(v)
    assert json.loads(out) == v


def test_render_value_unicode_not_escaped():
    # ensure_ascii=False so Korean text stays readable in the browser.
    v = {"msg": "안녕"}
    out = _render_value(v)
    assert "안녕" in out


# ---------- _http_reason_hint ----------


def test_http_reason_hint_auth_failures():
    for code in (401, 403):
        hint = _http_reason_hint(code)
        assert "인증" in hint or "authentication" in hint
        assert "demo" in hint  # warns about hardcoded fake keys


def test_http_reason_hint_not_found():
    assert "404" not in _http_reason_hint(404)  # text, not code
    assert "not found" in _http_reason_hint(404).lower()


def test_http_reason_hint_rate_limit():
    assert "rate" in _http_reason_hint(429).lower()


def test_http_reason_hint_server_error():
    assert "server" in _http_reason_hint(503).lower()


def test_http_reason_hint_success_is_empty():
    assert _http_reason_hint(200) == ""


# ---------- _diagnose_from_trace ----------


class _FakeTrace:
    def __init__(self, entries):
        self.entries = entries


class _FakeEntry:
    def __init__(self, kind, **payload):
        self.kind = kind
        self.payload = payload


def test_diagnose_from_trace_empty_returns_empty():
    assert _diagnose_from_trace(_FakeTrace([])) == ""
    assert _diagnose_from_trace(None) == ""


def test_diagnose_surfaces_401_http_failure():
    trace = _FakeTrace([
        _FakeEntry("http_call", method="GET",
                   url="https://newsapi.org/...?apiKey=demo",
                   status=401.0, ok=False,
                   body_preview='{"status":"error","code":"apiKeyInvalid"}'),
    ])
    out = _diagnose_from_trace(trace)
    assert "401" in out
    assert "newsapi.org" in out
    # Action hint should point to ail chat
    assert "ail chat" in out


def test_diagnose_ignores_successful_http_calls():
    trace = _FakeTrace([
        _FakeEntry("http_call", method="GET",
                   url="https://example.com/", status=200.0, ok=True),
    ])
    assert _diagnose_from_trace(trace) == ""


def test_diagnose_surfaces_intent_validation_failure():
    trace = _FakeTrace([
        _FakeEntry("intent_validation_failed",
                   intent="summarize", declared_type="Text",
                   error="declared Text but response parses as a JSON dict"),
    ])
    out = _diagnose_from_trace(trace)
    assert "summarize" in out
    assert "Text" in out


def test_diagnose_caps_to_three_hints():
    # Create 10 failing http_calls; diagnostic should show at most 3.
    entries = [
        _FakeEntry("http_call", method="GET", url=f"http://e{i}/",
                   status=500.0, ok=False, body_preview="")
        for i in range(10)
    ]
    out = _diagnose_from_trace(_FakeTrace(entries))
    # 3 url lines max
    assert out.count("http://e") <= 3


def test_diagnose_handles_network_error():
    trace = _FakeTrace([
        _FakeEntry("http_call", method="GET",
                   url="https://offline.invalid/", status=None, ok=False,
                   network_error="Name or service not known"),
    ])
    out = _diagnose_from_trace(trace)
    assert "offline.invalid" in out
    assert "network" in out.lower() or "네트워크" in out


# ---------- _render_value continued ----------


def test_render_value_non_json_serializable_falls_back_to_str():
    class Weird:
        def __repr__(self):
            return "<Weird>"
    v = {"x": Weird()}
    out = _render_value(v)
    # Didn't crash; fell back to Python str() of the dict.
    assert isinstance(out, str)


# ---------- _looks_like_html ----------


# ---------- POST response + view.html ----------


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


TEXT_RETURNING_AIL = """\
entry main(input: Text) {
    return input
}
"""

# AIL has no dict literal; records come from intents, state.read, or
# external effects. The end-to-end JSON pretty-print path is exercised
# via state.read below, which returns a list.

LIST_RETURNING_AIL = """\
entry main(input: Text) {
    r = perform state.read("payload")
    if is_ok(r) { return unwrap(r) }
    return "unset"
}
"""


def _wait_for_server(port: int) -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.2
            ).read()
            return
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.05)


def _serve(project, port):
    thread = threading.Thread(
        target=serve_project,
        kwargs={"project": project, "port": port, "watch": False},
        daemon=True,
    )
    thread.start()
    _wait_for_server(port)
    return thread


def test_post_returns_text_content_type(tmp_path):
    proj = Project.init(tmp_path / "plain")
    proj.intent_path.write_text("# plain\n\nPlain.\n", encoding="utf-8")
    proj.write_app_source(TEXT_RETURNING_AIL)
    port = _find_free_port()
    _serve(proj, port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/",
        data=b"hello", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 200
        ctype = r.headers.get("Content-Type", "")
        assert "text/plain" in ctype
        body = r.read().decode("utf-8")
    assert body.strip() == "hello"


def test_post_pretty_prints_list_as_json(tmp_path, monkeypatch):
    # entry that returns a list via state.read — the server renders
    # structured data as pretty-printed JSON, not Python repr.
    proj = Project.init(tmp_path / "data")
    proj.intent_path.write_text("# data\n\nData.\n", encoding="utf-8")
    proj.write_app_source(LIST_RETURNING_AIL)
    # Pre-populate the state key the entry reads. Force AIL_STATE_DIR
    # to this project's dir — prior tests may have left the env var
    # set to a different path (serve_project uses setdefault).
    state_dir = proj.state_dir / "state" / "keyval"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AIL_STATE_DIR", str(state_dir))
    (state_dir / "payload.json").write_text(
        json.dumps([1, 2, "three"]), encoding="utf-8")
    port = _find_free_port()
    _serve(proj, port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/",
        data=b"", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = r.read().decode("utf-8")
    parsed = json.loads(body)
    assert parsed == [1, 2, "three"]


def test_get_serves_view_html_when_present(tmp_path):
    # The whole point of the view.html pattern: if the project has
    # one, GET / returns its bytes verbatim instead of the default
    # textarea UI. AIL code stays focused on computation.
    proj = Project.init(tmp_path / "dash")
    proj.intent_path.write_text("# dash\n\nDashboard.\n", encoding="utf-8")
    proj.write_app_source(TEXT_RETURNING_AIL)
    view_html = (
        "<!doctype html><html><body>"
        "<h1>custom dashboard</h1>"
        "<script>fetch('/', {method:'POST'})</script>"
        "</body></html>"
    )
    (proj.root / "view.html").write_text(view_html, encoding="utf-8")
    port = _find_free_port()
    _serve(proj, port)

    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/", timeout=2
    ) as r:
        assert r.status == 200
        assert "text/html" in r.headers.get("Content-Type", "")
        body = r.read().decode("utf-8")
    # Served byte-exact: the custom title is visible and no default
    # textarea chrome leaked in.
    assert "custom dashboard" in body
    assert "<textarea" not in body


def test_get_falls_back_to_default_ui_without_view_html(tmp_path):
    proj = Project.init(tmp_path / "noview")
    proj.intent_path.write_text("# noview\n\nNo view.\n", encoding="utf-8")
    # TEXT_RETURNING_AIL uses `input`, so the default UI renders a
    # textarea. Without view.html we must get the built-in page.
    proj.write_app_source(TEXT_RETURNING_AIL)
    port = _find_free_port()
    _serve(proj, port)

    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/", timeout=2
    ) as r:
        body = r.read().decode("utf-8")
    assert "<textarea" in body
    # No custom title from a user-supplied view.html leaks in.
    assert "custom dashboard" not in body
