"""Minimal HTTP server for an agentic AIL project.

POST /  with raw text body  →  runs entry main(input=body), returns the value.
GET  /healthz                →  200 ok.

Uses Python's stdlib `http.server`. Not production-grade; v0 is meant
for local development and small-traffic demos. Production hardening
(concurrency, timeouts, auth) is L2 v1+ work.
"""
from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .. import run as ail_run
from .agent import _looks_like_error
from .project import Project

_run_log: dict[str, dict] = {}
_run_log_lock = threading.Lock()


def _get_log_state(project_key: str) -> dict:
    with _run_log_lock:
        if project_key not in _run_log:
            _run_log[project_key] = {
                "lines": [], "lock": threading.Lock(), "run_id": 0}
        return _run_log[project_key]


def _friendly_api_error(exc: BaseException) -> str:
    """Map known API/network exceptions to one-line Korean messages."""
    name = type(exc).__name__
    msg = str(exc)
    if "OverloadedError" in name or "529" in msg:
        return "API가 일시적으로 과부하 상태예요. 잠시 후 다시 시도해주세요."
    if "RateLimitError" in name or "429" in msg:
        return "API 요청 한도를 초과했어요. 잠시 후 다시 시도해주세요."
    if "AuthenticationError" in name or "401" in msg:
        return "API 키가 올바르지 않아요. ANTHROPIC_API_KEY를 확인해주세요."
    if "APIConnectionError" in name or "ConnectionError" in name:
        return "API 서버에 연결할 수 없어요. 인터넷 연결을 확인해주세요."
    if "APITimeoutError" in name or "TimeoutError" in name:
        return "API 응답 시간이 초과됐어요. 잠시 후 다시 시도해주세요."
    return f"오류가 발생했어요: {name}: {msg}"


def _resolve_program_path(project, requested: str):
    """Pick which .ail file to run for /authoring-run.

    Precedence: explicit `?program=` query (must match an existing
    `.ail` file) → `.ail/active_program` marker → `app.ail`. Returns
    a Path, or None if the requested name doesn't exist and no
    sensible default can be found.
    """
    root = project.root
    if requested:
        if "/" in requested or "\\" in requested or ".." in requested:
            return None
        if not requested.endswith(".ail"):
            return None
        target = (root / requested).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            return None
        if not target.is_file():
            return None
        return target
    marker = project.state_dir / "active_program"
    if marker.is_file():
        try:
            name = marker.read_text(encoding="utf-8").strip()
        except OSError:
            name = ""
        if name and name.endswith(".ail") and "/" not in name:
            candidate = root / name
            if candidate.is_file():
                return candidate
    if project.app_path.is_file():
        return project.app_path
    try:
        for p in root.iterdir():
            if p.is_file() and p.suffix == ".ail":
                return p
    except OSError:
        pass
    return None


