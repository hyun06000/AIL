"""Cross-runtime conformance test suite.

For every case under `cases/`:

  1. Run via the Python interpreter (`python -m ail.cli run … --raw`).
  2. Run via the Go interpreter (`../../go-impl/ail-go run … --input`)
     if the binary is available.
  3. Compare each runtime's stdout to the case's `.expected` file and
     — most importantly — to each other.

Any byte-level divergence between the two runtimes is a failing test.
This is the concrete rule Opus 4 laid out in CLAUDE.md: "AIL is
defined by what both runtimes agree on. A feature that works only
in one runtime is not an AIL feature — it is an implementation
feature."

Case file shape (under `cases/`):

    NNN_name.ail            — the AIL program
    NNN_name.input          — optional; passed as `--input`. If missing,
                              the empty string is used.
    NNN_name.expected       — the exact stdout both runtimes must emit
                              (trailing newline is stripped before compare).
    NNN_name.skip-go        — optional marker file. If present, the Go
                              runtime is skipped for this case (because
                              the feature isn't yet in go-impl). The file
                              contents are used as the pytest skip reason
                              — put a brief note about which feature the
                              Go runtime is missing.

Adding a case: drop three files (`.ail`, `.input`, `.expected`) into
`cases/` following the `NNN_name` naming pattern. No code changes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest


HERE = Path(__file__).parent
CASES_DIR = HERE / "cases"
REPO_ROOT = HERE.parent.parent.parent
REFERENCE_IMPL = REPO_ROOT / "reference-impl"
GO_BINARY = REPO_ROOT / "go-impl" / "ail-go"


def _discover_cases() -> list[str]:
    """Return sorted case stems (e.g. '001_fizzbuzz')."""
    return sorted(p.stem for p in CASES_DIR.glob("*.ail"))


def _read_case(stem: str) -> tuple[str, str, Optional[str]]:
    """Return (input_text, expected_output, skip_go_reason).

    `skip_go_reason` is None when the case is expected to run on Go;
    otherwise it is the human-readable reason pytest should report
    when skipping the Go run.
    """
    input_path = CASES_DIR / f"{stem}.input"
    input_text = input_path.read_text() if input_path.exists() else ""
    expected = (CASES_DIR / f"{stem}.expected").read_text().rstrip("\n")
    skip_go_path = CASES_DIR / f"{stem}.skip-go"
    skip_go_reason = None
    if skip_go_path.exists():
        skip_go_reason = (skip_go_path.read_text().strip()
                          or "go-impl does not support this case yet")
    return input_text, expected, skip_go_reason


CASES = _discover_cases()


def _run_python(case: str, input_text: str) -> subprocess.CompletedProcess:
    # Invoke via `python -m ail.cli` with cwd at reference-impl so the
    # package resolves from the editable install or the repo checkout,
    # not from a stale site-packages copy.
    return subprocess.run(
        [sys.executable, "-m", "ail.cli", "run",
         str(CASES_DIR / f"{case}.ail"),
         "--input", input_text, "--raw", "--mock"],
        capture_output=True, text=True, cwd=REFERENCE_IMPL,
    )


def _run_go(case: str, input_text: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(GO_BINARY), "run",
         str(CASES_DIR / f"{case}.ail"),
         "--input", input_text],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("case", CASES)
def test_python_runtime_matches_expected(case: str) -> None:
    """The Python runtime's `--raw` output exactly matches .expected."""
    input_text, expected, _ = _read_case(case)
    result = _run_python(case, input_text)
    assert result.returncode == 0, (
        f"python runtime failed on {case}:\n"
        f"stderr:\n{result.stderr}\n"
        f"stdout:\n{result.stdout}"
    )
    actual = result.stdout.rstrip("\n")
    assert actual == expected, (
        f"{case}: python output differs from expected.\n"
        f"  expected: {expected!r}\n"
        f"  actual:   {actual!r}"
    )


@pytest.mark.parametrize("case", CASES)
def test_go_runtime_matches_expected(case: str) -> None:
    """The Go runtime's stdout exactly matches .expected (when
    go-impl supports the case; `.skip-go` opts out per-case)."""
    input_text, expected, skip_go_reason = _read_case(case)
    if skip_go_reason is not None:
        pytest.skip(skip_go_reason)
    if not GO_BINARY.exists():
        pytest.skip(
            f"go-impl/ail-go binary not found at {GO_BINARY}. "
            "Build it with: cd go-impl && go build -o ail-go ."
        )
    result = _run_go(case, input_text)
    assert result.returncode == 0, (
        f"go runtime failed on {case}:\n"
        f"stderr:\n{result.stderr}\n"
        f"stdout:\n{result.stdout}"
    )
    actual = result.stdout.rstrip("\n")
    assert actual == expected, (
        f"{case}: go output differs from expected.\n"
        f"  expected: {expected!r}\n"
        f"  actual:   {actual!r}"
    )


@pytest.mark.parametrize("case", CASES)
def test_runtimes_produce_identical_output(case: str) -> None:
    """The two runtimes produce byte-identical stdout on this case.

    This is the load-bearing test of the suite — the one that makes
    AIL a language rather than two similar languages that happen to
    share a file extension. A failure here means the spec is
    ambiguous (both runtimes are internally consistent but disagree
    on what the program means) or one runtime has a bug.
    """
    input_text, _, skip_go_reason = _read_case(case)
    if skip_go_reason is not None:
        pytest.skip(skip_go_reason)
    if not GO_BINARY.exists():
        pytest.skip(
            f"go-impl/ail-go binary not found at {GO_BINARY}. "
            "Build it with: cd go-impl && go build -o ail-go ."
        )
    py_result = _run_python(case, input_text)
    go_result = _run_go(case, input_text)
    assert py_result.returncode == 0, (
        f"python runtime errored on {case}:\n{py_result.stderr}")
    assert go_result.returncode == 0, (
        f"go runtime errored on {case}:\n{go_result.stderr}")
    py_out = py_result.stdout.rstrip("\n")
    go_out = go_result.stdout.rstrip("\n")
    assert py_out == go_out, (
        f"{case}: runtimes diverge.\n"
        f"  python: {py_out!r}\n"
        f"  go:     {go_out!r}"
    )
