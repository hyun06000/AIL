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
    *, project_name: str, host: str, port: int, history: list,
    programs: list | None = None,
    session_total_tokens: int = 0,
) -> str:
    """Render the chat shell. History is seeded into the page so a
    reload preserves the conversation across restarts.

    `programs` is the current per-`.ail` metadata (from
    `list_project_programs`). Seeding it into the page lets the Run
    widget show the real parse state / env_required / input_hint on
    initial render — without it the widget falls back to a dummy
    `{name: 'app.ail', parses: true, ...}` and a broken program
    looks like it has a working textarea.
    """
    name = escape(project_name or "ail project")
    history_json = _history_to_json_embed(history)
    # Safely quoted project name for embedding in JS.
    import json as _json
    programs_json = _json.dumps(programs or [])
    json_project_name = _json.dumps(project_name or "ail-project")
    session_total_tokens_json = _json.dumps(int(session_total_tokens))

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
      height: 100vh; overflow: hidden; }}
    #file-tree {{
      position: fixed; top: 0; left: 0; width: 260px; height: 100vh;
      padding: 16px 12px; border-right: 1px solid var(--border);
      background: #fafafa; overflow-y: auto; font-size: 12px;
      box-sizing: border-box; z-index: 100; transition: transform 0.2s;
    }}
    #file-tree.collapsed {{ transform: translateX(-252px); }}
    #file-tree h3 {{ font-size: 12px; font-weight: 600; margin: 0 0 8px;
      color: var(--muted); letter-spacing: 0.04em;
      text-transform: uppercase; font-family: inherit; }}
    #file-tree .ft-item {{ padding: 6px 8px; border-radius: 4px;
      margin-bottom: 2px; cursor: pointer; }}
    #file-tree .ft-item:hover {{ background: #e5e7eb; }}
    #file-tree .ft-name {{ font-family: ui-monospace, Menlo, monospace;
      font-weight: 500; color: #111; }}
    #file-tree .ft-bad .ft-name {{ color: #b91c1c; }}
    #file-tree .ft-caption {{ color: #6b7280; margin-top: 2px;
      line-height: 1.35; font-size: 11px; }}
    #file-tree .ft-meta {{ color: #9ca3af; font-size: 10px;
      margin-top: 1px; font-family: ui-monospace, Menlo, monospace; }}
    #file-tree-toggle {{ position: fixed; top: 12px; left: 268px;
      z-index: 101; background: #fff; border: 1px solid var(--border);
      padding: 4px 8px; border-radius: 4px; cursor: pointer;
      font-family: inherit; font-size: 11px; color: var(--muted);
      transition: left 0.2s; }}
    #file-tree.collapsed + #file-tree-toggle {{ left: 12px; }}
    @media (max-width: 900px) {{
      #file-tree {{ transform: translateX(-252px); }}
      #file-tree.open {{ transform: translateX(0); }}
    }}
    header {{ margin-bottom: 12px; flex-shrink: 0; }}
    h1 {{ margin: 0; font-size: 18px; letter-spacing: -0.01em; }}
    .sub {{ color: var(--muted); font-size: 13px; margin-top: 2px; }}
    .sub a {{ color: var(--muted); text-decoration: underline;
      text-decoration-color: #d1d5db; cursor: pointer; }}
    .sub a:hover {{ color: #111; text-decoration-color: #111; }}
    .thread {{ flex: 1; overflow-y: auto; padding: 12px 0;
      display: flex; flex-direction: column; gap: 10px;
      scrollbar-width: none; }}
    .thread::-webkit-scrollbar {{ display: none; }}
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
    .file-tag {{ display: inline-flex; align-items: center; gap: 4px;
      padding: 2px 8px; background: #f3f4f6; border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px; cursor: pointer; user-select: none; }}
    .file-tag:hover {{ background: #e5e7eb; }}
    .file-tag .toggle-arrow {{ font-style: normal; font-size: 9px; opacity: 0.6; }}
    .file-preview {{ display: none; margin: 2px 0 4px 0;
      background: #1e1e2e; border-radius: 6px; overflow: hidden; }}
    .file-preview.open {{ display: block; }}
    .file-preview pre {{ margin: 0; padding: 12px 14px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px; color: #cdd6f4; white-space: pre; overflow-x: auto;
      max-height: 400px; overflow-y: auto; }}
    .action-bar {{ margin: 8px 0; display: flex; flex-direction: column;
      gap: 6px; align-items: flex-start; padding-left: 14px; }}
    .run-btn {{ font-family: inherit; font-size: 14px; font-weight: 500;
      padding: 10px 20px; border-radius: 8px; border: 0;
      background: #047857; color: #fff; cursor: pointer; }}
    .run-btn:hover {{ opacity: 0.9; }}
    .serve-btn {{ font-family: inherit; font-size: 14px; font-weight: 500;
      padding: 10px 20px; border-radius: 8px; border: 1px solid #047857;
      background: #fff; color: #047857; cursor: pointer; }}
    .serve-btn:hover {{ background: #f0fdf4; }}
    .run-card {{ background: #fff; border: 1px solid var(--border);
      border-radius: 10px; padding: 14px 16px; margin: 4px 0 10px 14px;
      max-width: 80%; display: flex; flex-direction: column; gap: 10px; }}
    .run-card.service {{ background: #f0fdf4; border-color: #bbf7d0; }}
    .run-card .title {{ font-size: 13px; font-weight: 600;
      color: #047857; text-transform: uppercase; letter-spacing: 0.06em; }}
    .run-card .desc {{ font-size: 13px; color: #374151; }}
    .run-card .share-link {{ font-size: 13px; color: #047857;
      text-decoration: none; display: inline-block; padding: 4px 0; }}
    .run-card .share-link:hover {{ text-decoration: underline; }}
    .run-card textarea {{ font-family: inherit; font-size: 14px;
      padding: 8px 10px; border: 1px solid var(--border);
      border-radius: 6px; background: #fff; color: #111;
      resize: vertical; min-height: 36px; max-height: 160px;
      line-height: 1.4; }}
    .run-card textarea:focus {{ outline: 2px solid #111;
      outline-offset: -1px; }}
    .run-card .run-inline {{ align-self: flex-start;
      font-family: inherit; font-size: 13px; font-weight: 500;
      padding: 8px 16px; border-radius: 6px; border: 0;
      background: #047857; color: #fff; cursor: pointer; }}
    .run-card .run-inline:hover {{ opacity: 0.9; }}
    .run-card .run-inline:disabled {{ opacity: 0.5; cursor: wait; }}
    .program-picker {{ display: flex; align-items: center; gap: 8px;
      font-size: 12px; color: #374151;
      flex-wrap: wrap; min-width: 0; max-width: 100%; }}
    .program-picker select {{ font-family: ui-monospace, Menlo,
      monospace; font-size: 12px; padding: 4px 8px;
      border: 1px solid var(--border); border-radius: 4px;
      background: #fff;
      max-width: 100%; min-width: 0;
      text-overflow: ellipsis; overflow: hidden; }}
    .program-picker .flag {{ font-size: 11px; color: #6b7280;
      font-family: ui-monospace, Menlo, monospace;
      min-width: 0; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap; }}
    .program-picker .flag.bad {{ color: #b91c1c; }}
    /* Also constrain the Run card itself so long dropdown labels
       don't push its width past the chat bubble. */
    .run-card {{ min-width: 0; }}
    .run-card select {{ max-width: 100%; }}
    .env-block {{ border: 1px solid #fde68a; background: #fffbeb;
      border-radius: 6px; padding: 10px 12px; display: flex;
      flex-direction: column; gap: 6px; }}
    .env-block .env-title {{ font-size: 12px; font-weight: 600;
      color: #92400e; }}
    .env-row {{ display: flex; gap: 6px; align-items: center; }}
    .env-row label {{ font-family: ui-monospace, SFMono-Regular, Menlo,
      monospace; font-size: 12px; min-width: 180px; color: #111; }}
    .env-row input {{ flex: 1; font-family: ui-monospace, Menlo,
      monospace; font-size: 12px; padding: 6px 8px;
      border: 1px solid var(--border); border-radius: 4px;
      background: #fff; color: #111; }}
    .env-row input:focus {{ outline: 2px solid #111; outline-offset: -1px; }}
    .env-row button {{ font-family: inherit; font-size: 12px;
      padding: 6px 10px; border-radius: 4px; border: 0;
      background: #111; color: #fff; cursor: pointer; }}
    .env-row .status {{ font-size: 11px; color: #047857;
      font-family: ui-monospace, Menlo, monospace; }}
    .env-row .status.err {{ color: #b91c1c; }}
    .run-result {{ background: #f0fdf4;
      border: 1px solid #bbf7d0; border-radius: 10px;
      padding: 12px 14px; margin: 4px 0 8px 14px; max-width: 80%; }}
    .run-result.err {{ background: #fef2f2; border-color: #fecaca; }}
    .run-result .label {{ font-size: 12px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.06em;
      color: #047857; margin-bottom: 6px; }}
    .run-result.err .label {{ color: #b91c1c; }}
    .run-result pre {{ margin: 0; white-space: pre-wrap;
      word-break: break-word; font-family: ui-monospace,
      SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px;
      line-height: 1.5; color: #111; }}
    .md-body {{ font-size: 14px; line-height: 1.65;
      color: #111; word-break: break-word; }}
    .md-body h1 {{ font-size: 1.25em; font-weight: 700;
      margin: 0.6em 0 0.3em; }}
    .md-body h2 {{ font-size: 1.1em; font-weight: 700;
      margin: 0.6em 0 0.2em; }}
    .md-body h3 {{ font-size: 1em; font-weight: 600;
      margin: 0.5em 0 0.2em; }}
    .md-body p {{ margin: 0.4em 0; }}
    .md-body ul, .md-body ol {{
      margin: 0.3em 0; padding-left: 1.4em; }}
    .md-body li {{ margin: 0.15em 0; }}
    .md-body code {{ font-family: ui-monospace, Menlo,
      monospace; font-size: 0.88em; background: rgba(0,0,0,0.07);
      padding: 1px 4px; border-radius: 3px; }}
    .md-body pre {{ background: rgba(0,0,0,0.06);
      padding: 8px 10px; border-radius: 6px; overflow-x: auto;
      font-size: 12px; margin: 0.4em 0; white-space: pre; }}
    .md-body pre code {{ background: none; padding: 0; }}
    .md-body a {{ color: #0e7490; text-decoration: underline; }}
    .md-body hr {{ border: none; border-top: 1px solid #d1d5db;
      margin: 0.6em 0; }}
    /* Bubbles that hold rendered markdown get no white-space: pre-wrap
       (the default .bubble rule) — headings and lists are already
       block-formatted by the markdown renderer. */
    .bubble.md-body {{ white-space: normal; max-width: 90%; }}
    .bubble.md-body table {{ border-collapse: collapse; margin: 8px 0;
      font-size: 13px; }}
    .bubble.md-body th, .bubble.md-body td {{
      border: 1px solid #e5e7eb; padding: 6px 10px; text-align: left;
      vertical-align: top; }}
    .bubble.md-body th {{ background: #f3f4f6; font-weight: 600; }}
    .bubble.md-body blockquote {{ margin: 8px 0; padding: 4px 12px;
      border-left: 3px solid #d1d5db; color: #4b5563;
      background: #f9fafb; }}
    .bubble.md-body pre {{ margin: 8px 0; padding: 10px 12px;
      background: #f3f4f6; border-radius: 6px; overflow-x: auto;
      font-size: 12px; line-height: 1.5; }}
    .bubble.md-body code {{ background: #f3f4f6; padding: 1px 4px;
      border-radius: 3px; font-size: 0.9em;
      font-family: ui-monospace, Menlo, monospace; }}
    .bubble.md-body pre code {{ background: transparent; padding: 0; }}
    .run-result .md-body strong {{ font-weight: 700; }}
    .run-result .md-body em {{ font-style: italic; }}
    .run-result .diag {{ margin-top: 8px; padding-top: 8px;
      border-top: 1px solid #fecaca; font-size: 12px;
      color: #6b7280; white-space: pre-wrap; }}
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
    /* Settings panel */
    .settings-overlay {{ display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.35); z-index: 900; }}
    .settings-overlay.open {{ display: block; }}
    .settings-panel {{ position: fixed; top: 0; right: -420px; width: 400px;
      height: 100vh; background: #fff; border-left: 1px solid var(--border);
      box-shadow: -4px 0 24px rgba(0,0,0,0.10); z-index: 901;
      transition: right 0.22s ease; display: flex; flex-direction: column;
      overflow: hidden; }}
    .settings-panel.open {{ right: 0; }}
    .settings-hdr {{ padding: 18px 20px 14px; border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between; }}
    .settings-hdr h2 {{ margin: 0; font-size: 15px; font-weight: 600; }}
    .settings-close {{ background: none; border: none; font-size: 18px;
      cursor: pointer; color: var(--muted); padding: 2px 6px;
      border-radius: 4px; }}
    .settings-close:hover {{ background: #f3f4f6; color: #111; }}
    .settings-body {{ flex: 1; overflow-y: auto; padding: 16px 20px; }}
    .settings-section-title {{ font-size: 11px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.08em;
      color: var(--muted); margin: 0 0 10px; }}
    .senv-row {{ display: flex; align-items: center; gap: 8px;
      padding: 8px 0; border-bottom: 1px solid #f3f4f6; }}
    .senv-name {{ font-family: ui-monospace, Menlo, monospace;
      font-size: 12px; color: #111; flex: 1; min-width: 0;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .senv-mask {{ font-size: 12px; color: var(--muted);
      letter-spacing: 2px; flex-shrink: 0; }}
    .senv-btn {{ font-family: inherit; font-size: 11px; padding: 4px 8px;
      border-radius: 4px; border: 1px solid var(--border);
      background: #fff; cursor: pointer; color: #374151; white-space: nowrap; }}
    .senv-btn:hover {{ background: #f3f4f6; }}
    .senv-btn.del {{ border-color: #fecaca; color: #b91c1c; }}
    .senv-btn.del:hover {{ background: #fef2f2; }}
    .senv-edit-row {{ padding: 8px 0 10px; border-bottom: 1px solid #f3f4f6; }}
    .senv-edit-row .senv-name {{ margin-bottom: 6px; }}
    .senv-edit-row input {{ width: 100%; font-family: ui-monospace, Menlo, monospace;
      font-size: 12px; padding: 6px 8px; border: 1px solid var(--border);
      border-radius: 4px; background: #fff; margin-bottom: 6px; }}
    .senv-edit-row input:focus {{ outline: 2px solid #111; outline-offset: -1px; }}
    .senv-edit-actions {{ display: flex; gap: 6px; }}
    .settings-add {{ padding: 16px 20px; border-top: 1px solid var(--border);
      display: flex; flex-direction: column; gap: 6px; }}
    .settings-add input {{ font-family: ui-monospace, Menlo, monospace;
      font-size: 12px; padding: 7px 10px; border: 1px solid var(--border);
      border-radius: 4px; background: #fff; }}
    .settings-add input:focus {{ outline: 2px solid #111; outline-offset: -1px; }}
    .settings-add-btn {{ font-family: inherit; font-size: 13px; font-weight: 500;
      padding: 8px 14px; border-radius: 6px; border: 0;
      background: #111; color: #fff; cursor: pointer; align-self: flex-start; }}
    .settings-add-btn:hover {{ opacity: 0.85; }}
    .settings-empty {{ color: var(--muted); font-size: 13px;
      text-align: center; padding: 24px 0; }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <h1>{name}</h1>
      <div class="sub">ail authoring · {escape(host)}:{port} · 채팅으로 프로젝트를 만드세요
        · <a href="#" id="export-chat">대화 내보내기 / Export</a>
        · <a href="#" id="copy-chat">복사 / Copy</a>
        · <a href="#" id="save-image">이미지로 저장 / Save image</a>
        · <a href="#" id="open-settings">⚙ 설정 / Settings</a>
        · <a href="#" id="reset-chat" style="color:#b91c1c;">대화 초기화 / Reset chat</a>
      </div>
    </header>

    <aside id="file-tree">
      <h3>📁 프로젝트 / Project files</h3>
      <div id="file-tree-body"><span style="color:#9ca3af">로딩…</span></div>
    </aside>
    <button id="file-tree-toggle" onclick="toggleFileTree()">◀ hide</button>

    <div id="deploy-bar" style="display:flex;align-items:center;gap:10px;
         padding:8px 12px;margin-bottom:6px;border:1px solid #e5e7eb;
         border-radius:8px;background:#fff;font-size:13px;"></div>
    <details id="deploy-help" style="margin-bottom:8px;padding:0 4px;
             font-size:12px;color:#4b5563;line-height:1.55;">
      <summary style="cursor:pointer;color:#6b7280;padding:2px 0;
               user-select:none;">
        ❓ 배포가 뭔가요? / What does Deploy do?
      </summary>
      <div style="padding:8px 12px;margin-top:6px;background:#f9fafb;
           border:1px solid #e5e7eb;border-radius:6px;">
        <p style="margin:0 0 8px 0;"><b>🚀 배포하기</b>를 누르면 — 지금 이
        컴퓨터에서 앱이 백그라운드로 계속 실행됩니다. 채팅창을 닫거나 이
        창을 닫아도 앱은 살아 있어요. 배포되면
        <b>🔗 열기</b> 버튼이 생기는데, 그걸 누르면 새 탭에서
        실제 앱이 열립니다. (주소는 <code>http://127.0.0.1:포트/run</code>
        형태)</p>
        <p style="margin:0 0 8px 0;"><b>⏹ 중단</b>을 누르면 멈춥니다. 멈추기
        전까지는 계속 도는 거예요. 컴퓨터를 끄거나 재부팅하면 같이
        멈춥니다 — 다시 켰을 때는 다시 배포하기를 누르세요.</p>
        <p style="margin:0 0 8px 0;"><b>📍 어디서 접속되나요?</b><br>
        기본은 <b>이 컴퓨터에서만</b> 접속됩니다 (안전을 위해). 같은
        컴퓨터의 다른 브라우저 창에서 🔗 열기를 누르면 그대로 동작해요.
        다른 사람의 컴퓨터/휴대폰/외부 인터넷에서는 보이지 않습니다.</p>
        <p style="margin:0;"><b>🌐 다른 컴퓨터(서버)에서 항상 켜두고
        싶다면</b> — 프로젝트 폴더를 그 컴퓨터에 복사하고
        터미널에서:<br>
        <code style="display:inline-block;margin-top:4px;padding:3px 6px;
              background:#fff;border:1px solid #e5e7eb;border-radius:3px;
              font-family:ui-monospace,Menlo,monospace;">
        ail serve --host 0.0.0.0 --port 8090 &lt;폴더경로&gt;
        </code><br>
        를 실행하면 같은 네트워크의 다른 기기에서
        <code>http://&lt;그 컴퓨터의 IP&gt;:8090/run</code>으로 접속할 수
        있어요. (이건 고급 사용자용 — 보통은 이 컴퓨터에 배포하면 충분합니다.)
        </p>
      </div>
    </details>

    <div class="settings-overlay" id="settings-overlay"></div>
    <div class="settings-panel" id="settings-panel">
      <div class="settings-hdr">
        <h2>환경 설정 / Settings</h2>
        <button class="settings-close" id="settings-close">✕</button>
      </div>
      <div class="settings-body">
        <p class="settings-section-title">저장된 키 / Saved keys</p>
        <div id="senv-list"></div>
      </div>
      <div class="settings-add">
        <p class="settings-section-title" style="margin-bottom:8px">새 키 추가 / Add key</p>
        <input type="text" id="senv-new-name" placeholder="키 이름 (예: DISCORD_WEBHOOK_URL)" autocomplete="off" spellcheck="false">
        <input type="password" id="senv-new-value" placeholder="값 / Value" autocomplete="off">
        <button class="settings-add-btn" id="senv-add-btn">저장 / Save</button>
      </div>
    </div>

    <div class="thread" id="thread">
      <div class="hint" id="hint">
        대화로 프로젝트를 만들어요. 어떤 걸 만들고 싶은지 아래에 입력하세요.<br>
        <small>Build by chatting. Describe what you want to make below.</small>
      </div>
    </div>

    <form class="composer" id="composer" onsubmit="return onSend(event);">
      <textarea id="msg" rows="1"
                placeholder="메시지 입력 후 Enter로 전송 (Shift+Enter 줄바꿈)"
                autocomplete="off" spellcheck="false"></textarea>
      <button type="submit" class="send" id="send">전송</button>
      <button type="button" class="send" id="cancel-chat"
              style="display:none;background:#b91c1c;">중단</button>
    </form>
  </div>

  <script>
    const thread = document.getElementById('thread');
    const msgEl = document.getElementById('msg');
    const sendBtn = document.getElementById('send');
    const cancelBtn = document.getElementById('cancel-chat');
    const hint = document.getElementById('hint');
    let currentAbortController = null;

    // Multi-program state (v1.13.1). These MUST be declared before the
    // history replay below, because addAgent() → addRunWidget() reads
    // them when replaying a `ready_to_run` turn — and `let` bindings
    // are in the Temporal Dead Zone until their declaration executes.
    // Field-test 2026-04-23: placing these after the replay threw
    // "Cannot access 'programsForNext' before initialization", which
    // halted the forEach after the first agent turn and left the chat
    // looking empty after a page reload. (Function declarations are
    // hoisted; `let` is not.)
    //
    // `programsForNext` is seeded from the server-rendered list so
    // that parse state / env_required / input_hint are accurate on
    // the first run-widget render after a page reload. Without
    // seeding, the widget falls back to a dummy {{parses: true}} and
    // a broken program's parse-error banner never shows.
    let programsForNext = {programs_json};
    let activeProgramForNext = programsForNext.length > 0
      ? programsForNext[0].name : null;
    let inputUsedForNext = programsForNext.length > 0
      ? !!programsForNext[0].input_used : true;
    let envRequiredForNext = programsForNext.length > 0
      ? (programsForNext[0].env_required || []) : [];

    // File tree — NERDTree-style side panel, refreshed after every
    // agent turn so file writes appear immediately.
    const fileTreeEl = document.getElementById('file-tree');
    const fileTreeBody = document.getElementById('file-tree-body');
    const fileTreeToggle = document.getElementById('file-tree-toggle');
    function toggleFileTree() {{
      fileTreeEl.classList.toggle('collapsed');
      fileTreeToggle.textContent =
        fileTreeEl.classList.contains('collapsed') ? '▶ show' : '◀ hide';
    }}
    window.toggleFileTree = toggleFileTree;
    function kindIcon(kind) {{
      return kind === 'ail' ? '🧩'
           : kind === 'html' ? '👁'
           : kind === 'doc' ? '📄'
           : '📦';
    }}
    async function refreshFileTree() {{
      try {{
        const r = await fetch('/authoring-tree');
        if (!r.ok) return;
        const d = await r.json();
        fileTreeBody.innerHTML = '';
        if (!d.entries || d.entries.length === 0) {{
          fileTreeBody.innerHTML =
            '<span style="color:#9ca3af">아직 파일 없음</span>';
          return;
        }}
        for (const e of d.entries) {{
          const item = document.createElement('div');
          item.className = 'ft-item' + (e.parses ? '' : ' ft-bad');
          const name = document.createElement('div');
          name.className = 'ft-name';
          name.textContent = kindIcon(e.kind) + ' ' + e.path +
                             (e.parses ? '' : ' ✗');
          item.appendChild(name);
          const cap = document.createElement('div');
          cap.className = 'ft-caption';
          cap.textContent = e.caption;
          item.appendChild(cap);
          const meta = document.createElement('div');
          meta.className = 'ft-meta';
          meta.textContent = e.bytes + ' bytes';
          item.appendChild(meta);
          item.addEventListener('click', async () => {{
            try {{
              const fr = await fetch(
                '/authoring-file?path=' + encodeURIComponent(e.path));
              const fd = await fr.json();
              alert(e.path + '\\n\\n' + (fd.content || '(empty)').slice(0, 4000));
            }} catch(err) {{}}
          }});
          fileTreeBody.appendChild(item);
        }}
      }} catch (e) {{ /* ignore */ }}
    }}
    refreshFileTree();

    // Token usage (hyun06000 2026-04-24: "토큰 얼마나 쓰는지 알
    // 수 없는 건 단점"). Session total is seeded from storage so
    // reopening the tab doesn't reset the counter.
    let sessionTotalTokens = {session_total_tokens_json};
    function fmtTokens(n) {{
      if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
      if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k';
      return String(n);
    }}
    const tokenWidget = document.createElement('div');
    tokenWidget.style.cssText =
      'position:fixed;bottom:8px;right:12px;font-size:11px;' +
      'color:#6b7280;font-family:ui-monospace,Menlo,monospace;' +
      'background:rgba(255,255,255,0.85);padding:4px 8px;' +
      'border:1px solid #e5e7eb;border-radius:6px;' +
      'pointer-events:none;z-index:1000;';
    function renderTokenWidget() {{
      tokenWidget.textContent = '세션 누적 ' + fmtTokens(sessionTotalTokens) + ' tok';
    }}
    renderTokenWidget();
    document.body.appendChild(tokenWidget);

    // Deploy bar — PRINCIPLES.md §5. Only relevant for projects that
    // declare a long-running independent agent (evolve-server). For
    // single-shot programs (dispatcher + view.html, scripts) the
    // chat's Run widget is the sufficient surface — Deploy here just
    // adds noise + false affordance. Field test 2026-04-26: a Deploy
    // button pinned at top makes non-devs feel "I should press this"
    // even when there's nothing to deploy.
    const deployBar = document.getElementById('deploy-bar');
    const deployHelp = document.getElementById('deploy-help');
    async function refreshDeployBar() {{
      deployBar.innerHTML = '';
      let rec = null;
      let deployable = false;
      try {{
        const r = await fetch('/authoring-deploy/status');
        if (r.ok) {{
          const body = await r.json();
          rec = body && body.deployment ? body.deployment : null;
          deployable = !!(body && body.deployable);
        }}
      }} catch (e) {{ /* ignore */ }}
      // Hide bar entirely if not deployable AND not deployed —
      // single-shot project, no live process. No reason to show.
      const shouldShow = !!rec || deployable;
      deployBar.style.display = shouldShow ? 'flex' : 'none';
      if (deployHelp) deployHelp.style.display = shouldShow ? '' : 'none';
      if (!shouldShow) return;
      if (rec) {{
        const badge = document.createElement('span');
        badge.textContent = '🟢 배포 중';
        badge.style.color = '#047857';
        badge.style.fontWeight = '600';
        deployBar.appendChild(badge);
        const info = document.createElement('span');
        info.textContent = 'port ' + rec.port + ' · pid ' + rec.pid;
        info.style.color = '#6b7280';
        info.style.fontFamily = 'ui-monospace,Menlo,monospace';
        info.style.fontSize = '11px';
        deployBar.appendChild(info);
        const openBtn = document.createElement('a');
        openBtn.href = rec.url;
        openBtn.target = '_blank';
        openBtn.rel = 'noopener';
        openBtn.textContent = '🔗 열기';
        openBtn.style.cssText =
          'margin-left:auto;padding:4px 10px;background:#047857;' +
          'color:#fff;border-radius:4px;text-decoration:none;' +
          'font-size:12px;';
        deployBar.appendChild(openBtn);
        const stopBtn = document.createElement('button');
        stopBtn.textContent = '⏹ 중단';
        stopBtn.style.cssText =
          'padding:4px 10px;background:#fff;color:#b91c1c;' +
          'border:1px solid #fecaca;border-radius:4px;cursor:pointer;' +
          'font-size:12px;font-family:inherit;';
        stopBtn.onclick = async () => {{
          if (!confirm('배포된 프로세스를 종료할까요?')) return;
          stopBtn.disabled = true;
          try {{
            await fetch('/authoring-deploy?stop=1', {{method:'POST'}});
          }} catch (e) {{}}
          await refreshDeployBar();
        }};
        deployBar.appendChild(stopBtn);
      }} else {{
        const label = document.createElement('span');
        label.textContent = '⚫ 배포 안 됨';
        label.style.color = '#6b7280';
        deployBar.appendChild(label);
        const hint = document.createElement('span');
        hint.textContent = '채팅을 닫아도 앱이 계속 돌게 하려면 배포하세요';
        hint.style.color = '#9ca3af';
        hint.style.fontSize = '11px';
        deployBar.appendChild(hint);
        const deployBtn = document.createElement('button');
        deployBtn.textContent = '🚀 배포하기';
        deployBtn.style.cssText =
          'margin-left:auto;padding:4px 12px;background:#047857;' +
          'color:#fff;border:0;border-radius:4px;cursor:pointer;' +
          'font-size:12px;font-family:inherit;';
        deployBtn.onclick = async () => {{
          deployBtn.disabled = true;
          deployBtn.textContent = '배포 중…';
          try {{
            const r = await fetch('/authoring-deploy', {{method:'POST'}});
            if (!r.ok) {{
              alert('배포 실패: ' + await r.text());
            }}
          }} catch (e) {{
            alert('배포 실패: ' + e.message);
          }}
          await refreshDeployBar();
        }};
        deployBar.appendChild(deployBtn);
      }}
    }}
    refreshDeployBar();

    // v1.54/v1.56: auto-fix + auto-re-run loop. All author models
    // are agentic (PRINCIPLES.md §4 extension). Field test showed
    // the agent genuinely progresses on each retry (fork pattern
    // discovered, head format discovered, etc.), but requiring the
    // user to click Run between each fix broke the flow. So after
    // auto-fix emits ready_to_run, we also auto-trigger the run —
    // capped at AUTO_CYCLE_MAX per chat turn to prevent runaway.
    const AUTO_FIX_MAX = 1;          // fix attempts per failed run
    const AUTO_CYCLE_MAX = 5;        // run→fix→run cycles per session
    let autoCycleCount = 0;
    async function autoFixOnError(failed, attempt) {{
      if (attempt >= AUTO_FIX_MAX) return;
      // Fade out the stale Run widgets so the user's eye moves to
      // the auto-fix status + the new widget that will replace them.
      document.querySelectorAll('.run-card').forEach(el => {{
        el.style.opacity = '0.45';
        el.style.pointerEvents = 'none';
        const badge = el.querySelector('.superseded-badge');
        if (!badge) {{
          const b = document.createElement('div');
          b.className = 'superseded-badge';
          b.style.cssText =
            'font-size:10px;color:#9ca3af;margin-top:4px;' +
            'font-style:italic;';
          b.textContent = '(이전 버전 — 자동 수정 진행 중)';
          el.appendChild(b);
        }}
      }});
      const status = document.createElement('div');
      status.className = 'turn agent auto-fix-status';
      const statusBubble = document.createElement('div');
      statusBubble.className = 'bubble';
      statusBubble.style.cssText =
        'background:#fef3c7;border:1px solid #fde68a;color:#78350f;' +
        'font-size:13px;';
      // hyun06000 2026-04-24: "자동수정도 약간의 로그를 실시간으로
      // 볼 수 있을까?" The wait was opaque; now show elapsed time
      // + a rolling hint about the three stages the auto-fix goes
      // through (reading error, asking the model, applying file).
      const elapsedLine = document.createElement('div');
      const hintLine = document.createElement('div');
      elapsedLine.style.cssText = 'margin-top:4px;font-size:11px;color:#92400e;';
      hintLine.style.cssText =
        'margin-top:2px;font-size:11px;color:#b45309;' +
        'font-family:ui-monospace,Menlo,monospace;';
      statusBubble.innerHTML =
        '⚙ <b>자동 수정 중…</b> ' +
        '<span style="font-size:11px;color:#92400e">' +
        '(' + (attempt + 1) + '/' + AUTO_FIX_MAX +
        ') 에이전트가 에러를 읽고 스스로 고치고 있어요. ' +
        '클릭 필요 없음.</span>';
      statusBubble.appendChild(elapsedLine);
      statusBubble.appendChild(hintLine);
      status.appendChild(statusBubble);
      thread.appendChild(status);
      scrollBottom();

      const fixStart = Date.now();
      const stages = [
        '→ 에러 메시지 읽기…',
        '→ 진단 로그 분석…',
        '→ Claude에게 수정 요청 전송…',
        '→ 응답 대기 (생성 중)…',
        '→ 응답 대기 (여전히 생성 중)…',
      ];
      let stageIdx = 0;
      const fixTimer = setInterval(() => {{
        const s = Math.floor((Date.now() - fixStart) / 1000);
        elapsedLine.textContent = '⏱ ' + s + 's 경과';
        // Advance the hint every ~3s so the user sees movement even
        // though we can't stream the model output yet.
        const targetIdx = Math.min(
          Math.floor(s / 3), stages.length - 1);
        if (targetIdx !== stageIdx) {{
          stageIdx = targetIdx;
          hintLine.textContent = stages[stageIdx];
        }} else if (!hintLine.textContent) {{
          hintLine.textContent = stages[0];
        }}
      }}, 250);

      const errSummary =
        '이전 실행이 에러로 끝났어. PRINCIPLES.md §4 — 저자 모델은 ' +
        '에이전틱. 원인부터 한 줄로 진단한 뒤, `<file>`로 고쳐진 ' +
        '전체 소스를 emit하고 `<action>ready_to_run</action>`을 달아. ' +
        '하드코딩 우회 금지 (search + filter 결과가 0이면 필터 조건을 ' +
        '고치거나 쿼리를 재설계하지, 결과를 상수로 박지 말 것). ' +
        'Error: ' + (failed.value || '') + ' | ' +
        'Diagnostic: ' + (failed.diagnostic || '');
      try {{
        const r = await fetch('/authoring-chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'text/plain; charset=utf-8' }},
          body: errSummary,
        }});
        clearInterval(fixTimer);
        status.remove();
        const text = await r.text();
        if (!r.ok) {{ addError('자동 수정 실패: ' + text); return; }}
        const data = JSON.parse(text);
        if (typeof data.session_total_tokens === 'number') {{
          sessionTotalTokens = data.session_total_tokens;
          renderTokenWidget();
        }}
        if (Array.isArray(data.programs)) programsForNext = data.programs;
        if (data.active_program) activeProgramForNext = data.active_program;
        addAgent(data.reply || '(empty)', data.files || [], data.action || null);
        // Tag the auto-fix reply bubble visually so user knows THIS
        // turn came from the auto-fix loop, not their own typing.
        const fixTurn = thread.lastElementChild;
        if (fixTurn) {{
          const tag = document.createElement('div');
          tag.style.cssText =
            'font-size:10px;color:#047857;margin:2px 0 4px 14px;' +
            'font-weight:500;';
          tag.textContent = '✨ 자동 수정된 답변 / auto-fix reply';
          fixTurn.insertBefore(tag, fixTurn.firstChild);
        }}
        appendTokenFooter(thread.lastElementChild,
                          data.input_tokens, data.output_tokens);
        // Clear "CTA" bubble so the user knows what to do next.
        const cta = document.createElement('div');
        cta.className = 'turn agent';
        const ctaBubble = document.createElement('div');
        ctaBubble.className = 'bubble';
        ctaBubble.style.cssText =
          'background:#ecfdf5;border:1px solid #a7f3d0;' +
          'color:#065f46;font-size:12px;';
        const shouldAutoRun =
          data.action === 'ready_to_run' &&
          autoCycleCount < AUTO_CYCLE_MAX;
        if (shouldAutoRun) {{
          autoCycleCount += 1;
          ctaBubble.innerHTML =
            '🔄 <b>자동 재실행 중</b> (' + autoCycleCount + '/' +
            AUTO_CYCLE_MAX + ') — 수정된 코드를 바로 돌려봐요…';
        }} else {{
          ctaBubble.innerHTML =
            '✓ <b>자동 수정 완료.</b> ' +
            (autoCycleCount >= AUTO_CYCLE_MAX
              ? '자동 재실행 한도(' + AUTO_CYCLE_MAX + '회)에 도달했어요. ' +
                '채팅으로 다른 접근을 제안해주세요.'
              : '아래 새 Run 버튼으로 다시 실행해보세요.');
        }}
        cta.appendChild(ctaBubble);
        thread.appendChild(cta);
        refreshFileTree();
        scrollBottom();
        if (shouldAutoRun) {{
          // Small delay so the user can see the fix reply + CTA
          // scroll into view before the run fires. Then click the
          // most recent Run button programmatically.
          setTimeout(() => {{
            const allRunBtns = document.querySelectorAll(
              '.run-card:not([style*="opacity: 0.45"]) .run-inline');
            const btn = allRunBtns[allRunBtns.length - 1];
            if (btn && !btn.disabled) btn.click();
          }}, 800);
        }}
      }} catch (e) {{
        clearInterval(fixTimer);
        status.remove();
        addError('자동 수정 네트워크 오류: ' + e.message);
      }}
    }}

    function appendTokenFooter(turnEl, inputTokens, outputTokens) {{
      if (!turnEl) return;
      const inp = Number(inputTokens) || 0;
      const out = Number(outputTokens) || 0;
      if (inp === 0 && out === 0) return;
      const foot = document.createElement('div');
      foot.style.cssText =
        'font-size:10px;color:#9ca3af;margin-top:2px;' +
        'font-family:ui-monospace,Menlo,monospace;';
      foot.textContent = '↑ ' + fmtTokens(inp) + ' · ↓ ' + fmtTokens(out) +
        ' · 누적 ' + fmtTokens(sessionTotalTokens);
      turnEl.appendChild(foot);
    }}

    // Replay history embedded by the server on first render.
    const INITIAL_HISTORY = {history_json};
    if (INITIAL_HISTORY.length > 0) {{
      hint.remove();
      INITIAL_HISTORY.forEach(entry => {{
        if (entry.kind === 'run_result') {{
          addRunResult(entry);
        }} else {{
          addUser(entry.user);
          addAgent(entry.reply, entry.files || [], entry.action || null);
        }}
      }});
      scrollBottom();
    }}

    msgEl.addEventListener('input', () => {{
      msgEl.style.height = 'auto';
      msgEl.style.height = Math.min(msgEl.scrollHeight, 160) + 'px';
    }});

    msgEl.addEventListener('keydown', (e) => {{
      // Standard chat UX: Enter sends, Shift+Enter inserts a newline.
      // isComposing + keyCode 229 guards Korean/Japanese IME so that
      // Enter while composing Hangul commits the composition rather
      // than sending a half-typed message.
      if (e.key === 'Enter' && !e.shiftKey
          && !e.isComposing && e.keyCode !== 229) {{
        e.preventDefault();
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
      // Render as markdown if the reply shape is structured (spec
      // cards, fix diagnoses, multi-section answers). Field-test
      // 2026-04-24: v1.58.2 spec replies rendered as raw `## 목적`
      // text because addAgent only linkified. Detect markdown
      // structure and upgrade to a rendered view; plain chat lines
      // stay simple.
      if (looksLikeMarkdown(reply)) {{
        bubble.classList.add('md-body');
        bubble.innerHTML = renderMarkdown(reply);
      }} else {{
        bubble.innerHTML = linkifyText(reply);
      }}
      turn.appendChild(bubble);
      thread.appendChild(turn);

      if (files && files.length) {{
        const box = document.createElement('div');
        box.className = 'files';
        files.forEach(f => {{
          const wrapper = document.createElement('div');

          const tag = document.createElement('span');
          tag.className = 'file-tag';
          if (f.skipped) {{
            tag.textContent = '✗ ' + f.path + ' — ' + f.skipped;
            tag.style.color = '#b91c1c';
          }} else if (f.path === 'view.html') {{
            // The user's "어디에 뭐가 뜨는지" problem: a written
            // view.html has no visible artifact in the chat. Give it
            // a direct "preview in new window" action so the user
            // can see the rendered page the moment it is written.
            const arrow = document.createElement('span');
            arrow.className = 'toggle-arrow';
            arrow.textContent = '▶';
            tag.appendChild(arrow);
            tag.appendChild(document.createTextNode('✓ ' + f.path + ' (' + f.bytes + ' bytes)'));

            const preview = document.createElement('div');
            preview.className = 'file-preview';
            const pre = document.createElement('pre');
            preview.appendChild(pre);
            wrapper.appendChild(preview);

            let loaded = false;
            tag.addEventListener('click', async () => {{
              const isOpen = preview.classList.toggle('open');
              arrow.textContent = isOpen ? '▼' : '▶';
              if (isOpen && !loaded) {{
                pre.textContent = '로딩 중…';
                try {{
                  const r = await fetch('/authoring-file?path=' + encodeURIComponent(f.path));
                  const d = await r.json();
                  pre.textContent = d.content;
                }} catch(e) {{
                  pre.textContent = '(읽기 실패)';
                }}
                loaded = true;
              }}
            }});

            const openBtn = document.createElement('a');
            openBtn.href = '/run';
            openBtn.target = '_blank';
            openBtn.rel = 'noopener';
            openBtn.textContent = '👁 새 창으로 열기 (독립 실행)';
            openBtn.style.cssText =
              'margin-left:8px;font-size:11px;padding:2px 8px;' +
              'background:#047857;color:#fff;border-radius:4px;' +
              'text-decoration:none;display:inline-block;';
            wrapper.appendChild(openBtn);
          }} else {{
            const arrow = document.createElement('span');
            arrow.className = 'toggle-arrow';
            arrow.textContent = '▶';
            tag.appendChild(arrow);
            tag.appendChild(document.createTextNode('✓ ' + f.path + ' (' + f.bytes + ' bytes)'));

            const preview = document.createElement('div');
            preview.className = 'file-preview';
            const pre = document.createElement('pre');
            preview.appendChild(pre);
            wrapper.appendChild(preview);

            let loaded = false;
            tag.addEventListener('click', async () => {{
              const isOpen = preview.classList.toggle('open');
              arrow.textContent = isOpen ? '▼' : '▶';
              if (isOpen && !loaded) {{
                pre.textContent = '로딩 중…';
                try {{
                  const r = await fetch('/authoring-file?path=' + encodeURIComponent(f.path));
                  const d = await r.json();
                  pre.textContent = d.content;
                }} catch(e) {{
                  pre.textContent = '(읽기 실패)';
                }}
                loaded = true;
              }}
            }});
          }}
          wrapper.insertBefore(tag, wrapper.firstChild);
          box.appendChild(wrapper);
        }});
        thread.appendChild(box);
      }}

      if (action === 'spec_pending') {{
        // Spec-first flow (PRINCIPLES §6 follow-up, user request
        // 2026-04-24 late evening). Agent drafted a spec; user
        // approves before any file is written.
        addSpecApprovalCard();
      }} else if (action === 'ready_to_run') {{
        addRunWidget(false);
      }} else if (action === 'ready_to_serve' || action === 'ready_to_deploy') {{
        addRunWidget(true);
      }}
    }}

    // `programsForNext` / `activeProgramForNext` / `inputUsedForNext`
    // / `envRequiredForNext` are declared above the history replay —
    // they must initialize before `addRunWidget` references them.

    // Inline widget that the user can invoke repeatedly without
    // leaving the chat. For `ready_to_run` it's a plain run box.
    // For `ready_to_serve` it's the same widget wrapped as a service
    // card with a share link to /service (the classic service UI on
    // a separate route, for handing out to non-chat consumers).
    // `inputUsed` controls whether to render the input textarea —
    // when false (entry doesn't reference input), the widget is a
    // bare Run button with no confusing empty input field.
    function addSpecApprovalCard() {{
      const card = document.createElement('div');
      card.className = 'run-card';
      card.style.background = '#eff6ff';
      card.style.borderColor = '#bfdbfe';
      const title = document.createElement('div');
      title.className = 'title';
      title.style.color = '#1e40af';
      title.textContent = '📋 명세 검토 / Review spec';
      card.appendChild(title);
      const desc = document.createElement('div');
      desc.className = 'desc';
      desc.textContent =
        '에이전트가 위 명세대로 빌드하면 괜찮을까요? ' +
        '수정이 필요하면 채팅으로 설명해주세요.';
      card.appendChild(desc);
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:8px;margin-top:8px;';
      const approve = document.createElement('button');
      approve.className = 'run-inline';
      approve.textContent = '✅ 이대로 빌드 / Approve & build';
      approve.onclick = async () => {{
        approve.disabled = true;
        approve.textContent = '빌드 요청 중…';
        try {{
          const r = await fetch('/authoring-chat', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'text/plain; charset=utf-8' }},
            body: '승인합니다. 이 명세대로 빌드해주세요 — ' +
              '<file> 태그로 실제 .ail 소스를 emit하고 ' +
              '<action>ready_to_run</action>을 달아주세요.',
          }});
          const text = await r.text();
          const data = JSON.parse(text);
          if (typeof data.session_total_tokens === 'number') {{
            sessionTotalTokens = data.session_total_tokens;
            renderTokenWidget();
          }}
          if (Array.isArray(data.programs)) programsForNext = data.programs;
          if (data.active_program) activeProgramForNext = data.active_program;
          addAgent(data.reply || '(empty)', data.files || [],
                   data.action || null);
          appendTokenFooter(thread.lastElementChild,
                            data.input_tokens, data.output_tokens);
          refreshFileTree();
          card.style.opacity = '0.5';
          card.style.pointerEvents = 'none';
        }} catch (e) {{
          addError('승인 전송 실패: ' + e.message);
          approve.disabled = false;
          approve.textContent = '✅ 이대로 빌드 / Approve & build';
        }}
      }};
      row.appendChild(approve);
      const hint = document.createElement('span');
      hint.style.cssText =
        'font-size:11px;color:#6b7280;align-self:center;';
      hint.textContent = '또는 채팅으로 "X 부분 바꿔줘" 식으로 수정 요청';
      row.appendChild(hint);
      card.appendChild(row);
      thread.appendChild(card);
      scrollBottom();
    }}

    function addRunWidget(service) {{
      // v1.13.1: widget operates on a selected program. `programs`
      // and `activeProgramForNext` come from the latest agent turn.
      // Falls back to legacy single-program behaviour when the list
      // is empty (pre-v1.13.1 history replays).
      const programs = programsForNext && programsForNext.length > 0
        ? programsForNext.slice()
        : [{{
            name: 'app.ail',
            input_used: inputUsedForNext,
            env_required: envRequiredForNext,
            parses: true,
          }}];
      let selected = activeProgramForNext
        && programs.find(p => p.name === activeProgramForNext)
        ? activeProgramForNext
        : programs[0].name;
      const meta = () => programs.find(p => p.name === selected) || programs[0];
      let inputUsed = meta().input_used;
      let envRequired = meta().env_required || [];
      const card = document.createElement('div');
      card.className = 'run-card' + (service ? ' service' : '');

      if (service) {{
        const title = document.createElement('div');
        title.className = 'title';
        title.textContent = '🌐 독립 실행 준비 / Ready to serve';
        card.appendChild(title);
        const desc = document.createElement('div');
        desc.className = 'desc';
        desc.textContent = '이 프로그램은 채팅과 분리된 URL에서 돌릴 수 ' +
          '있어요. 새 탭에서 열면 채팅 세션과 독립적으로 동작합니다.';
        card.appendChild(desc);
        const link = document.createElement('a');
        link.className = 'share-link';
        link.href = '/run';
        link.target = '_blank';
        link.textContent = '🚀 새 탭에서 실행 / Open /run in new tab →';
        card.appendChild(link);
      }} else {{
        const title = document.createElement('div');
        title.className = 'title';
        title.textContent = '▶ 실행 / Run';
        card.appendChild(title);
      }}

      // Program picker. Only shown when there are 2+ programs.
      const dynSlot = document.createElement('div');
      dynSlot.style.display = 'flex';
      dynSlot.style.flexDirection = 'column';
      dynSlot.style.gap = '10px';
      if (programs.length > 1) {{
        const pickerRow = document.createElement('div');
        pickerRow.className = 'program-picker';
        const label = document.createElement('span');
        label.textContent = '프로그램 / Program:';
        pickerRow.appendChild(label);
        const sel = document.createElement('select');
        programs.forEach(p => {{
          const opt = document.createElement('option');
          opt.value = p.name;
          // Cap purpose length so a long # PURPOSE: line doesn't
          // stretch the dropdown past its card. The full text is in
          // the file tree side panel / the prompt inventory.
          const CAP = 50;
          const trimmedPurpose = (p.purpose || '').length > CAP
            ? p.purpose.slice(0, CAP - 1) + '…'
            : (p.purpose || '');
          const purposeSuffix = trimmedPurpose ? ' — ' + trimmedPurpose : '';
          opt.textContent = p.name + purposeSuffix + (p.parses ? '' : ' (parse error)');
          opt.title = p.name + (p.purpose ? ' — ' + p.purpose : '');
          if (p.name === selected) opt.selected = true;
          sel.appendChild(opt);
        }});
        sel.onchange = () => {{
          selected = sel.value;
          inputUsed = meta().input_used;
          envRequired = meta().env_required || [];
          redrawDynamic();
        }};
        pickerRow.appendChild(sel);
        const flag = document.createElement('span');
        flag.className = 'flag';
        pickerRow.appendChild(flag);
        card.appendChild(pickerRow);
        // Update flag whenever selection changes too.
        const refreshFlag = () => {{
          const m = meta();
          if (!m.parses) {{
            flag.className = 'flag bad';
            flag.textContent = '✗ parse error — fix before running';
          }} else {{
            flag.className = 'flag';
            flag.textContent = '';
          }}
        }};
        refreshFlag();
        const _orig = sel.onchange;
        sel.onchange = () => {{ _orig(); refreshFlag(); }};
      }}
      card.appendChild(dynSlot);

      function redrawDynamic() {{
        dynSlot.innerHTML = '';
        renderDynamic();
      }}

      function renderDynamic() {{
      // Parse-error banner. If the selected program doesn't parse,
      // nothing downstream is trustworthy — `entry_uses_input`
      // conservatively returns True on parse failure, so without
      // this banner the user sees a textarea with a generic
      // placeholder and no idea that the underlying .ail is broken.
      // Field test 2026-04-23: exactly that happened on a program
      // whose author (prior prompt) emitted `if !resp.ok` which
      // AIL rejects at lex time.
      if (!meta().parses) {{
        const parseBanner = document.createElement('div');
        parseBanner.className = 'env-block';
        parseBanner.style.borderColor = '#fca5a5';
        parseBanner.style.background = '#fef2f2';
        const title = document.createElement('div');
        title.className = 'env-title';
        title.style.color = '#b91c1c';
        title.textContent = '⚠ 파싱 에러 — 먼저 수정이 필요해요 / Parse error';
        parseBanner.appendChild(title);
        const detail = document.createElement('div');
        detail.style.fontSize = '12px';
        detail.style.color = '#7f1d1d';
        detail.style.fontFamily = 'ui-monospace, Menlo, monospace';
        detail.style.whiteSpace = 'pre-wrap';
        detail.style.wordBreak = 'break-word';
        detail.textContent = (meta().parse_error || '')
          .toString().slice(0, 400);
        parseBanner.appendChild(detail);
        const fixBar = document.createElement('div');
        fixBar.style.marginTop = '8px';
        const fixBtn = document.createElement('button');
        fixBtn.className = 'run-inline';
        fixBtn.style.background = '#b91c1c';
        fixBtn.textContent = '🔧 에이전트에게 수정 요청 / Ask agent to fix';
        fixBtn.onclick = () => {{
          fixBtn.disabled = true;
          send('이 프로그램이 파싱되지 않아요. 에러를 보고 고쳐주세요. / '
               + 'This program has a parse error — please fix it.');
        }};
        fixBar.appendChild(fixBtn);
        parseBanner.appendChild(fixBar);
        dynSlot.appendChild(parseBanner);
        // Skip the Run UI entirely — running a broken program just
        // re-surfaces the same error the user can already see above.
        return;
      }}
      // Env-var requirement block — shown when the authored .ail
      // calls `perform env.read("VAR")` for any var that isn't set.
      // Masked input; value NEVER goes into chat history or ledger.
      const unset = envRequired.filter(e => !e.set);
      if (unset.length > 0) {{
        const envBox = document.createElement('div');
        envBox.className = 'env-block';
        const envTitle = document.createElement('div');
        envTitle.className = 'env-title';
        envTitle.textContent = '설정 필요 / This program needs:';
        envBox.appendChild(envTitle);
        unset.forEach(e => {{
          const row = document.createElement('div');
          row.className = 'env-row';
          const lbl = document.createElement('label');
          lbl.textContent = e.name;
          row.appendChild(lbl);
          const field = document.createElement('input');
          field.type = 'password';
          field.placeholder = '여기에 붙여넣으세요 / paste here';
          field.autocomplete = 'off';
          row.appendChild(field);
          const setBtn = document.createElement('button');
          setBtn.type = 'button';
          setBtn.textContent = '저장 / Set';
          const status = document.createElement('span');
          status.className = 'status';
          const save = async () => {{
            const v = field.value;
            if (!v) return;
            setBtn.disabled = true;
            try {{
              const r = await fetch('/authoring-set-env', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ name: e.name, value: v }}),
              }});
              if (r.ok) {{
                status.textContent = '✓ saved';
                status.className = 'status';
                field.value = '';
                field.placeholder = '✓ set (clear to update)';
              }} else {{
                status.textContent = '✗ ' + await r.text();
                status.className = 'status err';
              }}
            }} catch (err) {{
              status.textContent = '✗ ' + err.message;
              status.className = 'status err';
            }} finally {{
              setBtn.disabled = false;
            }}
          }};
          setBtn.onclick = save;
          field.onkeydown = (ev) => {{
            if (ev.key === 'Enter') {{ ev.preventDefault(); save(); }}
          }};
          row.appendChild(setBtn);
          row.appendChild(status);
          envBox.appendChild(row);
        }});
        dynSlot.appendChild(envBox);
      }}

      let input = null;
      if (inputUsed) {{
        input = document.createElement('textarea');
        input.rows = 1;
        // Per-program placeholder (`# INPUT: ...` at the top of the
        // .ail) wins when the author supplied one — field test
        // showed the generic hint left non-programmers staring at
        // an empty box with no idea what to type.
        const hint = meta().input_hint;
        input.placeholder = hint
          ? hint
          : (service
              ? '입력이 필요하면 여기 (비워두면 빈 입력) / input (optional)'
              : '입력 (선택) / input (optional, leave blank if none)');
        input.autocomplete = 'off';
        input.spellcheck = false;
        input.addEventListener('input', () => {{
          input.style.height = 'auto';
          input.style.height = Math.min(input.scrollHeight, 160) + 'px';
        }});
        input.addEventListener('keydown', (e) => {{
          if (e.key === 'Enter' && !e.shiftKey
              && !e.isComposing && e.keyCode !== 229) {{
            e.preventDefault();
            fire();
          }}
        }});
        dynSlot.appendChild(input);
      }} else {{
        const note = document.createElement('div');
        note.className = 'desc';
        note.textContent =
          '이 프로그램은 입력이 필요 없어요. 실행 버튼을 누르세요.';
        dynSlot.appendChild(note);
      }}

      const runBtn = document.createElement('button');
      runBtn.className = 'run-inline';
      runBtn.textContent = '실행 / Run';
      const fire = async () => {{
        runBtn.disabled = true;
        const placeholder = document.createElement('div');
        placeholder.className = 'run-result';
        placeholder.style.background = '#f3f4f6';
        placeholder.style.borderColor = '#e5e7eb';
        placeholder.textContent = '실행 중…';
        thread.appendChild(placeholder);
        scrollBottom();

        // Approval polling. While the run is in-flight, poll for any
        // `perform human.approve(plan)` pending on the server. When
        // one appears, render a card with the plan text + Approve /
        // Decline buttons. Clicking either posts the decision, which
        // unblocks the server-side executor. The run keeps going and
        // may hit more approvals — so we keep polling until `fire`
        // returns.
        const shownApprovals = new Set();
        let pollTimer = null;
        const poll = async () => {{
          try {{
            const resp = await fetch('/authoring-approval-pending');
            if (resp.status !== 200) return;
            const rec = await resp.json();
            if (!rec || !rec.id) return;
            if (shownApprovals.has(rec.id)) return;
            shownApprovals.add(rec.id);
            renderApprovalCard(rec);
          }} catch (e) {{
            // Transient network error during a run is common (the
            // polling request races the run-completion response).
            // Swallow quietly.
          }}
        }};
        pollTimer = setInterval(poll, 500);
        poll();  // immediate first check

        // Live log polling — shows `perform log(msg)` lines in the
        // placeholder while the run is in-flight.
        let logSince = 0;
        let logRunId = null;
        const logPre = document.createElement('pre');
        logPre.style.cssText = 'margin:6px 0 0;font-size:12px;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto;color:#374151;';
        placeholder.appendChild(logPre);
        const logPoll = async () => {{
          try {{
            const lr = await fetch('/run-log-poll?since=' + logSince);
            if (lr.status !== 200) return;
            const ld = await lr.json();
            if (logRunId === null) logRunId = ld.run_id;
            if (ld.run_id !== logRunId) {{ logSince = 0; logRunId = ld.run_id; logPre.textContent = ''; }}
            if (ld.lines && ld.lines.length > 0) {{
              for (const line of ld.lines) {{
                logPre.textContent += line + '\\n';
              }}
              logPre.scrollTop = logPre.scrollHeight;
              scrollBottom();
            }}
            logSince = ld.total;
          }} catch (e) {{}}
        }};
        const logTimer = setInterval(logPoll, 400);
        logPoll();

        try {{
          const url = '/authoring-run?program=' + encodeURIComponent(selected);
          const r = await fetch(url, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'text/plain; charset=utf-8' }},
            body: input ? input.value : '',
          }});
          clearInterval(logTimer);
          await logPoll();  // final flush
          placeholder.remove();
          const text = await r.text();
          let data;
          try {{ data = JSON.parse(text); }}
          catch (e) {{
            addError('실행 결과 파싱 실패: ' + text.slice(0, 200));
            return;
          }}
          addRunResult(data);
          scrollBottom();
          // PRINCIPLES.md §4 extension (user, 2026-04-24): the
          // authoring agent is agentic too, so a failed run should
          // trigger an automatic fix-attempt instead of making the
          // user click-click-click. Bounded at 3 retries per Run
          // click to prevent loops.
          if (data && data.ok === false) {{
            await autoFixOnError(data, 0);
          }}
        }} catch (e) {{
          clearInterval(logTimer);
          placeholder.remove();
          addError('네트워크 오류: ' + e.message);
        }} finally {{
          if (pollTimer) clearInterval(pollTimer);
          runBtn.disabled = false;
        }}
      }};

      function renderApprovalCard(rec) {{
        const box = document.createElement('div');
        box.className = 'run-result';
        box.style.background = '#fffbeb';
        box.style.borderColor = '#fde68a';
        const label = document.createElement('div');
        label.className = 'label';
        label.style.color = '#b45309';
        label.textContent = '⏸ 승인 대기 / Approval needed';
        box.appendChild(label);
        const planPre = document.createElement('pre');
        planPre.textContent = rec.plan || '';
        box.appendChild(planPre);
        const btnRow = document.createElement('div');
        btnRow.style.display = 'flex';
        btnRow.style.gap = '8px';
        btnRow.style.marginTop = '8px';
        const approveBtn = document.createElement('button');
        approveBtn.className = 'run-inline';
        approveBtn.style.background = '#047857';
        approveBtn.textContent = '✅ 승인 / Approve';
        const declineBtn = document.createElement('button');
        declineBtn.className = 'run-inline';
        declineBtn.style.background = '#b91c1c';
        declineBtn.textContent = '❌ 거절 / Decline';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'status';
        statusSpan.style.marginLeft = '8px';
        // v1.58.11: the textarea is shown with an explicit label +
        // a hint that spells out "Approve/Decline buttons below
        // submit whatever is in this box together with the
        // decision." Field test: user couldn't find a submit
        // button because the Approve/Decline buttons read like
        // standalone y/n — the comment felt stranded.
        const feedbackLabel = document.createElement('div');
        feedbackLabel.textContent = '💬 의견 (선택 / optional):';
        feedbackLabel.style.cssText =
          'margin-top:8px;font-size:12px;font-weight:500;color:#374151;';
        box.appendChild(feedbackLabel);
        const feedback = document.createElement('textarea');
        feedback.placeholder =
          '예: "승인, 다만 브랜치 이름은 X로" / "URL 틀렸어요, Y로 바꿔줘". ' +
          '여기 쓴 내용은 아래 승인 또는 거절 버튼을 누를 때 함께 전달됩니다.';
        feedback.style.cssText =
          'width:100%;font-family:inherit;font-size:13px;padding:8px;' +
          'border:1px solid #e5e7eb;border-radius:6px;' +
          'min-height:50px;resize:vertical;margin-top:4px;box-sizing:border-box;';
        box.appendChild(feedback);
        const submitHint = document.createElement('div');
        submitHint.style.cssText =
          'font-size:11px;color:#6b7280;margin-top:4px;';
        submitHint.textContent =
          '↓ 버튼을 누르면 위 의견과 함께 전송됩니다 / ' +
          'Clicking below submits your decision along with the comment.';
        box.appendChild(submitHint);
        btnRow.appendChild(approveBtn);
        btnRow.appendChild(declineBtn);
        btnRow.appendChild(statusSpan);
        box.appendChild(btnRow);
        thread.appendChild(box);
        scrollBottom();

        // Dynamic label so the user can see the comment is
        // attached: empty → plain "승인"; non-empty → "의견과 함께
        // 승인". Feels like hitting a "submit with comment" button
        // instead of a naked y/n.
        const baseApprove = '✅ 승인 / Approve';
        const baseDecline = '❌ 거절 / Decline';
        const updateBtnLabels = () => {{
          const has = feedback.value.trim().length > 0;
          approveBtn.textContent = has
            ? '✅ 의견과 함께 승인 / Approve with comment'
            : baseApprove;
          declineBtn.textContent = has
            ? '❌ 의견과 함께 거절 / Decline with comment'
            : baseDecline;
        }};
        feedback.addEventListener('input', updateBtnLabels);
        // Ctrl/Cmd+Enter → submit as Approve (fastest path when
        // user is typing a confirmation-with-guidance).
        feedback.addEventListener('keydown', (e) => {{
          if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {{
            e.preventDefault();
            approveBtn.click();
          }}
        }});

        const decide = async (decision) => {{
          approveBtn.disabled = true;
          declineBtn.disabled = true;
          feedback.disabled = true;
          statusSpan.textContent = '전송 중…';
          const comment = feedback.value.trim();
          try {{
            const body = {{ id: rec.id, decision: decision }};
            if (comment) body.comment = comment;
            const r = await fetch('/authoring-approve', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify(body),
            }});
            if (!r.ok) {{
              const msg = await r.text();
              statusSpan.textContent = '✗ ' + msg;
              approveBtn.disabled = false;
              declineBtn.disabled = false;
              return;
            }}
            label.textContent = decision === 'approve'
              ? '✅ 승인됨 / Approved'
              : '❌ 거절됨 / Declined';
            label.style.color = decision === 'approve'
              ? '#047857' : '#b91c1c';
            statusSpan.textContent = comment
              ? (decision === 'approve' ? '의견: ' : '사유: ') + comment
              : '';
            btnRow.innerHTML = '';
            feedback.style.display = 'none';
          }} catch (e) {{
            statusSpan.textContent = '✗ ' + e.message;
            approveBtn.disabled = false;
            declineBtn.disabled = false;
            feedback.disabled = false;
          }}
        }};
        approveBtn.onclick = () => decide('approve');
        declineBtn.onclick = () => decide('decline');
      }}
      runBtn.onclick = fire;
      dynSlot.appendChild(runBtn);
      }}  // end renderDynamic

      renderDynamic();
      thread.appendChild(card);
    }}

    function renderMarkdown(text) {{
      // Minimal markdown renderer — no external deps.
      // Handles: fenced code, headers, bold/italic, inline code,
      // links, ul/ol lists, hr, paragraphs.
      if (!text) return '';
      const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

      // 1. Fenced code blocks (``` ... ```) — extract before inline pass
      const fenced = [];
      text = text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (_, lang, code) => {{
        const idx = fenced.length;
        fenced.push(`<pre><code>${{esc(code.replace(/\\n$/,''))}}</code></pre>`);
        return `\x00FENCED${{idx}}\x00`;
      }});

      // 1b. Force heading and hr lines to be their own blocks — fixes the
      // common LLM output where headings have no blank line before/after.
      // Without this, `## 목적\\n사용자가...\\n## 다음` collapses into one
      // paragraph and only the first heading renders.
      text = text.replace(/(^|\\n)(#{1,6} [^\\n]+)/g, '$1\\n$2\\n');
      text = text.replace(/(^|\\n)(---+)(?=\\n|$)/g, '$1\\n$2\\n');

      // 2. Split into blocks by blank lines
      const blocks = text.split(/\\n{{2,}}/);
      const rendered = blocks.map(rawBlock => {{
        // Trim block-leading/trailing newlines left over from the
        // heading-isolation pre-pass — otherwise lines[0] is empty
        // and headings render as paragraphs.
        const block = rawBlock.replace(/^\\n+|\\n+$/g, '');
        if (!block) return '';
        // Restore fenced placeholders
        if (/^\x00FENCED\\d+\x00$/.test(block.trim())) {{
          return fenced[parseInt(block.match(/\\d+/)[0])];
        }}
        // hr
        if (/^---+$/.test(block.trim())) return '<hr>';

        const lines = block.split('\\n');

        // Heading (# at start of block's first line) — h1..h6
        const hm = lines[0].match(/^(#{1,6})\\s+(.+)/);
        if (hm) {{
          const lvl = hm[1].length;
          return `<h${{lvl}}>${{inlineRender(hm[2])}}</h${{lvl}}>`;
        }}

        // Table — header row + separator row + body rows
        // Detect: line0 contains pipes, line1 is the |---|---|... separator
        // (any column count, optional leading/trailing pipes, : for alignment)
        if (lines.length >= 2 && /\\|/.test(lines[0]) &&
            /^[\\s|:-]+$/.test(lines[1]) && /\\|/.test(lines[1]) &&
            /-/.test(lines[1])) {{
          const splitRow = (l) => {{
            let s = l.trim();
            if (s.startsWith('|')) s = s.slice(1);
            if (s.endsWith('|')) s = s.slice(0, -1);
            return s.split('|').map(c => c.trim());
          }};
          const headers = splitRow(lines[0]);
          const bodyRows = lines.slice(2)
            .filter(l => /\\|/.test(l))
            .map(splitRow);
          const thead = '<thead><tr>' +
            headers.map(h => `<th>${{inlineRender(h)}}</th>`).join('') +
            '</tr></thead>';
          const tbody = '<tbody>' +
            bodyRows.map(row =>
              '<tr>' + row.map(c => `<td>${{inlineRender(c)}}</td>`).join('') + '</tr>'
            ).join('') +
            '</tbody>';
          return `<table>${{thead}}${{tbody}}</table>`;
        }}

        // Blockquote (lines starting with > — gather as paragraph in <blockquote>)
        if (lines.every(l => /^\\s*>\\s?/.test(l) || l.trim() === '')) {{
          const inner = lines
            .map(l => l.replace(/^\\s*>\\s?/, ''))
            .join(' ').trim();
          return `<blockquote>${{inlineRender(inner)}}</blockquote>`;
        }}

        // Unordered list
        if (lines.every(l => /^\\s*[-*]\\s/.test(l) || l.trim() === '')) {{
          const items = lines.filter(l => /^\\s*[-*]\\s/.test(l))
            .map(l => `<li>${{inlineRender(l.replace(/^\\s*[-*]\\s+/, ''))}}</li>`);
          return `<ul>${{items.join('')}}</ul>`;
        }}

        // Ordered list
        if (lines.every(l => /^\\s*\\d+\\.\\s/.test(l) || l.trim() === '')) {{
          const items = lines.filter(l => /^\\s*\\d+\\.\\s/.test(l))
            .map(l => `<li>${{inlineRender(l.replace(/^\\s*\\d+\\.\\s+/, ''))}}</li>`);
          return `<ol>${{items.join('')}}</ol>`;
        }}

        // Paragraph (join lines, render inline)
        return `<p>${{inlineRender(lines.join(' '))}}</p>`;
      }});

      return rendered.join('');
    }}

    function inlineRender(s) {{
      const esc = t => t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      // Inline code
      s = s.replace(/`([^`]+)`/g, (_, c) => `<code>${{esc(c)}}</code>`);
      // Bold
      s = s.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
      s = s.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
      s = s.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g,
        (_, t, u) => `<a href="${{esc(u)}}" target="_blank">${{esc(t)}}</a>`);
      // Bare URLs (http/https not already inside an href)
      s = s.replace(/(?<!href=["'])https?:[/][/][^\\s<>"')]+/g,
        u => `<a href="${{esc(u)}}" target="_blank">${{esc(u)}}</a>`);
      return s;
    }}

    function linkifyText(text) {{
      const esc = t => t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      const escaped = esc(text);
      return escaped.replace(/https?:[/][/][^\\s<>"']+/g,
        u => `<a href="${{u}}" target="_blank">${{u}}</a>`);
    }}

    function looksLikeMarkdown(text) {{
      // Heuristic: contains at least one markdown marker.
      // Widened v1.58.10 — field test showed replies dominated by
      // fenced code or inline backtick code rendered raw because
      // the old regex didn't catch ``` or `x`.
      if (!text) return false;
      if (/^```/m.test(text)) return true;
      if (/^#{{1,6}}\\s|^\\s*[-*]\\s|^\\s*\\d+\\.\\s|\\*\\*|\\[.+\\]\\(|^---|^\\|/m.test(text)) return true;
      if (/`[^`\\n]+`/.test(text)) return true;
      return false;
    }}

    function addRunResult(r) {{
      const box = document.createElement('div');
      box.className = 'run-result' + (r.ok ? '' : ' err');
      const label = document.createElement('div');
      label.className = 'label';
      label.textContent = r.ok ? '실행 결과 / Result' : '실행 실패 / Error';
      box.appendChild(label);
      const raw = r.ok
        ? (r.value || '(empty)')
        : (r.error || r.value || '(no message)');
      if (r.ok && looksLikeMarkdown(raw)) {{
        const md = document.createElement('div');
        md.className = 'md-body';
        md.innerHTML = renderMarkdown(raw);
        box.appendChild(md);
      }} else {{
        const pre = document.createElement('pre');
        pre.textContent = raw;
        box.appendChild(pre);
      }}
      if (r.diagnostic) {{
        // Collapsible — diagnosis is long and mostly for the agent
        // on the next turn, not for the user on this turn.
        // hyun06000 2026-04-24: "다 보여주지 않아도 될듯. 적어도
        // 접었다 펴는 토글 정도로."
        const details = document.createElement('details');
        details.style.cssText =
          'margin-top:6px;font-size:12px;color:#6b7280;';
        const summary = document.createElement('summary');
        summary.style.cssText =
          'cursor:pointer;user-select:none;color:#6b7280;';
        const diagFirstLine = r.diagnostic.split('\\n')
          .find(l => l.trim().length > 0) || '진단';
        summary.textContent = '🔍 진단 보기 / Show diagnosis  · ' +
          diagFirstLine.slice(0, 80) +
          (diagFirstLine.length > 80 ? '…' : '');
        details.appendChild(summary);
        const d = document.createElement('pre');
        d.style.cssText =
          'margin:6px 0 0;padding:8px;background:#f3f4f6;' +
          'border-radius:4px;font-size:11px;white-space:pre-wrap;' +
          'color:#374151;max-height:300px;overflow-y:auto;';
        d.textContent = r.diagnostic;
        details.appendChild(d);
        box.appendChild(details);
      }}
      // Pre-auto-fix era had a manual "🔧 에이전트에게 수정 요청"
      // button here. v1.54 auto-fix fires on every !r.ok, so the
      // button and the "⚙ 자동 수정 중…" spinner ended up rendered
      // at the same time — redundant and visually confusing. Drop
      // the manual button; auto-fix handles the failure path. When
      // AUTO_CYCLE_MAX is hit the CTA bubble tells the user to
      // intervene via chat, which is the only remaining exit.
      thread.appendChild(box);
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
      cancelBtn.style.display = '';
      currentAbortController = new AbortController();

      // Pending bubble with elapsed-time counter. hyun06000 asked
      // for visible token feedback during the wait; the honest
      // piece we can show before the response arrives is how long
      // the user has been waiting.
      const pendingTurn = document.createElement('div');
      pendingTurn.className = 'turn agent';
      const pendingBubble = document.createElement('div');
      pendingBubble.className = 'bubble';
      pendingBubble.style.color = '#6b7280';
      const waitStart = Date.now();
      pendingBubble.textContent = '⏳ Claude 응답 중… (0s)';
      pendingTurn.appendChild(pendingBubble);
      thread.appendChild(pendingTurn);
      scrollBottom();
      const pendingTimer = setInterval(() => {{
        const s = Math.floor((Date.now() - waitStart) / 1000);
        pendingBubble.textContent = '⏳ Claude 응답 중… (' + s + 's)';
      }}, 250);

      try {{
        const r = await fetch('/authoring-chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'text/plain; charset=utf-8' }},
          body: userText,
          signal: currentAbortController.signal,
        }});
        clearInterval(pendingTimer);
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
        // Pick up input-usage flag from the agent turn so the
        // next Run widget renders with or without the input box.
        if (typeof data.input_used !== 'undefined') {{
          inputUsedForNext = data.input_used;
        }}
        if (Array.isArray(data.env_required)) {{
          envRequiredForNext = data.env_required;
        }}
        if (Array.isArray(data.programs)) {{
          programsForNext = data.programs;
        }}
        if (data.active_program) {{
          activeProgramForNext = data.active_program;
        }}
        addAgent(data.reply || '(empty)', data.files || [], data.action || null);
        if (typeof data.session_total_tokens === 'number') {{
          sessionTotalTokens = data.session_total_tokens;
          appendTokenFooter(thread.lastElementChild, data.input_tokens, data.output_tokens);
          renderTokenWidget();
        }}
        // Agent turn may have written files — refresh the tree so
        // the user sees new / updated files immediately.
        refreshFileTree();
      }} catch (e) {{
        clearInterval(pendingTimer);
        pendingTurn.remove();
        if (e.name === 'AbortError') {{
          addError('중단됨 / Cancelled');
        }} else {{
          addError('네트워크 오류: ' + e.message);
        }}
      }} finally {{
        sendBtn.disabled = false;
        msgEl.disabled = false;
        cancelBtn.style.display = 'none';
        currentAbortController = null;
        msgEl.value = '';
        msgEl.style.height = 'auto';
        msgEl.focus();
        scrollBottom();
      }}
    }}

    cancelBtn.addEventListener('click', () => {{
      if (currentAbortController) currentAbortController.abort();
    }});

    function onSend(e) {{
      e.preventDefault();
      const t = msgEl.value.trim();
      if (!t) return false;
      send(t);
      return false;
    }}


    // Chat export / copy affordances.
    async function fetchChatMarkdown() {{
      const r = await fetch('/authoring-chat-export');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.text();
    }}

    document.getElementById('export-chat').addEventListener('click',
      async (e) => {{
        e.preventDefault();
        try {{
          const md = await fetchChatMarkdown();
          const blob = new Blob([md], {{ type: 'text/markdown' }});
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = {json_project_name} + '-chat.md';
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        }} catch (err) {{
          addError('내보내기 실패 / export failed: ' + err.message);
        }}
    }});

    document.getElementById('copy-chat').addEventListener('click',
      async (e) => {{
        e.preventDefault();
        // Capture the link element synchronously — after an `await`
        // the event has finished propagating and e.currentTarget
        // becomes null, which crashed with "Cannot read properties
        // of null (reading 'textContent')" during field test.
        const link = e.currentTarget;
        const orig = link.textContent;
        try {{
          const md = await fetchChatMarkdown();
          if (navigator.clipboard && navigator.clipboard.writeText) {{
            await navigator.clipboard.writeText(md);
          }} else {{
            // Fallback for browsers without the Clipboard API (or for
            // any non-secure context). Uses a hidden textarea +
            // document.execCommand('copy') — deprecated but still the
            // only cross-context fallback.
            const ta = document.createElement('textarea');
            ta.value = md;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.top = '-1000px';
            document.body.appendChild(ta);
            ta.select();
            const ok = document.execCommand('copy');
            document.body.removeChild(ta);
            if (!ok) throw new Error('execCommand copy returned false');
          }}
          link.textContent = '✓ 복사됨 / copied';
          setTimeout(() => {{ link.textContent = orig; }}, 1500);
        }} catch (err) {{
          addError('복사 실패 / copy failed: ' + err.message);
        }}
    }});

    // Image export — captures the actual chat UI via html2canvas.
    function loadHtml2Canvas() {{
      if (window.html2canvas) return Promise.resolve(window.html2canvas);
      return new Promise((resolve, reject) => {{
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
        s.onload = () => resolve(window.html2canvas);
        s.onerror = () => reject(new Error('html2canvas 로드 실패. 인터넷 연결을 확인해주세요.'));
        document.head.appendChild(s);
      }});
    }}

    document.getElementById('save-image').addEventListener('click', async (e) => {{
      e.preventDefault();
      const link = e.currentTarget;
      const orig = link.textContent;
      link.textContent = '캡처 중…';
      try {{
        const h2c = await loadHtml2Canvas();
        // Hide UI controls that shouldn't appear in the screenshot
        const hideEls = document.querySelectorAll(
          '.composer, .settings-panel, .settings-overlay, .run-card .run-inline, #fix-btn'
        );
        hideEls.forEach(el => {{ el.dataset._h2cHidden = el.style.visibility; el.style.visibility = 'hidden'; }});
        const canvas = await h2c(thread, {{
          backgroundColor: getComputedStyle(document.documentElement)
            .getPropertyValue('--bg').trim() || '#fafafa',
          scale: 2,
          useCORS: true,
          scrollX: 0,
          scrollY: 0,
          width: thread.scrollWidth,
          height: thread.scrollHeight,
          windowWidth: thread.scrollWidth,
          windowHeight: thread.scrollHeight,
        }});
        hideEls.forEach(el => {{ el.style.visibility = el.dataset._h2cHidden || ''; }});
        const proj = document.querySelector('h1')?.textContent || 'chat';
        canvas.toBlob(blob => {{
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = proj.replace(/\\s+/g, '-').toLowerCase() + '-chat.png';
          a.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        }}, 'image/png');
      }} catch (err) {{
        addError('이미지 저장 실패: ' + err.message);
      }} finally {{
        link.textContent = orig;
      }}
    }});

    // ── Settings panel ──────────────────────────────────────────────
    const settingsPanel   = document.getElementById('settings-panel');
    const settingsOverlay = document.getElementById('settings-overlay');
    const senvList        = document.getElementById('senv-list');

    async function openSettings() {{
      await refreshEnvList();
      settingsPanel.classList.add('open');
      settingsOverlay.classList.add('open');
    }}
    function closeSettings() {{
      settingsPanel.classList.remove('open');
      settingsOverlay.classList.remove('open');
    }}
    document.getElementById('open-settings').addEventListener('click', (e) => {{
      e.preventDefault(); openSettings();
    }});

    document.getElementById('reset-chat').addEventListener('click', async (e) => {{
      e.preventDefault();
      if (!confirm('대화 기록을 초기화할까요? 이 작업은 되돌릴 수 없습니다.\\nReset chat history? This cannot be undone.')) return;
      try {{
        const r = await fetch('/authoring-reset-chat', {{ method: 'POST' }});
        if (!r.ok) {{ alert('초기화 실패: HTTP ' + r.status); return; }}
        location.reload();
      }} catch (err) {{
        alert('초기화 실패: ' + err.message);
      }}
    }});
    document.getElementById('settings-close').addEventListener('click', closeSettings);
    settingsOverlay.addEventListener('click', closeSettings);

    async function refreshEnvList() {{
      try {{
        const r = await fetch('/authoring-env-list');
        const keys = await r.json();
        renderEnvList(keys);
      }} catch (e) {{
        senvList.innerHTML = '<p class="settings-empty">불러오기 실패</p>';
      }}
    }}

    function renderEnvList(keys) {{
      senvList.innerHTML = '';
      if (!keys.length) {{
        senvList.innerHTML = '<p class="settings-empty">저장된 키가 없어요.</p>';
        return;
      }}
      keys.forEach(name => {{
        const row = document.createElement('div');
        row.className = 'senv-row';
        row.dataset.name = name;
        row.innerHTML = `
          <span class="senv-name">${{name}}</span>
          <span class="senv-mask">••••••</span>
          <button class="senv-btn edit-btn">수정</button>
          <button class="senv-btn del del-btn">삭제</button>`;
        row.querySelector('.edit-btn').onclick = () => showEditRow(name, row);
        row.querySelector('.del-btn').onclick  = () => deleteEnvKey(name, row);
        senvList.appendChild(row);
      }});
    }}

    function showEditRow(name, row) {{
      const edit = document.createElement('div');
      edit.className = 'senv-edit-row';
      edit.innerHTML = `
        <div class="senv-name">${{name}}</div>
        <input type="password" placeholder="새 값 / New value" autocomplete="off">
        <div class="senv-edit-actions">
          <button class="senv-btn save-edit-btn" style="background:#111;color:#fff;border:0">저장</button>
          <button class="senv-btn cancel-edit-btn">취소</button>
        </div>`;
      const inp = edit.querySelector('input');
      edit.querySelector('.save-edit-btn').onclick = async () => {{
        const val = inp.value.trim();
        if (!val) return;
        await saveEnvKey(name, val);
        edit.remove();
        row.style.display = 'flex';
      }};
      edit.querySelector('.cancel-edit-btn').onclick = () => {{
        edit.remove(); row.style.display = 'flex';
      }};
      row.style.display = 'none';
      row.after(edit);
      inp.focus();
    }}

    async function saveEnvKey(name, value) {{
      await fetch('/authoring-set-env', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ name, value }}),
      }});
    }}

    async function deleteEnvKey(name, row) {{
      if (!confirm(`"${{name}}" 키를 삭제할까요?`)) return;
      const r = await fetch('/authoring-delete-env', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ name }}),
      }});
      if (r.ok) {{
        row.remove();
        if (!senvList.querySelector('.senv-row')) {{
          senvList.innerHTML = '<p class="settings-empty">저장된 키가 없어요.</p>';
        }}
      }}
    }}

    document.getElementById('senv-add-btn').addEventListener('click', async () => {{
      const nameEl = document.getElementById('senv-new-name');
      const valEl  = document.getElementById('senv-new-value');
      const name = nameEl.value.trim();
      const value = valEl.value.trim();
      if (!name || !value) return;
      const r = await fetch('/authoring-set-env', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ name, value }}),
      }});
      if (r.ok) {{
        nameEl.value = ''; valEl.value = '';
        await refreshEnvList();
      }} else {{
        const msg = await r.text();
        addError('저장 실패: ' + msg);
      }}
    }});

    msgEl.focus();
  </script>
</body>
</html>
"""


def _history_to_json_embed(history: list) -> str:
    """Serialize chat history for embedding in the page. Each entry is
    sanitized to only include the fields the UI needs. Both regular
    turns and run_result entries are supported so reloading the page
    preserves the full conversation including run outputs."""
    import json
    safe = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == "run_result":
            safe.append({
                "kind": "run_result",
                "ok": bool(entry.get("ok", False)),
                "value": str(entry.get("value", "")),
                "error": str(entry.get("error", "")),
                "diagnostic": str(entry.get("diagnostic", "")),
            })
            continue
        safe.append({
            "user": str(entry.get("user", "")),
            "reply": str(entry.get("reply", "")),
            "files": entry.get("files", []) if isinstance(entry.get("files"), list) else [],
            "action": entry.get("action") if entry.get("action") in (
                "ready_to_run", "ready_to_serve", "ready_to_deploy"
            ) else None,
        })
    return json.dumps(safe, ensure_ascii=False).replace("</", "<\\/")
