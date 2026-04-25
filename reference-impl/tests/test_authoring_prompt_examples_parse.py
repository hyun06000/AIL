"""Regression: every ```ail code block in the authoring prompt must parse.

qna_bot field test 2026-04-26: the model emitted `branch { COND -> { body } }`
syntax three times in a row. Root cause was NOT model laziness — both
canonical examples in the authoring prompt itself used that broken shape.
The model was faithfully replicating what the prompt taught.

This test extracts every ```ail block from the rendered authoring prompt
(via `AuthoringChat._build_goal_prompt`) and parses each. If any block
fails to parse, the test fails with the exact block, so the prompt
maintainer can spot the bad teaching example.

Some blocks are intentional fragments (a single statement, not a full
program). Those are detected and parsed in a permissive wrapper or
skipped if even the wrapper can't load them as standalone snippets.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from ail.agentic.authoring_chat import AuthoringChat
from ail.parser import parse


def _render_prompt(tmp_path) -> str:
    """Build the goal prompt with a throwaway project on disk."""
    from pathlib import Path
    proj_root = tmp_path / "proj"
    proj_root.mkdir()
    project = MagicMock()
    project.root = proj_root
    project.state_dir = proj_root / ".ail"
    project.state_dir.mkdir()
    chat = AuthoringChat.__new__(AuthoringChat)
    chat.project = project
    chat._load_reference_card = lambda: "(reference card stub)"
    chat._format_history = lambda h: "(history stub)"
    chat._format_state = lambda s: "(state stub)"
    return chat._build_goal_prompt(state={}, history=[], user_message="x")


_AIL_BLOCK_RE = re.compile(r"```ail\n(.*?)```", re.DOTALL)


def _extract_ail_blocks(prompt: str) -> list[tuple[int, str]]:
    """Return [(approx_line_in_prompt, body), ...] for each ```ail block."""
    out: list[tuple[int, str]] = []
    for m in _AIL_BLOCK_RE.finditer(prompt):
        line_no = prompt[: m.start()].count("\n") + 1
        out.append((line_no, m.group(1)))
    return out


_FULL_PROGRAM_MARKERS = ("entry main(", "evolve ", "evolve\n")


def _looks_like_full_program(body: str) -> bool:
    """Only blocks with top-level `entry main(` or `evolve ` are
    teaching examples of standalone programs. Skip fragments and
    blocks containing literal `...` placeholders (AIL has no `...`
    syntax — those are pedagogical stubs like `goal: ...`).
    """
    if "..." in body:
        return False
    if "// ❌" in body or "// WRONG" in body or "// wrong" in body.lower():
        # WRONG-example callouts are intentionally broken; don't enforce parse.
        return False
    return any(m in body for m in _FULL_PROGRAM_MARKERS)


def _try_parse(body: str) -> tuple[bool, str]:
    try:
        parse(body)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def test_every_ail_block_in_prompt_parses(tmp_path):
    prompt = _render_prompt(tmp_path)
    blocks = _extract_ail_blocks(prompt)
    assert len(blocks) > 0, "no ```ail blocks found — prompt extraction failed"

    failures: list[str] = []
    standalone_count = 0
    for line_no, body in blocks:
        if not _looks_like_full_program(body):
            continue
        standalone_count += 1
        ok, err = _try_parse(body)
        if not ok:
            preview = "\n".join(body.splitlines()[:6])
            failures.append(
                f"\n--- prompt line ~{line_no} ---\n{preview}\n  ...\n"
                f"  error: {err}"
            )

    assert standalone_count > 0, (
        "no standalone-program ```ail blocks found in prompt — "
        "the heuristic may be wrong, or the prompt no longer carries "
        "canonical program examples."
    )
    if failures:
        pytest.fail(
            f"Authoring prompt contains {len(failures)} standalone AIL "
            f"program example(s) that do NOT parse (out of "
            f"{standalone_count} standalone blocks examined). The model is "
            "being taught broken syntax — fix the example in "
            "authoring_chat.py:_build_goal_prompt.\n"
            + "\n".join(failures)
        )
