"""Project class tests — init, ledger writes, app.ail round-trip."""
import json
from pathlib import Path

import pytest

from ail.agentic.project import Project


def test_init_creates_layout(tmp_path):
    proj = Project.init(tmp_path / "demo")
    assert proj.intent_path.exists()
    assert proj.state_dir.exists()
    assert proj.ledger_path.exists()
    body = proj.intent_path.read_text(encoding="utf-8")
    assert "# demo" in body
    # Initial ledger entry
    lines = proj.ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"] == "init"


def test_init_explicit_name_used_in_template(tmp_path):
    proj = Project.init(tmp_path / "folder", name="My App")
    body = proj.intent_path.read_text(encoding="utf-8")
    assert "# My App" in body


def test_init_refuses_to_clobber(tmp_path):
    Project.init(tmp_path / "demo")
    with pytest.raises(FileExistsError):
        Project.init(tmp_path / "demo")


def test_at_requires_intent_md(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        Project.at(tmp_path / "empty")


def test_at_opens_existing(tmp_path):
    Project.init(tmp_path / "demo")
    proj = Project.at(tmp_path / "demo")
    spec = proj.read_intent()
    assert spec.name == "demo"


def test_app_source_round_trip(tmp_path):
    proj = Project.init(tmp_path / "demo")
    assert proj.read_app_source() == ""
    proj.write_app_source("entry main(x: Text) { return x }")
    txt = proj.read_app_source()
    assert "entry main" in txt
    assert txt.endswith("\n")  # normalized


def test_ledger_appends(tmp_path):
    proj = Project.init(tmp_path / "demo")
    proj.append_ledger({"event": "test", "n": 1})
    proj.append_ledger({"event": "test", "n": 2})
    lines = proj.ledger_path.read_text(encoding="utf-8").splitlines()
    # init + 2 manual = 3 records
    assert len(lines) == 3
    last = json.loads(lines[-1])
    assert last["event"] == "test" and last["n"] == 2
    assert "ts" in last


def test_write_tests_extracts_from_intent(tmp_path):
    proj = Project.init(tmp_path / "demo")
    spec = proj.read_intent()
    proj.write_tests(spec)
    payload = json.loads(proj.tests_path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    # The template includes one negative test: empty input expects error
    assert any(t["input"] == "" and t["expect_ok"] is False for t in payload)
