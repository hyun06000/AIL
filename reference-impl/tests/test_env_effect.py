"""Tests for `perform env.read(name)` — read an OS environment variable
as Result[Text]. Primary use case: supplying credentials (API tokens,
webhook URLs) without hardcoding them, since the authoring prompt
forbids placeholder keys in source."""
from __future__ import annotations

import os
import tempfile

from ail import run


def _run_src(src: str, *, tmp_path, input: str = ""):
    fp = tmp_path / "app.ail"
    fp.write_text(src, encoding="utf-8")
    return run(str(fp), input=input)


def test_env_read_returns_ok_when_var_is_set(tmp_path, monkeypatch):
    monkeypatch.setenv("AIL_TEST_VAR", "hello-world")
    src = """
entry main(input: Text) {
    r = perform env.read("AIL_TEST_VAR")
    if is_ok(r) { return unwrap(r) }
    return "missing"
}
"""
    result, _ = _run_src(src, tmp_path=tmp_path)
    assert result.value == "hello-world"


def test_env_read_returns_ok_on_empty_string(tmp_path, monkeypatch):
    # Empty string is a valid env value and must NOT collapse to an
    # error (reserving error() for "variable not set at all").
    monkeypatch.setenv("AIL_TEST_EMPTY", "")
    src = """
entry main(input: Text) {
    r = perform env.read("AIL_TEST_EMPTY")
    if is_ok(r) { return "set" }
    return "missing"
}
"""
    result, _ = _run_src(src, tmp_path=tmp_path)
    assert result.value == "set"


def test_env_read_errors_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("AIL_DEFINITELY_UNSET", raising=False)
    src = """
entry main(input: Text) {
    r = perform env.read("AIL_DEFINITELY_UNSET")
    return unwrap_error(r)
}
"""
    result, _ = _run_src(src, tmp_path=tmp_path)
    assert "not set" in result.value


def test_env_read_rejects_empty_name(tmp_path):
    src = """
entry main(input: Text) {
    r = perform env.read("")
    return unwrap_error(r)
}
"""
    result, _ = _run_src(src, tmp_path=tmp_path)
    assert "non-empty string" in result.value
