"""Tests for import resolution and the bundled standard library."""
from __future__ import annotations

import pytest

from ail import compile_source
from ail.runtime import MockAdapter
from ail.runtime.executor import Executor
from ail.runtime.model import ModelResponse
from ail.stdlib import (
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


def test_relative_import_requires_base_directory():
    """Without importing_from, a `./` import has no base to resolve
    against. This is distinct from the v1.56 change where relative
    imports ARE supported when the executor passes project_root."""
    with pytest.raises(ImportResolutionError, match="no base directory"):
        resolve("./my_helpers")


def test_relative_import_resolves_project_local_ail_file(tmp_path):
    """PRINCIPLES.md §6 (user, 2026-04-24): "에이전트가 스스로 필요한
    도구를 코딩하고 .ail 파일로 저장해서 그걸 import할 수 있게 하면
    좋을듯." This test is the keystone — each program the agent
    writes becomes a reusable tool for the next program."""
    (tmp_path / "greeter.ail").write_text(
        'pure fn hello(name: Text) -> Text {\n'
        '    return join(["Hello, ", name, "!"], "")\n'
        '}\n',
        encoding="utf-8",
    )
    prog = resolve("./greeter", importing_from=tmp_path)
    fn_names = [
        d.name for d in prog.declarations if hasattr(d, "name")
    ]
    assert "hello" in fn_names


def test_relative_import_confined_to_project_root(tmp_path):
    """`../../etc/passwd` type escapes are rejected."""
    (tmp_path / "proj").mkdir()
    with pytest.raises(ImportResolutionError, match="escapes"):
        resolve("../../outside", importing_from=tmp_path / "proj")


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


def test_index_of_primitive_and_contains_on_top_of_it():
    """v1.53: index_of runtime primitive, contains now uses it.
    Verifies both the primitive and the helper compose correctly."""
    from ail import compile_source, MockAdapter
    from ail.runtime import Executor

    src = """
    import contains from "stdlib/utils"

    entry main(input: Text) {
        a = index_of("hello world", "world")
        b = index_of("hello world", "xyz")
        c = contains("hello world", "world")
        d = contains("hello world", "xyz")
        return join([to_text(a), to_text(b), to_text(c), to_text(d)], "|")
    }
    """
    program = compile_source(src)
    result = Executor(program, MockAdapter()).run_entry({"input": ""})
    parts = str(result.value).split("|")
    assert parts[0] == "6"       # "world" starts at index 6
    assert parts[1] == "-1"      # absent → -1
    assert parts[2] == "true"
    assert parts[3] == "false"


def test_stdlib_utils_new_helpers_execute_correctly():
    """v1.52 additions to stdlib/utils.ail. These are the fns authoring
    agents used to reinvent inline; each end-to-end call here is a
    regression guard against the bug class of "pure fn compiles but
    runtime shape is wrong" that hit the pre-fix sum_list/flatten."""
    from ail import compile_source, MockAdapter
    from ail.runtime import Executor

    src = """
    import contains from "stdlib/utils"
    import count_occurrences from "stdlib/utils"
    import truncate from "stdlib/utils"
    import to_upper_first from "stdlib/utils"
    import plural_count from "stdlib/utils"
    import is_numeric from "stdlib/utils"
    import csv_to_rows from "stdlib/utils"
    import rows_to_csv from "stdlib/utils"

    entry main(input: Text) {
        c = contains("hello world", "wor")
        n = count_occurrences("a,b,c,d", ",")
        t = truncate("abcdefghij", 4)
        u = to_upper_first("korean")
        p = plural_count(3, "item", "items")
        nm = is_numeric("  42.5 ")
        csv = rows_to_csv(csv_to_rows("a,b\\nc,d"))
        return join([to_text(c), to_text(n), t, u, p, to_text(nm), csv], "|")
    }
    """
    program = compile_source(src)
    executor = Executor(program, MockAdapter())
    result = executor.run_entry({"input": ""})
    parts = str(result.value).split("|")
    assert parts[0] == "true"       # contains
    assert parts[1] == "3"          # count_occurrences
    assert parts[2] == "abcd…"      # truncate with ellipsis
    assert parts[3] == "Korean"     # to_upper_first
    assert parts[4] == "3 items"    # plural_count (n != 1)
    assert parts[5] == "true"       # is_numeric
    assert parts[6] == "a,b\nc,d"   # csv round-trip


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
    from ail.parser.ast import Identifier
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
