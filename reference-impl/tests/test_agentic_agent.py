"""Agent loop tests — bring_up state machine using a pre-written app.ail
to avoid hitting an LLM. Authoring is exercised separately by tests
that mock the adapter; v0 just verifies the loop's branching.
"""
import json
from pathlib import Path

from ail.agentic.project import Project
from ail.agentic.agent import bring_up


SIMPLE_AIL = """\
pure fn echo_or_err(s: Text) -> Result[Text] {
    if length(s) == 0 { return error("empty") }
    return ok(s)
}

entry main(input: Text) {
    r = echo_or_err(input)
    if is_ok(r) { return unwrap(r) }
    return "ERR"
}
"""


def _write_intent(proj: Project, body: str) -> None:
    proj.intent_path.write_text(body, encoding="utf-8")


def test_bring_up_runs_existing_app_and_passes_tests(tmp_path):
    proj = Project.init(tmp_path / "demo")
    _write_intent(proj, """# demo

Echoes input or returns ERR for empty.

## Tests
- "hello" → succeed
- "" → succeed

## Deployment
- port 18080
""")
    proj.write_app_source(SIMPLE_AIL)

    rc = bring_up(proj, serve=False)
    assert rc == 0

    # Ledger should record the test runs
    records = [
        json.loads(line)
        for line in proj.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    test_runs = [r for r in records if r.get("event") == "test_run"]
    assert len(test_runs) == 2
    assert all(r["passed"] for r in test_runs)


def test_bring_up_aborts_on_test_failure(tmp_path):
    proj = Project.init(tmp_path / "demo")
    # Test expects an error but the program always succeeds.
    _write_intent(proj, """# demo

## Tests
- "anything" → 에러

## Deployment
- port 18081
""")
    proj.write_app_source("""\
entry main(input: Text) {
    return "always ok"
}
""")
    rc = bring_up(proj, serve=False)
    assert rc == 2  # tests failed sentinel — expect_ok=False but ran_ok=True


def test_bring_up_skips_authoring_when_app_exists(tmp_path, monkeypatch):
    """If app.ail is non-empty, bring_up must not call ask()."""
    proj = Project.init(tmp_path / "demo")
    proj.write_app_source(SIMPLE_AIL)
    _write_intent(proj, """# demo

## Tests
- "x" → succeed
""")

    called = {"ask": 0}
    import ail.agentic.agent as agent_mod
    original = agent_mod.ask

    def fake_ask(*a, **kw):
        called["ask"] += 1
        return original(*a, **kw)

    monkeypatch.setattr(agent_mod, "ask", fake_ask)
    rc = bring_up(proj, serve=False)
    assert rc == 0
    assert called["ask"] == 0
