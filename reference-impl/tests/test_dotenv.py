"""Tests for _load_dotenv_if_present in ail.__init__."""
from __future__ import annotations
import os
from pathlib import Path

import pytest


def test_loads_simple_key_value(tmp_path, monkeypatch):
    from ail import _load_dotenv_if_present

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AIL_TEST_VAR", raising=False)
    (tmp_path / ".env").write_text("AIL_TEST_VAR=hello\n")

    _load_dotenv_if_present()
    assert os.environ.get("AIL_TEST_VAR") == "hello"


def test_strips_quotes(tmp_path, monkeypatch):
    from ail import _load_dotenv_if_present

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AIL_TEST_QUOTED", raising=False)
    (tmp_path / ".env").write_text('AIL_TEST_QUOTED="hi there"\n')

    _load_dotenv_if_present()
    assert os.environ.get("AIL_TEST_QUOTED") == "hi there"


def test_ignores_comments_and_blanks(tmp_path, monkeypatch):
    from ail import _load_dotenv_if_present

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AIL_TEST_KEEP", raising=False)
    (tmp_path / ".env").write_text(
        "# this is a comment\n"
        "\n"
        "AIL_TEST_KEEP=value\n"
        "# AIL_TEST_SKIP=should_not_set\n"
    )

    _load_dotenv_if_present()
    assert os.environ.get("AIL_TEST_KEEP") == "value"
    assert "AIL_TEST_SKIP" not in os.environ


def test_does_not_overwrite_existing(tmp_path, monkeypatch):
    from ail import _load_dotenv_if_present

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AIL_TEST_EXISTING", "original")
    (tmp_path / ".env").write_text("AIL_TEST_EXISTING=from_file\n")

    _load_dotenv_if_present()
    # Existing env var wins
    assert os.environ.get("AIL_TEST_EXISTING") == "original"


def test_missing_file_is_silent(tmp_path, monkeypatch):
    """No .env anywhere in the searched dirs — should not raise."""
    from ail import _load_dotenv_if_present

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    # Searched dirs include parents up to 4 levels; tmp_path itself has
    # no .env and its parents are unlikely to. Just assert no exception.
    _load_dotenv_if_present()
