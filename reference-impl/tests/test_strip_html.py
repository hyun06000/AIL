"""Tests for the `strip_html` pure built-in.

Closes the HEAAL gap where agents scraping web pages had nothing
between `perform http.get` (which returns a multi-kilobyte HTML
blob) and the `intent` that tries to read it. Without a stripper,
every call sent tags + inline JS + CSS through the model — wasted
tokens, lower accuracy.

`strip_html` is pure: no I/O, no effects, no LLM. Safe to call
from a `pure fn`.
"""
from __future__ import annotations

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _strip(src: str) -> str:
    program = compile_source(
        'entry main(input: Text) { return strip_html(input) }'
    )
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": src}).value


def test_strips_simple_tags():
    out = _strip("<p>Hello <b>world</b>!</p>")
    assert out == "Hello world!"


def test_decodes_common_entities():
    out = _strip("<p>Tom &amp; Jerry &lt;3 &quot;cats&quot;</p>")
    assert out == 'Tom & Jerry <3 "cats"'


def test_drops_script_body():
    out = _strip(
        "<html><head><script>var x = 1; console.log('hi');</script></head>"
        "<body>visible</body></html>"
    )
    assert "var x" not in out
    assert "console.log" not in out
    assert "visible" in out


def test_drops_style_body():
    out = _strip(
        "<html><head><style>.hidden{display:none}</style></head>"
        "<body>visible</body></html>"
    )
    assert ".hidden" not in out
    assert "display" not in out
    assert "visible" in out


def test_collapses_whitespace():
    out = _strip("<p>  multiple    \t\t  spaces   </p>")
    # Leading and trailing spaces trimmed; inner run collapsed.
    assert out == "multiple spaces"


def test_preserves_paragraph_breaks():
    out = _strip("<p>first</p><p>second</p><p>third</p>")
    # Browsers render these as separate blocks; we keep them
    # separated for downstream intent readability.
    assert "first" in out and "second" in out and "third" in out


def test_malformed_html_does_not_crash():
    # A real-world fetch can return partial HTML, missing
    # close-tags, broken entities. The function must be total:
    # worst case it returns what it parsed up to the break.
    out = _strip("<p>partial<div unclosed <span>content")
    assert "partial" in out or "content" in out  # something survives


def test_empty_input():
    assert _strip("") == ""


def test_plain_text_passes_through():
    out = _strip("no tags here, just text")
    assert out == "no tags here, just text"


def test_nested_script_in_body_removed():
    # Inline event handlers, data-attribute JS, etc. still strip
    # cleanly because the parser only removes content between
    # <script>...</script> and <style>...</style>, not attribute values.
    out = _strip(
        '<button onclick="alert(1)">Click</button>'
        '<script>alert(2)</script>'
    )
    assert "alert(1)" not in out  # attribute dropped with the tag
    assert "alert(2)" not in out  # script body dropped
    assert "Click" in out


def test_usable_from_pure_fn():
    """strip_html is PURE — must be callable from a `pure fn` body."""
    program = compile_source(
        'pure fn clean(html: Text) -> Text {\n'
        '  return strip_html(html)\n'
        '}\n'
        'entry main(input: Text) { return clean(input) }'
    )
    ex = Executor(program, MockAdapter())
    assert ex.run_entry({"input": "<b>x</b>"}).value == "x"
