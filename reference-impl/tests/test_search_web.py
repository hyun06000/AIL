"""Tests for the search.web effect.

These tests run without any real HTTP calls by monkey-patching
urllib.request.urlopen. The three backends (Google, SearXNG,
DuckDuckGo) are exercised in isolation and in fallback order.
"""
from __future__ import annotations

import io
import json
import os
import unittest.mock as mock

import pytest

from ail import compile_source
from ail.runtime.executor import Executor, ConfidentValue
from ail.runtime.model import MockAdapter
from ail.runtime.provenance import LITERAL_ORIGIN


def _make_exec() -> Executor:
    p = compile_source('entry main(input: Text) { return "" }')
    return Executor(p, MockAdapter())


def _origin():
    return LITERAL_ORIGIN


def _cv(v):
    return ConfidentValue(v, 1.0, origin=_origin())


def _fake_http_response(body: str, status: int = 200):
    """Return a context-manager mock mimicking urllib.urlopen response."""
    encoded = body.encode("utf-8")
    m = mock.MagicMock()
    m.__enter__ = lambda s: s
    m.__exit__ = mock.MagicMock(return_value=False)
    m.read.return_value = encoded
    m.status = status
    return m


# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------

def test_search_web_returns_result_ok_with_list(monkeypatch):
    """Google backend happy-path: returns ok(list) with title/url/snippet."""
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_SEARCH_CX", "test-cx")

    payload = json.dumps({"items": [
        {"title": "AIL Lang", "link": "https://example.com/ail",
         "snippet": "A language for AI authors"},
    ]})

    with mock.patch("urllib.request.urlopen",
                    return_value=_fake_http_response(payload)):
        ex = _make_exec()
        result = ex._search_web([_cv("AIL language")], {}, _origin())

    assert isinstance(result.value, dict)
    assert result.value["ok"] is True
    items = result.value["value"]
    assert len(items) == 1
    assert items[0]["title"] == "AIL Lang"
    assert items[0]["url"] == "https://example.com/ail"
    assert items[0]["snippet"] == "A language for AI authors"


def test_search_web_confidence_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_SEARCH_CX", "cx")
    payload = json.dumps({"items": [
        {"title": "T", "link": "https://x.com", "snippet": "S"}]})
    with mock.patch("urllib.request.urlopen",
                    return_value=_fake_http_response(payload)):
        result = _make_exec()._search_web([_cv("q")], {}, _origin())
    assert result.confidence == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------

def test_search_web_missing_query_is_error():
    ex = _make_exec()
    result = ex._search_web([], {}, _origin())
    assert result.value["ok"] is False
    assert "query" in result.value["error"]


def test_search_web_empty_query_is_error():
    ex = _make_exec()
    result = ex._search_web([_cv("   ")], {}, _origin())
    assert result.value["ok"] is False


# ---------------------------------------------------------------------------
# Backend fallback chain
# ---------------------------------------------------------------------------

def test_search_web_skips_google_when_no_keys(monkeypatch):
    """Without Google env vars the effect must not call googleapis.com."""
    monkeypatch.delenv("GOOGLE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_CX", raising=False)
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)

    ddg_html = """
    <div class="result__body">
      <a class="result__a" href="https://ddg.example.com">DDG Result</a>
      <div class="result__snippet">A snippet from DDG</div>
    </div>
    """
    with mock.patch("urllib.request.urlopen",
                    return_value=_fake_http_response(ddg_html)) as m:
        result = _make_exec()._search_web([_cv("test query")], {}, _origin())
    # urlopen called exactly once — only DDG
    assert m.call_count == 1
    url_called = m.call_args[0][0].full_url
    assert "duckduckgo" in url_called


def test_search_web_falls_back_to_searxng_on_google_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_SEARCH_CX", "cx")
    monkeypatch.setenv("SEARXNG_BASE_URL", "http://localhost:8888")
    monkeypatch.delenv("GOOGLE_SEARCH_CX", raising=False)  # key without cx → skip google

    searxng_payload = json.dumps({"results": [
        {"title": "SX", "url": "https://sx.example.com", "content": "SX snippet"}
    ]})
    with mock.patch("urllib.request.urlopen",
                    return_value=_fake_http_response(searxng_payload)):
        result = _make_exec()._search_web([_cv("q")], {}, _origin())
    assert result.value["ok"] is True
    assert result.confidence == pytest.approx(0.8)
    assert result.value["value"][0]["title"] == "SX"


def test_search_web_all_backends_fail_returns_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_CX", raising=False)
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)

    import urllib.error
    with mock.patch("urllib.request.urlopen",
                    side_effect=urllib.error.URLError("network down")):
        result = _make_exec()._search_web([_cv("q")], {}, _origin())
    assert result.value["ok"] is False
    assert "all backends failed" in result.value["error"]


# ---------------------------------------------------------------------------
# count parameter
# ---------------------------------------------------------------------------

def test_search_web_count_kwarg(monkeypatch):
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_SEARCH_CX", "cx")
    payload = json.dumps({"items": [
        {"title": f"T{i}", "link": f"https://x.com/{i}", "snippet": "s"}
        for i in range(5)
    ]})
    with mock.patch("urllib.request.urlopen",
                    return_value=_fake_http_response(payload)) as m:
        _make_exec()._search_web([_cv("q")], {"count": _cv(3)}, _origin())
    url = m.call_args[0][0].full_url
    assert "num=3" in url


def test_search_web_count_capped_at_20(monkeypatch):
    """count is capped at 20; the Google request URL must reflect that."""
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_SEARCH_CX", "cx")
    # Return items so Google succeeds (no DDG fallback).
    payload = json.dumps({"items": [
        {"title": "T", "link": "https://x.com", "snippet": "s"}]})
    with mock.patch("urllib.request.urlopen",
                    return_value=_fake_http_response(payload)) as m:
        _make_exec()._search_web([_cv("q"), _cv(999)], {}, _origin())
    url = m.call_args[0][0].full_url
    assert "num=20" in url


# ---------------------------------------------------------------------------
# browser.fetch must not exist
# ---------------------------------------------------------------------------

def test_browser_fetch_removed():
    """browser.fetch was intentionally removed — must raise RuntimeError."""
    ex = _make_exec()
    with pytest.raises(RuntimeError, match="unknown effect"):
        ex._builtin_effect("browser.fetch", [_cv("https://example.com")], {})
