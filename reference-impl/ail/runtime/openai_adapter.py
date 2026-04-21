"""OpenAI-compatible model adapter.

Works with any server that implements the OpenAI Chat Completions API:
- vLLM  (`python -m vllm.entrypoints.openai.api_server`)
- LM Studio, LocalAI, llama.cpp --server, etc.

Uses only the Python standard library.

Usage:

    from ail.runtime.openai_adapter import OpenAICompatibleAdapter
    from ail import run

    adapter = OpenAICompatibleAdapter(
        model="qwen2.5-coder:14b",
        base_url="http://localhost:8000",
    )
    result, trace = run("program.ail", input="hello", adapter=adapter)

Environment variables:
  AIL_OPENAI_COMPAT_MODEL    — model name (required if not passed to __init__)
  AIL_OPENAI_COMPAT_BASE_URL — server base URL (default: http://localhost:8000)
  AIL_OPENAI_COMPAT_API_KEY  — API key (default: "EMPTY" — vLLM accepts any)
  AIL_OPENAI_COMPAT_TIMEOUT_S — request timeout seconds (default: 300)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from .model import ModelResponse
from .json_parsing import parse_value_confidence


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_TIMEOUT_S = 300.0


class OpenAICompatibleAdapter:
    name = "openai_compat"

    def __init__(self, model: Optional[str] = None,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 timeout: Optional[float] = None,
                 temperature: float = 0.0):
        self.model = model or os.environ.get(
            "AIL_OPENAI_COMPAT_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get(
            "AIL_OPENAI_COMPAT_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.api_key = api_key or os.environ.get(
            "AIL_OPENAI_COMPAT_API_KEY", "EMPTY")
        if timeout is None:
            env_t = os.environ.get("AIL_OPENAI_COMPAT_TIMEOUT_S")
            timeout = float(env_t) if env_t else DEFAULT_TIMEOUT_S
        self.timeout = timeout
        self.temperature = temperature

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None) -> ModelResponse:
        system = self._build_system_prompt(goal, constraints, context,
                                           expected_type, examples)
        user = self._build_user_prompt(inputs)

        # Skip JSON mode for AIL authoring (same logic as OllamaAdapter)
        is_authoring = context.get("_intent_name") == "__author_ail__"

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "stream": False,
        }
        if not is_authoring:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"OpenAI-compatible request failed at {self.base_url}: {e}. "
                f"Is the server running? Model: '{self.model}'"
            ) from e

        data = json.loads(raw)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(
                f"Unexpected response shape from {self.base_url}: {data!r}"
            ) from e

        value, confidence = parse_value_confidence(content)
        usage = data.get("usage", {})

        return ModelResponse(
            value=value,
            confidence=confidence,
            model_id=f"openai_compat/{self.model}",
            raw={
                "finish_reason": (data["choices"][0].get("finish_reason")
                                  if data.get("choices") else None),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            },
        )

    def _build_system_prompt(self, goal, constraints, context,
                             expected_type, examples) -> str:
        lines = [
            "You are executing an AIL intent. AIL programs describe *intent*;",
            "you produce the result that satisfies the declared goal and constraints.",
            "",
            "Respond with ONE JSON object and nothing else:",
            '  {"value": <result>, "confidence": <float 0.0 to 1.0>}',
            "",
            "The confidence reflects your calibrated belief the result meets",
            "the goal. 1.0 = certain; 0.5 = unsure; 0.0 = could not satisfy.",
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
            lines.append("CONTEXT:")
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
        return "\n".join(f"{k}: {v}" for k, v in inputs.items())
