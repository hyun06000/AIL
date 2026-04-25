"""Subprocess-based deployment management — **scaffolding, build to delete**.

PRINCIPLES.md §5-bis (Arche, 2026-04-24): OS primitives (subprocess,
pid, SIGTERM) are not HEAAL-native. A proper lifecycle for an AIL
agent is expressed in the grammar — e.g. ``evolve my_agent { metric:
health; when health < 0.1 { shutdown } }`` — and handled by the
agent-community layer. Until that layer exists, we spawn independent
server processes with ``python -m ail run`` (or ``serve``) and track
them via a pidfile. This module is that scaffolding, deliberately
isolated so the replacement can swap in as a single change.

**Replacement layer (Arche v1.60.9 review, 2026-04-26 — name TENTATIVE):**
Arche proposed **Polis** as the working label for the agent community
layer where ``perform process.spawn`` and ``perform process.stop``
become first-class effects. Telos (msg_1777157709_11) flagged that
hard-coding an L3 label in L2 risks the code lying once that L3 design
moves; we treat "Polis" as a working name only — the *interface*
boundary is what matters, not the label. The replacement may end up
called Polis, may be folded back into HEAAOS, or may pick up a new
name entirely. What stays true: when the replacement ships, the call
sites in ``server.py`` retarget to those effects and *this file gets
deleted*. Keep the deletion path clear: do not let HTTP, UI, or
editing-loop concerns leak in here, and do not let any caller depend
on subprocess details (``Popen``, ``os.kill``, signals). Callers see
this module as a pure ``start_deployment(project) → record`` /
``stop_deployment`` interface, which the future ``perform process.*``
will satisfy identically — whatever it ends up being called.

What lives here:
- ``.ail/deployment.json`` read/write (pid, port, url, started_at, log)
- Port allocation (scan 8090..8199 for a free TCP port)
- Subprocess spawn via ``python -m ail run|serve`` with
  ``start_new_session`` so the child survives the parent exit
- Signal-based stop (SIGTERM)
- Liveness probe (``os.kill(pid, 0)``) with stale-record cleanup

What must NOT leak in here:
- HTTP handler code (that stays in server.py and calls into these fns)
- Anything tied to the chat UI or the editing loop
- Any caller-visible reliance on ``Popen`` / ``os.kill`` semantics
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


_PORT_SCAN_START = 8090
_PORT_SCAN_END = 8200


def _deployment_path(project) -> Path:
    return project.state_dir / "deployment.json"


def _log_path(project) -> Path:
    return project.state_dir / "deployment.log"


def _pick_free_port() -> int:
    for p in range(_PORT_SCAN_START, _PORT_SCAN_END):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            s.close()
    return 0


def read_deployment(project) -> Optional[dict]:
    """Return the current deployment record, or None if no live
    deployment exists. A record whose pid is no longer alive is
    treated as stale — we clean up the file and return None so the
    caller sees the system in its true state."""
    path = _deployment_path(project)
    if not path.is_file():
        return None
    try:
        rec = json.loads(path.read_text())
        os.kill(int(rec["pid"]), 0)
        return rec
    except (ProcessLookupError, ValueError, OSError, KeyError):
        path.unlink(missing_ok=True)
        return None


def _resolve_active_program_path(project):
    """Resolve which `.ail` file to treat as the deploy target.

    Precedence: `.ail/active_program` marker → `app.ail` → first
    `.ail` file found in the project root. qna_bot field test
    2026-04-26: when the agent emits a descriptively-named file
    like `qna_server.ail` (default-named `app.ail` doesn't exist),
    `_program_is_evolve_server` was reading an empty source and
    returning False, breaking the whole Deploy CTA chain.
    """
    root = project.root
    marker = project.state_dir / "active_program"
    if marker.is_file():
        try:
            name = marker.read_text(encoding="utf-8").strip()
        except OSError:
            name = ""
        if name and name.endswith(".ail") and "/" not in name and "\\" not in name:
            candidate = root / name
            if candidate.is_file():
                return candidate
    if project.app_path.is_file():
        return project.app_path
    try:
        for p in sorted(root.iterdir()):
            if p.is_file() and p.suffix == ".ail":
                return p
    except OSError:
        pass
    return None


def _program_is_evolve_server(project) -> bool:
    """Return True if the project's active program declares an
    evolve-server block (an `evolve` decl with a
    `when request_received(req)` arm).

    Resolves the active program via marker → app.ail → any .ail in
    root, so descriptively-named files (e.g. qna_server.ail) work.

    Evolve-server programs cannot be deployed via `ail serve` — that
    only serves view.html. They need `ail run`, which dispatches to
    `executor.run_server()` and starts the Flask listener defined by
    the user's `when request_received` arm. Detecting this here lets
    Deploy auto-pick the right launcher.
    """
    target = _resolve_active_program_path(project)
    if target is None:
        return False
    try:
        source = target.read_text(encoding="utf-8")
    except Exception:
        return False
    try:
        from ..parser import parse
        from ..parser.ast import EvolveDecl
        program = parse(source)
        for decl in program.declarations:
            if isinstance(decl, EvolveDecl) and decl.server_arm is not None:
                return True
    except Exception:
        return False
    return False


def start_deployment(project) -> dict:
    """Spawn the project on a free port and record the resulting
    {pid, port, url, started_at, log, mode}. Returns the existing record
    unchanged if a live deployment already exists. Raises RuntimeError
    if no port is available.

    Two launch modes:
    - **evolve-server** — app.ail has `evolve { when request_received }`.
      Spawn `python -m ail run app.ail` with `PORT=<picked>` so the
      executor's `run_server()` Flask listener binds the picked port.
      The user's `request_received` arm handles every route, including
      serving view.html for `/` and `/run`.
    - **single-shot / view.html** — anything else. Spawn `python -m ail
      serve` which serves view.html and the `/run` widget. The program
      runs once per Run click, not as a persistent listener.

    Mode is auto-detected from app.ail's grammar so the agent can write
    either kind without the user having to choose a launcher.
    """
    existing = read_deployment(project)
    if existing is not None:
        return existing
    port = _pick_free_port()
    if not port:
        raise RuntimeError(
            f"no free port in {_PORT_SCAN_START}-{_PORT_SCAN_END - 1}")
    log_path = _log_path(project)
    log_fh = open(log_path, "a", encoding="utf-8")

    is_evolve_server = _program_is_evolve_server(project)
    if is_evolve_server:
        mode = "evolve-server"
        # Resolve the actual evolve-server file — was hard-coded
        # `project.app_path` and silently picking app.ail even when the
        # active program lived in qna_server.ail (qna_bot field test
        # 2026-04-26).
        target = _resolve_active_program_path(project) or project.app_path
        cmd = [sys.executable, "-m", "ail", "run", str(target)]
        env = dict(os.environ)
        env["PORT"] = str(port)
        log_fh.write(
            f"\n=== ail run (evolve-server) start "
            f"{time.strftime('%Y-%m-%dT%H:%M:%S')} port={port} ===\n")
    else:
        mode = "single-shot"
        cmd = [sys.executable, "-m", "ail", "serve",
               str(project.root), "--port", str(port), "--host", "127.0.0.1"]
        env = None
        log_fh.write(
            f"\n=== ail serve start {time.strftime('%Y-%m-%dT%H:%M:%S')} "
            f"port={port} ===\n")
    log_fh.flush()
    proc = subprocess.Popen(
        cmd,
        stdout=log_fh, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
        cwd=str(project.root),
    )
    record = {
        "pid": proc.pid,
        "port": port,
        "url": f"http://127.0.0.1:{port}/",
        "started_at": time.time(),
        "log": str(log_path),
        "mode": mode,
    }
    if mode == "single-shot":
        record["url"] = f"http://127.0.0.1:{port}/run"
    _deployment_path(project).write_text(
        json.dumps(record, ensure_ascii=False))
    project.append_ledger({
        "event": "deployment_start",
        "pid": proc.pid,
        "port": port,
        "mode": mode,
    })
    return record


def stop_deployment(project) -> bool:
    """Send SIGTERM to the deployed process and clear the record.
    Returns True if something was stopped, False if there was no
    record to stop. ``ProcessLookupError`` (already dead) counts as
    True — the record is still cleaned."""
    path = _deployment_path(project)
    if not path.is_file():
        return False
    try:
        rec = json.loads(path.read_text())
        pid = int(rec["pid"])
    except (ValueError, OSError, KeyError):
        path.unlink(missing_ok=True)
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    path.unlink(missing_ok=True)
    project.append_ledger({"event": "deployment_stop", "pid": pid})
    return True


def self_terminate(project, delay_s: float = 0.2) -> None:
    """Schedule a SIGTERM on the current process (used by `/admin/stop`
    inside an `ail serve` instance). Runs in a daemon thread so the
    HTTP response can flush first. Also clears any local deployment
    record — relevant for the edge case where the serve process knows
    about its own deployment.json and wants to leave the system
    consistent on exit."""
    import threading
    path = _deployment_path(project)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    project.append_ledger({"event": "admin_stop"})
    def _suicide():
        time.sleep(delay_s)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=_suicide, daemon=True).start()
