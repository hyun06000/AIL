"""Tests for import resolution and the bundled standard library."""
from __future__ import annotations

import pytest

from ail_mvp import compile_source
from ail_mvp.runtime import MockAdapter
from ail_mvp.runtime.executor import Executor
from ail_mvp.runtime.model import ModelResponse
from ail_mvp.stdlib import (
    resolve, available_stdlib_modules, ImportResolutionError, _clear_cache,
)


class ScriptedAdapter(MockAdapter):
    """Adapter that returns a scripted response per intent name."""

    def __init__(self, scripts):
        super().__init__()
        self.scripts = scripts
        self.calls = []

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None):
        name = context.get("_intent_name", "?")
        self.calls.append(name)
        if name in self.scripts:
            v, c = self.scripts[name]
            return ModelResponse(value=v, confidence=c, model_id="scripted", raw={})
        return ModelResponse(value="(nope)", confidence=0.5, model_id="scripted", raw={})


# ---------- resolver ----------


def test_stdlib_core_resolves():
    _clear_cache()
    program = resolve("stdlib/core")
    names = {getattr(d, "name", None) for d in program.declarations}
    assert "identity" in names
    assert "refuse" in names


def test_stdlib_language_resolves():
    _clear_cache()
    program = resolve("stdlib/language")
    names = {getattr(d, "name", None) for d in program.declarations}
    # Every intent documented in spec/06 §2 should be present
    for expected in ("summarize", "translate", "classify", "extract", "rewrite", "critique"):
        assert expected in names, f"stdlib/language missing {expected}"


def test_unknown_stdlib_module_raises():
    _clear_cache()
    with pytest.raises(ImportResolutionError, match="not found"):
        resolve("stdlib/nonexistent_module")


def test_relative_import_rejected_in_mvp():
    with pytest.raises(ImportResolutionError, match="relative imports"):
        resolve("./my_helpers")


def test_url_import_rejected():
    with pytest.raises(ImportResolutionError, match="URL"):
        resolve("org://somecorp/lib@v1")


def test_resolver_caches_parsed_module():
    _clear_cache()
    first = resolve("stdlib/language")
    second = resolve("stdlib/language")
    # Same Program instance -> cache working
    assert first is second


def test_available_stdlib_modules_lists_bundled():
    mods = available_stdlib_modules()
    assert "core" in mods
    assert "language" in mods


# ---------- end-to-end: import then call ----------


def test_importing_stdlib_makes_intents_callable():
    src = """
    import summarize from "stdlib/language"

    entry main(text: Text) {
        brief = summarize(text, 50)
        return brief
    }
    """
    adapter = ScriptedAdapter({"summarize": ("short version", 0.9)})
    program = compile_source(src)
    executor = Executor(program, adapter)
    result = executor.run_entry({"text": "long document"})

    assert result.value == "short version"
    assert "summarize" in executor.intents
    assert "summarize" in adapter.calls


def test_importing_language_brings_in_all_intents():
    """Importing any symbol from a module brings the whole module's
    declarations into scope in the MVP (whole-module import).
    """
    src = """
    import classify from "stdlib/language"
    entry main(x: Text) { return x }
    """
    program = compile_source(src)
    executor = Executor(program, MockAdapter())
    # Every stdlib/language intent should be reachable
    for name in ("summarize", "translate", "classify", "extract", "rewrite", "critique"):
        assert name in executor.intents


def test_local_intent_shadows_imported():
    """A local intent with the same name as an imported one wins."""
    src = """
    import summarize from "stdlib/language"

    intent summarize(source: Text, max_tokens: Number) -> Text {
        goal: local_override_that_ignores_the_stdlib_version
    }

    entry main(text: Text) {
        return summarize(text, 10)
    }
    """
    program = compile_source(src)
    executor = Executor(program, MockAdapter())
    local = executor.intents["summarize"]
    # The local version's goal is an Identifier with our unique name
    from ail_mvp.parser.ast import Identifier
    assert isinstance(local.goal, Identifier)
    assert local.goal.name == "local_override_that_ignores_the_stdlib_version"


def test_multiple_imports_merged():
    src = """
    import identity from "stdlib/core"
    import classify from "stdlib/language"
    entry main(x: Text) { return x }
    """
    program = compile_source(src)
    executor = Executor(program, MockAdapter())
    # Both modules' intents are present
    assert "identity" in executor.intents     # from core
    assert "classify" in executor.intents     # from language
    assert set(executor.imported_sources) == {"stdlib/core", "stdlib/language"}
