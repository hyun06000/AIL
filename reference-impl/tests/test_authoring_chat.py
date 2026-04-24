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


def test_prompt_never_tells_user_to_use_terminal_for_secrets(tmp_path):
    """v1.13.1 — user complaint: agent was telling them to `export`
    env vars in terminal. Non-programmers don't know terminals or
    env vars. The chat UI has a masked input — agent must route
    users there, never to a shell."""
    proj = Project.init(tmp_path / "noterm")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=[],
        user_message="post to Discord",
    )
    # Explicit anti-terminal phrasing.
    assert "Never say" in prompt
    assert "export DISCORD_WEBHOOK_URL" in prompt or "export " in prompt
    # Explicit user-vocabulary guidance.
    assert "설정 필요" in prompt
    # Don't-mention-env-variable framing.
    assert "환경변수" in prompt  # as anti-pattern to avoid
    assert "shell profile" in prompt or "shell" in prompt.lower()


def test_prompt_teaches_agent_to_take_actions_not_refuse(tmp_path):
    """v1.12.7 — field test: user asked 'post to communities', agent
    replied 'I can't post on your behalf'. Wrong — AIL has http.post
    with headers, the agent CAN post to Discord/Mastodon/GitHub/etc.
    The prompt must override the default chatbot-refusal instinct
    and teach the canonical side-effect primitives."""
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=[],
        user_message="Discord 서버에 홍보글 올려줘",
    )
    # The override framing must be present.
    assert "Override the default" in prompt
    assert "refusal reflex" in prompt
    # Side-effect primitives explicitly catalogued.
    assert "perform http.post" in prompt
    assert "perform schedule.every" in prompt
    assert "perform env.read" in prompt
    # Concrete post examples so the agent has templates, not memory.
    assert "DISCORD_WEBHOOK_URL" in prompt
    assert "MASTODON_TOKEN" in prompt
    assert "GITHUB_TOKEN" in prompt
    # Explicit anti-refusal list.
    assert "I can't post on your behalf" in prompt
    assert "I'm just an AI" in prompt
    # Honesty about services without APIs (HN, GeekNews, X).
    assert "Hacker News" in prompt
    assert "no posting API" in prompt or "no API" in prompt


def test_prompt_prefers_live_data_over_training_knowledge(tmp_path):
    """v1.12.6 — field-test correction. Previous v1.12.6 draft told
    the agent to use `intent` directly for 'knowledge' questions,
    falling back on the model's frozen training weights for lists /
    recommendations. Wrong direction: model weights are stale. We
    want the model's reasoning + tool-use; the facts should come from
    live HTTP sources on every run."""
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=[],
        user_message="요즘 가장 핫한 harness engineering 프로젝트 찾아줘",
    )
    # Rule framing: training is stale, fetch live data.
    assert "training" in prompt.lower() and "stale" in prompt.lower()
    assert "reasoning + tool-use" in prompt
    # Anti-pattern: Google scraping blocked.
    assert "do NOT scrape Google" in prompt
    # Concrete API endpoints the agent can actually use.
    assert "api.github.com/search/repositories" in prompt
    assert "hn.algolia.com" in prompt
    assert "reddit.com" in prompt.lower()
    # Worked example is present so the agent sees the pattern.
    assert "top_repos" in prompt or "sort=stars" in prompt


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
    # Research guidance: the agent is pushed toward live http.get,
    # not toward pulling answers from its frozen training weights.
    assert "perform http.get" in prompt


def test_agent_sees_all_turns_by_default(tmp_path):
    """UI ≤ agent memory. The prior 12-turn hard cap violated this;
    agent forgot turn 3 of a 20-turn chat while the UI showed all 20."""
    from ail.agentic.authoring_chat import AuthoringChat
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    for i in range(20):
        chat._append_history(f"user says {i}", f"agent reply {i}", [], None)
    history = chat._load_history()
    assert len(history) == 20, "load_history must not silently cap"
    formatted = chat._format_history(history)
    for i in range(20):
        assert f"user says {i}" in formatted, f"turn {i} missing from prompt"


def test_file_content_is_retained_in_history(tmp_path):
    """Previously only {path, bytes} was stored — agent saw a filename
    it could no longer read. Now content is inlined in the fence."""
    from ail.agentic.authoring_chat import AuthoringChat
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(
        proj,
        _ScriptedChatAdapter([
            '<reply>ok</reply>\n'
            '<file path="greeter.ail">\nentry main() { return "hi" }\n</file>'
        ]),
    )
    chat.turn("make a greeter")
    history = chat._load_history()
    file_entry = history[0]["files"][0]
    assert "content" in file_entry
    assert 'return "hi"' in file_entry["content"]
    formatted = chat._format_history(history)
    assert "<<<FILE greeter.ail" in formatted
    assert 'return "hi"' in formatted


