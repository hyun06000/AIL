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
    # Chat-mode project. Fresh remains True throughout authoring; only
    # an explicit mark_authored transitions to service UI (v1.12.3).
    assert project_is_fresh(proj) is True

    out2 = chat.turn("에러로")
    assert out2["action"] == "ready_to_run"
    # Still fresh — ready_to_run means "runnable in chat", not "deployed".
    assert project_is_fresh(proj) is True
    # app.ail now has real content.
    assert "entry main" in proj.app_path.read_text(encoding="utf-8")


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


def test_authoring_run_endpoint_runs_and_returns_json(tmp_path):
    """v1.12.3 — clicking Run no longer kills the chat. POST
    /authoring-run executes app.ail, returns a JSON outcome, and
    records it to history so the agent sees it on the next turn."""
    import json as _json

    proj = Project.init(tmp_path / "runchat")
    proj.write_app_source(
        'entry main(input: Text) { return "hello from app" }')

    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-run",
        data=b"", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = _json.loads(r.read().decode("utf-8"))
    assert body["ok"] is True
    assert "hello from app" in body["value"]

    # Run result recorded in chat history so the agent has context.
    hist_path = proj.state_dir / "chat_history.jsonl"
    assert hist_path.is_file()
    entries = [_json.loads(line) for line in
               hist_path.read_text(encoding="utf-8").strip().splitlines()
               if line]
    assert any(e.get("kind") == "run_result" and e.get("ok") for e in entries)


def test_back_to_chat_endpoint_removes_authored_marker(tmp_path):
    """v1.12.3 — reversible transition. Once authored, the user can
    return to the chat to iterate. Conversation history is preserved."""
    proj = Project.init(tmp_path / "back")
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    # Seed chat history so post-rollback the project counts as chat-mode.
    (proj.state_dir / "chat_history.jsonl").write_text(
        '{"ts": 1, "user": "hi", "reply": "ok", "files": [], "action": null}\n',
        encoding="utf-8",
    )
    mark_authored(proj)
    assert (proj.state_dir / "authored_at").is_file()

    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/back-to-chat",
        data=b"", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 200

    assert not (proj.state_dir / "authored_at").is_file()
    # GET / now serves the chat UI again.
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
        body = r.read().decode("utf-8")
    assert "ail authoring" in body


def test_service_ui_shows_back_link_when_chat_history_exists(tmp_path):
    """The back-to-chat button only appears on the service UI when
    there's actually a chat to return to."""
    proj = Project.init(tmp_path / "backlink")
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    # Seed chat history so the affordance activates.
    (proj.state_dir / "chat_history.jsonl").write_text(
        '{"ts": 1, "user": "x", "reply": "y", "files": [], "action": null}\n',
        encoding="utf-8",
    )
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
    # The visible button (not just JS referencing the id) is rendered.
    assert 'class="back-link"' in body
    # Default-language (no Korean preamble in INTENT.md) → English label.
    assert "Back to chat" in body


def test_service_ui_no_back_link_without_chat_history(tmp_path):
    """Legacy examples with no chat history shouldn't show a stray
    'back to chat' link that goes nowhere."""
    proj = Project.init(tmp_path / "nobacklink")
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    # No chat_history.jsonl.
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
    # No visible button (even though the JS handler string exists
    # unconditionally, the `class="back-link"` element is conditional).
    assert 'class="back-link"' not in body


def test_history_format_includes_run_results_for_agent_context(tmp_path):
    """The agent's context on the next turn must show the run outcome
    so it knows to fix an error or move on from a success."""
    proj = Project.init(tmp_path / "hist")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    chat._append_run_result("", {
        "ok": False,
        "value": "",
        "error": "ParseError: unexpected token",
        "diagnostic": "",
    })
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=chat._load_history(),
        user_message="fix it",
    )
    assert "Run result — ERROR" in prompt
    assert "ParseError" in prompt


def test_chat_ui_renders_inline_run_widget_not_one_shot_button(tmp_path):
    """v1.12.4 — the chat never leaves. `ready_to_run` renders an
    inline card with input textarea + Run button the user can press
    repeatedly, not a one-shot button that disappears after one run."""
    from ail.agentic.authoring_ui import render_authoring_page
    html = render_authoring_page(
        project_name="x", host="127.0.0.1", port=8080,
        history=[{
            "user": "make X",
            "reply": "ok",
            "files": [],
            "action": "ready_to_run",
        }],
    )
    # The `addRunWidget` function exists and is wired to both actions.
    # Signature now takes (service, inputUsed) — check both call sites.
    assert "addRunWidget(false, inputUsedForNext)" in html
    assert "addRunWidget(true, inputUsedForNext)" in html
    # No more one-way-trip redirect to /authoring-complete from a
    # button click — that endpoint is gone from the UI JS.
    assert "authoring-complete" not in html


