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
    # Safely quoted project name for embedding in JS.
    import json as _json
    json_project_name = _json.dumps(project_name or "ail-project")

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
    .sub a {{ color: var(--muted); text-decoration: underline;
      text-decoration-color: #d1d5db; cursor: pointer; }}
    .sub a:hover {{ color: #111; text-decoration-color: #111; }}
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
      font-size: 12px; color: #374151; }}
    .program-picker select {{ font-family: ui-monospace, Menlo,
      monospace; font-size: 12px; padding: 4px 8px;
      border: 1px solid var(--border); border-radius: 4px;
      background: #fff; }}
    .program-picker .flag {{ font-size: 11px; color: #6b7280;
      font-family: ui-monospace, Menlo, monospace; }}
    .program-picker .flag.bad {{ color: #b91c1c; }}
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
  </style>
</head>
<body>
  <div class="page">
    <header>
      <h1>{name}</h1>
      <div class="sub">ail authoring · {escape(host)}:{port} · 채팅으로 프로젝트를 만드세요
        · <a href="#" id="export-chat">대화 내보내기 / Export</a>
        · <a href="#" id="copy-chat">복사 / Copy</a>
      </div>
    </header>

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
        addRunWidget(false);
      }} else if (action === 'ready_to_serve' || action === 'ready_to_deploy') {{
        addRunWidget(true);
      }}
    }}

    // Multi-program state (v1.13.1). Each turn's response carries the
    // full list of `.ail` files in the project plus which is active;
    // the Run widget uses this to render a selector.
    let programsForNext = [];
    let activeProgramForNext = null;
    // Backward-compat shadows for single-program cases — kept in sync
    // with the active program's metadata.
    let inputUsedForNext = true;
    let envRequiredForNext = [];

    // Inline widget that the user can invoke repeatedly without
    // leaving the chat. For `ready_to_run` it's a plain run box.
    // For `ready_to_serve` it's the same widget wrapped as a service
    // card with a share link to /service (the classic service UI on
    // a separate route, for handing out to non-chat consumers).
    // `inputUsed` controls whether to render the input textarea —
    // when false (entry doesn't reference input), the widget is a
    // bare Run button with no confusing empty input field.
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
        title.textContent = '🌐 서비스 모드 / Service mode';
        card.appendChild(title);
        const desc = document.createElement('div');
        desc.className = 'desc';
        desc.textContent = '이 프로그램을 반복해서 호출할 수 있어요. ' +
          '외부에 공유할 페이지도 준비돼 있어요.';
        card.appendChild(desc);
        const link = document.createElement('a');
        link.className = 'share-link';
        link.href = '/service';
        link.target = '_blank';
        link.textContent = '공유용 페이지 열기 / Open public page →';
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
          opt.textContent = p.name + (p.parses ? '' : ' (parse error)');
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
      // Env-var requirement block — shown when the authored app.ail
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
        input.placeholder = service
          ? '입력이 필요하면 여기 (비워두면 빈 입력) / input (optional)'
          : '입력 (선택) / input (optional, leave blank if none)';
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
        try {{
          const url = '/authoring-run?program=' + encodeURIComponent(selected);
          const r = await fetch(url, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'text/plain; charset=utf-8' }},
            body: input ? input.value : '',
          }});
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
        }} catch (e) {{
          placeholder.remove();
          addError('네트워크 오류: ' + e.message);
        }} finally {{
          runBtn.disabled = false;
        }}
      }};
      runBtn.onclick = fire;
      dynSlot.appendChild(runBtn);
      }}  // end renderDynamic

      renderDynamic();
      thread.appendChild(card);
    }}

    function addRunResult(r) {{
      const box = document.createElement('div');
      box.className = 'run-result' + (r.ok ? '' : ' err');
      const label = document.createElement('div');
      label.className = 'label';
      label.textContent = r.ok ? '실행 결과 / Result' : '실행 실패 / Error';
      box.appendChild(label);
      const pre = document.createElement('pre');
      pre.textContent = r.ok
        ? (r.value || '(empty)')
        : (r.error || r.value || '(no message)');
      box.appendChild(pre);
      if (r.diagnostic) {{
        const d = document.createElement('div');
        d.className = 'diag';
        d.textContent = r.diagnostic;
        box.appendChild(d);
      }}
      // On error, offer a one-click "ask the agent to fix it" button.
      // Sends a short message to the chat so the agent sees the error
      // context in history and writes a correction.
      if (!r.ok) {{
        const fixBar = document.createElement('div');
        fixBar.style.marginTop = '8px';
        const fixBtn = document.createElement('button');
        fixBtn.className = 'run-inline';
        fixBtn.style.background = '#b91c1c';
        fixBtn.textContent = '🔧 에이전트에게 수정 요청 / Ask agent to fix';
        fixBtn.onclick = () => {{
          fixBtn.disabled = true;
          send('방금 발생한 에러를 고쳐주세요. / Please fix the error above.');
        }};
        fixBar.appendChild(fixBtn);
        box.appendChild(fixBar);
      }}
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
