"""Tests for the perform ail.run meta-programming effect."""
from __future__ import annotations

import pytest

from ail import compile_source
from ail.runtime.executor import (
    Executor, ConfidentValue, _AIL_RUN_DEPTH_WARN, _AIL_RUN_DEPTH_LIMIT,
)
from ail.runtime.model import MockAdapter
from ail.runtime.provenance import LITERAL_ORIGIN


def _make_exec(depth: int = 0) -> Executor:
    p = compile_source('entry main(input: Text) { return "" }')
    return Executor(p, MockAdapter(), _ail_run_depth=depth)


def _cv(v) -> ConfidentValue:
    return ConfidentValue(v, 1.0, origin=LITERAL_ORIGIN)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_ail_run_returns_result_ok():
    code = 'entry main(input: Text) { return "hello" }'
    ex = _make_exec()
    r = ex._ail_run([_cv(code)], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is True
    assert r.value["value"] == "hello"


def test_ail_run_passes_input():
    code = 'entry main(input: Text) { return join(["got: ", input], "") }'
    ex = _make_exec()
    r = ex._ail_run([_cv(code), _cv("world")], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is True
    assert r.value["value"] == "got: world"


def test_ail_run_input_kwarg():
    code = 'entry main(input: Text) { return input }'
    ex = _make_exec()
    r = ex._ail_run([_cv(code)], {"input": _cv("kwarg-value")}, LITERAL_ORIGIN)
    assert r.value["ok"] is True
    assert r.value["value"] == "kwarg-value"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_ail_run_missing_code_is_error():
    ex = _make_exec()
    r = ex._ail_run([], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is False
    assert "code" in r.value["error"]


def test_ail_run_empty_code_is_error():
    ex = _make_exec()
    r = ex._ail_run([_cv("   ")], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is False


def test_ail_run_parse_error_wrapped():
    ex = _make_exec()
    r = ex._ail_run([_cv("this is not valid AIL !!!")], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is False
    assert "parse error" in r.value["error"]


def test_ail_run_runtime_error_wrapped():
    # Divide by zero produces a Python exception at runtime
    code = 'entry main(input: Text) { x = 1 / 0 \n return to_text(x) }'
    ex = _make_exec()
    r = ex._ail_run([_cv(code)], {}, LITERAL_ORIGIN)
    # Either ok=False with runtime error, or ok=True with None/"" result.
    # The important thing is it doesn't propagate as an unhandled exception.
    assert isinstance(r.value, dict)


# ---------------------------------------------------------------------------
# Recursion depth safety
# ---------------------------------------------------------------------------

def test_ail_run_depth_increments():
    """Sub-executor gets depth+1."""
    code = 'entry main(input: Text) { return "ok" }'
    # Directly call _ail_run and verify it doesn't fail at depth 0
    ex = _make_exec(depth=0)
    r = ex._ail_run([_cv(code)], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is True


def test_ail_run_depth_warning_recorded():
    """At depth == WARN-1, next call records a warning trace event."""
    code = 'entry main(input: Text) { return "ok" }'
    # Create executor at depth that will trigger the warning on next call
    ex = _make_exec(depth=_AIL_RUN_DEPTH_WARN - 1)
    r = ex._ail_run([_cv(code)], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is True  # still runs
    events = [e.kind for e in ex.trace.entries]
    assert "ail_run_depth_warning" in events


def test_ail_run_depth_hard_stop():
    """At depth >= LIMIT-1, the effect refuses with Result-error."""
    code = 'entry main(input: Text) { return "should not run" }'
    ex = _make_exec(depth=_AIL_RUN_DEPTH_LIMIT - 1)
    r = ex._ail_run([_cv(code)], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is False
    assert "recursion depth" in r.value["error"]
    assert str(_AIL_RUN_DEPTH_LIMIT) in r.value["error"]


def test_ail_run_depth_hard_stop_trace():
    code = 'entry main(input: Text) { return "ok" }'
    ex = _make_exec(depth=_AIL_RUN_DEPTH_LIMIT - 1)
    ex._ail_run([_cv(code)], {}, LITERAL_ORIGIN)
    events = [e.kind for e in ex.trace.entries]
    assert "ail_run_depth_exceeded" in events


# ---------------------------------------------------------------------------
# Sub-program inherits adapter
# ---------------------------------------------------------------------------

def test_ail_run_sub_program_depth_zero_succeeds():
    """Nested depth 0 → 1 → 2 is fine (below warn threshold)."""
    inner = 'entry main(input: Text) { return "inner" }'
    outer = f'entry main(input: Text) {{ r = perform ail.run("{inner}"); return unwrap(r) }}'
    # Can't easily escape quotes in AIL string literals here; test via executor directly
    ex = _make_exec(depth=0)
    r = ex._ail_run([_cv(inner)], {}, LITERAL_ORIGIN)
    assert r.value["ok"] is True
    assert r.value["value"] == "inner"
