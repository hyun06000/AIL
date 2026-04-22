"""Auto-fix tests — bring_up with a stub adapter that returns a known
patched app.ail. Verifies the diagnose → chat → re-test loop.
"""
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

from ail.agentic.project import Project
from ail.agentic.agent import (
    bring_up,
    _diagnose_and_repair,
    _recent_test_failures,
    _format_repair_request,
)


@dataclass
class _StubResponse:
    value: Any
    raw: dict = None


class _StubAdapter:
    name = "stub"

    def __init__(self, payloads):
        # Allow a list of payloads consumed in order, one per chat call.
        self._payloads = list(payloads)
        self.calls = 0

    def invoke(self, **kwargs):
        self.calls += 1
        if not self._payloads:
            raise RuntimeError("StubAdapter exhausted")
        return _StubResponse(value=self._payloads.pop(0), raw={})


BROKEN_APP = """\
entry main(input: Text) {
    return "always ok"
}
"""

FIXED_APP = """\
entry main(input: Text) {
    if length(input) == 0 { return error("empty") }
    return ok(input)
}
"""

INTENT_BODY = """# demo

## Tests
- "hello" → succeed
- "" → 에러
"""


def _project(tmp_path):
    proj = Project.init(tmp_path / "demo")
    proj.intent_path.write_text(INTENT_BODY, encoding="utf-8")
    proj.write_app_source(BROKEN_APP)
    return proj


def test_recent_test_failures_extracts_only_latest_block(tmp_path):
    proj = _project(tmp_path)
    # Simulate two prior test runs in the ledger
    proj.append_ledger({"event": "test_run", "input": "old", "passed": False,
                        "expect_ok": True, "ran_ok": False})
    proj.append_ledger({"event": "auto_fix_attempt", "attempt": 1})
    # Latest block — only these should come back
    proj.append_ledger({"event": "test_run", "input": "x", "passed": True,
                        "expect_ok": True, "ran_ok": True})
    proj.append_ledger({"event": "test_run", "input": "y", "passed": False,
                        "expect_ok": False, "ran_ok": True})
    failures = _recent_test_failures(proj, limit=10)
    assert len(failures) == 1
    assert failures[0]["input"] == "y"


def test_format_repair_request_mentions_failures():
    fails = [
        {"input": "", "expect_ok": False, "ran_ok": True, "error": None},
    ]
    msg = _format_repair_request(fails)
    assert "empty" not in msg.lower() or "input=''" in msg
    assert "expected to error" in msg
    assert "observed: ran without error" in msg


def test_diagnose_and_repair_succeeds_on_first_try(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    spec = proj.read_intent()
    # Run tests once so failures land in the ledger.
    from ail.agentic.agent import _run_tests
    _run_tests(proj, spec.tests)

    adapter = _StubAdapter([
        {"intent_md": None, "app_ail": FIXED_APP, "summary": "fix"},
    ])
    # chat_apply uses _default_adapter() — patch it to return our stub
    import ail.agentic.chat as chat_mod
    monkeypatch.setattr(chat_mod, "_default_adapter", lambda: adapter)

    passed = _diagnose_and_repair(proj, spec, max_attempts=3)
    assert passed == 2
    assert proj.read_app_source().strip() == FIXED_APP.strip()


def test_diagnose_and_repair_gives_up_after_max_attempts(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    spec = proj.read_intent()
    from ail.agentic.agent import _run_tests
    _run_tests(proj, spec.tests)

    # Stub returns a "fix" that's also broken — same BROKEN_APP each time.
    adapter = _StubAdapter([
        {"intent_md": None, "app_ail": BROKEN_APP, "summary": "noop"},
        {"intent_md": None, "app_ail": BROKEN_APP, "summary": "noop"},
    ])
    import ail.agentic.chat as chat_mod
    monkeypatch.setattr(chat_mod, "_default_adapter", lambda: adapter)

    passed = _diagnose_and_repair(proj, spec, max_attempts=2)
    assert passed < 2
    assert adapter.calls == 2  # actually attempted both


def test_diagnose_stops_when_model_returns_no_change(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    spec = proj.read_intent()
    from ail.agentic.agent import _run_tests
    _run_tests(proj, spec.tests)

    adapter = _StubAdapter([
        {"intent_md": None, "app_ail": None, "summary": "I see no problem"},
    ])
    import ail.agentic.chat as chat_mod
    monkeypatch.setattr(chat_mod, "_default_adapter", lambda: adapter)

    passed = _diagnose_and_repair(proj, spec, max_attempts=5)
    # Model declined — gives up immediately, doesn't burn the full budget.
    assert adapter.calls == 1
    assert passed < 2


def test_bring_up_with_auto_fix_recovers(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    adapter = _StubAdapter([
        {"intent_md": None, "app_ail": FIXED_APP, "summary": "fix"},
    ])
    import ail.agentic.chat as chat_mod
    monkeypatch.setattr(chat_mod, "_default_adapter", lambda: adapter)

    rc = bring_up(proj, serve=False, auto_fix_attempts=2)
    assert rc == 0
    assert "ok(input)" in proj.read_app_source()


def test_bring_up_without_auto_fix_aborts_as_before(tmp_path):
    proj = _project(tmp_path)
    rc = bring_up(proj, serve=False, auto_fix_attempts=0)
    assert rc == 2
