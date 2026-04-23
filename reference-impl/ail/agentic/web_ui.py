"""Minimal browser UI for a running agentic service.

When the user opens http://<host>:<port>/ in a browser they get a
single-page form: a textarea, a Send button, a result area, and
the project's description from INTENT.md so they can tell what
service they're looking at.

No framework, no npm, no build step. Stdlib-only: the HTML is
rendered as a string by render_page() and served from the existing
stdlib HTTPServer.

The same endpoint still accepts `POST /` with a raw text body
(the machine-friendly path used by curl and scripts). Browsers
submit the form via `fetch('/', { method: 'POST' ...})` — same
endpoint, different content origin.

Localization: render_page() detects Hangul in the project preamble
and flips the few UI strings to Korean. The non-developer audience
we target most likely reads in only one of those two languages; if
others matter we'll revisit.
"""
from __future__ import annotations

from html import escape
from typing import Optional

from .ui import detect_language


def entry_uses_input(source: str) -> bool:
    """True if the program's `entry` body references its input parameter.

    Used by the browser UI to decide whether to render an input textarea:
    an agentic project whose entry ignores its input (e.g. a visit-counter
    that only reads from state) should not confuse the user with a typing
    box that does nothing.

    Defaults to True on any parse failure or missing entry — showing the
    input box on an unknown program is safer than hiding it from a program
    that does use input.
    """
    try:
        from ..parser import parse
        from ..parser.ast import EntryDecl
    except Exception:
        return True

    try:
        program = parse(source or "")
    except Exception:
        return True

    entry = None
    for decl in getattr(program, "declarations", []) or []:
        if isinstance(decl, EntryDecl):
            entry = decl
            break
    if entry is None:
        return True
    if not entry.params:
        return False

    param_name = entry.params[0][0]
    return _body_references(entry.body, param_name)


def _body_references(body, name: str) -> bool:
    """Walk any AST fragment (list, dataclass, etc.) looking for an
    Identifier whose `name` matches. Generic so future AST node types
    don't silently escape the check."""
    from ..parser.ast import Identifier
    from dataclasses import fields, is_dataclass

    def walk(node) -> bool:
        if isinstance(node, Identifier):
            return node.name == name
        if isinstance(node, (list, tuple)):
            return any(walk(x) for x in node)
        if isinstance(node, dict):
            return any(walk(v) for v in node.values())
        if is_dataclass(node):
            return any(walk(getattr(node, f.name)) for f in fields(node))
        return False

    return walk(body)


_STRINGS = {
    "en": {
        "placeholder": "Type your input here",
        "send": "Send",
        "result_label": "Result",
        "empty_result": "(response will appear here)",
        "error_prefix": "Error",
        "auto_reload_tip": (
            "Edit INTENT.md and save — this service will re-check "
            "your tests and update itself automatically. No restart "
            "needed."
        ),
        "edit_here_tip": "Tell it what you want, in plain language:",
        "about_label": "About this service",
        "run_button": "Run",
        "no_input_hint": "This service takes no input. Press Run to invoke it.",
    },
    "ko": {
        "placeholder": "여기에 입력을 적어 보세요",
        "send": "보내기",
        "result_label": "결과",
        "empty_result": "(여기에 응답이 나타납니다)",
        "error_prefix": "오류",
        "auto_reload_tip": (
            "INTENT.md를 편집하고 저장하면 이 서비스가 자동으로 "
            "테스트를 다시 돌리고 갱신됩니다. 재시작할 필요 없습니다."
        ),
        "edit_here_tip": "평범한 말로 무엇을 원하는지 입력하세요:",
        "about_label": "이 서비스에 관하여",
        "run_button": "실행",
        "no_input_hint": "이 서비스는 입력이 필요 없습니다. 실행 버튼을 누르세요.",
    },
}


