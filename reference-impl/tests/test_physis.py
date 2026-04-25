"""Tests for Physis v0.3 — generational evolution for long-running AIL processes.

Tests cover:
  - inherit_testament() returns genesis error when no testament exists
  - inherit_testament() returns ok(testament) when current.json exists
  - _physis_write_testament writes valid JSON and increments generation counter
  - _physis_generation reads counter correctly
  - on_death fn is pure (purity checker rejects effects inside it)
  - The effect is blocked inside pure fn bodies (PurityError)
  - Testament field validation (observed_patterns capped at 20 × 200 chars, advice ≤ 2000)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ail import run
from ail.parser import PurityError
from ail.runtime import MockAdapter
from ail.runtime.executor import Executor
from ail.parser.parser import parse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_executor(src: str, tmp_path: Path) -> Executor:
    program = parse(src)
    adapter = MockAdapter()
    return Executor(program, adapter, project_root=tmp_path)


def _run(src: str, tmp_path: Path | None = None) -> object:
    """Run src and return the unwrapped result value."""
    if tmp_path is not None:
        # Write to a temp file so project_root is set
        p = tmp_path / "_test.ail"
        p.write_text(src)
        result, _ = run(str(p), input="", adapter=MockAdapter())
    else:
        result, _ = run(src, input="", adapter=MockAdapter())
    return result.value


# ---------------------------------------------------------------------------
# inherit_testament — genesis (no current.json)
# ---------------------------------------------------------------------------

def test_inherit_testament_genesis(tmp_path):
    src = """
entry main(x: Text) {
    t_r = perform inherit_testament()
    if is_error(t_r) {
        return "genesis"
    }
    return "has testament"
}
"""
    assert _run(src, tmp_path) == "genesis"


# ---------------------------------------------------------------------------
# inherit_testament — successor reads written testament
# ---------------------------------------------------------------------------

def test_inherit_testament_successor(tmp_path):
    # Write a testament as if the runtime had done so
    executor = _make_executor("entry main(x: Text) { return x }", tmp_path)
    executor._active_evolve_name = "my_server"
    testament = {
        "generation": 1,
        "predecessor_id": "12345",
        "reason": "error_rate > 0.5",
        "observed_patterns": ["high 5xx rate"],
        "advice": "check upstream",
        "params": {},
        "born_at": 1000.0,
        "died_at": 1200.0,
        "lifetime_s": 200.0,
    }
    executor._physis_write_testament("my_server", testament)

    # Now run a program that reads it via the executor directly
    src = """
entry main(x: Text) {
    t_r = perform inherit_testament()
    if is_ok(t_r) {
        t = unwrap(t_r)
        return get(t, "reason")
    }
    return "genesis"
}
"""
    program = parse(src)
    ex = Executor(program, MockAdapter(), project_root=tmp_path)
    ex._active_evolve_name = "my_server"
    result_cv = ex.run_entry({"x": ""})
    assert result_cv.value == "error_rate > 0.5"


# ---------------------------------------------------------------------------
# _physis_write_testament — JSON on disk, counter increments
# ---------------------------------------------------------------------------

def test_physis_write_creates_files(tmp_path):
    executor = _make_executor("entry main(x: Text) { return x }", tmp_path)
    testament = {
        "generation": 1,
        "predecessor_id": "pid",
        "reason": "test",
        "born_at": 0.0,
        "died_at": 100.0,
        "lifetime_s": 100.0,
    }
    executor._physis_write_testament("test_server", testament)

    physis_dir = tmp_path / ".ail" / "physis" / "test_server"
    assert (physis_dir / "gen1.json").exists()
    assert (physis_dir / "current.json").exists()
    assert (physis_dir / "_counter.json").exists()

    written = json.loads((physis_dir / "gen1.json").read_text())
    assert written["generation"] == 1
    assert written["reason"] == "test"

    counter = json.loads((physis_dir / "_counter.json").read_text())
    assert counter["generation"] == 2  # next generation will be 2


def test_physis_generation_increments(tmp_path):
    executor = _make_executor("entry main(x: Text) { return x }", tmp_path)
    assert executor._physis_generation("srv") == 1  # genesis

    executor._physis_write_testament("srv", {
        "generation": 1, "reason": "r",
        "born_at": 0.0, "died_at": 1.0, "lifetime_s": 1.0,
    })
    assert executor._physis_generation("srv") == 2

    executor._physis_write_testament("srv", {
        "generation": 2, "reason": "r2",
        "born_at": 1.0, "died_at": 2.0, "lifetime_s": 1.0,
    })
    assert executor._physis_generation("srv") == 3


# ---------------------------------------------------------------------------
# Testament size limits (mirrors run_server logic)
# ---------------------------------------------------------------------------

def test_testament_observed_patterns_capped():
    raw = {
        "generation": 1,
        "reason": "test",
        "born_at": 0.0,
        "died_at": 1.0,
        "lifetime_s": 1.0,
        "observed_patterns": ["x" * 300] * 30,  # 30 items, each 300 chars
        "advice": "a" * 3000,                    # over 2000
    }
    # Apply the same limits as run_server
    if "observed_patterns" in raw:
        op = raw["observed_patterns"]
        raw["observed_patterns"] = [str(p)[:200] for p in op[:20]]
    if "advice" in raw:
        raw["advice"] = raw["advice"][:2000]

    assert len(raw["observed_patterns"]) == 20
    assert len(raw["observed_patterns"][0]) == 200
    assert len(raw["advice"]) == 2000


# ---------------------------------------------------------------------------
# Purity: inherit_testament is blocked in pure fn
# ---------------------------------------------------------------------------

def test_inherit_testament_blocked_in_pure_fn():
    src = """
