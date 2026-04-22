"""Tests for the browser UI renderer and the GET / server path."""
import threading
import urllib.request
from pathlib import Path

from ail.agentic.project import Project
from ail.agentic.web_ui import render_page, extract_preamble


SIMPLE_AIL = """\
entry main(input: Text) {
    return input
}
"""


def test_render_page_contains_name_and_preamble():
    html = render_page(
        project_name="word-counter",
        intent_preamble="Counts words in the incoming text.",
        host="127.0.0.1",
        port=8080,
    )
    assert "word-counter" in html
    assert "Counts words" in html
    assert "127.0.0.1:8080" in html
    # Form elements must be present so a user can actually do something.
    assert "<textarea" in html
    assert "<button" in html
    assert 'id="result"' in html


def test_render_page_localizes_to_korean_when_preamble_is_korean():
    html = render_page(
        project_name="형태소-분석기",
        intent_preamble="한국어 형태소로 나눠서 CSV로 돌려주는 서비스",
        host="127.0.0.1",
        port=8088,
    )
    # Korean UI strings replace the English ones
    assert "보내기" in html         # send button
    assert "결과" in html             # result label
    assert "형태소-분석기" in html
    # Callout about auto-reload is in Korean
    assert "INTENT.md" in html
    assert "재시작할 필요 없습니다" in html


def test_render_page_escapes_dangerous_characters():
    html = render_page(
        project_name="<script>alert(1)</script>",
        intent_preamble="a & b <c> \"quoted\"",
        host="127.0.0.1",
        port=8080,
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_extract_preamble_takes_text_between_title_and_first_header():
    text = (
        "# demo\n\n"
        "This is the paragraph users see.\n\n"
        "## Behavior\n- rule\n"
    )
    assert extract_preamble(text) == "This is the paragraph users see."


def test_extract_preamble_handles_missing_headers():
    assert extract_preamble("# demo\n\nJust a description.\n") == "Just a description."
    assert extract_preamble("") == ""


def test_extract_preamble_handles_multiline_paragraph():
    text = "# demo\n\nLine one.\nLine two.\n\n## Next\n"
    assert extract_preamble(text) == "Line one.\nLine two."


# --------------------- end-to-end via the HTTP server ---------------

def _find_free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_server_get_slash_returns_html(tmp_path):
    from ail.agentic.server import serve_project
    proj = Project.init(tmp_path / "demo")
    proj.intent_path.write_text(
        "# demo\n\nEchoes input.\n\n## Tests\n- \"hi\" → succeed\n",
        encoding="utf-8",
    )
    proj.write_app_source(SIMPLE_AIL)
    port = _find_free_port()

    thread = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    thread.start()
    # Wait for the server to be listening.
    import time, urllib.error
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz",
                                   timeout=0.2).read()
            break
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.05)

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/", timeout=2
        ) as r:
            assert r.status == 200
            ctype = r.headers.get("Content-Type", "")
            assert "text/html" in ctype
            body = r.read().decode("utf-8")
        assert "demo" in body
        assert "Echoes input" in body
        assert "<textarea" in body
    finally:
        # Trigger server shutdown — easiest is just to let the daemon
        # thread die when the test ends, but the stdlib server has no
        # clean cross-thread stop. Since it's a daemon thread, process
        # exit will reap it.
        pass