def test_history_budget_elides_with_visible_boundary(tmp_path):
    """When char budget is exceeded, oldest turns drop out — but with
    a loud boundary marker, not silently."""
    from ail.agentic.authoring_chat import AuthoringChat
    from ail.agentic import authoring_chat as ac_mod
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    # Each entry ~1.2KB; with a tight budget we must elide.
    filler = "x" * 1000
    for i in range(20):
        chat._append_history(f"turn {i} message", f"turn {i} {filler}", [], None)
    history = chat._load_history()
    # Force elision by shrinking budget for this test.
    original = ac_mod._HISTORY_CHAR_BUDGET
    try:
        ac_mod._HISTORY_CHAR_BUDGET = 5000
        formatted = chat._format_history(history)
    finally:
        ac_mod._HISTORY_CHAR_BUDGET = original
    assert "압축됨" in formatted, "budget overflow must leave explicit boundary"
    assert "chat_history.jsonl" in formatted, "boundary must point at storage"
    # Most recent must survive.
    assert "turn 19" in formatted


def test_run_result_is_not_double_truncated(tmp_path):
    """Storage truncates at 4KB; format step no longer re-truncates
    to 500 chars (that clobbered error diagnostics the agent needed)."""
    from ail.agentic.authoring_chat import AuthoringChat
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    long_value = "A" * 3000
    chat._append_run_result("input", {"ok": True, "value": long_value})
    history = chat._load_history()
    formatted = chat._format_history(history)
    # Count A's — if double-truncation returned, we'd see ~500.
    assert formatted.count("A") >= 3000


def test_prompt_no_longer_claims_full_log_unconditionally(tmp_path):
    """Old prompt said 'On every turn you get the full log' — a lie
    under the 12-turn cap. New prompt is truthful and explains the
    boundary marker."""
    from ail.agentic.authoring_chat import AuthoringChat
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt({}, [], "hi")
    assert "boundary marker" in prompt or "압축됨" in prompt
    assert "<<<FILE" in prompt, "prompt must teach the file-fence convention"


def test_extract_purpose(tmp_path):
    from ail.agentic.authoring_chat import extract_purpose
    assert extract_purpose(
        "# PURPOSE: fetches weather and formats a message\nentry main() { return 42 }"
    ) == "fetches weather and formats a message"
    assert extract_purpose(
        "// PURPOSE: 날씨 메시지 포맷터\nentry main() { return 42 }"
    ) == "날씨 메시지 포맷터"
    assert extract_purpose("entry main() { return 42 }") is None
    assert extract_purpose("# PURPOSE:   \n") is None


def test_program_inventory_surfaces_purpose_to_agent(tmp_path):
    """Agent sees a scan-friendly inventory block in PROJECT STATE,
    not just filenames — so it knows what sits on disk without
    parsing every file's body."""
    from ail.agentic.authoring_chat import AuthoringChat
    proj = Project.init(tmp_path / "p")
    (proj.root / "weather.ail").write_text(
        "# PURPOSE: 매일 아침 날씨 요약\nentry main() { return 1 }",
        encoding="utf-8",
    )
    (proj.root / "joke.ail").write_text(
        "# PURPOSE: 하루의 농담 한 줄 뽑기\nentry main() { return 2 }",
        encoding="utf-8",
    )
    (proj.root / "plain.ail").write_text(
        "entry main() { return 3 }", encoding="utf-8",
    )
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    state = chat._read_project_state()
    assert "__PROGRAM_INVENTORY__" in state
    inventory = state["__PROGRAM_INVENTORY__"]
    assert "weather.ail: 매일 아침 날씨 요약" in inventory
    assert "joke.ail: 하루의 농담 한 줄 뽑기" in inventory
    # The file without a PURPOSE comment should still appear, flagged.
    assert "plain.ail" in inventory
    assert "(no # PURPOSE:" in inventory
    # Formatted state must render inventory above the per-file sources.
    formatted = chat._format_state(state)
    assert "PROGRAMS ON DISK (inventory)" in formatted
    assert formatted.index("PROGRAMS ON DISK") < formatted.index("--- weather.ail ---")


def test_list_project_programs_includes_purpose(tmp_path):
    from ail.agentic.authoring_chat import list_project_programs
    proj = Project.init(tmp_path / "p")
    (proj.root / "a.ail").write_text(
        "# PURPOSE: does thing A\nentry main() { return 1 }", encoding="utf-8",
    )
    programs = list_project_programs(proj)
    assert any(p["name"] == "a.ail" and p["purpose"] == "does thing A"
               for p in programs)


def test_prompt_teaches_purpose_convention(tmp_path):
    from ail.agentic.authoring_chat import AuthoringChat
    proj = Project.init(tmp_path / "p")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt({}, [], "hi")
    assert "# PURPOSE:" in prompt
    assert "PROGRAMS ON DISK (inventory)" in prompt or "filename — purpose" in prompt


