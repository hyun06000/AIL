"""Anthropic model adapter.

Translates an AIL intent invocation into a Messages API call. The adapter
composes a structured system prompt that includes goal, constraints,
context, and (optionally) examples, then parses the response.

Requires: pip install anthropic, and ANTHROPIC_API_KEY in env.
"""
from __future__ import annotations
import os
from typing import Optional

from .model import ModelResponse
from .json_parsing import parse_value_confidence


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

        if context.get("_intent_name") == "__authoring_chat__":
            user_msg = inputs.get("user_message", "(no input)")
            resp = client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=goal,
                messages=[
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": "<reply>"},
                ],
            )
            text = "<reply>" + "".join(
                block.text for block in resp.content if getattr(block, "type", None) == "text"
            ).strip()
            return ModelResponse(
                value=text,
                confidence=0.9,
                model_id=resp.model,
                raw={
                    "stop_reason": resp.stop_reason,
                    "input_tokens": getattr(resp.usage, "input_tokens", None),
                    "output_tokens": getattr(resp.usage, "output_tokens", None),
                },
            )

        system = self._build_system_prompt(goal, constraints, context, expected_type, examples)
        user = self._build_user_prompt(inputs)

        resp = client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()

        value, confidence = parse_value_confidence(text)

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
