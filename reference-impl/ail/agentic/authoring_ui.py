"""HTML for the project-authoring chat.

Served on GET / when the project is fresh (no authored_at marker yet
and no meaningful app.ail on disk). After the user clicks "Run it now"
the marker is written and subsequent GET / serves the regular service
UI (view.html or the default textarea page).

Kept in Python as a string template so there's no second asset
directory to ship with the wheel.
"""
from __future__ import annotations

from html import escape


def render_authoring_page(
    *, project_name: str, host: str, port: int, history: list
) -> str:
    """Render the chat shell. History is seeded into the page so a
    reload preserves the conversation across restarts."""
    name = escape(project_name or "ail project")
    history_json = _history_to_json_embed(history)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} — ail authoring</title>
  <style>
    :root {{
      --bg: #fafafa; --fg: #111; --muted: #6b7280;
      --accent: #111; --border: #e5e7eb; --card: #fff;
      --user-bg: #111; --user-fg: #fff;
      --agent-bg: #fff; --agent-fg: #111;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; height: 100%;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                   "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
      background: var(--bg); color: var(--fg);
      -webkit-font-smoothing: antialiased; }}
    .page {{ max-width: 720px; margin: 0 auto; padding: 24px;
      display: flex; flex-direction: column;
      min-height: 100vh; }}
    header {{ margin-bottom: 12px; }}
    h1 {{ margin: 0; font-size: 18px; letter-spacing: -0.01em; }}
    .sub {{ color: var(--muted); font-size: 13px; margin-top: 2px; }}
    .thread {{ flex: 1; overflow-y: auto; padding: 12px 0;
      display: flex; flex-direction: column; gap: 10px; }}
    .turn {{ display: flex; }}
    .turn.user {{ justify-content: flex-end; }}
    .bubble {{ max-width: 80%; padding: 10px 14px;
      border-radius: 12px; font-size: 15px; line-height: 1.55;
      white-space: pre-wrap; word-break: break-word; }}
    .user .bubble {{ background: var(--user-bg); color: var(--user-fg);
      border-bottom-right-radius: 4px; }}
    .agent .bubble {{ background: var(--agent-bg); color: var(--agent-fg);
      border: 1px solid var(--border); border-bottom-left-radius: 4px; }}
    .files {{ display: flex; flex-direction: column; gap: 4px;
      margin: 4px 0 10px 14px; font-size: 12px; color: var(--muted); }}
    .file-tag {{ display: inline-block; padding: 2px 8px;
      background: #f3f4f6; border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px; }}
    .action-bar {{ margin: 8px 0; display: flex;
      justify-content: flex-start; padding-left: 14px; }}
    .run-btn {{ font-family: inherit; font-size: 14px; font-weight: 500;
      padding: 10px 20px; border-radius: 8px; border: 0;
      background: #047857; color: #fff; cursor: pointer; }}
    .run-btn:hover {{ opacity: 0.9; }}
    .composer {{ position: sticky; bottom: 0; padding: 12px 0;
      background: var(--bg); border-top: 1px solid var(--border);
      display: flex; gap: 8px; align-items: flex-end; }}
    textarea {{ flex: 1; font-family: inherit; font-size: 15px;
      padding: 10px 12px; border: 1px solid var(--border);
      border-radius: 8px; background: #fff; color: var(--fg);
      resize: none; line-height: 1.4; max-height: 160px; }}
    textarea:focus {{ outline: 2px solid #111; outline-offset: -1px; }}
    button.send {{ font-family: inherit; font-size: 14px; font-weight: 500;
      padding: 10px 18px; border-radius: 8px; border: 0;
      background: var(--accent); color: #fff; cursor: pointer; }}
    button.send:hover {{ opacity: 0.9; }}
    button:disabled {{ opacity: 0.5; cursor: wait; }}
    .hint {{ color: var(--muted); font-size: 13px; text-align: center;
      padding: 24px 0; }}
    .err {{ color: #b91c1c; background: #fef2f2;
      border: 1px solid #fecaca; padding: 10px 14px; border-radius: 8px;
      font-size: 14px; margin: 8px 0; }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <h1>{name}</h1>
      <div class="sub">ail authoring · {escape(host)}:{port} · 채팅으로 프로젝트를 만드세요</div>
    </header>

    <div class="thread" id="thread">
      <div class="hint" id="hint">
        대화로 프로젝트를 만들어요. 어떤 걸 만들고 싶은지 아래에 입력하세요.<br>
        <small>Build by chatting. Describe what you want to make below.</small>
      </div>
    </div>

    <form class="composer" id="composer" onsubmit="return onSend(event);">
      <textarea id="msg" rows="1" placeholder="예: 텍스트 감정을 분석하는 서비스를 만들고 싶어요"
                autocomplete="off" spellcheck="false"></textarea>
      <button type="submit" class="send" id="send">전송</button>
    </form>
  </div>

  <script>
    const thread = document.getElementById('thread');
    const msgEl = document.getElementById('msg');
    const sendBtn = document.getElementById('send');
    const hint = document.getElementById('hint');

    // Replay history embedded by the server on first render.
    const INITIAL_HISTORY = {history_json};
    if (INITIAL_HISTORY.length > 0) {{
      hint.remove();
      INITIAL_HISTORY.forEach(entry => {{
        addUser(entry.user);
        addAgent(entry.reply, entry.files || [], entry.action || null);
      }});
      scrollBottom();
    }}

    msgEl.addEventListener('input', () => {{
      msgEl.style.height = 'auto';
      msgEl.style.height = Math.min(msgEl.scrollHeight, 160) + 'px';
    }});

    msgEl.addEventListener('keydown', (e) => {{
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {{
        document.getElementById('composer').requestSubmit();
      }}
    }});

    function scrollBottom() {{
      requestAnimationFrame(() => {{
        thread.scrollTop = thread.scrollHeight;
      }});
    }}

    function addUser(text) {{
      const turn = document.createElement('div');
      turn.className = 'turn user';
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      turn.appendChild(bubble);
      thread.appendChild(turn);
    }}

    function addAgent(reply, files, action) {{
      const turn = document.createElement('div');
      turn.className = 'turn agent';
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = reply;
      turn.appendChild(bubble);
      thread.appendChild(turn);

      if (files && files.length) {{
        const box = document.createElement('div');
        box.className = 'files';
        files.forEach(f => {{
          const tag = document.createElement('span');
          tag.className = 'file-tag';
          if (f.skipped) {{
            tag.textContent = '✗ ' + f.path + ' — ' + f.skipped;
            tag.style.color = '#b91c1c';
          }} else {{
            tag.textContent = '✓ ' + f.path + ' (' + f.bytes + ' bytes)';
          }}
          box.appendChild(tag);
        }});
        thread.appendChild(box);
      }}

      if (action === 'ready_to_run') {{
        const bar = document.createElement('div');
        bar.className = 'action-bar';
        const btn = document.createElement('button');
        btn.className = 'run-btn';
        btn.textContent = '▶ 실행해보기 / Run it now';
        btn.onclick = runNow;
        bar.appendChild(btn);
        thread.appendChild(bar);
      }}
    }}

    function addError(msg) {{
      const d = document.createElement('div');
      d.className = 'err';
      d.textContent = msg;
      thread.appendChild(d);
    }}

    async function send(userText) {{
      hint && hint.remove();
      addUser(userText);
      scrollBottom();

      sendBtn.disabled = true;
      msgEl.disabled = true;

      // Placeholder "…" bubble while waiting.
      const pendingTurn = document.createElement('div');
      pendingTurn.className = 'turn agent';
      const pendingBubble = document.createElement('div');
      pendingBubble.className = 'bubble';
      pendingBubble.textContent = '…';
      pendingBubble.style.color = '#6b7280';
      pendingTurn.appendChild(pendingBubble);
      thread.appendChild(pendingTurn);
      scrollBottom();

      try {{
        const r = await fetch('/authoring-chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'text/plain; charset=utf-8' }},
          body: userText,
        }});
        pendingTurn.remove();
        const text = await r.text();
        if (!r.ok) {{
          addError('오류: ' + text);
          return;
        }}
        let data;
        try {{
          data = JSON.parse(text);
        }} catch (e) {{
          addError('응답 파싱 실패: ' + text.slice(0, 200));
          return;
        }}
        addAgent(data.reply || '(empty)', data.files || [], data.action || null);
      }} catch (e) {{
        pendingTurn.remove();
        addError('네트워크 오류: ' + e.message);
      }} finally {{
        sendBtn.disabled = false;
        msgEl.disabled = false;
        msgEl.value = '';
        msgEl.style.height = 'auto';
        msgEl.focus();
        scrollBottom();
      }}
    }}

    function onSend(e) {{
      e.preventDefault();
      const t = msgEl.value.trim();
      if (!t) return false;
      send(t);
      return false;
    }}

    async function runNow() {{
      try {{
        const r = await fetch('/authoring-complete', {{ method: 'POST' }});
        if (!r.ok) {{
          addError('실행 전환 실패: ' + await r.text());
          return;
        }}
        // Reload — server now serves the service UI.
        window.location.href = '/';
      }} catch (e) {{
        addError('네트워크 오류: ' + e.message);
      }}
    }}

    msgEl.focus();
  </script>
</body>
</html>
"""


def _history_to_json_embed(history: list) -> str:
    """Serialize chat history for embedding in the page. Each entry is
    sanitized to only include the fields the UI needs."""
    import json
    safe = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        safe.append({
            "user": str(entry.get("user", "")),
            "reply": str(entry.get("reply", "")),
            "files": entry.get("files", []) if isinstance(entry.get("files"), list) else [],
            "action": entry.get("action") if entry.get("action") in ("ready_to_run", "ready_to_deploy") else None,
        })
    # Safe to inline since we control all field types.
    return json.dumps(safe, ensure_ascii=False).replace("</", "<\\/")
