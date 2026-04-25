"""Tests for `agentic.process_manager` deployment-mode detection.

The Deploy button must auto-pick the right launcher: `ail run` for
evolve-server programs (so the user's `when request_received` arm
actually starts), and `ail serve` for everything else (single-shot
programs that present a `view.html` + `/run` widget).

A non-developer should never see the difference — they click Deploy
and the URL works either way.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ail.agentic import Project
from ail.agentic.process_manager import _program_is_evolve_server


def _make_project(tmp_path: Path, app_source: str) -> Project:
    (tmp_path / "INTENT.md").write_text("# test\n")
    (tmp_path / "app.ail").write_text(app_source)
    (tmp_path / ".ail").mkdir(exist_ok=True)
    return Project.at(tmp_path)


def test_detects_evolve_server(tmp_path):
    src = textwrap.dedent("""
    evolve my_server {
        listen: 8080
        metric: error_rate
        when request_received(req) {
            perform http.respond(200, "text/plain", "hi")
        }
        rollback_on: error_rate > 0.5
        history: keep_last 100
    }
    """)
    proj = _make_project(tmp_path, src)
    assert _program_is_evolve_server(proj) is True


def test_single_shot_program_is_not_evolve_server(tmp_path):
    src = textwrap.dedent("""
    entry main(input: Text) -> Text {
        return "hello"
    }
    """)
    proj = _make_project(tmp_path, src)
    assert _program_is_evolve_server(proj) is False


def test_evolve_without_request_arm_is_not_server(tmp_path):
    """A plain `evolve` (no `when request_received`) is metric-driven
    tuning, not a server. Must not trigger the evolve-server path."""
    src = textwrap.dedent("""
    intent guess(x: Number) -> Number {
        goal: "double it"
    }
    evolve guess {
        metric: confidence(sampled: 1.0)
        when confidence < 0.5 {
            retune confidence_threshold: within [0.3, 0.8]
        }
        rollback_on: confidence < 0.15
        history: keep_last 5
    }
    entry main(x: Number) -> Number {
        return guess(x)
    }
    """)
    proj = _make_project(tmp_path, src)
    assert _program_is_evolve_server(proj) is False


def test_unparseable_app_is_not_server(tmp_path):
    """A broken app.ail must return False (not crash). The Deploy
    button still needs to make a decision — false is the safe default
    (single-shot uses `ail serve` which only serves files)."""
    proj = _make_project(tmp_path, "this is not valid AIL {{{")
    assert _program_is_evolve_server(proj) is False


def test_missing_app_is_not_server(tmp_path):
    (tmp_path / "INTENT.md").write_text("# test\n")
    (tmp_path / ".ail").mkdir(exist_ok=True)
    proj = Project.at(tmp_path)
    assert _program_is_evolve_server(proj) is False


def test_descriptively_named_evolve_server_via_active_program_marker(tmp_path):
    """qna_bot field test 2026-04-26: agent emits qna_server.ail
    (no app.ail) and writes the active_program marker pointing at
    it. Without resolving via the marker, _program_is_evolve_server
    reads an empty source from app_path and returns False, which
    breaks the Deploy CTA chain (service card never fades, no
    'Deploy' button appears, user sees both 'Run' and 'Open in new
    tab' simultaneously and gets confused)."""
    (tmp_path / "INTENT.md").write_text("# test\n")
    (tmp_path / ".ail").mkdir()
    (tmp_path / ".ail" / "active_program").write_text("qna_server.ail")
    src = textwrap.dedent("""
    intent answer(q: Text) -> Text { goal: "answer" }
    evolve qna_server {
        listen: 8090
        metric: error_rate
        when request_received(req) {
            perform http.respond(200, "text/plain", "hi")
        }
        rollback_on: error_rate > 0.99
        history: keep_last 10
    }
    entry main(input: Text) { return "ok" }
    """)
    (tmp_path / "qna_server.ail").write_text(src)
    proj = Project.at(tmp_path)
    assert _program_is_evolve_server(proj) is True


def test_descriptively_named_evolve_server_no_marker_fallback(tmp_path):
    """When the marker is missing AND app.ail is missing, the
    detector should still find the evolve-server by scanning the
    project root for any `.ail` file."""
    (tmp_path / "INTENT.md").write_text("# test\n")
    (tmp_path / ".ail").mkdir()
    src = textwrap.dedent("""
    evolve s {
        listen: 8090
        metric: error_rate
        when request_received(req) {
            perform http.respond(200, "text/plain", "hi")
        }
        rollback_on: error_rate > 0.99
        history: keep_last 10
    }
    entry main(input: Text) { return "ok" }
    """)
    (tmp_path / "qna_server.ail").write_text(src)
    proj = Project.at(tmp_path)
    assert _program_is_evolve_server(proj) is True


def test_python_dash_m_ail_is_runnable():
    """Deploy spawns `python -m ail run <file>` (process_manager).
    Without ail/__main__.py the package isn't directly runnable and
    spawn dies immediately with `No module named ail.__main__`,
    leaving a phantom deployment record in the UI. qna_bot field
    test 2026-04-26: deploy clicked → 즉시 silent fail → user sees
    'running' indicator but server never bound."""
    import subprocess, sys
    r = subprocess.run(
        [sys.executable, "-m", "ail", "version"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, (
        f"`python -m ail version` failed (returncode={r.returncode}). "
        f"stderr: {r.stderr!r}. The `ail/__main__.py` shim is missing, "
        "so process_manager's Deploy spawn will die instantly."
    )
    assert "ail" in (r.stdout + r.stderr).lower()