def test_turn_returns_and_persists_token_usage(tmp_path):
    """Each turn must surface input/output tokens for the UI widget
    and accumulate them in .ail/token_usage.jsonl so reopening the
    tab doesn't reset the running total."""
    from ail.agentic.authoring_chat import AuthoringChat, read_session_total_tokens
    from ail.runtime.model import ModelResponse
    proj = Project.init(tmp_path / "p")

    class _UsageAdapter:
        name = "usage"
        def __init__(self): self.n = 0
        def invoke(self, **kw):
            self.n += 1
            return ModelResponse(
                value="<reply>ok</reply>",
                confidence=0.9,
                model_id="test",
                raw={"input_tokens": 100 * self.n,
                     "output_tokens": 10 * self.n},
            )

    chat = AuthoringChat(proj, _UsageAdapter())
    r1 = chat.turn("first")
    assert r1["input_tokens"] == 100
    assert r1["output_tokens"] == 10
    assert r1["session_total_tokens"] == 110

    r2 = chat.turn("second")
    assert r2["input_tokens"] == 200
    assert r2["output_tokens"] == 20
    assert r2["session_total_tokens"] == 110 + 220  # cumulative

    # Storage should let a fresh AuthoringChat instance read the total.
    assert read_session_total_tokens(proj) == 330


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


def test_authoring_prompt_carries_critical_errors_block_at_top(tmp_path):
    """The two parse errors that recur in field tests (pure fn with
    perform; hardcode after empty filter) must be in the prompt's
    critical-errors block near the top, not buried mid-document."""
    from ail.agentic.authoring_chat import AuthoringChat
    proj = Project.init(tmp_path / "p")
    prompt = AuthoringChat(proj, _ScriptedChatAdapter([]))._build_goal_prompt({}, [], "hi")
    assert "TWO CRITICAL PARSE ERRORS" in prompt
    assert "CRITICAL-1" in prompt and "CRITICAL-2" in prompt
    # The critical block should appear before the "THE PROJECT'S
    # SUBJECT" preamble the agent reads for domain framing.
    assert prompt.index("TWO CRITICAL PARSE ERRORS") < prompt.index("THE PROJECT'S SUBJECT IS")


def test_ui_has_auto_fix_handler_on_failed_run(tmp_path):
    """PRINCIPLES.md §4 extension: a failed run auto-triggers a fix
    turn. Checking the JS literal here rather than via a browser is
    a weak but cheap regression: the important thing is that the
    handler exists and is wired to ok===false."""
    from ail.agentic.authoring_ui import render_authoring_page
    html = render_authoring_page(
        project_name="x", host="127.0.0.1", port=8080, history=[])
    assert "autoFixOnError" in html
    assert "ok === false" in html
    assert "AUTO_FIX_MAX" in html


def test_authoring_tree_endpoint_lists_project_files_with_captions(tmp_path):
    """The NERDTree-style side panel reads from /authoring-tree. Each
    entry must carry a one-line caption (PURPOSE for .ail, canned
    descriptors for view.html / INTENT.md / README.md)."""
    import json as _json
    proj = Project.init(tmp_path / "tree")
    (proj.root / "diary.ail").write_text(
        "# PURPOSE: 날짜별 일기 기록\nentry main() { return 1 }",
        encoding="utf-8",
    )
    (proj.root / "view.html").write_text(
        "<!doctype html><body>x</body>", encoding="utf-8",
    )
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/authoring-tree", timeout=2) as r:
        d = _json.loads(r.read().decode("utf-8"))
    entries = {e["path"]: e for e in d["entries"]}
    assert "diary.ail" in entries
    assert entries["diary.ail"]["caption"] == "날짜별 일기 기록"
    assert entries["diary.ail"]["kind"] == "ail"
    assert "view.html" in entries
    assert entries["view.html"]["kind"] == "html"


def test_looks_like_error_catches_self_reported_x_mark(tmp_path):
    """hyun06000 field test 2026-04-24: a program caught an inner
    parse_json failure, logged '❌ 가이드 분석 실패' and continued
    happily. _looks_like_error missed it → ok=true → auto-fix never
    fired. New signal: any line starting with ❌ in the return string
    counts as self-reported error."""
    from ail.agentic.agent import _looks_like_error
    assert _looks_like_error(
        "=== step log ===\n✓ A\n❌ B failed\n✓ C\n")
    assert _looks_like_error("❌ only line")
    # Plain success should NOT trip.
    assert not _looks_like_error("✓ A\n✓ B\n✓ C\n")
    # ❌ in the middle of a line (not at line start) is prose, not a
    # status marker. Don't flag.
    assert not _looks_like_error("failure rate is < 1% ❌ but manageable")


def test_effects_emit_auto_log_markers_during_run(tmp_path):
    """hyun06000 2026-04-24: "로그가 스트리밍 안 돼서 답답함." The
    fix is runtime-level auto-emission of '→ perform X' markers for
    every effect call, so progress shows up even without explicit
    `perform log(...)` in the program."""
    from ail import compile_source, MockAdapter
    from ail.runtime import Executor

    collected = []
    src = """
    entry main(input: Text) {
        x = perform clock.now()
        return "ok"
    }
    """
    program = compile_source(src)
    ex = Executor(program, MockAdapter(),
                  log_callback=lambda s: collected.append(s))
    ex.run_entry({"input": ""})
    assert any("→ perform clock.now" in s for s in collected)


