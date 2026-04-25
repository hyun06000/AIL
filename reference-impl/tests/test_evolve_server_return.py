"""Regression tests for evolve-server bare-return + intent error origin.

qna_bot field test 2026-04-26 surfaced two runtime bugs:

1. **Bare `return`** (after `perform http.respond`) overrode the actual
   response with the literal string `"None"`. The ReturnSignal handler
   in `run_server.catch_all` had no None-case and fell through to
   `str(v)`. Every route was returning HTTP 200 + body "None".

2. **`_invoke_intent` adapter-error fallback** referenced an
   undefined local `origin`, raising `NameError: name 'origin' is not
   defined` for any intent call when the model adapter failed (e.g.
   missing API key). The error surfaced as a 500 with a JSON-wrapped
   NameError instead of the intended low-confidence INTENT_ERROR
   value.

Both are tested below by spawning `ail run` in a subprocess on a
random free port and curling — the run_server dispatcher only exists
inside Flask.run, so an in-process test would need to refactor the
Flask app construction.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
import urllib.error

import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(("127.0.0.1", port))
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _curl(url: str, method: str = "GET", body: bytes | None = None,
          ct: str = "application/json") -> tuple[int, str]:
    req = urllib.request.Request(url, method=method, data=body)
    if body is not None:
        req.add_header("Content-Type", ct)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


@pytest.fixture
def server(tmp_path):
    """Yield (project_dir, port) for an ail-run server, cleaned up on teardown."""
    project = tmp_path / "proj"
    project.mkdir()
    port = _free_port()
    procs: list[subprocess.Popen] = []

    def _start(source: str) -> int:
        (project / "app.ail").write_text(source)
        env = dict(os.environ)
        env["PORT"] = str(port)
        # Block any real model adapter — the intent-error test wants
        # the adapter to fail so the fallback path is exercised.
        for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY",
                  "AIL_OLLAMA_MODEL", "AIL_OPENAI_COMPAT_MODEL"):
            env.pop(k, None)
        p = subprocess.Popen(
            [sys.executable, "-m", "ail.cli", "run", "app.ail"],
            cwd=project, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(p)
        assert _wait_for_port(port), "server did not bind in time"
        return port

    yield _start
    for p in procs:
        p.terminate()
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()


def test_bare_return_after_http_respond_preserves_body(server):
    """Bug: bare `return` after `perform http.respond` was sending
    the literal string `"None"` as the response body."""
    src = textwrap.dedent("""
    evolve s {
        listen: 8090
        metric: error_rate
        when request_received(req) {
            perform http.respond(200, "text/plain", "hello-world")
            return
        }
        rollback_on: error_rate > 0.99
        history: keep_last 10
    }
    entry main(input: Text) { return "ok" }
    """)
    port = server(src)
    code, body = _curl(f"http://127.0.0.1:{port}/")
    assert code == 200
    assert body == "hello-world", f"body was {body!r}, expected 'hello-world'"


def test_bare_return_preserves_status_and_content_type(server):
    """Bug variant: bare `return` was also clobbering status (forcing
    200) and content-type (forcing text/plain)."""
    src = textwrap.dedent("""
    evolve s {
        listen: 8090
        metric: error_rate
        when request_received(req) {
            perform http.respond(404, "application/json", "{\\"error\\":\\"x\\"}")
            return
        }
        rollback_on: error_rate > 0.99
        history: keep_last 10
    }
    entry main(input: Text) { return "ok" }
    """)
    port = server(src)
    code, body = _curl(f"http://127.0.0.1:{port}/")
    assert code == 404
    assert body == '{"error":"x"}'


def test_intent_adapter_error_does_not_crash_with_nameerror(server):
    """Bug: when an intent's model adapter raised (no credentials),
    the fallback path referenced an undefined `origin`, producing
    `NameError: name 'origin' is not defined` instead of a graceful
    INTENT_ERROR value the AIL program could observe."""
    src = textwrap.dedent("""
    intent ask(q: Text) -> Text {
        goal: "echo"
    }
    evolve s {
        listen: 8090
        metric: error_rate
        when request_received(req) {
            answer = ask("hi")
            perform http.respond(200, "text/plain", answer)
            return
        }
        rollback_on: error_rate > 0.99
        history: keep_last 10
    }
    entry main(input: Text) { return "ok" }
    """)
    port = server(src)
    code, body = _curl(f"http://127.0.0.1:{port}/")
    # Without the fix: 500 + body containing "name 'origin' is not defined".
    # With the fix: 200 + body starting with "INTENT_ERROR:" (graceful).
    assert "name 'origin' is not defined" not in body
    assert code == 200
    assert body.startswith("INTENT_ERROR:"), f"unexpected body: {body!r}"
