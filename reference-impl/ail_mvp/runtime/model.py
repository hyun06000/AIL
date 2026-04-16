"""Model adapter protocol.

A model adapter presents a language model to the AIRT dispatcher. The MVP
ships with one adapter (Anthropic) plus a deterministic mock adapter for
testing.

Adapters are responsible for:
- Translating an intent + context into a prompt
- Invoking the model
- Returning a (value, confidence) pair with a structured rationale
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Any, Optional


@dataclass
class ModelResponse:
    value: Any
    confidence: float
    model_id: str
    raw: dict[str, Any]          # provider-specific for trace purposes


class ModelAdapter(Protocol):
    name: str

    def invoke(
        self,
        *,
        goal: str,
        constraints: list[str],
        context: dict[str, Any],
        inputs: dict[str, Any],
        expected_type: Optional[str] = None,
        examples: Optional[list[tuple[Any, Any]]] = None,
    ) -> ModelResponse: ...


# --- Mock adapter for tests & offline development ---


class MockAdapter:
    """Deterministic adapter that echoes a canned response. Useful for tests
    without network access.
    """

    name = "mock"

    def __init__(self, responses: Optional[dict[str, Any]] = None,
                 default_confidence: float = 0.85):
        self.responses = responses or {}
        self.default_confidence = default_confidence

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None) -> ModelResponse:
        # Match by intent name if the caller provided one in context
        intent_name = context.get("_intent_name", "unknown")
        value = self.responses.get(intent_name, f"[mock response for {intent_name}]")
        return ModelResponse(
            value=value, confidence=self.default_confidence,
            model_id="mock-1", raw={"goal": goal, "inputs": inputs},
        )
