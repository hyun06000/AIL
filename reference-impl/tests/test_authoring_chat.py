"""Tests for the authoring chat — the conversational project-creation
flow that replaces the old 'edit INTENT.md manually then run ail ask'
pattern.

Three layers:
1. Unit tests on the XML protocol parser.
2. Unit tests on file-writing safety (path traversal, extensions, size).
3. Executor-level end-to-end: scripted adapter walks through a 2-turn
   conversation and verifies INTENT.md + app.ail get written with the
   right content and the fresh/authored transition fires at the right
   point.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request

import pytest

from ail.agentic.authoring_chat import (
    AuthoringChat, mark_authored, project_is_fresh,
)
from ail.agentic.project import Project
from ail.agentic.server import serve_project
from ail.runtime.model import ModelResponse


# ---------- scripted adapter ----------


class _ScriptedChatAdapter:
    name = "scripted-chat"

    def __init__(self, responses):
        self._queue = list(responses)
        self.invocations = 0

    def invoke(self, **kw):
        self.invocations += 1
        if not self._queue:
            raise AssertionError("scripted queue exhausted")
        return ModelResponse(
            value=self._queue.pop(0),
            confidence=0.9,
            model_id="scripted",
            raw={},
        )


# ---------- XML parsing ----------


def test_parse_reply_only(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    reply, files, action = chat._parse_response(
        "<reply>Hello there</reply>")
    assert reply == "Hello there"
    assert files == []
    assert action is None


def test_parse_file_with_path(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    raw = (
        "<reply>wrote it</reply>\n"
        "<file path=\"INTENT.md\">\n"
        "# demo\n"
        "description\n"
        "</file>"
    )
    reply, files, action = chat._parse_response(raw)
    assert reply == "wrote it"
    assert len(files) == 1
    assert files[0][0] == "INTENT.md"
    assert files[0][1] == "# demo\ndescription"


def test_parse_multiple_files_and_action(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    raw = (
        "<reply>done</reply>\n"
        "<file path=\"INTENT.md\">\ncontent A\n</file>\n"
        "<file path=\"app.ail\">\nentry main(x: Text) { return x }\n</file>\n"
        "<action>ready_to_run</action>"
    )
    reply, files, action = chat._parse_response(raw)
    assert len(files) == 2
    paths = [f[0] for f in files]
    assert paths == ["INTENT.md", "app.ail"]
    assert action == "ready_to_run"


def test_parse_strips_outer_code_fence(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    raw = "```\n<reply>hi</reply>\n```"
    reply, _, _ = chat._parse_response(raw)
    assert reply == "hi"


def test_parse_rejects_unknown_action(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    raw = "<reply>x</reply><action>launch_missiles</action>"
    _, _, action = chat._parse_response(raw)
    assert action is None


# ---------- file-writing safety ----------


def test_write_file_accepts_ail_and_md(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    ok, _ = chat._write_file("INTENT.md", "# hi")
    assert ok
    ok, _ = chat._write_file("app.ail", "entry main(x: Text) { return x }")
    assert ok
    ok, _ = chat._write_file("view.html", "<html></html>")
    assert ok


def test_write_file_rejects_path_traversal(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    ok, detail = chat._write_file("../outside.md", "attack")
    assert not ok
    assert "path" in detail.lower()


def test_write_file_rejects_absolute(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    ok, _ = chat._write_file("/etc/passwd", "nope")
    assert not ok


def test_write_file_rejects_disallowed_extension(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    ok, detail = chat._write_file("malware.sh", "rm -rf /")
    assert not ok
    assert "extension" in detail


def test_write_file_rejects_oversize(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, adapter=_ScriptedChatAdapter([]))
    big = "x" * (70 * 1024)
    ok, detail = chat._write_file("INTENT.md", big)
    assert not ok
    assert "too large" in detail


# ---------- project_is_fresh ----------


def test_fresh_on_new_project(tmp_path):
    proj = Project.init(tmp_path / "p")
    assert project_is_fresh(proj) is True


def test_not_fresh_after_mark(tmp_path):
    proj = Project.init(tmp_path / "p")
    mark_authored(proj)
    assert project_is_fresh(proj) is False


def test_not_fresh_when_entry_present(tmp_path):
    proj = Project.init(tmp_path / "p")
    proj.write_app_source(
        "entry main(input: Text) { return input }")
    assert project_is_fresh(proj) is False


def test_fresh_when_app_only_has_comments(tmp_path):
    proj = Project.init(tmp_path / "p")
    proj.write_app_source("// just a comment, no entry yet")
    assert project_is_fresh(proj) is True


# ---------- executor: end-to-end turn ----------


def test_turn_writes_files_from_reply(tmp_path):
    proj = Project.init(tmp_path / "demo")
    responses = [
        "<reply>좋아요. 빈 입력은 에러로 할까요 아니면 0으로 할까요?</reply>\n"
        "<file path=\"INTENT.md\">\n"
        "# demo\n단어 세기 서비스.\n\n## Deployment\n- 포트 8080\n"
        "</file>",
    ]
    adapter = _ScriptedChatAdapter(responses)
    chat = AuthoringChat(proj, adapter)

    out = chat.turn("단어 수 세는 서비스 만들어줘")
    assert "빈 입력" in out["reply"]
    assert any(f["path"] == "INTENT.md" for f in out["files"])
    assert out["action"] is None
    assert project_is_fresh(proj) is True  # no app.ail yet
    assert "단어 세기" in proj.intent_path.read_text(encoding="utf-8")


def test_two_turn_conversation_reaches_ready_to_run(tmp_path):
    proj = Project.init(tmp_path / "demo")
    r1 = (
        "<reply>빈 입력 처리는?</reply>\n"
        "<file path=\"INTENT.md\">\n# demo\n단어 세기\n</file>"
    )
    r2 = (
        "<reply>에러로 설정했어요.</reply>\n"
        "<file path=\"app.ail\">\n"
        "entry main(input: Text) { return to_text(length(input)) }\n"
        "</file>\n<action>ready_to_run</action>"
    )
    chat = AuthoringChat(proj, _ScriptedChatAdapter([r1, r2]))

    chat.turn("단어 세는 서비스")
    assert project_is_fresh(proj) is True  # still no entry

    out2 = chat.turn("에러로")
    assert out2["action"] == "ready_to_run"
    assert project_is_fresh(proj) is False  # entry present


def test_chat_ui_enter_sends_shift_enter_newlines(tmp_path):
    """v1.12.2 — standard chat UX. Enter sends, Shift+Enter adds a
    newline. Hangul/Japanese IME composition must not submit on Enter
    (guarded by isComposing + keyCode 229)."""
    from ail.agentic.authoring_ui import render_authoring_page
    html = render_authoring_page(
        project_name="x", host="127.0.0.1", port=8080, history=[])
    # Handler fires on Enter without Shift
    assert "e.key === 'Enter' && !e.shiftKey" in html
    # IME safety
    assert "!e.isComposing" in html
    assert "keyCode !== 229" in html
    # Submits the composer form
    assert "requestSubmit()" in html
    # Placeholder mentions the convention
    assert "Shift+Enter" in html


def test_prompt_includes_heaal_identity_and_research_guidance(tmp_path):
    """v1.12.1 regression — agent claimed ignorance of HEAAL and
    refused to web-search, even though AIL has perform http.get. The
    system prompt must teach both: (a) AIL/HEAAL identity directly,
    (b) how to offer http.get + intent when asked about unknowns."""
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=[],
        user_message="what is HEAAL?",
    )
    # Identity block exists.
    assert "AI-Intent Language" in prompt
    assert "ail-interpreter" in prompt
    assert "HEAAL" in prompt
    # Safety properties the agent should know.
    assert "No `while` keyword" in prompt
    assert "`Result` type required" in prompt
    assert "`pure fn` statically verified" in prompt
    # Research guidance (the v1.12.1 fix).
    assert "perform http.get" in prompt
    assert "propose" in prompt.lower() or "suggest" in prompt.lower()


def test_history_persists_across_instances(tmp_path):
    proj = Project.init(tmp_path / "demo")
    c1 = AuthoringChat(
        proj,
        _ScriptedChatAdapter(["<reply>first</reply>"]),
    )
    c1.turn("hello")

    # New instance on same project — history should load.
    c2 = AuthoringChat(proj, _ScriptedChatAdapter([]))
    history = c2._load_history()
    assert len(history) == 1
    assert history[0]["user"] == "hello"
    assert history[0]["reply"] == "first"


# ---------- server integration ----------


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_listening(port: int) -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.2
            ).read()
            return
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.05)


def test_fresh_project_serves_chat_ui_on_get(tmp_path):
    proj = Project.init(tmp_path / "fresh")
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
        assert r.status == 200
        body = r.read().decode("utf-8")
    # Chat page signatures — not the textarea default.
    assert "ail authoring" in body
    assert "authoring-chat" in body
    assert "<textarea id=\"input\"" not in body  # not the service UI


def test_authored_project_serves_service_ui_on_get(tmp_path):
    proj = Project.init(tmp_path / "done")
    proj.write_app_source(
        "entry main(input: Text) { return input }")
    mark_authored(proj)
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
        body = r.read().decode("utf-8")
    # Service UI (textarea page), not chat.
    assert "authoring-chat" not in body
    assert "<textarea" in body


def test_authoring_complete_endpoint_transitions_state(tmp_path):
    proj = Project.init(tmp_path / "transit")
    proj.write_app_source(
        "entry main(input: Text) { return input }")
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    # With app.ail already containing an entry, project_is_fresh is
    # already False — but the marker hasn't been set. Hit the endpoint
    # anyway; it must be idempotent.
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-complete",
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 200

    # Marker now exists.
    marker = proj.state_dir / "authored_at"
    assert marker.is_file()
