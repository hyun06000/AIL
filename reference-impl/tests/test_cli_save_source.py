"""Tests for the `--save-source` CLI helper.

`--save-source PATH` is the file-persisting companion to `--show-source`.
This file tests the internal `_write_source` helper and the argparse
wiring; the end-to-end `ail ask --save-source FILE` flow needs a real
model adapter to exercise and lives under the benchmark/integration
harness rather than here.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from ail.cli import _write_source, main as cli_main


def test_write_source_creates_file(tmp_path):
    dest = tmp_path / "saved.ail"
    source = "pure fn f(x: Number) -> Number { return x + 1 }"
    _write_source(str(dest), source)
    assert dest.read_text(encoding="utf-8") == source + "\n"


def test_write_source_idempotent_trailing_newline(tmp_path):
    # Input that already ends in \n — writer must not add a second one.
    dest = tmp_path / "saved.ail"
    source = "pure fn f(x: Number) -> Number { return x + 1 }\n"
    _write_source(str(dest), source)
    assert dest.read_text(encoding="utf-8") == source  # exactly one trailing \n


def test_write_source_creates_parent_dirs(tmp_path):
    dest = tmp_path / "sub" / "deeper" / "saved.ail"
    _write_source(str(dest), "entry main(x: Text) { return 0 }")
    assert dest.exists()
    assert dest.parent.is_dir()


def test_write_source_stdout_dash(capsys):
    source = "entry main(x: Text) { return 1 }"
    _write_source("-", source)
    captured = capsys.readouterr()
    assert source in captured.out


def test_write_source_prints_confirmation_to_stderr(tmp_path, capsys):
    dest = tmp_path / "saved.ail"
    _write_source(str(dest), "entry main(x: Text) { return 0 }")
    captured = capsys.readouterr()
    assert "AIL saved" in captured.err
    assert str(dest) in captured.err


def test_cli_accepts_save_source_flag():
    """argparse wiring smoke test — not an end-to-end run (that needs an
    adapter), just that the flag parses without error."""
    # `ail version` short-circuits before doing any work; we can't call
    # ask without an adapter, but we can verify the help string includes
    # --save-source by running with --help in a subprocess. Simpler: just
    # import and check the parser spec indirectly via a help capture.
    import argparse
    import contextlib
    import io as _io
    buf = _io.StringIO()
    with contextlib.suppress(SystemExit):
        with contextlib.redirect_stdout(buf):
            cli_main(["ask", "--help"])
    assert "--save-source" in buf.getvalue()