def test_admin_stop_endpoint_only_in_serve_mode(tmp_path):
    """The /admin/stop endpoint is exposed only when serve_only=True.
    In edit mode it must return 404 so accidentally POSTing to it from
    the chat UI can't kill the authoring server."""
    proj = Project.init(tmp_path / "p")
    proj.write_app_source("entry main(input: Text) { return input }")
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/admin/stop",
        data=b"", method="POST")
    try:
        urllib.request.urlopen(req, timeout=2)
        assert False, "expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_deploy_status_endpoint_returns_404_when_no_deployment(tmp_path):
    """GET /authoring-deploy/status returns 404 if no deployment.json
    exists yet. The UI relies on this to flip to the 'not deployed'
    state on page load."""
    proj = Project.init(tmp_path / "p")
    proj.write_app_source("entry main(input: Text) { return input }")
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{port}/authoring-deploy/status", timeout=2)
        assert False, "expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_serve_only_mode_redirects_root_and_disables_chat(tmp_path):
    """`ail serve` — PRINCIPLES.md §5 Program Independence at the
    process level. The edit URL redirects to the runtime URL, and the
    chat POST endpoint is 404. This proves the chat can be closed
    without taking the program down."""
    proj = Project.init(tmp_path / "indep")
    proj.write_app_source("entry main(input: Text) { return input }")
    (proj.root / "view.html").write_text(
        "<!doctype html><body>RUNTIME_ONLY</body>", encoding="utf-8",
    )
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False,
                "serve_only": True},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    # GET / → 302 to /run (don't auto-follow so we can assert the
    # redirect target).
    req = urllib.request.Request(f"http://127.0.0.1:{port}/")
    class _NoRedirect(urllib.request.HTTPErrorProcessor):
        def http_response(self, request, response):
            return response
        https_response = http_response
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(req, timeout=2) as r:
        assert r.status == 302
        assert r.headers.get("Location") == "/run"

    # GET /run serves the runtime view.
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/run", timeout=2) as r:
        assert "RUNTIME_ONLY" in r.read().decode("utf-8")

    # POST /authoring-chat → 404 (chat is off).
    req_post = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-chat",
        data=b"hello", method="POST")
    try:
        urllib.request.urlopen(req_post, timeout=2)
        assert False, "expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_run_route_serves_runtime_ui_independent_of_authored_marker(tmp_path):
    """PRINCIPLES.md §5 Program Independence: /run is the runtime URL
    for a program, separate from the edit URL (/). It must serve the
    runtime view (view.html if present, else the textarea) regardless
    of whether the legacy authored_at marker is set."""
    proj = Project.init(tmp_path / "runroute")
    proj.write_app_source("entry main(input: Text) { return input }")
    (proj.root / "view.html").write_text(
        "<!doctype html><title>app</title><body>HELLO_FROM_VIEW</body>",
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

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/run", timeout=2) as r:
        body = r.read().decode("utf-8")
    assert "HELLO_FROM_VIEW" in body
    assert "authoring-chat" not in body  # no chat shell on /run

    # /service alias — back-compat.
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/service", timeout=2) as r:
        body2 = r.read().decode("utf-8")
    assert "HELLO_FROM_VIEW" in body2


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
    # The `addRunWidget` function exists and is wired to both
    # actions. v1.13.1 simplified the signature — the widget now
    # pulls programs/env/input from module-level state set by the
    # latest /authoring-chat response.
    assert "addRunWidget(false)" in html
    assert "addRunWidget(true)" in html
    assert "programsForNext" in html
    assert "activeProgramForNext" in html
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


# ---------- v1.13.0: chat-safe env var handling ----------


def test_list_required_env_vars_detects_env_read_calls(tmp_path):
    from ail.agentic.authoring_chat import list_required_env_vars
    src = '''
fn get_cred() -> Text {
    r = perform env.read("DISCORD_WEBHOOK_URL")
    return unwrap(r)
}
fn get_token() -> Text {
    t = perform env.read("MASTODON_TOKEN")
    if is_error(t) {
        // fallback to another var
        t = perform env.read("AIL_MASTODON_TOKEN")
    }
    return unwrap(t)
}
entry main(input: Text) { return get_cred() }
'''
    vars = list_required_env_vars(src)
    assert vars == ["DISCORD_WEBHOOK_URL", "MASTODON_TOKEN", "AIL_MASTODON_TOKEN"]


def test_list_required_env_vars_empty_for_no_env_calls(tmp_path):
    from ail.agentic.authoring_chat import list_required_env_vars
    assert list_required_env_vars('entry main(x: Text) { return x }') == []
    assert list_required_env_vars("") == []


def test_authoring_chat_response_includes_env_required(tmp_path):
    proj = Project.init(tmp_path / "env")
    # Seed app.ail that references DISCORD_WEBHOOK_URL.
    proj.write_app_source(
        'entry main(input: Text) {\n'
        '    w = perform env.read("DISCORD_WEBHOOK_URL")\n'
        '    return unwrap(w)\n'
        '}\n'
    )
    adapter = _ScriptedChatAdapter([
        "<reply>ok</reply><action>ready_to_run</action>",
    ])
    chat = AuthoringChat(proj, adapter)
    out = chat.turn("describe")
    assert "env_required" in out
    names = [e["name"] for e in out["env_required"]]
    assert "DISCORD_WEBHOOK_URL" in names


def test_set_env_endpoint_persists_and_sets_process_env(tmp_path, monkeypatch):
    import json as _json
    monkeypatch.delenv("AIL_TEST_WEBHOOK", raising=False)

    proj = Project.init(tmp_path / "set")
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-set-env",
        data=_json.dumps({
            "name": "AIL_TEST_WEBHOOK",
            "value": "https://discord.com/api/webhooks/secret",
        }).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 200

    # Process env updated.
    assert os.environ.get("AIL_TEST_WEBHOOK") == \
        "https://discord.com/api/webhooks/secret"

    # Persisted to gitignored secrets file.
    secrets_path = proj.state_dir / "secrets.json"
    assert secrets_path.is_file()
    data = _json.loads(secrets_path.read_text(encoding="utf-8"))
    assert data["AIL_TEST_WEBHOOK"] == \
        "https://discord.com/api/webhooks/secret"

    # Ledger records the name, not the value.
    ledger = (proj.state_dir / "ledger.jsonl").read_text(encoding="utf-8")
    assert "AIL_TEST_WEBHOOK" in ledger
    assert "https://discord.com/api/webhooks/secret" not in ledger


def test_set_env_rejects_invalid_name(tmp_path):
    import json as _json
    proj = Project.init(tmp_path / "invalid")
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    for bad_name in ["", "has spaces", "has-dash", "../evil"]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/authoring-set-env",
            data=_json.dumps({"name": bad_name, "value": "x"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=2)
            raise AssertionError(f"{bad_name!r} should have been rejected")
        except urllib.error.HTTPError as e:
            assert e.code == 400


def test_load_project_secrets_into_env(tmp_path, monkeypatch):
    import json as _json
    from ail.agentic.authoring_chat import load_project_secrets

    monkeypatch.delenv("AIL_LOADED_SECRET", raising=False)

    proj = Project.init(tmp_path / "loadme")
    # Seed a secrets file.
    (proj.state_dir / "secrets.json").write_text(
        _json.dumps({"AIL_LOADED_SECRET": "hello"}),
        encoding="utf-8",
    )

    load_project_secrets(proj)
    assert os.environ.get("AIL_LOADED_SECRET") == "hello"


def test_project_init_writes_gitignore_for_dot_ail(tmp_path):
    proj = Project.init(tmp_path / "gitigno")
    gi = proj.root / ".gitignore"
    assert gi.is_file()
    content = gi.read_text(encoding="utf-8")
    assert ".ail/" in content


def test_chat_ui_renders_env_secret_input_widget(tmp_path):
    from ail.agentic.authoring_ui import render_authoring_page
    html = render_authoring_page(
        project_name="x", host="127.0.0.1", port=8080, history=[])
    # Masked input + save endpoint present in the widget code.
    assert "authoring-set-env" in html
    assert "env-block" in html
    assert "type = 'password'" in html or "type = \"password\"" in html


# ---------- v1.13.1: multi-program support ----------


def test_list_project_programs_discovers_multiple_ail_files(tmp_path):
    from ail.agentic.authoring_chat import list_project_programs
    proj = Project.init(tmp_path / "multi")
    (proj.root / "app.ail").write_text(
        'entry main(input: Text) { return "app" }', encoding="utf-8")
    (proj.root / "sorter.ail").write_text(
        'entry main(input: Text) { return "sort" }', encoding="utf-8")
    (proj.root / "notes.md").write_text("irrelevant", encoding="utf-8")

    programs = list_project_programs(proj)
    names = [p["name"] for p in programs]
    assert "app.ail" in names
    assert "sorter.ail" in names
    assert len(programs) == 2
    # Each entry carries metadata the UI needs.
    for p in programs:
        assert "input_used" in p
        assert "env_required" in p
        assert "parses" in p
        assert "entry_present" in p


def test_turn_response_includes_programs_and_active(tmp_path):
    proj = Project.init(tmp_path / "multi2")
    (proj.root / "app.ail").write_text(
        'entry main(input: Text) { return input }', encoding="utf-8")
    (proj.root / "sorter.ail").write_text(
        'entry main(x: Text) { return x }', encoding="utf-8")

    adapter = _ScriptedChatAdapter([
        '<reply>ok</reply>\n'
        '<file path="word_counter.ail">\n'
        'entry main(input: Text) { return input }\n'
        '</file>\n'
        '<action>ready_to_run</action>',
    ])
    chat = AuthoringChat(proj, adapter)
    out = chat.turn("add a word counter")

    assert "programs" in out
    names = [p["name"] for p in out["programs"]]
    # All three are present.
    assert "word_counter.ail" in names
    assert "app.ail" in names
    assert "sorter.ail" in names
    # Freshly-written file is the active one.
    assert out["active_program"] == "word_counter.ail"


def test_run_endpoint_selects_program_by_query_param(tmp_path):
    """v1.13.1 — /authoring-run?program=FILENAME picks which .ail
    to execute. Running app.ail and sorter.ail in the same project
    returns different values."""
    import json as _json

    proj = Project.init(tmp_path / "pickme")
    (proj.root / "app.ail").write_text(
        'entry main(input: Text) { return "from app" }', encoding="utf-8")
    (proj.root / "sorter.ail").write_text(
        'entry main(input: Text) { return "from sorter" }',
        encoding="utf-8")

    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    # Explicit app.ail
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-run?program=app.ail",
        data=b"", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = _json.loads(r.read().decode("utf-8"))
    assert "from app" in body["value"]
    assert body["program"] == "app.ail"

    # Explicit sorter.ail
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/authoring-run?program=sorter.ail",
        data=b"", method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = _json.loads(r.read().decode("utf-8"))
    assert "from sorter" in body["value"]
    assert body["program"] == "sorter.ail"


def test_run_endpoint_rejects_path_traversal_in_program(tmp_path):
    """Security: the program query param must not escape the project
    root even if the server is only on localhost."""
    proj = Project.init(tmp_path / "safe")
    (proj.root / "app.ail").write_text(
        'entry main(input: Text) { return input }', encoding="utf-8")
    # Try to reach a file outside.
    (tmp_path / "evil.ail").write_text(
        'entry main(input: Text) { return "pwned" }', encoding="utf-8")

    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    for bad in ["../evil.ail", "../../evil.ail", "/etc/passwd", "foo.txt"]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/authoring-run?program="
            + urllib.request.quote(bad),
            data=b"", method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=2)
            raise AssertionError(f"{bad!r} should have been rejected")
        except urllib.error.HTTPError as e:
            assert e.code == 400


def test_active_program_marker_updated_on_write(tmp_path):
    proj = Project.init(tmp_path / "active")
    adapter = _ScriptedChatAdapter([
        '<reply>first</reply>\n'
        '<file path="first.ail">\n'
        'entry main(x: Text) { return "1" }\n'
        '</file>',
        '<reply>second</reply>\n'
        '<file path="second.ail">\n'
        'entry main(x: Text) { return "2" }\n'
        '</file>',
    ])
    chat = AuthoringChat(proj, adapter)
    chat.turn("one")
    assert (proj.state_dir / "active_program").read_text(encoding="utf-8") \
        == "first.ail"
    chat.turn("two")
    assert (proj.state_dir / "active_program").read_text(encoding="utf-8") \
        == "second.ail"


def test_prompt_teaches_input_reference_decision(tmp_path):
    """v1.13.4 — user bug: a PR-bot (self-contained, token-driven)
    still showed the user-input textarea next to the Run button
    because the agent wrote `payload = input` unnecessarily. Prompt
    must teach: reference `input` only when the entry legitimately
    consumes runtime user input."""
    proj = Project.init(tmp_path / "inputsense")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=[],
        user_message="PR 자동 생성봇 만들어줘",
    )
    assert "REFERENCE `input` ONLY WHEN" in prompt
    # Self-check rule present.
    assert "self-check" in prompt.lower() or "Self-check" in prompt
    # Broken pattern example (payload = input anti-pattern).
    assert "payload = input" in prompt
    # Correct-vs-broken framing.
    assert "Self-contained programs" in prompt


