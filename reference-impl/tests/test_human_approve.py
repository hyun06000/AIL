"""Tests for the `perform human.approve(plan)` effect.

HEAAL pattern: plan-validate-execute. A program that is about to do
something irreversible (post, send, create) must first hand the plan
to the user via `human.approve`, which blocks until the user clicks
Approve or Decline in the UI. Without this primitive, the class of
"program silently did the wrong thing" cannot be structurally closed.

The effect writes its pending record to `$AIL_APPROVAL_DIR/pending.json`
and polls that file for a decision. Tests drive the decision by
writing the file from a sibling thread, exactly as the agentic
server's `/authoring-approve` endpoint does at runtime.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str, inp: str = ""):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": inp}).value


@pytest.fixture()
def approval_dir(tmp_path, monkeypatch):
    d = tmp_path / "approvals"
    d.mkdir()
    monkeypatch.setenv("AIL_APPROVAL_DIR", str(d))
    return d


def _decide_after(approval_dir: Path, decision: str, reason: str = "",
                  delay_s: float = 0.2, comment: str = ""):
    """Write a decision into pending.json after `delay_s` seconds.

    Mirrors what the server's /authoring-approve endpoint does when
    the user clicks a button. Spawned as a daemon thread so tests
    drive the blocking `human.approve` effect end-to-end.
    """
    def _worker():
        time.sleep(delay_s)
        path = approval_dir / "pending.json"
        # Wait (briefly) for the effect to actually write the
        # pending record — without this the worker could race and
        # miss the file entirely.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if path.is_file():
                break
            time.sleep(0.05)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = decision
        if reason:
            data["reason"] = reason
        if comment:
            data["comment"] = comment
        path.write_text(json.dumps(data), encoding="utf-8")
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def test_approve_unblocks_program(approval_dir):
    _decide_after(approval_dir, "approved")
    out = _run(
        'entry main(input: Text) {\n'
        '  r = perform human.approve("post title X to repo Y?")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "did the action"\n'
        '}\n'
    )
    assert out == "did the action"
    # Cleanup: effect removes the pending file on decision.
    assert not (approval_dir / "pending.json").exists()


def test_approve_carries_user_comment_in_record(approval_dir):
    """v1.58.7: human.approve returns Record, not Boolean, so the
    user's optional comment ("승인, 브랜치 이름만 X로") reaches the
    program and lets the agent adapt its next step. Empty comment
    works too — backward-compatible with old tests."""
    _decide_after(approval_dir, "approved",
                  comment="branch name should be feature/heaal")
    out = _run(
        'entry main(input: Text) {\n'
        '  r = perform human.approve("create branch add-ail?")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  rec = unwrap(r)\n'
        '  return join(["user_comment=", to_text(get(rec, "comment"))], "")\n'
        '}\n'
    )
    assert out == "user_comment=branch name should be feature/heaal"


def test_approve_without_comment_still_works(approval_dir):
    """No comment → approved record has empty comment field. Programs
    that only check is_error and proceed (most do) are unaffected."""
    _decide_after(approval_dir, "approved")
    out = _run(
        'entry main(input: Text) {\n'
        '  r = perform human.approve("ok?")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  rec = unwrap(r)\n'
        '  return to_text(get(rec, "comment"))\n'
        '}\n'
    )
    assert out == ""


def test_decline_surfaces_as_error_result(approval_dir):
    _decide_after(approval_dir, "declined", reason="not today")
    out = _run(
        'entry main(input: Text) {\n'
        '  r = perform human.approve("post now?")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "should not reach here"\n'
        '}\n'
    )
    assert "user declined" in out
    assert "not today" in out


def test_outside_ui_context_returns_clean_error(tmp_path, monkeypatch):
    # Simulate running `ail run` (no agentic server, no AIL_APPROVAL_DIR).
    monkeypatch.delenv("AIL_APPROVAL_DIR", raising=False)
    out = _run(
        'entry main(input: Text) {\n'
        '  r = perform human.approve("post now?")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "ok"\n'
        '}\n'
    )
    assert "no UI context" in out


def test_empty_plan_rejected(approval_dir):
    out = _run(
        'entry main(input: Text) {\n'
        '  r = perform human.approve("")\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "ok"\n'
        '}\n'
    )
    assert "non-empty" in out


def test_pending_record_shape(approval_dir, monkeypatch):
    # While the run is blocked, the pending record must exist on
    # disk with id + plan + status=pending. Verify by having the
    # decision worker read the file before writing the decision.
    captured = {}

    def _capture_then_approve():
        path = approval_dir / "pending.json"
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if path.is_file():
                try:
                    captured.update(json.loads(
                        path.read_text(encoding="utf-8")))
                except Exception:
                    pass
                if captured.get("status") == "pending":
                    break
            time.sleep(0.05)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "approved"
        path.write_text(json.dumps(data), encoding="utf-8")

    threading.Thread(target=_capture_then_approve, daemon=True).start()
    _run(
        'entry main(input: Text) {\n'
        '  r = perform human.approve("planned: post title ABC")\n'
        '  return "done"\n'
        '}\n'
    )
    assert captured.get("plan") == "planned: post title ABC"
    assert captured.get("status") == "pending"
    assert "id" in captured
    assert "created_at" in captured