def _diagnose_from_trace(trace) -> str:
    """Turn a Trace of a failed request into a human-readable diagnostic.

    Non-programmers who open `ail up` in a browser and see a 500 need
    an actionable next step. The raw error string the program returned
    ("Failed to fetch news") is almost never enough — the real reason
    is usually upstream: a 401 from an API, a blown DNS, an intent
    call the harness floored to confidence 0. This scans the trace for
    the last few informative events and renders them as a short
    Korean + English hint.

    Returns an empty string when nothing interesting is in the trace.
    """
    if trace is None:
        return ""
    try:
        entries = trace.entries
    except AttributeError:
        return ""

    hints: list[str] = []
    for entry in reversed(entries):
        kind = entry.kind
        p = entry.payload
        if kind == "http_call" and not p.get("ok", True):
            url = p.get("url", "?")
            status = p.get("status")
            network_error = p.get("network_error")
            if network_error:
                hints.append(
                    f"HTTP 네트워크 실패 / network error: {url} — "
                    f"{network_error}"
                )
            elif status is not None:
                body_preview = p.get("body_preview") or ""
                reason_hint = _http_reason_hint(int(status))
                line = (
                    f"HTTP {int(status)} on {p.get('method','GET')} "
                    f"{url}"
                )
                if reason_hint:
                    line = line + f" — {reason_hint}"
                if body_preview:
                    line = (
                        line
                        + f"\n  response body (preview): "
                        + body_preview.replace("\n", " ")[:160]
                    )
                hints.append(line)
        elif kind == "intent_validation_failed":
            hints.append(
                "Intent 응답이 선언된 타입과 맞지 않음 / "
                f"intent `{p.get('intent','?')}` declared "
                f"`{p.get('declared_type','?')}` but model returned a "
                f"mismatching shape ({p.get('error','')[:120]}). "
                "confidence was floored to 0."
            )
        # Stop once we have a couple of hints — keep the error response
        # short enough to read on a phone.
        if len(hints) >= 3:
            break

    if not hints:
        return ""
    header = "— diagnosis / 진단 ————————————"
    action = (
        "\n다음 액션: `ail chat <project> \"...\"` 로 문제를 설명하고 "
        "다른 방법으로 바꿔달라고 요청하세요.\n"
        "Next step: run `ail chat <project> \"…\"` and ask the agent "
        "to try a different approach."
    )
    return header + "\n" + "\n".join(hints) + action


def _http_reason_hint(status: int) -> str:
    """Short human-readable hint for a non-2xx HTTP status.

    Korean + English because a non-programmer shouldn't have to look
    up what 401 means. Covers the failure modes AI-authored code
    typically hits (bad/missing API key, endpoint moved, rate limit,
    upstream broken).
    """
    if 200 <= status < 300:
        return ""
    if status == 401 or status == 403:
        return (
            "인증 실패 (API 키가 잘못되었거나 없음) / "
            "authentication failed (the API key is invalid or missing). "
            "프로그램이 고정된 'demo' 같은 가짜 키를 쓰고 있는지 확인."
        )
    if status == 404:
        return "엔드포인트를 찾을 수 없음 / endpoint not found"
    if status == 429:
        return "요청 제한 초과 / rate-limited"
    if 400 <= status < 500:
        return f"클라이언트 에러 / client error ({status})"
    if 500 <= status < 600:
        return f"업스트림 서버 에러 / upstream server error ({status})"
    return ""


def _render_value(value):
    """Format an entry main() return value for HTTP response.

    AIL programs that signal success-or-error with Result return a dict
    shape; collapse it to the inner value (or error message) so HTTP
    clients see plain text instead of language internals. Plain dict/
    list returns are re-formatted as pretty-printed JSON so a user who
    opens / in a browser sees readable structure instead of Python's
    repr syntax (`{'k': 'v'}` with single quotes).

    v1.13.1 also strips residual `{"value": X}` envelopes that LLM
    intent responses sometimes slip past `parse_value_confidence`
    (e.g. when nested). Without this, a markdown answer renders as a
    quoted-inside-JSON block instead of plain markdown.
    """
    if isinstance(value, dict) and value.get("_result"):
        if value.get("ok"):
            return _render_value(value.get("value", ""))
        return value.get("error", "error")
    if isinstance(value, str) and value.startswith("UNWRAP_ERROR:"):
        # Surface the inner message without the runtime sentinel prefix.
        return value[len("UNWRAP_ERROR:"):].strip()
    # Recursively strip `{"value": X}` and `{"value": X, "confidence": c}`
    # single/double-key envelopes — they're leaked LLM JSON wrappers,
    # not the structured data the user intended.
    value = _strip_value_envelopes(value)
    if isinstance(value, (dict, list)):
        import json as _json
        try:
            return _json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(value)
    return value


