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

        # Tell the UI whether the entry uses its input parameter so
        # the Run widget shown next to a ready_to_run/serve action
        # can hide the input textarea when the program takes no
        # input (v1.12.5).
        try:
            from .web_ui import entry_uses_input
            app_source = self.project.app_path.read_text(encoding="utf-8")
            input_used = entry_uses_input(app_source)
        except Exception:
            input_used = True

        return {
            "reply": reply,
            "files": applied_writes,
            "action": action,
            "input_used": input_used,
        }

    # ---------- prompt construction ----------

    def _build_goal_prompt(
        self, state: dict[str, str], history: list[dict], user_message: str
    ) -> str:
        reference_card = self._load_reference_card()
        history_text = self._format_history(history)
        state_text = self._format_state(state)

        return f"""You are a co-author for an AIL project. The user is typically NOT a programmer. Your job is to elicit what they want, ask ONE clarifying question at a time, and write/update files incrementally.

=== PROJECT IDENTITY ===
AIL stands for "AI-Intent Language". It's a programming language designed for LLMs to author code. The Python interpreter is the PyPI package `ail-interpreter`. The GitHub repo is https://github.com/hyun06000/AIL. Humans describe what they want in plain language; AIL + an LLM author the code; the runtime executes it safely.

AIL is the reference implementation of **HEAAL — Harness Engineering As A Language**. The core claim: safety constraints should be part of the *grammar*, not bolted on afterwards. Where other teams build harnesses AROUND Python (AGENTS.md files, pre-commit hooks, custom linters, retry wrappers, output validators), AIL puts the harness INSIDE the language. Concretely:

- No `while` keyword — infinite loops are impossible by construction, not "discouraged".
- `Result` type required on every failable op (`perform http.get`, `to_number`, `perform file.read`) — you cannot silently swallow errors.
- `pure fn` statically verified — the parser rejects side effects in pure bodies before runtime.
- `intent` is the only path to an LLM — every model call is explicit, type-checked, and auditable; the v1.10 harness validates intent return values against their declared types.
- `perform env.read` is the only sanctioned path for credentials — no hardcoded API keys in source.
- Every value carries provenance (which fn / intent / perform produced it).

So a user project written in AIL is "safe by construction" rather than "safe by convention". You're helping the user leverage these properties.

=== YOUR RESPONSE FORMAT ===
You respond in this exact XML format:

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
- Two action values are recognized. BOTH keep the user in the chat — nothing ever navigates away. The difference is framing and affordances, not UI mode:
  - `<action>ready_to_run</action>` — the DEFAULT for most tasks (one-shot answers, scripts, calculations, previews). Renders an inline "Run" card in the chat with an optional input textarea and a Run button. The user can click Run repeatedly with different inputs; each result appears as a bubble. They stay in the chat and can also say "이거 수정해줘" to have you iterate on the code.
  - `<action>ready_to_serve</action>` — use when the user has said they want a long-running service / dashboard / webhook / something other people or apps will call. Renders the same run widget wrapped as a "service card" (green, labeled 서비스 모드) with a link to `/service` — a shareable URL that serves the classic textarea page (or view.html) on a separate route for external consumers. The user STILL stays in the chat; `/service` opens in a new tab only when they click the link.
- When the conversation history contains a `[Run result — ERROR]` entry, that means the user just ran the program and got an error. Treat this as your top priority: explain briefly what went wrong, update app.ail to fix it, and re-emit `ready_to_run` so they can try again.
- When the conversation history contains a `[Run result — OK]` entry, the user saw the output. If they don't object, offer either more refinement questions OR `ready_to_serve` if they want a service. Don't re-offer `ready_to_run` with unchanged code.
- When the PROJECT STATE for `app.ail` includes `[PARSE ERROR]`, the code you previously wrote does NOT parse. Do NOT emit `ready_to_run` or `ready_to_serve`. Instead: write a corrected `<file path="app.ail">` and briefly explain the fix in `<reply>`. Common LLM mistakes to avoid: don't use `#` for comments (AIL uses `//`); `intent` constraints must be short identifier-style phrases like `output_is_valid_json` or `language_is_korean`, NOT free-prose sentences with articles like "their" or "a"; don't put JSON shape descriptions in constraints — that's free prose; only write syntax that appears in the reference card.
- Match the user's language (Korean or English). If they wrote Korean, reply in Korean.
- Ask one question at a time. Don't dump 10 decisions in one message.
- Keep the reply short (1–3 sentences plus a question). The UI is chat — not a document.
- The AIL reference card is authoritative. Do NOT import modules that aren't listed. Do NOT use syntax that isn't in the card.

=== KNOWLEDGE + RESEARCH ===
You have no live internet access from this chat yourself. BUT: AIL has `perform http.get(url) -> Record` and `intent` for summarization. So when the user asks about something you don't know — a news topic, current data, the state of a tool, etc. — do NOT just say "I can't search". Instead, propose authoring a small AIL program that fetches and summarizes it. Example pattern:

```ail
intent summarize(text: Text) -> Text {{ goal: short Korean summary }}
entry main(input: Text) {{
    resp = perform http.get("https://...")
    if resp.ok {{ return summarize(resp.body) }}
    return unwrap_error(resp)
}}
```

If the user asks about AIL / HEAAL / ail-interpreter itself, you already know the answer from the PROJECT IDENTITY section above — just answer directly. Don't claim ignorance of things you were told in this prompt.

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
            kind = entry.get("kind")
            if kind == "run_result":
                if entry.get("ok"):
                    parts.append(
                        f"[Run result — OK] {entry.get('value', '')[:500]}")
                else:
                    err = entry.get("error") or entry.get("value") or ""
                    parts.append(f"[Run result — ERROR] {str(err)[:500]}")
                    diag = entry.get("diagnostic") or ""
                    if diag:
                        parts.append(f"[Diagnostic] {str(diag)[:500]}")
                continue
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
            if action not in (
                "ready_to_run", "ready_to_serve", "ready_to_deploy"
            ):
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

        # Parse-check app.ail so the agent sees syntax errors in its
        # state view and prioritizes fixing them. Without this, the
        # agent happily re-emits ready_to_run on code that fails to
        # parse (field test 2026-04-23: LLM wrote free-prose inside
        # intent goal/constraints blocks).
        app = state.get("app.ail", "").strip()
        if app:
            parse_err = _parse_check(app)
            if parse_err:
                state["app.ail"] = (
                    state["app.ail"]
                    + f"\n\n[PARSE ERROR — this file will NOT run until "
                      f"fixed]\n{parse_err}"
                )
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

    def _append_run_result(self, run_input: str, outcome: dict) -> None:
        """Record a run-in-chat outcome to history so the next agent
        turn sees what happened. The UI also renders this as a
        result bubble."""
        p = self._history_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "kind": "run_result",
            "input": run_input,
            "ok": outcome.get("ok", False),
            "value": str(outcome.get("value", ""))[:2000],
            "error": str(outcome.get("error", ""))[:1000],
            "diagnostic": str(outcome.get("diagnostic", ""))[:2000],
        }
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _parse_check(source: str) -> Optional[str]:
    """Try parsing an AIL source. Return None on success, else a short
    human-readable error string (no Python traceback — the agent sees
    this in its prompt, and the UI surfaces it in run-error bubbles)."""
    try:
        from ..parser import parse
    except Exception:
        return None
    try:
        parse(source)
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return None


def project_is_fresh(project) -> bool:
    """True when GET / should serve the authoring chat UI.

    Three cases:
      1. `authored_at` marker present → return False (service UI).
      2. No marker, `chat_history.jsonl` present → chat project in
         mid-iteration. Serve chat regardless of app.ail state so the
         user can keep editing. Also enables "back to chat" to return
         here even when app.ail is fully authored.
      3. No marker, no chat history, app.ail contains an `entry` block
         → legacy hand-written project. Serve service UI (current
         behavior for word-counter, visit-counter, etc.).
      4. Otherwise → fresh project. Serve chat.
    """
    marker = project.state_dir / "authored_at"
    if marker.is_file():
        return False
    chat_history = project.state_dir / "chat_history.jsonl"
    if chat_history.is_file():
        return True
    app = project.root / "app.ail"
    if app.is_file():
        try:
            content = app.read_text(encoding="utf-8").strip()
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


def unmark_authored(project) -> None:
    """Reverse `mark_authored`. The user can return to the authoring
    chat to iterate further. Chat history is preserved — only the
    service-mode marker goes. Idempotent."""
    marker = project.state_dir / "authored_at"
    if marker.is_file():
        try:
            marker.unlink()
        except OSError:
            pass
