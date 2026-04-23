"""Tests for the intent-return type harness (v1.10).

Two layers:

1. Pure unit tests on `validate_and_coerce` — cover the type matrix
   (Text / Number / Boolean / [T]) plus the code-fence stripper.
2. Executor integration — an intent whose model returns a wrong
   shape must trigger one retry, and on repeated failure the call
   returns the raw value at confidence 0 so downstream attempt /
   confidence guards can route around it.
"""
from __future__ import annotations

from ail import ask, run
from ail.runtime import ConfidentValue
from ail.runtime.intent_validation import (
    strip_code_fence, validate_and_coerce,
)
from ail.runtime.model import ModelResponse


# ---------- strip_code_fence ----------


def test_strip_code_fence_language_tag():
    assert strip_code_fence("```json\n42\n```") == "42"


def test_strip_code_fence_no_tag():
    assert strip_code_fence("```\nhello\n```") == "hello"


def test_strip_code_fence_unchanged_when_no_fence():
    assert strip_code_fence("just text") == "just text"


def test_strip_code_fence_leaves_inner_fences():
    inner = "```python\nprint('hi')\n```"
    wrapped = f"```\n{inner}\n```"
    # Outer fence stripped; inner fence preserved verbatim.
    assert strip_code_fence(wrapped) == inner


def test_strip_code_fence_handles_non_string():
    assert strip_code_fence(42) == 42


# ---------- Text ----------


def test_text_passes_plain_string():
    v, err = validate_and_coerce("hello", "Text")
    assert err is None and v == "hello"


def test_text_rejects_dict():
    v, err = validate_and_coerce({"k": "v"}, "Text")
    assert err is not None and "Text" in err


def test_text_rejects_json_dict_string():
    # A stringified dict must not slip through as Text — this is the
    # exact failure the Korean news-dashboard hit in 2026-04-23.
    v, err = validate_and_coerce(
        '{"overall_summary": "...", "news_cards": []}', "Text")
    assert err is not None
    assert "JSON" in err or "dict" in err


def test_text_rejects_json_list_string():
    v, err = validate_and_coerce('[1, 2, 3]', "Text")
    assert err is not None


def test_text_allows_strings_with_braces_inline():
    # Braces in normal prose are fine — only a whole-response JSON
    # envelope is rejected.
    v, err = validate_and_coerce(
        "The set is {a, b, c} — three items.", "Text")
    assert err is None


def test_text_strips_outer_code_fence():
    v, err = validate_and_coerce(
        "```\nsome narrative\n```", "Text")
    assert err is None and v == "some narrative"


# ---------- Number ----------


def test_number_passes_int():
    v, err = validate_and_coerce(42, "Number")
    assert err is None and v == 42.0


def test_number_passes_float():
    v, err = validate_and_coerce(3.14, "Number")
    assert err is None and v == 3.14


def test_number_coerces_numeric_string():
    v, err = validate_and_coerce("  12.5 ", "Number")
    assert err is None and v == 12.5


def test_number_rejects_non_numeric_string():
    v, err = validate_and_coerce("twelve", "Number")
    assert err is not None


def test_number_rejects_boolean():
    # bool is an int subclass in Python; the model meant a truth value.
    v, err = validate_and_coerce(True, "Number")
    assert err is not None and "Boolean" in err


def test_number_strips_code_fence():
    v, err = validate_and_coerce("```\n42\n```", "Number")
    assert err is None and v == 42.0


# ---------- Boolean ----------


def test_boolean_passes_true():
    v, err = validate_and_coerce(True, "Boolean")
    assert err is None and v is True


def test_boolean_accepts_true_string():
    v, err = validate_and_coerce("True", "Boolean")
    assert err is None and v is True


def test_boolean_accepts_yes_no():
    assert validate_and_coerce("yes", "Boolean") == (True, None)
    assert validate_and_coerce("no", "Boolean") == (False, None)


def test_boolean_rejects_garbage():
    v, err = validate_and_coerce("maybe", "Boolean")
    assert err is not None


# ---------- List ----------


def test_list_of_text_accepts_clean_list():
    v, err = validate_and_coerce(["a", "b"], "[Text]")
    assert err is None and v == ["a", "b"]