def _strip_value_envelopes(value, _depth: int = 0):
    """Peel off `{"value": X}` and `{"value": X, "confidence": N}`
    dict wrappers recursively (capped at 6 levels so a truly
    pathological recursive structure can't loop us).

    Also handles string-encoded JSON envelopes — when a program calls
    `to_text(result_dict)` or `encode_json(result_dict)` and the result
    is a string like '{"value": "# actual content"}', this unwraps the
    inner value so the user sees the content, not the JSON wrapper.
    Only unwraps strings that are SOLELY a JSON envelope (the entire
    string is `{...}` with nothing else); strings that merely CONTAIN
    JSON as part of a larger document are left alone.
    """
    if _depth >= 6:
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                import json as _json
                parsed = _json.loads(stripped)
                if isinstance(parsed, dict):
                    keys = set(parsed.keys())
                    if keys == {"value"} or keys == {"value", "confidence"}:
                        return _strip_value_envelopes(
                            parsed["value"], _depth + 1)
            except (ValueError, TypeError):
                pass
        return value
    if not isinstance(value, dict):
        return value
    keys = set(value.keys())
    if keys == {"value"} or keys == {"value", "confidence"}:
        return _strip_value_envelopes(value["value"], _depth + 1)
    return value




def _make_handler(project: Project, serve_only: bool = False):
    """Build a request handler closed over a specific Project. Done as
    a factory so each project can have its own handler without globals.

    When `serve_only` is True the chat UI and its POST endpoint are
    disabled — `/` redirects to `/run`, and `/authoring-chat` returns
    404. This is how `ail serve` realizes PRINCIPLES.md §5 Program
    Independence at the process level.
    """

    class _Handler(BaseHTTPRequestHandler):
        # Suppress default per-request stderr logging — we record to ledger.
        def log_message(self, fmt, *args):  # noqa: N802 — stdlib name
            return

        def do_GET(self):  # noqa: N802 — stdlib name
            if self.path.startswith("/run-log-poll"):
                from urllib.parse import urlparse, parse_qs
                import json as _json
                qs = parse_qs(urlparse(self.path).query)
                try:
                    since = int(qs.get("since", ["0"])[0])
                except ValueError:
                    since = 0
                log_state = _get_log_state(str(project.root))
                with log_state["lock"]:
                    lines = log_state["lines"][since:]
                    total = len(log_state["lines"])
                    run_id = log_state["run_id"]
                body = _json.dumps({
                    "lines": lines,
                    "total": total,
                    "run_id": run_id,
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == "/authoring-env-list":
                import json as _json
                from .authoring_chat import list_project_secret_keys
                keys = list_project_secret_keys(project)
                body = _json.dumps(keys, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path in ("/healthz", "/health"):
                body = b"ok\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path.startswith("/authoring-file"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                fname = (qs.get("path", [""])[0] or "").strip()
                if not fname or "/" in fname or "\\" in fname or ".." in fname:
                    self._send_text(400, "invalid path\n")
                    return
                fpath = project.root / fname
                try:
                    fpath.relative_to(project.root.resolve())
                except ValueError:
                    self._send_text(400, "invalid path\n")
                    return
                try:
                    content = fpath.read_text(encoding="utf-8")
                except OSError:
                    self._send_text(404, "not found\n")
                    return
                import json as _json
                body = _json.dumps({"content": content}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            # Classic service UI for external sharing. Users who set
            # `ready_to_serve` stay in the chat; /service is the
            # sharable URL they hand to non-chat consumers (curl,
            # teammates, other apps). Always renders the textarea /
            # view.html page even for projects that still have an
            # active authoring chat.
            # v1.13.2: chat export. Returns the full conversation as
            # a markdown document for local save / sharing. Served
            # inline (not attachment) so the browser can either
            # display it or save-as depending on how the link is
            # clicked. The UI triggers a download via blob anyway.
            if self.path == "/authoring-approval-pending":
                # UI polls this while a run is in-flight. Returns the
                # current pending-approval record (id + plan) if the
                # program is blocked inside `perform human.approve`,
                # or 204 No Content otherwise. Idempotent, no side
                # effects — safe to call every 500ms.
                import json as _json
                pending_path = (
                    project.state_dir / "approvals" / "pending.json")
                if not pending_path.is_file():
                    self.send_response(204)
                    self.end_headers()
                    return
                try:
                    current = _json.loads(
                        pending_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    self.send_response(204)
                    self.end_headers()
                    return
                if current.get("status") != "pending":
                    # Decided record lingering after decision — treat
                    # as no-pending, the executor will clean it up.
                    self.send_response(204)
                    self.end_headers()
                    return
                body = _json.dumps({
                    "id": current.get("id"),
                    "plan": current.get("plan"),
                    "created_at": current.get("created_at"),
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header(
                    "Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == "/authoring-chat-export":
                from .authoring_chat import export_history_as_markdown
                md = export_history_as_markdown(project)
                body = md.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    f'inline; filename="{project.root.name}-chat.md"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # PRINCIPLES.md §5 Program Independence: edit URL ("/") and
            # runtime URL ("/run") stay separated. "/run" is the
            # user-facing standalone URL that opens in a new tab; the
            # chat session at "/" keeps working regardless.
            # "/service" is kept as a backward-compatible alias.
            if self.path in ("/run", "/run/", "/service", "/service/"):
                view_path = project.root / "view.html"
                if view_path.is_file():
                    try:
                        body = view_path.read_bytes()
                    except OSError as e:
                        self._send_text(500,
                            f"could not read view.html: {e}\n")
                        return
                    self.send_response(200)
                    self.send_header(
                        "Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                from .web_ui import render_page, extract_preamble, entry_uses_input
                try:
                    intent_text = project.intent_path.read_text(encoding="utf-8")
                except Exception:
                    intent_text = ""
                try:
                    app_source = project.app_path.read_text(encoding="utf-8")
                except Exception:
                    app_source = ""
                has_chat = (project.state_dir / "chat_history.jsonl").is_file()
                from .authoring_chat import extract_input_hint
                html = render_page(
                    project_name=project.root.name,
                    intent_preamble=extract_preamble(intent_text),
                    host=self.server.server_address[0],
                    port=self.server.server_address[1],
                    input_used=entry_uses_input(app_source),
                    input_hint=extract_input_hint(app_source),
                    show_back_to_chat=has_chat,
                )
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path in ("/", ""):
                if serve_only:
                    # PRINCIPLES.md §5: independent execution mode.
                    # Redirect the edit URL to the runtime URL so an
                    # operator landing on the server's root sees the
                    # running program, not a dead chat shell.
                    self.send_response(302)
                    self.send_header("Location", "/run")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                # Fresh project (no authored_at marker, no meaningful
                # app.ail) → serve the authoring chat UI. Users describe
                # what they want in plain language; the agent writes
                # INTENT.md and app.ail incrementally. Clicking "Run it
                # now" sets the marker and future GET / serves the
                # regular service UI.
                from .authoring_chat import project_is_fresh
                if project_is_fresh(project):
                    from .authoring_ui import render_authoring_page
                    from .authoring_chat import (
                        AuthoringChat, list_project_programs,
                        read_session_total_tokens,
                    )
                    chat = AuthoringChat(project, adapter=None)
                    history = chat._load_history()
                    session_total_tokens = read_session_total_tokens(project)
                    # Seed the current programs list so the run widget
                    # on initial render (before any new turn) already
                    # knows parse state, env_required, input_hint —
                    # otherwise it falls back to a dummy that claims
                    # everything parses, and broken programs get a
                    # confusing textarea instead of a parse-error
                    # banner on page reload.
                    programs = list_project_programs(project)
                    html = render_authoring_page(
                        project_name=project.root.name,
                        host=self.server.server_address[0],
                        port=self.server.server_address[1],
                        history=history,
                        programs=programs,
                        session_total_tokens=session_total_tokens,
                    )
                    body = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                # If the project has a view.html, serve it as the
                # dashboard page. The page's client-side JS is expected
                # to POST to / for data from entry main. This keeps
                # AIL code focused on computation and HTML markup in
                # its own file, editable without touching .ail sources.
                view_path = project.root / "view.html"
                if view_path.is_file():
                    try:
                        body = view_path.read_bytes()
                    except OSError as e:
                        self._send_text(500,
                            f"could not read view.html: {e}\n")
                        return
                    self.send_response(200)
                    self.send_header(
                        "Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                # No view.html — render the default textarea UI so a
                # non-developer can type into a box instead of running
                # curl.
                from .web_ui import render_page, extract_preamble, entry_uses_input
                try:
                    intent_text = project.intent_path.read_text(encoding="utf-8")
                except Exception:
                    intent_text = ""
                try:
                    app_source = project.app_path.read_text(encoding="utf-8")
                except Exception:
                    app_source = ""
                # Offer the "back to chat" affordance only when there's
                # an actual chat history to return to. Projects that
                # never went through authoring (committed examples,
                # legacy flows) don't get a stray button.
                has_chat = (project.state_dir / "chat_history.jsonl").is_file()
                from .authoring_chat import extract_input_hint
                html = render_page(
                    project_name=project.root.name,
                    intent_preamble=extract_preamble(intent_text),
                    host=self.server.server_address[0],
                    port=self.server.server_address[1],
                    input_used=entry_uses_input(app_source),
                    input_hint=extract_input_hint(app_source),
                    show_back_to_chat=has_chat,
                )
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                # Don't cache — INTENT.md edits should show on next load.
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            self._send_text(404, "POST / with the input as the body, "
                                 "or open / in a browser.\n")

        def do_POST(self):  # noqa: N802 — stdlib name
            if self.path == "/authoring-chat":
                if serve_only:
                    self._send_text(404,
                        "chat disabled in serve mode (ail serve). "
                        "Author via `ail up` in a separate terminal.\n")
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                user_msg = self.rfile.read(length).decode("utf-8") if length else ""
                if not user_msg.strip():
                    self._send_text(400, "empty message\n")
                    return
                try:
                    from .authoring_chat import AuthoringChat
                    from .. import _default_adapter
                    adapter = _default_adapter()
                    chat = AuthoringChat(project, adapter=adapter)
                    result = chat.turn(user_msg)
                except Exception as e:
                    import traceback as _tb
                    _tb.print_exc(file=sys.stderr)
                    self._send_text(500, _friendly_api_error(e) + "\n")
                    return
                import json as _json
                payload = _json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if self.path.startswith("/authoring-run"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                requested = (qs.get("program", [""])[0] or "").strip()
                program_path = _resolve_program_path(project, requested)
                if program_path is None:
                    self._send_text(400, "program not found\n")
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                run_input = self.rfile.read(length).decode("utf-8") if length else ""
                # Re-load secrets each run so keys set via the settings
                # panel are visible to effects (search.web, env.read, etc.)
                # without requiring a server restart.
                from .authoring_chat import load_project_secrets
                load_project_secrets(project)
                log_state = _get_log_state(str(project.root))
                with log_state["lock"]:
                    log_state["lines"] = []
                    log_state["run_id"] += 1

                def _log_cb(msg: str):
                    with log_state["lock"]:
                        log_state["lines"].append(msg)

                try:
                    result, trace = ail_run(
                        str(program_path), input=run_input,
                        log_callback=_log_cb)
                    value = result.value
                    is_err = _looks_like_error(value)
                    rendered = _render_value(value)
                    diagnostic = _diagnose_from_trace(trace) if is_err else ""
                    outcome = {
                        "ok": not is_err,
                        "value": str(rendered),
                        "diagnostic": diagnostic,
                    }
                except Exception as e:
                    # AIL-level errors (parse, lex, purity, import
                    # resolution) are users' actual problem; render
                    # them cleanly without a Python traceback in the
                    # user's face. Internal errors still carry a
                    # bounded traceback for debugging.
                    from ..parser import ParseError, LexError, PurityError
                    try:
                        from ..runtime.executor import ImportResolutionError
                    except ImportError:
                        ImportResolutionError = ()
                    clean_errs = (ParseError, LexError, PurityError)
                    if ImportResolutionError:
                        clean_errs = clean_errs + (ImportResolutionError,)
                    if isinstance(e, clean_errs):
                        outcome = {
                            "ok": False,
                            "value": "",
                            "error": f"{type(e).__name__}: {e}",
                            "diagnostic": "",
                        }
                    else:
                        import traceback
                        outcome = {
                            "ok": False,
                            "value": "",
                            "error": f"{type(e).__name__}: {e}",
                            "diagnostic": traceback.format_exc()[:1000],
                        }

                import os as _os
                try:
                    from .web_ui import entry_uses_input
                    from .authoring_chat import (
                        list_required_env_vars, extract_input_hint,
                    )
                    program_source = program_path.read_text(encoding="utf-8")
                    outcome["input_used"] = entry_uses_input(program_source)
                    outcome["input_hint"] = extract_input_hint(program_source)
                    outcome["env_required"] = [
                        {"name": n, "set": n in _os.environ}
                        for n in list_required_env_vars(program_source)
                    ]
                    outcome["program"] = program_path.name
                except Exception:
                    outcome["input_used"] = True
                    outcome["input_hint"] = None
                    outcome["env_required"] = []
                    outcome["program"] = "app.ail"

                try:
                    from .authoring_chat import AuthoringChat
                    chat = AuthoringChat(project, adapter=None)
                    chat._append_run_result(run_input, outcome)
                except Exception:
                    pass

                project.append_ledger({
                    "event": "authoring_run",
                    "ok": outcome.get("ok", False),
                    "input_chars": len(run_input),
                })
                import json as _json
                payload = _json.dumps(outcome, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            # Explicit service handoff: mark project as deployed so
            # future GET / serves the service UI. Only fires on an
            # explicit user decision ("서비스로 띄워줘"), no longer on
            # every "run" click.
            if self.path == "/authoring-reset-chat":
                history_path = project.state_dir / "chat_history.jsonl"
                try:
                    if history_path.is_file():
                        history_path.unlink()
                except OSError as e:
                    self._send_text(500, f"could not reset chat: {e}\n")
                    return
                project.append_ledger({"event": "chat_reset"})
                self._send_text(200, "ok\n")
                return

            if self.path == "/authoring-complete":
                from .authoring_chat import mark_authored
                mark_authored(project)
                project.append_ledger({"event": "authoring_complete"})
                self._send_text(200, "ok\n")
                return

            # Reversible back-out: remove the authored marker so GET /
            # serves the chat UI again. The user can iterate further
            # in the conversation. Chat history is preserved.
            if self.path == "/back-to-chat":
                from .authoring_chat import unmark_authored
                unmark_authored(project)
                project.append_ledger({"event": "back_to_chat"})
                self._send_text(200, "ok\n")
                return

            # Chat-safe secret entry. POST body = JSON {"name": "...",
            # "value": "..."}. Writes to process env AND to
            # .ail/secrets.json (gitignored). Values are NEVER echoed,
            # logged, or appended to chat_history.jsonl. Ledger only
            # records that a name was set, not the value.
            if self.path == "/authoring-approve":
                # v1.16.0 plan-validate-execute: while a run is blocked
                # inside `perform human.approve(plan)`, the UI POSTs
                # here with {"id": "...", "decision": "approve"|"decline",
                # "reason": "..."}. The executor's polling loop sees
                # the status flip and returns ok(true) / error(...).
                # ThreadingHTTPServer is what makes this work — this
                # handler runs in a different thread than the blocked
                # /authoring-run.
                import json as _json
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    raw = self.rfile.read(length).decode("utf-8") if length else ""
                    payload = _json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    self._send_text(400, "invalid json body\n")
                    return
                approval_id = str(payload.get("id", "")).strip()
                decision = str(payload.get("decision", "")).strip()
                reason = str(payload.get("reason", "")).strip()
                if decision not in ("approve", "decline"):
                    self._send_text(400,
                        "decision must be 'approve' or 'decline'\n")
                    return
                pending_path = (
                    project.state_dir / "approvals" / "pending.json")
                try:
                    current = _json.loads(
                        pending_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    self._send_text(404, "no pending approval\n")
                    return
                if approval_id and current.get("id") != approval_id:
                    self._send_text(409,
                        "approval id mismatch (stale UI?)\n")
                    return
                current["status"] = (
                    "approved" if decision == "approve" else "declined")
                if reason:
                    current["reason"] = reason
                import os as _os
                try:
                    tmp = pending_path.with_suffix(".tmp")
                    tmp.write_text(
                        _json.dumps(current, ensure_ascii=False),
                        encoding="utf-8")
                    _os.replace(tmp, pending_path)
                except OSError as e:
                    self._send_text(500,
                        f"could not write decision: {e}\n")
                    return
                project.append_ledger({
                    "event": "human_approve",
                    "id": current.get("id"),
                    "decision": current["status"],
                    "reason": reason or None,
                })
                self._send_text(200, "ok\n")
                return

            if self.path == "/authoring-set-env":
                import json as _json
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    raw = self.rfile.read(length).decode("utf-8") if length else ""
                    payload = _json.loads(raw)
                    name = str(payload.get("name", "")).strip()
                    value = str(payload.get("value", ""))
                    # Strip "KEY=value" or "export KEY=value" prefix if the
                    # user copy-pasted the whole shell export line.
                    if "=" in value:
                        lhs, _, rhs = value.partition("=")
                        lhs_clean = lhs.strip().removeprefix("export").strip()
                        if lhs_clean.upper() == name.upper() or lhs_clean == "":
                            value = rhs
                except (ValueError, UnicodeDecodeError):
                    self._send_text(400, "invalid json body\n")
                    return
                if not name or not name.replace("_", "").isalnum():
                    self._send_text(400,
                        "env var name must be alphanumeric + underscores\n")
                    return
                if not value:
                    self._send_text(400, "value required\n")
                    return
                from .authoring_chat import save_project_secret
                try:
                    save_project_secret(project, name, value)
                except OSError as e:
                    self._send_text(500, f"could not save secret: {e}\n")
                    return
                project.append_ledger({
                    "event": "env_set",
                    "name": name,
                    # NB: no `value` — never log secrets.
                })
                self._send_text(200, "ok\n")
                return

            if self.path == "/authoring-delete-env":
                import json as _json
                length = int(self.headers.get("Content-Length", "0") or "0")
                try:
                    raw = self.rfile.read(length).decode("utf-8") if length else ""
                    payload = _json.loads(raw)
                    name = str(payload.get("name", "")).strip()
                except (ValueError, UnicodeDecodeError):
                    self._send_text(400, "invalid json body\n")
                    return
                if not name:
                    self._send_text(400, "name required\n")
                    return
                from .authoring_chat import delete_project_secret
                try:
                    delete_project_secret(project, name)
                except OSError as e:
                    self._send_text(500, f"could not delete secret: {e}\n")
                    return
                project.append_ledger({"event": "env_delete", "name": name})
                self._send_text(200, "ok\n")
                return

            if self.path != "/":
                self._send_text(404, "POST / only\n")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8") if length else ""

            try:
                result, _trace = ail_run(str(project.app_path), input=body)
                value = result.value
                if _looks_like_error(value):
                    rendered = _render_value(value)
                    diagnostic = _diagnose_from_trace(_trace)
                    project.append_ledger({
                        "event": "request",
                        "path": "/",
                        "input_chars": len(body),
                        "ok": False,
                        "value_preview": str(rendered)[:200],
                        "diagnostic": diagnostic,
                    })
                    message = str(rendered)
                    if diagnostic:
                        message = message + "\n\n" + diagnostic
                    self._send_text(500, message + "\n")
                    return
                rendered = _render_value(value)
                response = (str(rendered) + "\n").encode("utf-8")
                project.append_ledger({
                    "event": "request",
                    "path": "/",
                    "input_chars": len(body),
                    "ok": True,
                    "value_preview": str(value)[:200],
                })
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                project.append_ledger({
                    "event": "request",
                    "path": "/",
                    "input_chars": len(body),
                    "ok": False,
                    "error": err,
                })
                self._send_text(500, err + "\n")

        def _send_text(self, code: int, text: str) -> None:
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def serve_project(
    project: Project, *, port: int, host: str = "127.0.0.1",
    watch: bool = True, logger=None, serve_only: bool = False,
) -> int:
    # Make `perform state.read/write/has/delete` resolve to this
    # project's .ail/state/keyval/ — outside an agentic context the
    # state effects return an explanatory error instead of crashing.
    import os as _os
    keyval_dir = project.state_dir / "state" / "keyval"
    keyval_dir.mkdir(parents=True, exist_ok=True)
    _os.environ.setdefault("AIL_STATE_DIR", str(keyval_dir))
    # `perform schedule.every(N)` writes to this file; the Scheduler
    # below polls it and drives recurring entry invocations.
    schedule_file = project.state_dir / "schedule.json"
    _os.environ.setdefault("AIL_SCHEDULE_FILE", str(schedule_file))
    # `perform human.approve(plan)` writes its pending record to
    # this directory. The authoring UI polls it and surfaces an
    # approve/decline card; without the env var the effect returns
    # a clean "no UI context" error.
    approval_dir = project.state_dir / "approvals"
    approval_dir.mkdir(parents=True, exist_ok=True)
    _os.environ.setdefault("AIL_APPROVAL_DIR", str(approval_dir))
    # v1.13.0: load any chat-entered secrets into env. `setdefault`
    # semantics: an explicit shell export still wins over the stored
    # value. File is gitignored by the scaffolder.
    from .authoring_chat import load_project_secrets
    load_project_secrets(project)
    """Block, serving the project until SIGINT. Returns exit code.

    If `watch` is True (default), a background thread polls INTENT.md
    and app.ail for edits and re-runs the declared tests on change.
    The HTTP server reads app.ail fresh on every request so the swap
    is automatic; the watcher's job is just to revalidate and warn.
    """
    from .ui import make_logger
    logger = logger or make_logger("friendly")
    handler = _make_handler(project, serve_only=serve_only)
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError as e:
        logger.port_bind_failed(host, port, str(e))
        return 3

    watcher = None
    if watch:
        from .watcher import Watcher
        watcher = Watcher(project, logger=logger)
        watcher.start()
        logger.watcher_watching()

    # Start the scheduler unconditionally — if the program never calls
    # `perform schedule.every(...)`, the file stays absent and the
    # scheduler thread idles at ~0.5s polls, cheap enough to ignore.
    from .scheduler import Scheduler

    def _invoke_scheduled_tick():
        try:
            result, _trace = ail_run(str(project.app_path), input="")
            value = result.value
            if _looks_like_error(value):
                project.append_ledger({
                    "event": "schedule_tick",
                    "ok": False,
                    "value_preview": str(_render_value(value))[:200],
                })
            else:
                project.append_ledger({
                    "event": "schedule_tick",
                    "ok": True,
                    "value_preview": str(value)[:200],
                })
        except Exception as e:
            project.append_ledger({
                "event": "schedule_tick",
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            })

    scheduler = Scheduler(
        schedule_file=schedule_file,
        invoke=_invoke_scheduled_tick,
        logger=logger,
    )
    scheduler.start()

    project.append_ledger({
        "event": "serve_start", "host": host, "port": port, "watch": watch,
    })
    logger.serving(host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.shutting_down()
    finally:
        scheduler.stop()
        if watcher is not None:
            watcher.stop()
        server.server_close()
        project.append_ledger({"event": "serve_stop"})
    return 0
