"""Conversational project authoring — the main entry for non-programmers.

Replaces the old "INTENT.md template + one-shot `ail ask`" flow with a
multi-turn chat where the agent writes INTENT.md and app.ail
incrementally based on the user's natural-language requirements.

Pattern: same as Claude Code. User types "I want X". Agent asks
clarifying questions, writes files as understanding grows, and at some
point asks "ready to run?" — at which point the project hands off to
the regular `ail up` serve loop.

Response protocol (the LLM emits):

    <reply>conversational message to the user</reply>
    <file path="INTENT.md">
    full new contents
    </file>
    <file path="app.ail">
    full new contents
    </file>
    <action>ready_to_run</action>

All tags optional except <reply>. Files listed by <file> tags are
written to disk (after path-safety check); the <action> surfaces as a
button in the UI.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from ..runtime.model import ModelAdapter


_ALLOWED_EXTENSIONS = {".md", ".ail", ".html", ".json", ".txt"}
_MAX_FILE_BYTES = 64 * 1024  # 64 KB per file write
_RECENT_HISTORY_TURNS = 12


class AuthoringChat:
    """One instance per project. Holds no state itself — history and
    credentials live on disk under the project's .ail/ directory so
    tabs can be closed and reopened."""

    def __init__(self, project, adapter: ModelAdapter):
        self.project = project
        self.adapter = adapter

    def turn(self, user_message: str) -> dict:
        """Process one user message; return structured response for UI."""
        history = self._load_history(limit=_RECENT_HISTORY_TURNS)
        project_state = self._read_project_state()

        goal_text = self._build_goal_prompt(project_state, history, user_message)

        response = self.adapter.invoke(
            goal=goal_text,
            constraints=[
                "respond in the XML protocol exactly as described",
                "match the user's language (Korean or English)",
                "ask one thing at a time",
                "do not emit ready_to_run until both INTENT.md and app.ail are coherent",
            ],
            context={"_intent_name": "__authoring_chat__"},
            inputs={},
            expected_type="Text",
            examples=None,
        )
        raw = response.value if isinstance(response.value, str) else str(response.value)
        reply, file_writes, action = self._parse_response(raw)

        if not reply:
            reply = "(응답 파싱 실패 — 다시 시도해주세요.)"

        applied_writes = []
        for path, content in file_writes:
            ok, summary = self._write_file(path, content)
            if ok:
                applied_writes.append({"path": path, "bytes": len(content.encode("utf-8"))})
            else:
                applied_writes.append({"path": path, "skipped": summary})

        self._append_history(user_message, reply, applied_writes, action)
        self.project.append_ledger({
            "event": "authoring_turn",
            "user_chars": len(user_message),
            "reply_chars": len(reply),
            "files": [w["path"] for w in applied_writes if "skipped" not in w],
            "action": action,
        })

        return {
            "reply": reply,
            "files": applied_writes,
            "action": action,
        }

    # ---------- prompt construction ----------

    def _build_goal_prompt(
        self, state: dict[str, str], history: list[dict], user_message: str
    ) -> str:
        reference_card = self._load_reference_card()
        history_text = self._format_history(history)
        state_text = self._format_state(state)

        return f"""You are a co-author for an AIL project. The user is typically NOT a programmer. Your job is to elicit what they want, ask ONE clarifying question at a time, and write/update files incrementally. You're writing AIL — study the reference card below.

You respond in this exact format:

<reply>your conversational reply to the user (plain text, in their language)</reply>
<file path="INTENT.md">
full new contents of INTENT.md
</file>
<file path="app.ail">
full new contents of app.ail
</file>
<action>ready_to_run</action>

