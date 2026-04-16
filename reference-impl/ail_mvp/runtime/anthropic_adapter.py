"""Anthropic model adapter.

Translates an AIL intent invocation into a Messages API call. The adapter
composes a structured system prompt that includes goal, constraints,
context, and (optionally) examples, then parses the response.

Requires: pip install anthropic, and ANTHROPIC_API_KEY in env.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Optional

from .model import ModelResponse


DEFAULT_MODEL = "claude-sonnet-4-5"


class AnthropicAdapter:
    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None):
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "The anthropic package is required. Install with: pip install anthropic"
            ) from e
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Export it or pass api_key explicitly."
            )

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None) -> ModelResponse:
        import anthropic
        client = anthropic.Anthropic(api_key=self._api_key)

        system = self._build_system_prompt(goal, constraints, context, expected_type, examples)
        user = self._build_user_prompt(inputs)

        resp = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()

        value, confidence = self._parse_response(text)

        return ModelResponse(
            value=value,
            confidence=confidence,
            model_id=resp.model,
            raw={
                "stop_reason": resp.stop_reason,
                "input_tokens": getattr(resp.usage, "input_tokens", None),
                "output_tokens": getattr(resp.usage, "output_tokens", None),
            },
        )

    # --- prompt assembly ---

    def _build_system_prompt(self, goal, constraints, context,
                             expected_type, examples) -> str:
        lines = [
            "You are executing an AIL intent. AIL programs describe *intent*;",
            "you produce the result that satisfies the declared goal and constraints.",
            "",
            "Respond in this exact JSON format (no surrounding prose, no code fence):",
            '  {"value": <your result>, "confidence": <number 0.0 to 1.0>}',
            "",
            "The confidence reflects your calibrated belief that your result",
            "satisfies the goal under the given context. Be honest; 1.0 means",
            "you are certain, 0.5 means unsure, 0.0 means you could not produce",
            "a satisfactory result.",
            "",
            f"GOAL: {goal}",
        ]
        if constraints:
            lines.append("")
            lines.append("CONSTRAINTS:")
            for c in constraints:
                lines.append(f"  - {c}")
        if context:
            lines.append("")
            lines.append("CONTEXT (situation this executes in):")
            for k, v in context.items():
                if k.startswith("_"):
                    continue
                lines.append(f"  {k}: {v}")
        if expected_type:
            lines.append("")
            lines.append(f"EXPECTED TYPE: {expected_type}")
        if examples:
            lines.append("")
            lines.append("EXAMPLES:")
            for inp, out in examples[:5]:
                lines.append(f"  input: {inp!r}")
                lines.append(f"  => {out!r}")
        return "\n".join(lines)

    def _build_user_prompt(self, inputs) -> str:
        if not inputs:
            return "(no input)"
        if len(inputs) == 1:
            k, v = next(iter(inputs.items()))
            return f"{k}: {v}"
        parts = [f"{k}: {v}" for k, v in inputs.items()]
        return "\n".join(parts)

    # --- response parsing ---

    def _parse_response(self, text: str) -> tuple[Any, float]:
        """Parse a model response into (value, confidence).

        Tolerates common response shapes:
          1. Pure JSON:           {"value": ..., "confidence": ...}
          2. Code-fenced JSON:    ```json\n{"value": ...}\n```
          3. JSON embedded in prose — extract the first balanced {...}
             that contains a "value" key
          4. Anything else — return raw text with a moderate confidence

        The returned confidence is clamped to [0.0, 1.0].
        """
        stripped = text.strip()

        # (2) Strip code fences before trying other parses
        stripped = self._strip_code_fence(stripped)

        # (1) Direct JSON
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and "value" in obj and "confidence" in obj:
                return obj["value"], self._clamp_confidence(obj["confidence"])
        except (json.JSONDecodeError, ValueError):
            pass

        # (3) Find the first balanced JSON object that mentions "value"
        extracted = self._extract_balanced_json(stripped)
        if extracted is not None:
            try:
                obj = json.loads(extracted)
                if isinstance(obj, dict) and "value" in obj:
                    return (
                        obj["value"],
                        self._clamp_confidence(obj.get("confidence", 0.5)),
                    )
            except (json.JSONDecodeError, ValueError):
                pass

        # (4) Fallback
        return text, 0.5

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """Remove an enclosing ``` fence if present. Preserves inner content."""
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        # Drop the opening fence line (possibly ```json)
        newline_idx = stripped.find("\n")
        if newline_idx == -1:
            return stripped
        body = stripped[newline_idx + 1:]
        if body.endswith("```"):
            body = body[: -3]
        return body.strip()

    @staticmethod
    def _extract_balanced_json(text: str) -> str | None:
        """Return the first balanced {...} substring that contains '"value"'.

        Respects nested braces and ignores braces inside JSON strings.
        Returns None if no such substring exists.
        """
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
                        candidate = text[start : i + 1]
                        if '"value"' in candidate:
                            return candidate
                        break
        return None

    @staticmethod
    def _clamp_confidence(raw: Any) -> float:
        """Coerce to float in [0.0, 1.0]. Non-numeric -> 0.5."""
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return 0.5
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v