def test_list_of_text_parses_json_list_string():
    v, err = validate_and_coerce('["a", "b"]', "[Text]")
    assert err is None and v == ["a", "b"]


def test_list_of_number_coerces_inner_strings():
    v, err = validate_and_coerce(["1", "2.5"], "[Number]")
    assert err is None and v == [1.0, 2.5]


def test_list_rejects_non_list():
    v, err = validate_and_coerce("not a list", "[Text]")
    assert err is not None


def test_list_surfaces_inner_index_on_error():
    v, err = validate_and_coerce(["ok", 42], "[Text]")
    assert err is not None and "element 1" in err


# ---------- pass-through for unknown types ----------


def test_unknown_return_type_passes_through():
    # Records / Result / nested composites are pass-through in v1.10.
    v, err = validate_and_coerce({"k": "v"}, "Result[Text]")
    assert err is None and v == {"k": "v"}


def test_none_return_type_passes_through():
    # Intent without a declared return type — no harness, no coercion.
    v, err = validate_and_coerce([1, 2, 3], None)
    assert err is None and v == [1, 2, 3]


# ---------- executor integration ----------


class _MisshapenAuthor:
    """First turn returns a dict-string pretending to be Text; second
    turn (retry) returns a clean string. Verifies the retry loop."""
    name = "misshapen-scripted"

    def __init__(self):
        self._calls = 0
        self.goals_seen = []
        self.constraints_seen = []

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None):
        self._calls += 1
        self.goals_seen.append(goal)
        self.constraints_seen.append(list(constraints))
        intent_name = context.get("_intent_name", "")
        if intent_name == "__author_ail__":
            return ModelResponse(
                value=(
                    "intent summarize(text: Text) -> Text "
                    "{ goal: short_summary }\n"
                    "entry main(input: Text) { return summarize(input) }"
                ),
                confidence=0.95, model_id="scripted",
                raw={},
            )
        if intent_name == "summarize":
            if self._calls == 2:
                # First intent call: dict-wrapped response that should
                # be rejected by the Text harness.
                return ModelResponse(
                    value='{"overall_summary": "long", "news_cards": []}',
                    confidence=0.8, model_id="scripted",
                    raw={},
                )
            # Retry — clean text this time.
            return ModelResponse(
                value="clean summary",
                confidence=0.8, model_id="scripted",
                raw={},
            )
        return ModelResponse(
            value="", confidence=0.5, model_id="scripted", raw={})


def test_intent_retry_recovers_from_misshapen_response(tmp_path):
    author = _MisshapenAuthor()
    result = ask("summarize something", adapter=author)
    # The misshapen first intent response was retried and the clean
    # second response became the final value.
    assert result.value == "clean summary"
    # Constraints on the retry include the harness's sharpening line.
    retry_constraints = author.constraints_seen[-1]
    assert any("declared return type" in c for c in retry_constraints)


class _AlwaysMisshapenAuthor:
    """Author returns the program; intent always returns a dict-string
    no matter how many times you ask. Verifies the confidence-floor
    fallback after retries are exhausted."""
    name = "always-misshapen-scripted"

    def __init__(self):
        self._calls = 0

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None):
        self._calls += 1
        intent_name = context.get("_intent_name", "")
        if intent_name == "__author_ail__":
            return ModelResponse(
                value=(
                    "intent summarize(text: Text) -> Text "
                    "{ goal: short_summary }\n"
                    "entry main(input: Text) { return summarize(input) }"
                ),
                confidence=0.95, model_id="scripted",
                raw={},
            )
        return ModelResponse(
            value='{"bad": "shape"}',
            confidence=0.8, model_id="scripted",
            raw={},
        )


def test_intent_falls_back_to_zero_confidence_after_exhausted_retries():
    author = _AlwaysMisshapenAuthor()
    result = ask("summarize something", adapter=author)
    # Retries exhausted. Confidence floored to 0 so downstream
    # attempt / branch guards can route around it. The raw value is
    # still surfaced for debugging (not silently blanked).
    assert result.confidence == 0.0
    assert "bad" in str(result.value)