def test_parse_error_in_app_ail_surfaces_in_agent_state(tmp_path):
    """v1.12.5 — when the LLM writes bad AIL, the next agent turn
    must see the parse error in its state view. Without this, the
    agent happily re-emits ready_to_run on broken code."""
    proj = Project.init(tmp_path / "badcode")
    # Deliberate parse error — exactly the field-test failure mode
    # (free-prose in `goal:` containing the `with` keyword, which
    # the parser treats as the `with context NAME:` production).
    bad = (
        'intent find(q: Text) -> Text {\n'
        '    goal: list developer communities with their links\n'
        '}\n'
        'entry main(input: Text) { return find(input) }\n'
    )
    proj.write_app_source(bad)
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    state = chat._read_project_state()
    assert "[PARSE ERROR" in state["app.ail"]
    # The prompt surfacing the state must carry the marker too, so
    # the model sees it in its context.
    prompt = chat._build_goal_prompt(state, [], "hi")
    assert "[PARSE ERROR" in prompt


def test_run_endpoint_input_used_reflects_entry(tmp_path):
    """v1.12.5 — /authoring-run response includes input_used so the
    UI knows whether to show the input textarea for subsequent runs."""
    import json as _json

    proj = Project.init(tmp_path / "nouse")
    # Entry declares input but never references it.
    proj.write_app_source(
        'entry main(input: Text) { return "hello" }')
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-run",
        data=b"", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = _json.loads(r.read().decode("utf-8"))
    assert body["ok"] is True
    assert body["input_used"] is False


def test_authoring_chat_turn_includes_input_used(tmp_path):
    """/authoring-chat response exposes input_used so the ready_to_run
    widget the agent surfaces can render with or without the input
    textarea. Before v1.12.5 the field was absent."""
    proj = Project.init(tmp_path / "echo")
    # Entry references input.
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    adapter = _ScriptedChatAdapter([
        "<reply>ok</reply><action>ready_to_run</action>",
    ])
    chat = AuthoringChat(proj, adapter)
    out = chat.turn("run it")
    assert out["input_used"] is True


def test_run_endpoint_parse_error_has_no_traceback(tmp_path):
    """v1.12.5 — AIL parse/lex/purity errors render cleanly in the
    UI. No Python traceback in the `diagnostic` field for these
    user-facing error classes."""
    import json as _json

    proj = Project.init(tmp_path / "broken")
    proj.write_app_source("this is not ail code at all !!!")
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-run",
        data=b"", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = _json.loads(r.read().decode("utf-8"))
    assert body["ok"] is False
    # Clean error — no traceback leakage.
    assert body["diagnostic"] == ""
    assert "Traceback" not in body.get("error", "")


def test_chat_ui_service_card_links_to_service_route(tmp_path):
    """ready_to_serve renders the service card with a share link to
    /service (classic UI on its own route, opened in a new tab)."""
    from ail.agentic.authoring_ui import render_authoring_page
    html = render_authoring_page(
        project_name="x", host="127.0.0.1", port=8080, history=[])
    # The share link is generated client-side; check the URL literal
    # appears in the render widget code.
    assert "'/service'" in html
    # Service card has distinguishing copy so it's clearly "service
    # mode" vs plain run.
    assert "서비스 모드" in html


def test_parse_recognizes_ready_to_serve_action(tmp_path):
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    _, _, action = chat._parse_response(
        "<reply>ok</reply><action>ready_to_serve</action>")
    assert action == "ready_to_serve"


def test_service_route_serves_classic_ui_independently(tmp_path):
    """v1.12.4 — /service is the shareable classic UI URL. Works
    regardless of chat state; doesn't touch authored_at marker."""
    proj = Project.init(tmp_path / "svcroute")
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    # Active chat (no marker). / serves chat, /service serves classic.
    (proj.state_dir / "chat_history.jsonl").write_text(
        '{"ts": 1, "user": "x", "reply": "y", "files": [], "action": null}\n',
        encoding="utf-8",
    )
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    # / → chat
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
        chat_body = r.read().decode("utf-8")
    assert "ail authoring" in chat_body

    # /service → classic UI
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/service", timeout=2
    ) as r:
        svc_body = r.read().decode("utf-8")
    assert "ail authoring" not in svc_body  # not chat
    assert "<textarea" in svc_body or "view.html" in svc_body.lower()

    # authored_at marker not created as a side effect.
    assert not (proj.state_dir / "authored_at").is_file()


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