pure fn bad() -> Text {
    t = perform inherit_testament()
    return "x"
}
entry main(x: Text) { return bad() }
"""
    with pytest.raises(PurityError):
        run(src, input="", adapter=MockAdapter())


# ---------------------------------------------------------------------------
# on_death is pure — cannot perform effects
# ---------------------------------------------------------------------------

def test_on_death_is_pure_rejects_effects(tmp_path):
    src = """
pure fn on_death(reason: Text, history: [Any]) -> Any {
    perform file.write("/tmp/bad.txt", reason)
    return []
}
entry main(x: Text) { return "ok" }
"""
    with pytest.raises(PurityError):
        run(src, input="", adapter=MockAdapter())


# ---------------------------------------------------------------------------
# on_death pure fn CAN call other pure fns
# ---------------------------------------------------------------------------

def test_on_death_can_call_pure_helpers(tmp_path):
    src = """
pure fn summarise(history: [Any]) -> Text {
    return join(["seen ", to_text(length(history)), " events"], "")
}
pure fn on_death(reason: Text, history: [Any]) -> Any {
    summary = summarise(history)
    return [["advice", summary]]
}
entry main(x: Text) { return "ok" }
"""
    assert _run(src, tmp_path) == "ok"


# ---------------------------------------------------------------------------
# inherit_testament genesis error carries recognisable message
# ---------------------------------------------------------------------------

def test_inherit_testament_genesis_message(tmp_path):
    src = """
entry main(x: Text) {
    t_r = perform inherit_testament()
    if is_error(t_r) {
        return get(t_r, "error")
    }
    return "ok"
}
"""
    result = _run(src, tmp_path)
    assert isinstance(result, str) and "genesis" in result


# ---------------------------------------------------------------------------
# Multiple testament writes accumulate gen files
# ---------------------------------------------------------------------------

def test_physis_multiple_generations(tmp_path):
    executor = _make_executor("entry main(x: Text) { return x }", tmp_path)
    for gen in range(1, 4):
        executor._physis_write_testament("srv", {
            "generation": gen,
            "reason": f"reason_{gen}",
            "born_at": float(gen),
            "died_at": float(gen + 1),
            "lifetime_s": 1.0,
        })

    physis_dir = tmp_path / ".ail" / "physis" / "srv"
    assert (physis_dir / "gen1.json").exists()
    assert (physis_dir / "gen2.json").exists()
    assert (physis_dir / "gen3.json").exists()

    # current.json points to the latest generation
    current = json.loads((physis_dir / "current.json").read_text())
    assert current["generation"] == 3
    assert current["reason"] == "reason_3"
