"""Natural-language diagnosis of authoring failures.

When the author model can't produce valid AIL after the retry budget
is spent, the raw parse error ("ParseError: unexpected token COLON")
is meaningless to a non-developer. This module asks the author model
one more time — not to write code, but to explain in the user's own
language what went wrong and suggest one concrete edit to INTENT.md
that would help next time.

The goal is end-user UX, not debugging. The raw error stays in
`.ail/ledger.jsonl` for anyone who needs to dig in; this layer is
the friendly face shown on stderr.

This follows a cross-cutting design principle recorded by hyun06000
on 2026-04-23:

  Errors that come from AI-generated code should be translated by
  AI into the user's language. We should never surface tokenizer
  or parser vocabulary to a non-developer.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Optional

from ..authoring import _default_adapter
from ..runtime.model import ModelAdapter


_DIAGNOSE_GOAL = (
    "The AI author tried to write AIL code from the user's INTENT.md "
    "below and couldn't produce a valid program. Write a short message "
    "(3–4 sentences) to the user, in the SAME natural language they "
    "used in their INTENT.md. The message should: "
    "(a) gently say the AI could not build this yet, "
    "(b) name in plain words what made it hard, "
    "(c) suggest ONE specific edit to INTENT.md that would help on the "
    "next try. The reader is a non-developer who does not know what a "
    "parser, compiler, or function type is."
)

_DIAGNOSE_CONSTRAINTS = [
    "Do not use technical words. No 'ParseError', 'syntax', 'colon', "
    "'token', 'compile', 'intent keyword', 'pure fn', 'stack trace'.",
    "Do not scold the user. Frame the difficulty as a limitation of "
    "what the AI could automate, never as a mistake by the user.",
    "Output the message as a plain Text string. No JSON object, no "
    "markdown headers, no code fences around it.",
    "Match the language of INTENT.md. If INTENT.md is Korean, reply in "
    "Korean; if English, reply in English.",
    "Length: keep under 4 sentences total.",
]


def diagnose_authoring_failure(
    *,
    intent_md: str,
    last_ail_source: str,
    errors: list[str],
    adapter: Optional[ModelAdapter] = None,
) -> str:
    """Return a plain-language diagnosis message in the user's language.

    Raises if the backend itself is unreachable; callers should catch
    and fall back to a static message in that case.
    """
    adapter = adapter or _default_adapter()
    response = adapter.invoke(
        goal=_DIAGNOSE_GOAL,
        constraints=_DIAGNOSE_CONSTRAINTS,
        context={
            "_intent_name": "__diagnose_authoring__",
            "intent_md": intent_md,
            "last_ail_attempt": last_ail_source[:4000],
            "error_messages": "\n".join(errors[-3:]) if errors else "",
        },
        inputs={"task": "diagnose"},
        expected_type="Text (plain-language message to the user)",
        examples=_diagnosis_examples(),
    )
    return _coerce_to_text(response.value)


# ---------------- helpers ----------------

def _coerce_to_text(raw: Any) -> str:
    """Tolerate the four shapes the backend might return."""
    if isinstance(raw, str):
        s = raw.strip()
        # Some adapters wrap a JSON object around the text.
        if s.startswith("{"):
            try:
                d = json.loads(s)
                if isinstance(d, dict):
                    return _coerce_to_text(d)
            except Exception:
                pass
        return s
    if isinstance(raw, dict):
        # Pick the first plausible text field.
        for key in ("message", "text", "output", "value", "reply", "diagnosis"):
            v = raw.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # As a last resort, assemble "reason" + "suggestion" shapes from
        # models that returned a structured object anyway.
        reason = raw.get("reason") or ""
        suggestion = raw.get("suggestion") or ""
        return (reason + ("\n\n" + suggestion if suggestion else "")).strip()
    return str(raw).strip()


def _diagnosis_examples() -> list[dict[str, Any]]:
    """Few-shot examples in both languages so the model matches tone."""
    return [
        {
            "intent_md": (
                "# word-counter\n\n"
                "문장을 입력하면 형태소로 나누는 분석기.\n\n"
                "## Behavior\n"
                "- 빈 입력은 에러\n"
                "- 한국어가 아니면 에러\n\n"
                "## Tests\n- \"\" → 에러\n"
            ),
            "last_ail_attempt": (
                "pure fn analyze(text: Text) -> List[Morpheme] {\n"
                "    result: List[Morpheme] = []\n"
                "    ...\n"
                "}\n"
            ),
            "error_messages": "ParseError: unexpected token COLON(':')@6:42",
            "task": "diagnose",
            "output": (
                "이 작업은 언어를 이해해야 하는 작업이라서 AI가 규칙만으로 "
                "계산하려다 막혔어요. 한국어 형태소 분석은 언어 모델의 판단이 "
                "필요한 종류의 일입니다. INTENT.md의 `## Behavior` 섹션에 "
                "\"언어 모델을 사용해서 형태소 분석을 수행한다\"라는 한 줄을 "
                "추가하고 다시 `ail up`을 실행해 보세요."
            ),
        },
        {
            "intent_md": (
                "# summarizer\n\n"
                "Summarize articles to one sentence.\n\n"
                "## Tests\n- \"Long article...\" → succeed\n"
            ),
            "last_ail_attempt": "pure fn summarize(text: Text) -> Text { ...",
            "error_messages": "ParseError: unexpected token",
            "task": "diagnose",
            "output": (
                "Summarizing an article needs the AI to actually read and "
                "understand the text, which is a reasoning task rather than "
                "a pure calculation. The AI tried to solve it with a formula "
                "and couldn't. Add a line to `## Behavior` that says "
                "\"Use a language model to summarize\" and run `ail up` again."
            ),
        },
    ]
