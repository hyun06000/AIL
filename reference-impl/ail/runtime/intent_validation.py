"""Validate an intent model's response against its declared return type.

The harness gap this closes:

    intent summarize(text: Text) -> Text { goal: short_summary }

Before v1.10, the runtime accepted whatever the model returned and
called it a Text — including a nested record, a raw RSS feed, or a
code-fenced JSON envelope. That leaked the "trust the LLM" escape
hatch through the harness. HEAAL's claim is that AIL's grammar
constrains what can flow through the program; leaving intent returns
unvalidated is a hole in that claim.

This module enforces the declared type at the intent boundary:

1. Strip any remaining markdown code fences.
2. Coerce the cleaned value against the declared type (`Text`,
   `Number`, `Boolean`, `[T]` for those three).
3. Return a (coerced_value, error_or_none) tuple. `error` is None on
   success, or a human-readable mismatch description that the caller
   can feed back into a retry prompt.

Records, `Result[T]`, and nested composite types are pass-through in
this release — the common intent-return shapes are scalars and flat
lists. A v1.11 pass will tighten composite validation.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional


# Match a markdown code fence with optional language tag:
#   ```json\n<...>\n```
#   ```\n<...>\n```
_CODE_FENCE = re.compile(
    r"^\s*```[a-zA-Z0-9_-]*\n(.*?)\n```\s*$",
    re.DOTALL,
)


def strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence if present.

    Returns the text unchanged if no fence wraps it; otherwise returns
    the content between the fence markers with surrounding whitespace
    trimmed. Only matches a single outer fence — nested fences inside
    the content are preserved.
    """
    if not isinstance(text, str):
        return text
    m = _CODE_FENCE.match(text)
    if m:
        return m.group(1).strip()
    return text


def validate_and_coerce(
    value: Any, return_type: Optional[str]
) -> tuple[Any, Optional[str]]:
    """Coerce `value` to match the declared `return_type`.

    Returns `(coerced_value, error)`. On success `error is None` and
    `coerced_value` is the cleaned value. On failure the caller gets
    a non-None error message suitable for feeding back into a retry
    prompt.

    `return_type is None` means the intent didn't declare one — the
    value passes through unchanged.
    """
    if return_type is None:
        return value, None

    rt = return_type.strip()

    # Strip a code fence if the value is a string wrapped in one.
    # Applies uniformly regardless of the declared type — a Number
    # declared as ```42``` is still 42.
    if isinstance(value, str):
        value = strip_code_fence(value)

    if rt == "Text":
        return _coerce_text(value)
    if rt == "Number":
        return _coerce_number(value)
    if rt == "Boolean":
        return _coerce_boolean(value)
    if rt.startswith("[") and rt.endswith("]"):
        inner = rt[1:-1].strip()
        return _coerce_list(value, inner)

    # Unknown or composite declared type: pass through for now. Records
    # and Result[T] need their own designs; flagging them as invalid
    # would break existing programs that currently work by convention.
    return value, None


# ---------- scalar coercers ----------


def _coerce_text(value: Any) -> tuple[Any, Optional[str]]:
    """A Text must be a plain string, not a structured payload the
    model packaged as JSON."""
    if not isinstance(value, str):
        return value, (
            f"declared Text but got {type(value).__name__} "
            f"({_preview(value)}) — return a plain string, no wrapping"
        )

    # Reject responses that are just a serialized dict/list. A string
    # like `{"ticks": 7, "news_cards": [...raw rss...]}` shouldn't be
    # passed along as if it were a text answer; the author asked for
    # text, not a data dump.
    trimmed = value.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        try:
            parsed = json.loads(trimmed)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            return value, (
                "declared Text but response parses as a JSON "
                f"{type(parsed).__name__} — return plain text, not a "
                "structured payload"
            )

    return value, None


def _coerce_number(value: Any) -> tuple[Any, Optional[str]]:
    """A Number must be numeric or trivially parseable as one."""
    if isinstance(value, bool):
        # bool is a subclass of int in Python; the model clearly
        # meant a truth value, not a number.
        return value, (
            f"declared Number but got Boolean ({value}) — "
            "return a number"
        )
    if isinstance(value, (int, float)):
        return float(value), None
    if isinstance(value, str):
        s = value.strip()
        try:
            return float(s), None
        except (TypeError, ValueError):
            return value, (
                f"declared Number but got non-numeric string "
                f"({_preview(value)}) — return just the number"
            )
    return value, (
        f"declared Number but got {type(value).__name__} "
        f"({_preview(value)}) — return a number"
    )


def _coerce_boolean(value: Any) -> tuple[Any, Optional[str]]:
    """A Boolean must be true/false, or a string that trivially maps."""
    if isinstance(value, bool):
        return value, None
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "yes", "y", "1"):
            return True, None
        if s in ("false", "no", "n", "0"):
            return False, None
        return value, (
            f"declared Boolean but got {_preview(value)} — "
            "return true or false"
        )
    return value, (
        f"declared Boolean but got {type(value).__name__} "
        f"({_preview(value)}) — return true or false"
    )


def _coerce_list(
    value: Any, inner: str
) -> tuple[Any, Optional[str]]:
    """A list return: must be a list, and every element must coerce
    to the inner type. Stop-on-first-error so the prompt retry only
    has to fix one thing at a time."""
    # If the model returned a JSON string describing a list, parse it.
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    value = parsed
            except (json.JSONDecodeError, ValueError):
                pass

    if not isinstance(value, list):
        return value, (
            f"declared [{inner}] but got {type(value).__name__} "
            f"({_preview(value)}) — return a list"
        )

    coerced = []
    for i, item in enumerate(value):
        c, err = validate_and_coerce(item, inner)
        if err is not None:
            return value, f"list element {i}: {err}"
        coerced.append(c)
    return coerced, None


# ---------- utilities ----------


def _preview(value: Any, limit: int = 80) -> str:
    s = repr(value) if not isinstance(value, str) else value
    if len(s) <= limit:
        return s
    return s[:limit] + "…"