Rules:
- <reply> is required. All other tags are optional.
- Include <file> only when you're writing or updating that file. Omit it to leave the file unchanged.
- When you include <file>, provide the COMPLETE new contents, not a diff. Everything between the tags replaces the file entirely.
- Allowed files: INTENT.md, app.ail, view.html, tests/*.
- <action>ready_to_run</action> ONLY when INTENT.md is substantive AND app.ail is a parseable AIL program that matches INTENT.md. Not before.
- Match the user's language (Korean or English). If they wrote Korean, reply in Korean.
- Ask one question at a time. Don't dump 10 decisions in one message.
- Keep the reply short (1–3 sentences plus a question). The UI is chat — not a document.
- The AIL reference card is authoritative. Do NOT import modules that aren't listed. Do NOT use syntax that isn't in the card.

=== AIL REFERENCE CARD ===
{reference_card}
=== END REFERENCE CARD ===

=== CURRENT PROJECT STATE ===
Project name: {self.project.root.name}

{state_text}
=== END PROJECT STATE ===

=== CONVERSATION HISTORY (most recent last) ===
{history_text}
=== END HISTORY ===

=== USER'S NEW MESSAGE ===
{user_message}
=== END MESSAGE ===

Now respond using the XML format above."""

    def _format_state(self, state: dict[str, str]) -> str:
        lines = []
        for name, content in state.items():
            lines.append(f"--- {name} ---")
            if not content.strip():
                lines.append("(empty)")
            else:
                lines.append(content.strip())
            lines.append("")
        return "\n".join(lines)

    def _format_history(self, history: list[dict]) -> str:
        if not history:
            return "(no prior turns)"
        parts = []
        for entry in history:
            parts.append(f"User: {entry.get('user', '')}")
            parts.append(f"Agent: {entry.get('reply', '')}")
            files = entry.get("files") or []
            if files:
                file_names = ", ".join(
                    f.get("path", "?") for f in files if isinstance(f, dict))
                if file_names:
                    parts.append(f"(files written: {file_names})")
        return "\n".join(parts)

    def _load_reference_card(self) -> str:
        from ..authoring import _load_reference_card
        return _load_reference_card()

    # ---------- response parsing ----------

    def _parse_response(
        self, raw: str
    ) -> tuple[str, list[tuple[str, str]], Optional[str]]:
        # Strip an outer fence if the model wrapped the whole thing.
        stripped = raw.strip()
        if stripped.startswith("```"):
            m = re.match(r"^```[a-zA-Z0-9_-]*\n(.*?)\n```\s*$", stripped, re.DOTALL)
            if m:
                stripped = m.group(1)

        reply = ""
        reply_match = re.search(r"<reply>(.*?)</reply>", stripped, re.DOTALL)
        if reply_match:
            reply = reply_match.group(1).strip()

        files: list[tuple[str, str]] = []
        for m in re.finditer(
            r'<file\s+path="([^"]+)">(.*?)</file>', stripped, re.DOTALL
        ):
            path = m.group(1).strip()
            content = m.group(2)
            # Strip one leading/trailing newline introduced by formatting
            if content.startswith("\n"):
                content = content[1:]
            if content.endswith("\n"):
                content = content[:-1]
            files.append((path, content))

        action = None
        action_match = re.search(r"<action>(.*?)</action>", stripped, re.DOTALL)
        if action_match:
            action = action_match.group(1).strip()
            if action not in ("ready_to_run", "ready_to_deploy"):
                action = None

        return reply, files, action

    # ---------- filesystem ----------

    def _read_project_state(self) -> dict[str, str]:
        files_to_show = ["INTENT.md", "app.ail"]
        # Include view.html if present
        if (self.project.root / "view.html").exists():
            files_to_show.append("view.html")
        state = {}
        for name in files_to_show:
            p = self.project.root / name
            if p.exists():
                try:
                    state[name] = p.read_text(encoding="utf-8")
                except OSError:
                    state[name] = "(read error)"
            else:
                state[name] = ""
        return state

    def _write_file(self, rel_path: str, content: str) -> tuple[bool, str]:
        """Write a file inside the project root. Returns (ok, detail).

        Rejections:
          - path traversal or absolute paths
          - extension not in allow-list
          - file too large
        """
        if ".." in rel_path.split("/") or rel_path.startswith("/"):
            return False, "path traversal rejected"
        target = (self.project.root / rel_path).resolve()
        try:
            target.relative_to(self.project.root.resolve())
        except ValueError:
            return False, "path escapes project root"
        ext = target.suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            return False, f"extension {ext!r} not allowed"
        payload = content.encode("utf-8")
        if len(payload) > _MAX_FILE_BYTES:
            return False, f"file too large ({len(payload)} > {_MAX_FILE_BYTES})"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return True, "written"

    # ---------- history ----------

    def _history_path(self) -> Path:
        return self.project.state_dir / "chat_history.jsonl"

    def _load_history(self, limit: Optional[int] = None) -> list[dict]:
        p = self._history_path()
        if not p.is_file():
            return []
        try:
            lines = p.read_text(encoding="utf-8").strip().splitlines()
        except OSError:
            return []
        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
        if limit is not None and len(entries) > limit:
            entries = entries[-limit:]
        return entries

    def _append_history(
        self, user_msg: str, reply: str, files: list[dict], action: Optional[str]
    ) -> None:
        p = self._history_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "user": user_msg,
            "reply": reply,
            "files": files,
            "action": action,
        }
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def project_is_fresh(project) -> bool:
    """True when the project hasn't been through authoring handoff yet.

    Fresh projects get the chat UI on GET /; authored projects get the
    existing service UI (textarea / view.html). The handoff marker is
    .ail/authored_at, written when the user clicks "Run it now".
    """
    marker = project.state_dir / "authored_at"
    if marker.is_file():
        return False
    # Also treat projects with a non-empty app.ail as authored (for legacy
    # examples that were hand-written and committed with INTENT.md +
    # app.ail).
    app = project.root / "app.ail"
    if app.is_file():
        try:
            content = app.read_text(encoding="utf-8").strip()
            # Strip comments and whitespace to see if there's real code.
            stripped = re.sub(r"//[^\n]*", "", content).strip()
            if stripped and "entry" in stripped:
                return False
        except OSError:
            pass
    return True


def mark_authored(project) -> None:
    """Record that the user has handed off from authoring to execution.
    Idempotent. Future GET / will serve the service UI instead of chat."""
    marker = project.state_dir / "authored_at"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"ts": time.time()}, ensure_ascii=False),
        encoding="utf-8",
    )
