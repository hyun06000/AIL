"""INTENT.md — the single human-edited file in an AIL project.

Plain Markdown with conventional section headers. The agent extracts
structure from the headers; users never see a schema.

Recognized sections (English / Korean both honored):
  preamble                   — everything before the first ## header
  ## Behavior  / ## 동작     — bullet list of behavioral requirements
  ## Tests     / ## 테스트   — bullet list of test cases
  ## Deployment / ## 배포    — port, environment, schedule
  ## Evolution / ## 진화     — (optional) when to retune, rollback

Test bullets follow the shape:
  - "input text" → expected outcome
  - "input text" → 에러            (anything containing 에러/error/fail
                                    means the program is expected to
                                    fail; otherwise it must succeed)

The expected-outcome side is recorded but only its success/failure
shape is checked in v0. Content match would require an LLM judge,
deferred to v1+.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


# Section header aliases — Markdown level-2 headers, English or Korean.
_SECTION_ALIASES: dict[str, list[str]] = {
    "behavior":   ["behavior", "동작"],
    "tests":      ["tests", "test", "테스트"],
    "deployment": ["deployment", "deploy", "배포"],
    "evolution":  ["evolution", "evolve", "진화"],
}

# Words that indicate a test case is expected to fail.
_FAILURE_WORDS = (
    "에러", "error", "fail", "실패", "오류",
    "not allowed", "허용되지", "거부",
)

# Default port when ## Deployment is absent or doesn't specify one.
DEFAULT_PORT = 8080


@dataclass
class TestCase:
    """A single test case extracted from INTENT.md ## Tests."""
    input: str
    expect_ok: bool          # True = must run successfully; False = must error
    raw: str                 # original bullet text, for reporting


@dataclass
class IntentSpec:
    """Parsed INTENT.md contents."""
    name: str
    preamble: str            # one-paragraph what-is-this
    behavior: list[str] = field(default_factory=list)
    tests: list[TestCase] = field(default_factory=list)
    port: int = DEFAULT_PORT
    deployment_notes: list[str] = field(default_factory=list)
    evolution: list[str] = field(default_factory=list)

    def authoring_goal(self) -> str:
        """Assemble the natural-language goal handed to the author model.

        Returns a single text block combining preamble + behavior bullets
        + a hint about the input shape and test expectations. The author
        model uses this to decide what AIL to write.
        """
        parts = [self.preamble.strip()]
        if self.behavior:
            parts.append("\nBehavior requirements:")
            parts.extend(f"- {b}" for b in self.behavior)
        if self.tests:
            parts.append("\nThe program will be exercised with these inputs:")
            for t in self.tests:
                shape = "succeed" if t.expect_ok else "error"
                parts.append(f'- input {t.input!r} → must {shape}')
        parts.append(
            "\nWrite an AIL program with `entry main(input: Text)` "
            "that handles all the cases above."
        )
        return "\n".join(parts)


# ---------------------------------------------------------------- parsing

_HEADER_RE = re.compile(r"^##+\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$", re.MULTILINE)
_PORT_RE   = re.compile(r"(?:port|포트)\s*[:=]?\s*(\d{2,5})", re.IGNORECASE)
_TITLE_RE  = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _normalize_header(text: str) -> str:
    """Map a header text to a canonical section key, or '' if unknown."""
    low = text.strip().lower()
    for key, aliases in _SECTION_ALIASES.items():
        if any(low == a or low.startswith(a + " ") or low.startswith(a + ":")
               for a in aliases):
            return key
    return ""


def _split_sections(body: str) -> dict[str, str]:
    """Split body into {section_key: text}. Unrecognized headers grouped
    under the last recognized section if any, else dropped."""
    out: dict[str, list[str]] = {"_preamble": []}
    current = "_preamble"
    pos = 0
    for m in _HEADER_RE.finditer(body):
        out[current].append(body[pos:m.start()])
        key = _normalize_header(m.group(1))
        if key:
            current = key
            out.setdefault(current, [])
            pos = m.end()
        else:
            # unknown header — keep its text in current section
            pos = m.start()
    out[current].append(body[pos:])
    return {k: "".join(v).strip() for k, v in out.items()}


def _parse_test_bullet(text: str) -> Optional[TestCase]:
    """Parse one ## Tests bullet into a TestCase. Returns None if the
    bullet doesn't have the recognized shape."""
    # Find the first quoted string as input.
    m = re.search(r'[\"\u201c\u201d]([^\"\u201c\u201d]*)[\"\u201c\u201d]', text)
    if not m:
        # Fall back to "input → ..." without quotes
        if "→" in text:
            inp, _, rest = text.partition("→")
            input_text = inp.strip().strip("`").strip("'")
            outcome = rest
        else:
            return None
    else:
        input_text = m.group(1)
        outcome = text[m.end():]

    expect_ok = not any(w in outcome.lower() for w in _FAILURE_WORDS)
    return TestCase(input=input_text, expect_ok=expect_ok, raw=text.strip())


def parse_intent_md(text: str, *, default_name: str = "app") -> IntentSpec:
    """Parse INTENT.md text into an IntentSpec.

    Tolerant of missing sections — every section is optional. The only
    required content is *some* preamble describing what to build.
    """
    title_m = _TITLE_RE.search(text)
    name = title_m.group(1).strip() if title_m else default_name
    body = text[title_m.end():] if title_m else text

    sections = _split_sections(body)
    preamble = sections.get("_preamble", "").strip()

    behavior = [m.group(1) for m in _BULLET_RE.finditer(sections.get("behavior", ""))]
    evolution = [m.group(1) for m in _BULLET_RE.finditer(sections.get("evolution", ""))]

    tests: list[TestCase] = []
    for m in _BULLET_RE.finditer(sections.get("tests", "")):
        tc = _parse_test_bullet(m.group(1))
        if tc is not None:
            tests.append(tc)

    deployment_notes = [m.group(1) for m in _BULLET_RE.finditer(sections.get("deployment", ""))]
    port = DEFAULT_PORT
    port_m = _PORT_RE.search(sections.get("deployment", ""))
    if port_m:
        port = int(port_m.group(1))

    return IntentSpec(
        name=name,
        preamble=preamble,
        behavior=behavior,
        tests=tests,
        port=port,
        deployment_notes=deployment_notes,
        evolution=evolution,
    )


def render_intent_template(name: str) -> str:
    """Return a starter INTENT.md for a freshly-initialized project."""
    return f"""# {name}

A short paragraph describing what this service should do, in plain
language. The AI reads this to decide what AIL program to write.

## Behavior
- (one bullet per behavioral requirement)
- (e.g. "Empty input returns an error")
- (e.g. "Inputs longer than 1000 characters are truncated")

## Tests
- "sample input" → expected outcome description
- "" → 에러
- (each bullet is one test case the AI will run before the service starts)

## Deployment
- 포트 {DEFAULT_PORT}
"""