def test_prompt_demands_finishing_the_job_in_one_turn(tmp_path):
    """v1.13.3 — two consecutive field tests where agent:
    1. Wrote INTENT.md only, never app.ail, never ready_to_run.
    2. Claimed '완성!' and told user to paste secret into an input
       box — but no env.read was in the (non-existent) program so
       no input box appeared. User waited on a phantom UI.

    Prompt must require a runnable `.ail` + ready_to_run, and must
    ban claim-reality mismatches. (v1.14.0 demoted INTENT.md to
    optional — the `.ail` is the only required artifact.)"""
    proj = Project.init(tmp_path / "finisher")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"app.ail": ""},
        history=[],
        user_message="PR 자동 생성 봇 만들어줘",
    )
    # Explicit "finished" requirements.
    assert "FINISH THE JOB IN ONE TURN" in prompt
    # The `.ail` file is mandatory; the action must be ready_to_run.
    assert ".ail`" in prompt  # referenced in finish-rule section
    assert "ready_to_run" in prompt
    # Counter-examples listed.
    assert "I'll build X" in prompt
    # Claim-reality matching rule.
    assert "Don't lie about what you did" in prompt
    assert "phantom UI" in prompt


def test_prompt_rejects_draft_only_as_first_choice(tmp_path):
    """v1.13.3 — user feedback: 'HN은 API 없어서 초안만 써드릴게요,
    복사해서 직접 올려주세요' is the behavior this project exists to
    kill. The agent pushes work BACK onto the non-programmer. Prompt
    must reframe draft-only as a last-resort and teach proposing API
    alternatives first."""
    proj = Project.init(tmp_path / "noexcuse")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "# promo\n\nAIL 홍보", "app.ail": ""},
        history=[],
        user_message="HN에 올려줘",
    )
    # Framing: this is the behavior the project kills.
    assert "behavior this project exists to kill" in prompt
    # Explicit anti-phrasings listed as rejected.
    assert "cop-out" in prompt or "✗" in prompt or "❌" in prompt
    # API-less channels have suggested alternatives.
    assert "Reddit r/programming" in prompt
    assert "Mastodon" in prompt
    assert "Bluesky" in prompt
    # Last-resort fallback clarified.
    assert "Only if the user insists" in prompt


