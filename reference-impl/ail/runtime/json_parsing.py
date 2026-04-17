"""Shared JSON-response parsing for model adapters.

Language models — especially small local ones — emit the (value, confidence)
JSON an AIL intent expects with varying degrees of discipline. They may wrap
it in markdown code fences, prefix it with explanatory prose, or produce
nested JSON. This module contains the tolerant parsing used by all adapters
so every adapter handles the same malformed-JSON shapes the same way.

Public entry point: `parse_value_confidence(text) -> (value, confidence)`.
Fallbacks: if no JSON with a "value" key can be extracted, returns the raw
text and a moderate confidence of 0.5 — the caller can still make progress.
"""
from __future__ import annotations

import json
from typing import Any


def parse_value_confidence(text: str) -> tuple[Any, float]:
    """Extract (value, confidence) from a model response.

    Tolerates these shapes:
      1. Pure JSON: `{"value": ..., "confidence": ...}`
      2. Code-fenced JSON: ` ```json\n{"value": ...}\n``` `
      3. JSON embedded in prose: finds the first balanced `{...}` that
         contains `"value"`
      4. Plain text: returns the raw text with confidence 0.5

    Confidence is clamped to [0.0, 1.0]; non-numeric values become 0.5.
    """
    stripped = _strip_code_fence(text.strip())

    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and "value" in obj and "confidence" in obj:
            return obj["value"], clamp_confidence(obj["confidence"])
    except (json.JSONDecodeError, ValueError):
        pass

    extracted = _extract_balanced_json(stripped)
    if extracted is not None:
        try:
            obj = json.loads(extracted)
            if isinstance(obj, dict) and "value" in obj:
                return obj["value"], clamp_confidence(obj.get("confidence", 0.5))
        except (json.JSONDecodeError, ValueError):
            pass

    return text, 0.5


def clamp_confidence(raw: Any) -> float:
    """Coerce raw to float in [0.0, 1.0]. Non-numeric input becomes 0.5."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.5
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _strip_code_fence(text: str) -> str:
    """Remove an enclosing ``` fence, preserving inner content."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    newline_idx = stripped.find("\n")
    if newline_idx == -1:
        return stripped
    body = stripped[newline_idx + 1:]
    if body.endswith("```"):
        body = body[:-3]
    return body.strip()


def _extract_balanced_json(text: str) -> str | None:
    """First balanced `{...}` substring that contains `"value"`, or None."""
    start_positions = [i for i, c in enumerate(text) if c == "{"]
    for start in start_positions:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    if '"value"' in candidate:
                        return candidate
                    break
    return None
