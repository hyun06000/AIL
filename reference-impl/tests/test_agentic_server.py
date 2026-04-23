"""Tests for the agentic HTTP server helpers.

Focuses on the small pure functions in server.py that don't need a
bound socket to exercise. Full end-to-end request/response is covered
by test_agentic_web_ui.py's serve_project test."""
import socket
import threading
import time
import urllib.error
import urllib.request

from ail.agentic.project import Project
from ail.agentic.server import _looks_like_html, _render_value, serve_project


# ---------- _looks_like_html ----------


def test_html_detection_doctype():
    assert _looks_like_html("<!DOCTYPE html><html></html>") is True
    assert _looks_like_html("<!doctype html>...") is True


def test_html_detection_html_root():
    assert _looks_like_html("<html><body>x</body></html>") is True


def test_html_detection_fragment():
    assert _looks_like_html("<div>hello</div>") is True
    assert _looks_like_html("<ul><li>a</li></ul>") is True


def test_html_detection_leading_whitespace_ok():
    assert _looks_like_html("\n\n  <!doctype html>...") is True


def test_html_detection_plain_text_false():
    assert _looks_like_html("hello world") is False
    assert _looks_like_html("42") is False
    assert _looks_like_html("") is False


def test_html_detection_punctuation_false():
    # Tokens starting with < but not a tag name must not be mis-rendered
    assert _looks_like_html("<3") is False
    assert _looks_like_html("< ") is False
    assert _looks_like_html("<-- comment") is False


def test_html_detection_non_string_false():
    assert _looks_like_html(42) is False
    assert _looks_like_html(None) is False
    assert _looks_like_html(["<div>"]) is False


def test_html_detection_json_false():
    # JSON output shouldn't accidentally be served as HTML
    assert _looks_like_html('{"k": "v"}') is False
    assert _looks_like_html("[1, 2, 3]") is False


# ---------- HTML POST response ----------


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


HTML_RETURNING_AIL = """\
pure fn page() -> Text {
    return "<!doctype html><html><body><h1>dash</h1></body></html>"
}

entry main(input: Text) {
    return page()
}
"""

TEXT_RETURNING_AIL = """\
entry main(input: Text) {
    return "hello"
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


def test_post_returns_html_content_type_when_entry_returns_html(tmp_path):
    proj = Project.init(tmp_path / "dash")
    proj.intent_path.write_text("# dash\n\nDashboard.\n", encoding="utf-8")
    proj.write_app_source(HTML_RETURNING_AIL)
    port = _find_free_port()
    _serve(proj, port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/",
        data=b"", method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 200
        assert "text/html" in r.headers.get("Content-Type", "")
        body = r.read().decode("utf-8")
    # Served byte-exact — no trailing newline sneaked in before <!doctype>.
    assert body.startswith("<!doctype html>")
    assert "<h1>dash</h1>" in body


def test_post_returns_text_content_type_when_entry_returns_text(tmp_path):
    proj = Project.init(tmp_path / "plain")
    proj.intent_path.write_text("# plain\n\nPlain.\n", encoding="utf-8")
    proj.write_app_source(TEXT_RETURNING_AIL)
    port = _find_free_port()
    _serve(proj, port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/",
        data=b"ignored", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 200
        ctype = r.headers.get("Content-Type", "")
        assert "text/plain" in ctype
        body = r.read().decode("utf-8")
    assert body.strip() == "hello"
