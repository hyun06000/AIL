"""Tests for the math builtins added in 2026-04-20 benchmark follow-up.

These builtins (`round`, `floor`, `ceil`, `sqrt`, `pow`) closed two
PurityError failures observed in the ail-coder:7b v2 benchmark (C07 BMI,
C12 standard deviation). They are declared pure in
`ail/parser/purity.py` and implemented identically in the Python and Go
runtimes.
"""
from __future__ import annotations

import math

import pytest

from ail import run
from ail.runtime import MockAdapter


def _run(src: str, input_value="") -> object:
    result, _ = run(src, input=input_value, adapter=MockAdapter())
    return result.value


def test_round_no_digits():
    src = """
    pure fn r(x: Number) -> Number { return round(x) }
    entry main(_: Text) { return r(2.6) }
    """
    assert _run(src) == 3


def test_round_with_digits():
    src = """
    pure fn r(x: Number, d: Number) -> Number { return round(x, d) }
    entry main(_: Text) { return r(3.14159, 2) }
    """
    assert _run(src) == pytest.approx(3.14)


def test_floor_and_ceil():
    src = """
    pure fn f(x: Number) -> Number { return floor(x) }
    pure fn c(x: Number) -> Number { return ceil(x) }
    entry main(_: Text) { return [f(2.9), c(2.1)] }
    """
    assert _run(src) == [2, 3]


def test_sqrt_positive():
    src = """
    pure fn s(x: Number) -> Number { return sqrt(x) }
    entry main(_: Text) { return s(16) }
    """
    assert _run(src) == pytest.approx(4.0)


def test_sqrt_negative_returns_result_error():
    src = """
    pure fn s(x: Number) -> Number { return sqrt(x) }
    entry main(_: Text) { return s(-1) }
    """
    v = _run(src)
    assert isinstance(v, dict) and v.get("_result") is True
    assert v.get("ok") is False


def test_pow():
    src = """
    pure fn p(b: Number, e: Number) -> Number { return pow(b, e) }
    entry main(_: Text) { return p(2, 10) }
    """
    assert _run(src) == 1024


def test_bmi_roundtrip_matches_benchmark_C07():
    # Reproduces the shape of the C07 benchmark prompt (BMI → health).
    # Before the fix this failed PurityError on `round`.
    src = """
    pure fn bmi(height_cm: Number, weight_kg: Number) -> Number {
        return round(weight_kg / pow(height_cm / 100, 2), 2)
    }
    entry main(_: Text) { return bmi(175, 70) }
    """
    assert _run(src) == pytest.approx(22.86, abs=0.01)


def test_sqrt_in_pure_fn_matches_benchmark_C12():
    # Reproduces the shape of the C12 benchmark prompt (std-dev). The
    # precise stdev implementation depends on `reduce` argument order,
    # which is orthogonal to this fix — here we just assert sqrt is
    # callable from a pure fn. Before the fix this raised PurityError.
    src = """
    pure fn euclidean(x: Number, y: Number) -> Number {
        return sqrt(x * x + y * y)
    }
    entry main(_: Text) { return euclidean(3, 4) }
    """
    assert _run(src) == pytest.approx(5.0)


def test_math_builtins_are_pure():
    # Using the new math builtins inside a `pure fn` must not raise
    # PurityError (they are in the trusted list now).
    src = """
    pure fn uses_all(x: Number) -> Number {
        return round(sqrt(pow(floor(ceil(x)), 2)), 3)
    }
    entry main(_: Text) { return uses_all(4.2) }
    """
    # floor(ceil(4.2)) = floor(5) = 5; pow(5,2)=25; sqrt(25)=5; round(5,3)=5
    assert _run(src) == 5
