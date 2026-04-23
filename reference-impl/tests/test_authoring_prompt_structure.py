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


def test_prompt_warns_against_assuming_ail_promo_subject():
    """v1.18.0 contamination fix. Field test 2026-04-24: user opened
    a fresh project with `ai들만을 위한 커뮤니티가 있다는 소문 들어봤어?`
    and the agent immediately asked 'Is this for AIL/HEAAL promotion?'
    — a contamination from the prompt's own AIL/HEAAL-heavy examples.
    The prompt must explicitly warn the model NOT to make that leap,
    and must contain at least one neutral (non-AIL) subject example."""
    p = _get_prompt()
    # Dedicated warning section must exist.
    assert "THE PROJECT'S SUBJECT IS WHATEVER THE USER SAYS IT IS" in p
    # Must name the failure explicitly so the model sees itself.
    assert "ai들만을 위한 커뮤니티" in p or "AI promotion" in p or \
        "prompt contamination" in p
    # Must supply non-AIL example subjects so the default isn't
    # "assume AIL" when filling ambiguity.
    non_ail_subjects = ["recipe", "weather", "garden", "calendar",
                        "stock", "newsletter", "poetry", "날씨"]
    matches = [s for s in non_ail_subjects if s.lower() in p.lower()]
    assert len(matches) >= 3, (
        "expected the prompt to mention at least 3 non-AIL subject "
        "examples to neutralize the implicit AIL bias; found: "
        f"{matches}")
    # The AIL description must be framed as tooling, not as the
    # project topic.
    assert "THE LANGUAGE YOU AUTHOR IN" in p
    assert "your TOOL, not the topic" in p


def test_write_helpers_freely_guidance_present():
    """v1.18.0: if a helper the agent wants isn't a built-in, the
    prompt must tell it to just write one. AIL programs are allowed
    to be long; clarity over cleverness."""
    p = _get_prompt()
    assert "IF A HELPER YOU WANT ISN'T A BUILT-IN, WRITE IT" in p or \
        "if a helper you want isn't a built-in" in p.lower()
    assert "allowed to be long" in p.lower() or \
        "programs are allowed to be long" in p.lower()


def test_http_post_json_rule_present():
    """v1.15.0 gap-closer: agents must use structured JSON effect."""
    p = _get_prompt()
    assert "http.post_json" in p
    assert "Never hand-roll JSON" in p


def test_http_graphql_rule_present():
    """v1.17.0 gap-closer: for GraphQL APIs, agents must use the
    specialized http.graphql effect rather than hand-rolling the
    error-detection tree over http.post_json + parse_json. Field test
    2026-04-24 saw three turns of misdiagnosed GitHub GraphQL
    failures with the hand-rolled pattern."""
    p = _get_prompt()
    assert "http.graphql" in p
    assert "Never hand-roll GraphQL error handling" in p
    # The GitHub canonical example must use http.graphql.
    first_idx = p.find("GitHub GraphQL")
    end_idx = p.find("```", first_idx)
    # Find the next ``` (closing fence after the opening fence)
    opening_fence = p.rfind("```ail", 0, first_idx)
    # The GitHub example starts at the `# GitHub GraphQL` comment;
    # it must contain `perform http.graphql` inside that block.
    closing_fence = p.find("```", p.find("# GitHub GraphQL"))
    assert closing_fence != -1
    github_block = p[p.find("# GitHub GraphQL"):closing_fence]
    assert "perform http.graphql" in github_block, (
        "GitHub canonical example must call `perform http.graphql` "
        "— not hand-rolled http.post_json + parse_json.")
    # And it must NOT retain the hand-rolled errors check in that
    # example (guards against a future edit partially rewriting it).
    assert 'get(data, "errors")' not in github_block


def test_input_hint_rule_present():
    """v1.15.2 UX: agents must declare a # INPUT: hint when entry uses input."""
    p = _get_prompt()
    assert "# INPUT:" in p
    assert "placeholder" in p.lower()


def test_human_approve_section_present():
    """v1.16.0 plan-validate-execute gate. The authoring prompt must
    call out `perform human.approve` as non-bypassable for irreversible
    side effects, and the three canonical examples (Discord / Mastodon
    / GitHub GraphQL) must demonstrate the plan-approve-post shape."""
    p = _get_prompt()
    assert "PLAN BEFORE IRREVERSIBLE ACTION" in p
    assert "perform human.approve" in p
    # Every canonical example that performs a side effect must show
    # the approval gate — otherwise an agent pattern-matching against
    # the examples would ship a program that skips the gate.
    first_example_idx = p.find("Discord webhook post")
    last_example_idx = p.find("Key contrasts with the \"bad old way\"")
    assert first_example_idx != -1 and last_example_idx != -1
    examples_block = p[first_example_idx:last_example_idx]
    assert examples_block.count("perform human.approve") >= 3, (
        "expected all three 'post to X' canonical examples to show the "
        "human.approve gate; got only "
        f"{examples_block.count('perform human.approve')} instances")
    # The contrast section must call out the approval gate as the
    # first HEAAL win, not an afterthought.
    contrast_idx = p.find("Key contrasts with the \"bad old way\"")
    first_bullet_idx = p.find("perform human.approve", contrast_idx)
    assert first_bullet_idx != -1
    # Make sure 'human.approve' appears in the contrast bullets
    # before 'pair-list' (the JSON-encoding contrast) — approval is
    # the higher-order HEAAL property.
    assert first_bullet_idx < p.find("pair-list", contrast_idx)
