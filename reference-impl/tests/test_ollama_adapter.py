"""Integration tests for the Ollama adapter.

These tests only run when `ollama serve` is reachable at localhost:11434.
They are skipped on CI by default (no ollama there) but exercise the
real local-model path on a developer machine.

Opt out with env var AIL_SKIP_OLLAMA_TESTS=1.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest


OLLAMA_HOST = os.environ.get("AIL_OLLAMA_HOST", "http://localhost:11434")
TEST_MODEL = os.environ.get("AIL_OLLAMA_TEST_MODEL", "llama3.1:latest")


def _ollama_available() -> bool:
    if os.environ.get("AIL_SKIP_OLLAMA_TESTS"):
        return False
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=1.0) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return False
    names = {m.get("name") for m in data.get("models", [])}
    return TEST_MODEL in names


pytestmark = pytest.mark.skipif(
    not _ollama_available(),
    reason=f"ollama not reachable at {OLLAMA_HOST} or model {TEST_MODEL} not pulled",
)


def test_classify_via_ollama():
    """A classify intent routed to llama3.1 returns a reasonable label.

    We don't assert the exact label (small-model output varies) — only
    that we get a non-empty result with an ollama-tagged origin.
    """
    from ail_mvp import run
    from ail_mvp.runtime.ollama_adapter import OllamaAdapter

    src = """
    import classify from "stdlib/language"
    entry main(text: Text) {
        return classify(text, "positive_negative_neutral")
    }
    """
    adapter = OllamaAdapter(model=TEST_MODEL)
    result, _ = run(src, input="I love this product", adapter=adapter)
    assert result.value          # non-empty
    assert result.origin.kind == "intent"
    assert result.origin.name == "classify"
    assert result.origin.model_id == f"ollama/{TEST_MODEL}"


def test_ollama_adapter_defaults_from_env(monkeypatch):
    """AIL_OLLAMA_MODEL / AIL_OLLAMA_HOST fallbacks are read at construction."""
    from ail_mvp.runtime.ollama_adapter import OllamaAdapter
    monkeypatch.setenv("AIL_OLLAMA_MODEL", "custom-model:tag")
    monkeypatch.setenv("AIL_OLLAMA_HOST", "http://example.invalid:12345")
    adapter = OllamaAdapter()
    assert adapter.model == "custom-model:tag"
    assert adapter.host == "http://example.invalid:12345"
