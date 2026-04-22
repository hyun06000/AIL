"""Diagnosis tests — verify the authoring-failure translator produces
plain text the caller can print directly, and tolerates the shape
variations adapters actually return.
"""
from dataclasses import dataclass
from typing import Any

from ail.agentic.diagnosis import (
    diagnose_authoring_failure,
    _coerce_to_text,
)


@dataclass
class _StubResponse:
    value: Any
    raw: dict = None


class _StubAdapter:
    name = "stub"

    def __init__(self, value):
        self._value = value
        self.calls = []

    def invoke(self, *, goal, constraints, context, inputs, expected_type, examples):
        self.calls.append({"goal": goal, "context_keys": list(context.keys())})
        return _StubResponse(value=self._value)


def test_diagnose_returns_plain_text_in_user_language():
    adapter = _StubAdapter(
        "이 작업은 언어 모델이 필요한 일입니다. "
        "INTENT.md에 \"언어 모델을 사용한다\" 한 줄을 추가해 보세요."
    )
    out = diagnose_authoring_failure(
        intent_md="# ko-app\n\n한국어 형태소 분석.\n",
        last_ail_source="pure fn analyze(text: Text) { result: List = [] }",
        errors=["ParseError: unexpected token COLON(':')@6:42"],
        adapter=adapter,
    )
    assert "언어 모델" in out
    # Plain text, not JSON
    assert not out.startswith("{")


def test_diagnose_passes_intent_md_and_errors_to_adapter():
    adapter = _StubAdapter("explanation")
    diagnose_authoring_failure(
        intent_md="# en-app\n\nSummarize.\n",
        last_ail_source="pure fn x() {",
        errors=["ParseError: ..."],
        adapter=adapter,
    )
    assert len(adapter.calls) == 1
    ctx_keys = adapter.calls[0]["context_keys"]
    assert "intent_md" in ctx_keys
    assert "error_messages" in ctx_keys
    assert "last_ail_attempt" in ctx_keys


def test_coerce_to_text_accepts_plain_string():
    assert _coerce_to_text("just a message") == "just a message"
    assert _coerce_to_text("  has surrounding whitespace  ") == "has surrounding whitespace"


def test_coerce_to_text_unwraps_json_string():
    raw = '{"message": "use an LLM"}'
    assert _coerce_to_text(raw) == "use an LLM"


def test_coerce_to_text_prefers_known_keys_from_dict():
    assert _coerce_to_text({"message": "m"}) == "m"
    assert _coerce_to_text({"text": "t"}) == "t"
    # Falls through to reason+suggestion pair
    out = _coerce_to_text({
        "reason": "this is hard",
        "suggestion": "try another way",
    })
    assert "this is hard" in out
    assert "try another way" in out


def test_diagnose_tolerates_dict_response():
    """Some adapters return a dict instead of a plain string."""
    adapter = _StubAdapter({"message": "말로 풀어서 이렇게 알려드립니다."})
    out = diagnose_authoring_failure(
        intent_md="# x\n",
        last_ail_source="",
        errors=["ParseError"],
        adapter=adapter,
    )
    assert "말로 풀어서" in out


def test_diagnose_examples_match_adapter_format():
    """Catches the v1.9.1 regression where examples were dicts but
    the AnthropicAdapter unpacks them as (input, output) tuples — a
    mismatch that crashed every diagnose call with 'too many values
    to unpack'."""
    from ail.agentic.diagnosis import _diagnosis_examples
    examples = _diagnosis_examples()
    assert examples, "should have at least one example"
    for example in examples:
        # Adapter does: for inp, out in examples[:5]
        assert len(example) == 2, (
            f"each example must be a 2-tuple (inputs_list, output); "
            f"got {len(example)}"
        )
        inp, out = example
        assert isinstance(inp, list)
        assert isinstance(out, str)


def test_detect_language():
    from ail.agentic.ui import detect_language
    assert detect_language("# 한국어 프로젝트\n\n받은 텍스트를 ...") == "ko"
    assert detect_language("# english project\n\nDoes a thing.") == "en"
    assert detect_language("") == "en"
    # Mixed but contains Hangul syllables → ko
    assert detect_language("# Mixed 한글 also OK") == "ko"
