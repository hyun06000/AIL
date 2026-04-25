"""Regression: purity check rejects indirect impurity.

Arche v1.60.9 code review (msg_1777157460_10): asked whether purity.py
catches the case where `pure fn A` calls `fn B` and B is not marked
pure. If not, that is a hole — a pure fn that calls an impure fn is
not pure.

Verification: it does. `_check_call_target` (purity.py:247) raises
PurityError when the call target is in `all_fns` but not in
`pure_fns`. These tests guard that path so future refactors can't
silently widen the contract.
"""
from __future__ import annotations

import textwrap

import pytest

from ail.parser import parse
from ail.parser.purity import PurityError, check_program


def _check(src: str) -> None:
    check_program(parse(textwrap.dedent(src)))


def test_pure_fn_calling_impure_fn_is_rejected():
    """The hole Arche asked about — must NOT be allowed."""
    src = """
    fn impure_helper() -> Text {
        r = perform clock.now("iso")
        return r
    }

    pure fn outer() -> Text {
        return impure_helper()
    }

    entry main(input: Text) { return outer() }
    """
    with pytest.raises(PurityError) as exc:
        _check(src)
    msg = str(exc.value).lower()
    assert "impure_helper" in msg or "non-pure" in msg


def test_pure_fn_calling_intent_is_rejected():
    src = """
    intent answer(q: Text) -> Text { goal: "x" }

    pure fn wrapper(q: Text) -> Text {
        return answer(q)
    }

    entry main(input: Text) { return wrapper("hi") }
    """
    with pytest.raises(PurityError) as exc:
        _check(src)
    assert "intent" in str(exc.value).lower()


def test_pure_fn_calling_pure_fn_is_ok():
    src = """
    pure fn inner(x: Number) -> Number {
        return x + 1
    }

    pure fn outer(x: Number) -> Number {
        return inner(x) * 2
    }

    entry main(input: Text) { return to_text(outer(3)) }
    """
    _check(src)  # should not raise


def test_pure_fn_calling_unknown_function_is_rejected():
    """Conservative default: if we cannot prove it pure, fail.
    Catches typos AND prevents accidental impurity via shadowed names."""
    src = """
    pure fn outer() -> Number {
        return some_function_we_never_declared(42)
    }

    entry main(input: Text) { return to_text(outer()) }
    """
    with pytest.raises(PurityError) as exc:
        _check(src)
    assert "cannot be verified pure" in str(exc.value).lower() or \
           "some_function_we_never_declared" in str(exc.value)


def test_pure_fn_indirect_chain_through_two_levels():
    """`pure A -> pure B -> impure C` must still be rejected — the
    impurity propagates as soon as the chain hits a non-pure target."""
    src = """
    fn impure_leaf() -> Text {
        r = perform clock.now("iso")
        return r
    }

    pure fn middle() -> Text {
        return impure_leaf()
    }

    pure fn top() -> Text {
        return middle()
    }

    entry main(input: Text) { return top() }
    """
    # `top` calling `middle` is fine (both pure).
    # `middle` calling `impure_leaf` must fail — that's where the
    # contract is checked, since `middle` is the one declaring purity
    # while invoking a non-pure target.
    with pytest.raises(PurityError) as exc:
        _check(src)
    assert "impure_leaf" in str(exc.value)
