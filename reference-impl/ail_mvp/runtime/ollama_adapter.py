"""Ollama model adapter.

Lets AIL run against a local model served by `ollama` (https://ollama.ai).
No API key, no network cost. Useful for development, CI fallback, and
experimentation with smaller models.

Uses only the Python standard library — no `requests` dependency. Talks
HTTP to `http://localhost:11434/api/chat` (the default ollama endpoint).

Usage:

    from ail_mvp.runtime.ollama_adapter import OllamaAdapter
    from ail_mvp import run

    adapter = OllamaAdapter(model="llama3.1:latest")
    result, trace = run("program.ail", input="hello", adapter=adapter)

Environment variables:
  AIL_OLLAMA_MODEL  — default model name if not passed to __init__
                      (e.g. "llama3.1:latest", "gemma2:latest")
  AIL_OLLAMA_HOST   — default "http://localhost:11434"

Small models emit (value, confidence) JSON with varying discipline; the
shared parser in json_parsing.py tolerates code fences, prose wrappers,
and missing-confidence fallbacks. When a small model produces plain
prose, the parser returns the prose text with confidence 0.5 — the
program keeps running but the low confidence signals the caller (or an
`attempt` block) to consider a stronger fallback.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from .model import ModelResponse
from .json_parsing import parse_value_confidence


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:latest"
DEFAULT_TIMEOUT_S = 120.0


class OllamaAdapter:
    name = "ollama"

    def __init__(self, model: Optional[str] = None,
                 host: Optional[str] = None,
                 timeout: float = DEFAULT_TIMEOUT_S,
                 temperature: float = 0.0):
        self.model = model or os.environ.get("AIL_OLLAMA_MODEL", DEFAULT_MODEL)
        self.host = (host or os.environ.get("AIL_OLLAMA_HOST",
                                            DEFAULT_HOST)).rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None) -> ModelResponse:
        system = self._build_system_prompt(goal, constraints, context,
                                           expected_type, examples)
        user = self._build_user_prompt(inputs)

        # JSON mode is the right default for AIL intent calls (we want
        # structured (value, confidence) back). For the authoring layer,
        # asking the model to also wrap its output in JSON makes a small
        # model fight two constraints at once and tends to fail. The
        # __author_ail__ intent name is the signal to skip JSON mode and
        # take whatever raw text the model produces.
        format_json = context.get("_intent_name") != "__author_ail__"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }
        if format_json:
            payload["format"] = "json"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Ollama request failed at {self.host}: {e}. "
                f"Is `ollama serve` running and is the model '{self.model}' pulled?"
            ) from e

        data = json.loads(raw)
        # Chat API: {"message": {"role": "assistant", "content": "..."}, ...}
        content = ""
        msg = data.get("message")
        if isinstance(msg, dict):
            content = msg.get("content", "")
        if not content:
            # Fallback: some ollama versions surface content at top level
            content = data.get("response", "")

        value, confidence = parse_value_confidence(content)

        return ModelResponse(
            value=value,
            confidence=confidence,
            model_id=f"ollama/{self.model}",
            raw={
                "done_reason": data.get("done_reason"),
                "total_duration_ns": data.get("total_duration"),
                "eval_count": data.get("eval_count"),
                "prompt_eval_count": data.get("prompt_eval_count"),
            },
        )

    # --- prompt assembly (mirrors AnthropicAdapter for consistency) ---

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