def test_history_format_highlights_first_user_message_as_purpose(tmp_path):
    """v1.14.0 — the opening user statement is the project's purpose
    anchor. _format_history must surface it prominently at the top
    of the conversation log so the agent can't miss it on turn N."""
    proj = Project.init(tmp_path / "anchor")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    history = [
        {"user": "AIL과 HEAAL을 홍보하는 봇 만들어줘",
         "reply": "네", "files": [], "action": None},
        {"user": "이번엔 정렬기도",
         "reply": "ok", "files": [], "action": None},
    ]
    formatted = chat._format_history(history)
    assert "PROJECT PURPOSE ANCHOR" in formatted
    # The FIRST user message appears under the anchor.
    assert "AIL과 HEAAL을 홍보하는 봇 만들어줘" in formatted
    # Placement: anchor comes BEFORE the full log.
    anchor_idx = formatted.index("PROJECT PURPOSE ANCHOR")
    log_idx = formatted.index("Full conversation log")
    assert anchor_idx < log_idx


def test_history_format_no_anchor_on_first_turn(tmp_path):
    proj = Project.init(tmp_path / "first")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    formatted = chat._format_history([])
    assert "no prior turns" in formatted
    assert "initial purpose" in formatted


def test_prompt_teaches_chat_history_is_memory(tmp_path):
    """v1.14.0 pivot — chat history is the agent's memory, not
    INTENT.md. The prompt anchors the agent to the history for
    project purpose, rather than re-synthesising INTENT.md every
    turn."""
    proj = Project.init(tmp_path / "purp")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"app.ail": ""},
        history=[],
        user_message="추천 봇도 만들어줘",
    )
    # New framing.
    assert "YOUR MEMORY IS THE CHAT HISTORY" in prompt
    # The first-user-message-is-purpose rule.
    assert "first user message" in prompt
    # Bake-purpose-into-every-new-program rule preserved.
    assert "Bake the history-established purpose" in prompt
    # INTENT.md demoted to legacy.
    assert "INTENT.md is NOT your memory" in prompt
    assert "legacy" in prompt.lower()


