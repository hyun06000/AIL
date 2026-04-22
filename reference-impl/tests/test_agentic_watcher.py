"""Watcher tests — drive the polling loop directly via _tick() so we
don't rely on real-time threading in tests.
"""
import json
import os
import time

from ail.agentic.project import Project
from ail.agentic.watcher import Watcher


SIMPLE_AIL = """\
entry main(input: Text) {
    if length(input) == 0 { return error("empty") }
    return input
}
"""


def _write_intent(proj: Project, body: str) -> None:
    proj.intent_path.write_text(body, encoding="utf-8")


def _bump_mtime(path):
    """Force mtime forward by at least one second so the watcher
    notices the change on filesystems with second-resolution mtime."""
    st = path.stat()
    new_mt = st.st_mtime + 2
    os.utime(path, (new_mt, new_mt))


def test_watcher_no_change_does_nothing(tmp_path):
    proj = Project.init(tmp_path / "demo")
    _write_intent(proj, """# demo

## Tests
- "hello" → succeed
""")
    proj.write_app_source(SIMPLE_AIL)

    w = Watcher(proj)
    w._tick()  # should be a no-op
    records = [
        json.loads(line)
        for line in proj.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    # Only the init record from Project.init should be present.
    assert all(r.get("event") != "watcher_revalidated" for r in records)


def test_watcher_detects_intent_md_edit(tmp_path):
    proj = Project.init(tmp_path / "demo")
    _write_intent(proj, """# demo

## Tests
- "hello" → succeed
""")
    proj.write_app_source(SIMPLE_AIL)

    w = Watcher(proj)
    # User edits INTENT.md (e.g. adds a new test).
    _write_intent(proj, """# demo

## Tests
- "hello" → succeed
- "x" → succeed
""")
    _bump_mtime(proj.intent_path)
    w._tick()

    records = [
        json.loads(line)
        for line in proj.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    intent_events = [r for r in records if r.get("event") == "watcher_intent_changed"]
    revalidated = [r for r in records if r.get("event") == "watcher_revalidated"]
    assert len(intent_events) == 1
    assert intent_events[0]["tests"] == 2
    assert len(revalidated) == 1
    assert revalidated[0]["passed"] == revalidated[0]["total"] == 2


def test_watcher_detects_app_ail_edit(tmp_path):
    proj = Project.init(tmp_path / "demo")
    _write_intent(proj, """# demo

## Tests
- "hello" → succeed
""")
    proj.write_app_source(SIMPLE_AIL)

    w = Watcher(proj)
    # User edits app.ail directly.
    proj.write_app_source(SIMPLE_AIL + "\n// added comment\n")
    _bump_mtime(proj.app_path)
    w._tick()

    records = [
        json.loads(line)
        for line in proj.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    app_events = [r for r in records if r.get("event") == "watcher_app_changed"]
    assert len(app_events) == 1


def test_watcher_warns_on_failing_tests_after_edit(tmp_path):
    proj = Project.init(tmp_path / "demo")
    _write_intent(proj, """# demo

## Tests
- "hello" → succeed
""")
    proj.write_app_source(SIMPLE_AIL)

    w = Watcher(proj)
    # Edit app.ail to a syntactically broken version — parse error
    # propagates as a runtime exception during the test run.
    proj.write_app_source("entry main(input: Text) { return\n")
    _bump_mtime(proj.app_path)
    w._tick()

    records = [
        json.loads(line)
        for line in proj.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    revalidated = [r for r in records if r.get("event") == "watcher_revalidated"]
    assert len(revalidated) == 1
    # The single test now fails — watcher records partial pass without
    # taking the server down.
    assert revalidated[0]["passed"] < revalidated[0]["total"]


def test_watcher_intent_change_with_simultaneous_app_change(tmp_path):
    proj = Project.init(tmp_path / "demo")
    _write_intent(proj, """# demo

## Tests
- "hello" → succeed
""")
    proj.write_app_source(SIMPLE_AIL)

    w = Watcher(proj)
    # Both files change in the same tick window.
    _write_intent(proj, """# demo

## Tests
- "hi" → succeed
""")
    proj.write_app_source(SIMPLE_AIL + "\n// changed\n")
    _bump_mtime(proj.intent_path)
    _bump_mtime(proj.app_path)
    w._tick()

    records = [
        json.loads(line)
        for line in proj.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    intent_events = [r for r in records if r.get("event") == "watcher_intent_changed"]
    assert len(intent_events) == 1
    assert intent_events[0]["also_app"] is True
    # The app.ail-only handler should NOT fire — combined handler covers it.
    app_events = [r for r in records if r.get("event") == "watcher_app_changed"]
    assert len(app_events) == 0