def render_page(
    *,
    project_name: str,
    intent_preamble: str,
    host: str,
    port: int,
    input_used: bool = True,
) -> str:
    """Render the single-page form as an HTML string.

    When `input_used` is False, the textarea is replaced with a short
    note and a bare Run button — a service whose `entry` ignores its
    input shouldn't show a typing box that does nothing.
    """
    lang = detect_language(intent_preamble)
    t = _STRINGS.get(lang, _STRINGS["en"])

    # Escape user-controlled content that lands in the DOM.
    name = escape(project_name or "ail project")
    preamble_lines = [escape(line) for line in (intent_preamble or "").splitlines()]
    preamble_html = "<br>".join(preamble_lines) or "<em>(no description in INTENT.md)</em>"
    # JS string literals for the two runtime-interpolated labels.
    err_json = _json_string(t["error_prefix"])
    empty_json = _json_string(t["empty_result"])

    button_label = t["send"] if input_used else t["run_button"]
    if input_used:
        input_block = (
            f'      <label class="tip" for="input">{escape(t["edit_here_tip"])}</label>\n'
            f'      <textarea id="input"\n'
            f'                placeholder="{escape(t["placeholder"])}"></textarea>\n'
            f'      <div class="row">\n'
            f'        <span class="status" id="status"></span>\n'
            f'        <span class="spacer"></span>\n'
            f'        <button id="send">{escape(button_label)}</button>\n'
            f'      </div>'
        )
    else:
        input_block = (
            f'      <div class="tip">{escape(t["no_input_hint"])}</div>\n'
            f'      <div class="row">\n'
            f'        <span class="status" id="status"></span>\n'
            f'        <span class="spacer"></span>\n'
            f'        <button id="send">{escape(button_label)}</button>\n'
            f'      </div>'
        )

    # All CSS + JS inline — one HTTP response, no asset pipeline.
    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} — ail</title>
  <style>
    :root {{
      --bg: #fafafa;
      --fg: #111;
      --muted: #6b7280;
      --accent: #111;
      --border: #e5e7eb;
      --card: #fff;
      --err: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0; padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                   "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
      background: var(--bg); color: var(--fg);
      -webkit-font-smoothing: antialiased;
    }}
    .page {{
      max-width: 680px;
      margin: 48px auto;
      padding: 0 24px;
    }}
    h1 {{
      font-size: 20px; font-weight: 600;
      margin: 0 0 6px 0; letter-spacing: -0.01em;
    }}
    .endpoint {{
      color: var(--muted); font-size: 13px;
      margin-bottom: 32px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .card h2 {{
      font-size: 13px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.08em;
      color: var(--muted);
      margin: 0 0 12px 0;
    }}
    .about {{ line-height: 1.6; color: #222; }}
    label.tip {{
      display: block; font-size: 14px;
      margin: 0 0 8px 0; color: var(--muted);
    }}
    textarea {{
      width: 100%;
      min-height: 120px;
      padding: 12px; font-family: inherit; font-size: 15px;
      border: 1px solid var(--border); border-radius: 8px;
      resize: vertical; background: #fff; color: var(--fg);
      line-height: 1.5;
    }}
    textarea:focus {{ outline: 2px solid #111; outline-offset: -1px; }}
    .row {{
      display: flex; gap: 12px; align-items: center;
      margin-top: 12px;
    }}
    .row .spacer {{ flex: 1; }}
    button {{
      font-family: inherit; font-size: 14px; font-weight: 500;
      padding: 10px 20px; border-radius: 8px; border: 0;
      background: var(--accent); color: #fff; cursor: pointer;
      transition: opacity 0.15s;
    }}
    button:hover {{ opacity: 0.85; }}
    button:disabled {{ opacity: 0.5; cursor: wait; }}
    .result {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 14px; line-height: 1.5;
      white-space: pre-wrap; word-break: break-word;
      padding: 16px; background: #f3f4f6; border-radius: 8px;
      min-height: 48px; color: #111;
    }}
    .result.empty {{ color: var(--muted); font-style: italic; }}
    .result.err {{ color: var(--err); background: #fef2f2; }}
    .result.html {{
      font-family: inherit; white-space: normal; background: #fff;
      padding: 0; border: 1px solid var(--border);
    }}
    .tip {{
      font-size: 13px; color: var(--muted); line-height: 1.5;
    }}
    .tip.callout {{
      padding: 12px 14px; background: #fff8e1;
      border: 1px solid #fde68a; border-radius: 8px;
      color: #92400e; margin-top: 16px;
    }}
    .status {{ font-size: 12px; color: var(--muted); }}
  </style>
</head>
<body>
  <div class="page">
    <h1>{name}</h1>
    <div class="endpoint">http://{escape(host)}:{port}/</div>

    <div class="card">
      <h2>{escape(t["about_label"])}</h2>
      <div class="about">{preamble_html}</div>
    </div>

    <div class="card">
{input_block}
    </div>

    <div class="card">
      <h2>{escape(t["result_label"])}</h2>
      <div class="result empty" id="result">
        {escape(t["empty_result"])}
      </div>
    </div>

    <div class="tip callout">{escape(t["auto_reload_tip"])}</div>
  </div>

  <script>
    const inputEl = document.getElementById("input");
    const btn = document.getElementById("send");
    const resultEl = document.getElementById("result");
    const statusEl = document.getElementById("status");
    const ERR = {err_json};
    const EMPTY = {empty_json};

    async function send() {{
      btn.disabled = true;
      statusEl.textContent = "…";
      resultEl.classList.remove("err");
      resultEl.classList.add("empty");
      resultEl.textContent = EMPTY;
      try {{
        const r = await fetch("/", {{
          method: "POST",
          headers: {{ "Content-Type": "text/plain; charset=utf-8" }},
          body: inputEl ? inputEl.value : "",
        }});
        const text = await r.text();
        if (r.ok) {{
          resultEl.classList.remove("empty", "err");
          const ct = (r.headers.get("Content-Type") || "").toLowerCase();
          if (ct.indexOf("text/html") !== -1) {{
            // entry returned HTML — render it, don't escape it.
            // The author is an LLM the user is running locally; the
            // output is no more dangerous than the JS they chose to
            // serve. This is the same trust boundary as `ail run`.
            resultEl.innerHTML = text;
            resultEl.classList.add("html");
          }} else {{
            resultEl.classList.remove("html");
            resultEl.textContent = text;
          }}
          statusEl.textContent = "";
        }} else {{
          resultEl.classList.remove("empty");
          resultEl.classList.add("err");
          resultEl.textContent = ERR + ": " + text;
          statusEl.textContent = "HTTP " + r.status;
        }}
      }} catch (e) {{
        resultEl.classList.remove("empty");
        resultEl.classList.add("err");
        resultEl.textContent = ERR + ": " + e.message;
        statusEl.textContent = "";
      }} finally {{
        btn.disabled = false;
      }}
    }}

    btn.addEventListener("click", send);
    if (inputEl) {{
      inputEl.addEventListener("keydown", (e) => {{
        if ((e.metaKey || e.ctrlKey) && e.key === "Enter") send();
      }});
    }}
  </script>
</body>
</html>
"""


def _json_string(s: str) -> str:
    """Minimal JSON-style quoted string for embedding in the inline
    script. We don't import json just to quote two labels."""
    escaped = (s.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r"))
    return f'"{escaped}"'


def extract_preamble(intent_md_text: str) -> str:
    """Pull the paragraph between the title and the first ## header —
    this is what shows up under "About this service" in the UI."""
    import re
    title_m = re.search(r"^#\s+.+?$", intent_md_text or "", re.MULTILINE)
    start = title_m.end() if title_m else 0
    tail = (intent_md_text or "")[start:]
    header_m = re.search(r"^##\s+", tail, re.MULTILINE)
    pre = tail[:header_m.start()] if header_m else tail
    return pre.strip()