def test_export_history_as_markdown_empty(tmp_path):
    from ail.agentic.authoring_chat import export_history_as_markdown
    proj = Project.init(tmp_path / "emptychat")
    md = export_history_as_markdown(proj)
    assert proj.root.name in md
    assert "no history yet" in md


def test_export_history_as_markdown_renders_turns(tmp_path):
    from ail.agentic.authoring_chat import export_history_as_markdown
    proj = Project.init(tmp_path / "turns")
    adapter = _ScriptedChatAdapter([
        '<reply>hi there</reply>\n'
        '<file path="app.ail">\nentry main(x: Text) { return x }\n</file>'
        '\n<action>ready_to_run</action>',
    ])
    chat = AuthoringChat(proj, adapter)
    chat.turn("make it")

    md = export_history_as_markdown(proj)
    assert "## Turn 1" in md
    assert "**User**" in md
    assert "make it" in md
    assert "**Agent**" in md
    assert "hi there" in md
    assert "app.ail" in md
    assert "ready_to_run" in md


def test_export_history_includes_run_results(tmp_path):
    from ail.agentic.authoring_chat import (
        AuthoringChat, export_history_as_markdown,
    )
    proj = Project.init(tmp_path / "results")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([
        '<reply>ok</reply>',
    ]))
    chat.turn("ping")
    # Simulate a run result being appended (the server does this on
    # /authoring-run; tests call the helper directly).
    chat._append_run_result("", {
        "ok": True, "value": "hello output", "diagnostic": "",
    })
    chat._append_run_result("", {
        "ok": False, "value": "", "error": "ParseError: x",
        "diagnostic": "",
    })
    md = export_history_as_markdown(proj)
    assert "### Run result" in md
    assert "hello output" in md
    assert "ParseError" in md


