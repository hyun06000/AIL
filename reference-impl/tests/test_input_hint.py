"""Tests for `# INPUT:` hint extraction + replay-order safety.

Two field-test bugs motivate these:

1. The input textarea's placeholder was a generic "input (optional)"
   that left non-programmers guessing what to type. Agents can now
   emit `# INPUT: <hint>` at the top of a .ail; extract_input_hint
   picks it up and the UI surfaces it as the placeholder.

2. The authoring page's JS declared `let programsForNext = []` and
   friends AFTER the history-replay loop, so on page reload the
   replay called addRunWidget which hit TDZ and threw — halting the
   forEach after the first turn so the chat appeared to lose every
   message below the first response. The assertion below locks in
   the lexical order that prevents the bug from regressing.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ail.agentic.authoring_chat import extract_input_hint
from ail.agentic.authoring_ui import render_authoring_page


def test_hint_from_hash_comment():
    src = "# INPUT: 번역할 문장을 붙여넣으세요 (예: '안녕하세요')\n" \
          "entry main(input: Text) { return input }"
    assert extract_input_hint(src) == (
        "번역할 문장을 붙여넣으세요 (예: '안녕하세요')")


def test_hint_from_slash_comment():
    src = "// INPUT: Paste the review to classify.\n" \
          "entry main(input: Text) { return input }"
    assert extract_input_hint(src) == "Paste the review to classify."


def test_hint_missing_returns_none():
    src = "entry main(input: Text) { return input }"
    assert extract_input_hint(src) is None


def test_hint_empty_returns_none():
    # A bare `# INPUT:` with nothing after should not produce an empty
    # placeholder — fall back to the localized default.
    src = "# INPUT: \nentry main(input: Text) { return input }"
    assert extract_input_hint(src) is None


def test_hint_case_insensitive():
    src = "# input: lowercase marker works too\n" \
          "entry main(input: Text) { return input }"
    assert extract_input_hint(src) == "lowercase marker works too"


def test_hint_truncated_when_too_long():
    body = "x" * 500
    src = f"# INPUT: {body}\nentry main(input: Text) {{ return input }}"
    hint = extract_input_hint(src)
    assert hint is not None
    assert len(hint) == 200
    assert hint.endswith("...")


def test_hint_ignored_below_first_20_lines():
    # A stray `# INPUT:` buried deep in a goal string shouldn't hijack
    # the placeholder. Only the first 20 lines are scanned.
    lines = ["# some comment"] * 25 + ["# INPUT: too deep"]
    src = "\n".join(lines) + "\nentry main(input: Text) { return input }"
    assert extract_input_hint(src) is None


def test_authoring_page_declares_let_state_before_history_replay():
    """Regression guard: `let programsForNext` / `let inputUsedForNext`
    must appear in the JS before the `INITIAL_HISTORY.forEach` that
    calls addRunWidget. Otherwise the replay throws TDZ and cuts off
    every message past the first one on page reload."""
    html = render_authoring_page(
        project_name="p",
        host="127.0.0.1",
        port=8080,
        history=[
            {"user": "hi", "reply": "hello", "files": [],
             "action": "ready_to_run"}
        ],
    )
    programs_idx = html.find("let programsForNext")
    replay_idx = html.find("INITIAL_HISTORY.forEach")
    assert programs_idx != -1, "expected `let programsForNext` in page"
    assert replay_idx != -1, "expected `INITIAL_HISTORY.forEach` in page"
    assert programs_idx < replay_idx, (
        "multi-program `let` state must be declared before the history "
        "replay loop — see test_input_hint.py docstring. "
        f"programs_idx={programs_idx}, replay_idx={replay_idx}")
    # And the same for the other three state bindings.
    for name in (
        "let activeProgramForNext",
        "let inputUsedForNext",
        "let envRequiredForNext",
    ):
        idx = html.find(name)
        assert idx != -1, f"expected `{name}` in page"
        assert idx < replay_idx, (
            f"`{name}` must be declared before history replay")
