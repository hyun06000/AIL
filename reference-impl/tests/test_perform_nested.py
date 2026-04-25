"""Regression tests for `perform` effects called from nested user fns.

Telos reported (2026-04-26 letter) that `perform env.read` inside a
user-defined fn — when that fn was itself called from another fn —
appeared to return a different value than calling `perform env.read`
directly. The minimal isolation tests below all pass; we keep them as
guards so any future regression in the executor's effect-dispatch
scope handling is caught immediately.

If a user reports the same symptom again, the next step is to widen
these tests to include `evolve`-server `request_received` arms (where
Telos's actual bug surfaced, in Stoa's `handle_post_message`).
"""
from __future__ import annotations

import os
import textwrap

import pytest

from ail import run, MockAdapter


def _run_with_env(source: str, env: dict[str, str]) -> str:
    saved = {k: os.environ.get(k) for k in env}
    try:
        os.environ.update(env)
        result, _ = run(source, input="x", adapter=MockAdapter())
        return str(result.value)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_direct_and_nested_env_read_agree():
    """Telos's minimal repro shape: read same env var directly in
    `entry` and indirectly through a fn. Both must return the same
    value; if they diverge, the executor's perform-dispatch is
    leaking scope between call frames."""
    src = textwrap.dedent("""
    fn inner() -> Text {
        r = perform env.read("AIL_TEST_NESTED_VAR")
        if is_error(r) { return "missing" }
        return unwrap(r)
    }

    entry main(input: Text) {
        direct_r = perform env.read("AIL_TEST_NESTED_VAR")
        direct = "missing"
        if not is_error(direct_r) {
            direct = unwrap(direct_r)
        }
        nested = inner()
        return join(["direct=", direct, " nested=", nested], "")
    }
    """)
    out = _run_with_env(src, {"AIL_TEST_NESTED_VAR": "hello-world"})
    assert "direct=hello-world" in out
    assert "nested=hello-world" in out


def test_two_level_fn_nesting_with_perform():
    """Stoa's actual call path was deeper: handle_post_message ->
    save_messages -> get_data_file -> perform env.read. Two levels
    of fn between the entry and the perform."""
    src = textwrap.dedent("""
    fn read_var() -> Text {
        r = perform env.read("AIL_TEST_TWO_LEVEL")
        if is_error(r) { return "DEFAULT" }
        return trim(unwrap(r))
    }

    fn save_thing(data: Text) -> Text {
        path = read_var()
        return path
    }

    entry main(input: Text) {
        direct = read_var()
        via_fn = save_thing("dummy")
        return join(["direct=", direct, " via_fn=", via_fn], "")
    }
    """)
    out = _run_with_env(src, {"AIL_TEST_TWO_LEVEL": "/data/messages.json"})
    assert "direct=/data/messages.json" in out
    assert "via_fn=/data/messages.json" in out


def test_perform_env_read_with_missing_var_falls_back_consistently():
    """When the env var is unset, both direct and nested must agree
    that it's missing. (A divergence here would mean is_error is
    behaving differently across call depths.)"""
    src = textwrap.dedent("""
    fn inner() -> Text {
        r = perform env.read("AIL_TEST_DEFINITELY_UNSET_XYZ")
        if is_error(r) { return "missing" }
        return unwrap(r)
    }

    entry main(input: Text) {
        direct_r = perform env.read("AIL_TEST_DEFINITELY_UNSET_XYZ")
        direct = "present"
        if is_error(direct_r) { direct = "missing" }
        nested = inner()
        return join(["direct=", direct, " nested=", nested], "")
    }
    """)
    os.environ.pop("AIL_TEST_DEFINITELY_UNSET_XYZ", None)
    result, _ = run(src, input="x", adapter=MockAdapter())
    out = str(result.value)
    assert "direct=missing" in out
    assert "nested=missing" in out