def test_export_endpoint_returns_markdown_with_disposition(tmp_path):
    import json as _json
    proj = Project.init(tmp_path / "exportep")
    (proj.state_dir / "chat_history.jsonl").write_text(
        _json.dumps({
            "ts": 1, "user": "hi", "reply": "hello",
            "files": [], "action": None,
        }) + "\n",
        encoding="utf-8",
    )
    proj.write_app_source(
        'entry main(input: Text) { return input }')

    port = _free_port()
    t = threading.Thread(
        target=serve_project,
        kwargs={"project": proj, "port": port, "watch": False},
        daemon=True,
    )
    t.start()
    _wait_listening(port)

    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/authoring-chat-export", timeout=2
    ) as r:
        assert r.status == 200
        ctype = r.headers.get("Content-Type", "")
        assert "text/markdown" in ctype
        disp = r.headers.get("Content-Disposition", "")
        assert "filename=" in disp
        body = r.read().decode("utf-8")
    assert "# " in body  # title heading
    assert "**User**" in body
    assert "hi" in body


def test_chat_ui_has_export_and_copy_links(tmp_path):
    from ail.agentic.authoring_ui import render_authoring_page
    html = render_authoring_page(
        project_name="x", host="127.0.0.1", port=8080, history=[])
    assert 'id="export-chat"' in html
    assert 'id="copy-chat"' in html
    assert "/authoring-chat-export" in html
    assert "navigator.clipboard.writeText" in html


def test_project_state_omits_intent_md_in_v1_14(tmp_path):
    """v1.14.0 — chat_history is the agent's memory. _read_project_state
    MUST NOT include INTENT.md in the PROJECT STATE block sent to the
    model. The file can still exist on disk (legacy scaffold) but the
    agent no longer reads it to avoid the dual-source-of-truth class
    of bugs."""
    proj = Project.init(tmp_path / "nointent")
    # INTENT.md exists on disk (default from init).
    assert proj.intent_path.is_file()
    proj.write_app_source(
        'entry main(input: Text) { return input }')
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    state = chat._read_project_state()
    # Agent context does NOT carry INTENT.md.
    assert "INTENT.md" not in state
    # But app.ail (and other .ail files) still surface.
    assert "app.ail" in state


def test_prompt_minimizes_human_interrogation(tmp_path):
    """v1.13.1 — user feedback: 'agent became a bad chatbot, asking
    too many clarifying questions instead of just doing the work.'
    The whole project's premise is minimizing human involvement.
    Prompt must push toward aggressive defaults, not interviews."""
    proj = Project.init(tmp_path / "quiet")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=[],
        user_message="make a word counter",
    )
    # Strong framing that asking is the failure mode.
    assert "DEFAULT AGGRESSIVELY" in prompt
    assert "MINIMIZE human involvement" in prompt
    # Specific anti-interrogation cases listed.
    assert "Do NOT ask about" in prompt
    assert "Korean vs English" in prompt
    assert "Port number" in prompt or "port number" in prompt.lower()
    # Allowed-to-ask cases explicitly limited.
    assert "Secrets" in prompt
    assert "Permissions" in prompt


def test_render_value_strips_value_envelope(tmp_path):
    """v1.13.1 — LLM intent responses sometimes slip through
    `{"value": X}` envelopes that parse_value_confidence doesn't
    unwrap. The renderer strips them so users see markdown, not
    `{"value": "...markdown..."}`."""
    from ail.agentic.server import _render_value
    # Single-key envelope around markdown → markdown alone.
    wrapped = {"value": "# Heading\n\nBody text."}
    assert _render_value(wrapped) == "# Heading\n\nBody text."
    # value + confidence envelope → inner.
    wrapped = {"value": "answer", "confidence": 0.9}
    assert _render_value(wrapped) == "answer"
    # Nested envelopes peel recursively.
    wrapped = {"value": {"value": "deep"}}
    assert _render_value(wrapped) == "deep"
    # A dict with OTHER keys is NOT unwrapped — it's genuine data.
    real_dict = {"value": "a", "other": "b"}
    import json as _json
    out = _render_value(real_dict)
    assert _json.loads(out) == real_dict


def test_prompt_teaches_multiple_program_file_naming(tmp_path):
    """v1.13.1 — agent must know not to overwrite when user asks for
    a new independent program."""
    proj = Project.init(tmp_path / "nameit")
    chat = AuthoringChat(proj, _ScriptedChatAdapter([]))
    prompt = chat._build_goal_prompt(
        state={"INTENT.md": "", "app.ail": ""},
        history=[],
        user_message="sorter도 만들어줘",
    )
    assert "new descriptively-named file" in prompt or \
        "NEW descriptively-named file" in prompt
    assert "word_counter.ail" in prompt or "news_fetcher.ail" in prompt
    # Don't-overwrite guidance.
    assert "Do NOT overwrite" in prompt


def test_chat_ui_service_card_links_to_run_route(tmp_path):
    """ready_to_serve renders the deploy card with a share link to
    /run — the runtime URL separated from the edit URL ("/") per
    PRINCIPLES.md §5. /service is kept as a back-compat alias."""
    from ail.agentic.authoring_ui import render_authoring_page
    html = render_authoring_page(
        project_name="x", host="127.0.0.1", port=8080, history=[])
    assert "'/run'" in html
    # Deploy card has distinguishing copy so it's clearly "independent
    # execution" vs plain run.
    assert "독립 실행" in html or "Ready to serve" in html


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
