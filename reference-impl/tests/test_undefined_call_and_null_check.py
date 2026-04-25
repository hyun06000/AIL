"""Regression: undefined function calls raise loudly + new is_null/make_record builtins.

qna_bot field test 2026-04-26 (박상현 자다 깬 피드백): the prompt was
teaching `is_null(question)` and `make_record([[k,v]])` but neither was
defined. The executor's `_builtin_call` fallback returned
`ConfidentValue(True)` for ANY undefined name, silently routing every
request into the wrong branch. The user saw "질문 처리 중 오류" with no
diagnostic.

Three guards now in place:
1. `is_null` is a real builtin (`true` iff value is None).
2. `make_record` is a real builtin (pair list → dict).
3. Calling any other undefined name raises NameError instead of
   returning a silent True.
"""
from __future__ import annotations

import textwrap

import pytest

from ail import run, MockAdapter


def _run(src: str) -> str:
    result, _ = run(src, input="x", adapter=MockAdapter())
    return str(result.value)


def test_is_null_true_for_none_only():
    src = textwrap.dedent("""
    entry main(input: Text) {
        rec = make_record([["a", 1]])
        missing = get(rec, "nope")
        present = get(rec, "a")
        return to_text(is_null(missing)) + "|" + to_text(is_null(present))
                   + "|" + to_text(is_null("")) + "|" + to_text(is_null(0))
    }
    """)
    assert _run(src) == "true|false|false|false"


def test_make_record_builds_dict_with_get_and_dot_access():
    src = textwrap.dedent("""
    entry main(input: Text) {
        r = make_record([["status", 200], ["body", "hello"]])
        return to_text(get(r, "body")) + "|" + to_text(r.status)
    }
    """)
    assert _run(src) == "hello|200"


def test_undefined_function_raises_nameerror_loudly():
    """Was returning silent True via the MVP fallback; now must
    raise so the auto-fix loop and field debugging can see the
    actual problem name."""
    src = textwrap.dedent("""
    entry main(input: Text) {
        return to_text(some_function_that_does_not_exist("x"))
    }
    """)
    with pytest.raises(NameError, match="undefined function"):
        run(src, input="x", adapter=MockAdapter())


def test_undefined_function_error_includes_offending_name():
    src = textwrap.dedent("""
    entry main(input: Text) {
        return to_text(typo_in_helper_name(input))
    }
    """)
    with pytest.raises(NameError) as exc:
        run(src, input="x", adapter=MockAdapter())
    assert "typo_in_helper_name" in str(exc.value)
