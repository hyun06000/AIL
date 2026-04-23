"""Structural guards on the authoring prompt.

These don't test the LLM — they test that specific instructional
sections we depend on are still in the prompt. Past prompt edits
accidentally drowned out narrow rules (like "one program, one file")
by re-referencing the canonical `app.ail` filename a dozen times
elsewhere. These assertions make that regression louder.
"""
from __future__ import annotations

import re

from ail.agentic.authoring_chat import AuthoringChat


class _StubProject:
    """Minimal project-like object for prompt construction. AuthoringChat
    calls `.root.name` and `.state_dir` during `_build_goal_prompt`, so
    only those need to resolve to anything sensible."""

    class _Root:
        name = "test-proj"

    root = _Root()

    @property
    def state_dir(self):
        import pathlib
        return pathlib.Path("/tmp/_ail_stub_state")


def _get_prompt() -> str:
    chat = AuthoringChat(_StubProject(), adapter=None)
    # Empty state / empty history / empty user message — we're checking
    # the static scaffolding, not any runtime content.
    return chat._build_goal_prompt(state={}, history=[], user_message="")


def test_one_program_one_file_section_present():
    p = _get_prompt()
    assert "ONE PROGRAM, ONE FILE" in p, (
        "The 'one program, one file' section is the hard rule that "
        "stops agents from overwriting earlier programs to iterate. "
        "Do not remove or soften it without a replacement.")


def test_one_program_one_file_calls_out_bluesky_regression():
    # The canonical failure example: turn 9 overwriting github_promo.ail
    # with Bluesky code. It's verbatim in the prompt so the agent sees
    # itself in the anti-pattern.
    p = _get_prompt()
    assert "overwrites `github_promo.ail` with Bluesky code" in p


def test_response_format_does_not_hardcode_app_ail():
    """The XML-format example must use a placeholder, not `app.ail`.
    Hardcoding `app.ail` in the protocol example nudges the agent to
    reuse that filename for every new program — which is how the
    overwrite regression came back."""
    p = _get_prompt()
    # Find the YOUR RESPONSE FORMAT section
    m = re.search(
        r"=== YOUR RESPONSE FORMAT ===(.+?)===", p, re.DOTALL)
    assert m is not None, "YOUR RESPONSE FORMAT section missing"
    section = m.group(1)
    assert 'path="app.ail"' not in section, (
        "The YOUR RESPONSE FORMAT section must not hardcode "
        "`<file path=\"app.ail\">` — use a descriptive placeholder.")
    assert "DESCRIPTIVE_NAME.ail" in section, (
        "Expected the placeholder `DESCRIPTIVE_NAME.ail` in the "
        "response-format section.")


def test_http_post_json_rule_present():
    """v1.15.0 gap-closer: agents must use structured JSON effect."""
    p = _get_prompt()
    assert "http.post_json" in p
    assert "Never hand-roll JSON" in p


def test_input_hint_rule_present():
    """v1.15.2 UX: agents must declare a # INPUT: hint when entry uses input."""
    p = _get_prompt()
    assert "# INPUT:" in p
    assert "placeholder" in p.lower()
