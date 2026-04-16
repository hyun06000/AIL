"""Tests for AnthropicAdapter response parsing.

These tests exercise the static parsing methods only and do not
require an API key or network access.
"""
from __future__ import annotations

import pytest

# Skip gracefully if the anthropic package isn't installed
anthropic = pytest.importorskip("anthropic")

from ail_mvp.runtime.anthropic_adapter import AnthropicAdapter


class _Parser:
    """Expose the static parser methods without constructing an adapter
    (which requires ANTHROPIC_API_KEY)."""
    _parse_response = AnthropicAdapter._parse_response
    _strip_code_fence = staticmethod(AnthropicAdapter._strip_code_fence)
    _extract_balanced_json = staticmethod(AnthropicAdapter._extract_balanced_json)
    _clamp_confidence = staticmethod(AnthropicAdapter._clamp_confidence)


def test_direct_json():
    v, c = _Parser._parse_response(_Parser, '{"value": "hi", "confidence": 0.9}')
    assert v == "hi"
    assert c == 0.9


def test_code_fenced_json():
    text = '```json\n{"value": "hi", "confidence": 0.8}\n```'
    v, c = _Parser._parse_response(_Parser, text)
    assert v == "hi"
    assert c == 0.8


def test_code_fenced_without_language_tag():
    text = '```\n{"value": 42, "confidence": 0.5}\n```'
    v, c = _Parser._parse_response(_Parser, text)
    assert v == 42
    assert c == 0.5


def test_embedded_json_in_prose():
    text = 'Sure! Here is my answer: {"value": "Seoul", "confidence": 0.95} I hope that helps.'
    v, c = _Parser._parse_response(_Parser, text)
    assert v == "Seoul"
    assert c == 0.95


def test_nested_object_as_value():
    text = '{"value": {"city": "Seoul", "country": "KR"}, "confidence": 0.9}'
    v, c = _Parser._parse_response(_Parser, text)
    assert v == {"city": "Seoul", "country": "KR"}
    assert c == 0.9


def test_confidence_clamped_above_one():
    v, c = _Parser._parse_response(_Parser, '{"value": "x", "confidence": 1.5}')
    assert c == 1.0


def test_confidence_clamped_below_zero():
    v, c = _Parser._parse_response(_Parser, '{"value": "x", "confidence": -0.2}')
    assert c == 0.0


def test_confidence_non_numeric_falls_back_to_half():
    v, c = _Parser._parse_response(_Parser, '{"value": "x", "confidence": "high"}')
    assert c == 0.5


def test_plain_prose_falls_back():
    v, c = _Parser._parse_response(_Parser, "I don't know.")
    assert v == "I don't know."
    assert c == 0.5


def test_missing_value_key_falls_back():
    v, c = _Parser._parse_response(_Parser, '{"answer": "x", "confidence": 0.9}')
    # No "value" key -> falls back to raw text with 0.5
    assert c == 0.5


def test_string_with_braces_does_not_confuse_extractor():
    """A JSON value containing { should not break nested-brace counting."""
    text = '{"value": "the set is {}", "confidence": 0.9}'
    v, c = _Parser._parse_response(_Parser, text)
    assert v == "the set is {}"
    assert c == 0.9
