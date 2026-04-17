"""Tests for fn declarations, if/else, for loops, and built-in functions."""
from __future__ import annotations

import pytest

from ail import run, compile_source
from ail.runtime import MockAdapter


# ---------- fn basics ----------


def test_fn_simple_return():
    src = """
    fn double(x: Number) -> Number { return x * 2 }
    entry main(x: Text) { return double(5) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 10
    assert result.confidence == 1.0


def test_fn_recursive_factorial():
    src = """
    fn factorial(n: Number) -> Number {
        if n <= 1 { return 1 }
        return n * factorial(n - 1)
    }
    entry main(x: Text) { return factorial(6) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 720


def test_fn_multiple_params():
    src = """
    fn add3(a: Number, b: Number, c: Number) -> Number {
        return a + b + c
    }
    entry main(x: Text) { return add3(1, 2, 3) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 6


def test_fn_calling_another_fn():
    src = """
    fn square(n: Number) -> Number { return n * n }
    fn sum_of_squares(a: Number, b: Number) -> Number {
        return square(a) + square(b)
    }
    entry main(x: Text) { return sum_of_squares(3, 4) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 25


# ---------- if / else ----------


def test_if_then():
    src = """
    fn check(n: Number) -> Text {
        if n > 10 { return "big" }
        return "small"
    }
    entry main(x: Text) { return check(20) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "big"


def test_if_else():
    src = """
    fn check(n: Number) -> Text {
        if n > 10 { return "big" } else { return "small" }
    }
    entry main(x: Text) { return check(3) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "small"


def test_if_else_if_else():
    src = """
    fn grade(score: Number) -> Text {
        if score >= 90 { return "A" }
        else if score >= 80 { return "B" }
        else if score >= 70 { return "C" }
        else { return "F" }
    }
    entry main(x: Text) { return grade(85) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "B"


# ---------- for ----------


def test_for_sum():
    src = """
    fn sum_list(nums: Number) -> Number {
        total = 0
        for n in nums { total = total + n }
        return total
    }
    entry main(x: Text) { return sum_list(range(1, 6)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 15


def test_for_with_if():
    src = """
    fn count_positive(nums: Number) -> Number {
        count = 0
        for n in nums {
            if n > 0 { count = count + 1 }
        }
        return count
    }
    entry main(x: Text) { return count_positive([-1, 0, 1, 2, -3, 4]) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 3


def test_for_building_list():
    src = """
    fn squares(nums: Number) -> Number {
        result = []
        for n in nums {
            result = append(result, n * n)
        }
        return result
    }
    entry main(x: Text) { return squares(range(1, 5)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == [1, 4, 9, 16]


# ---------- builtins ----------


def test_builtin_split_join():
    src = """
    entry main(text: Text) {
        words = split(text, " ")
        upper_text = upper(join(words, "-"))
        return upper_text
    }
    """
    result, _ = run(src, input="hello world", adapter=MockAdapter())
    assert result.value == "HELLO-WORLD"


def test_builtin_length():
    src = """
    entry main(x: Text) {
        return length(split("a,b,c,d", ","))
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 4


def test_builtin_sort_reverse():
    src = """
    entry main(x: Text) {
        sorted_nums = sort([3, 1, 4, 1, 5])
        reversed_nums = reverse(sorted_nums)
        return reversed_nums
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == [5, 4, 3, 1, 1]


def test_builtin_range():
    src = """
    entry main(x: Text) { return range(0, 5) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == [0, 1, 2, 3, 4]


def test_builtin_to_number():
    src = """
    entry main(x: Text) {
        n = to_number("42")
        return n + 8
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 50.0


def test_builtin_replace():
    src = """
    entry main(x: Text) {
        return replace("hello world", "world", "AIL")
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "hello AIL"


def test_builtin_starts_ends_with():
    src = """
    entry main(x: Text) {
        a = starts_with("hello", "he")
        b = ends_with("hello", "xyz")
        return join([to_text(a), to_text(b)], ",")
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "True,False"


def test_modulo_operator():
    src = """
    entry main(x: Text) { return 17 % 5 }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 2


# ---------- hybrid: fn + intent ----------


def test_fn_and_intent_in_same_program():
    """fn handles the deterministic part, intent handles the LLM part."""
    from ail.runtime.model import ModelResponse

    class Scripted(MockAdapter):
        def invoke(self, **kw):
            return ModelResponse(value="positive", confidence=0.9,
                                 model_id="s", raw={})

    src = """
    intent classify(text: Text) -> Text { goal: sentiment_label }

    fn format_result(label: Text, count: Number) -> Text {
        return join([label, " (", to_text(count), " words)"], "")
    }

    entry main(text: Text) {
        label = classify(text)
        wc = length(split(text, " "))
        return format_result(label, wc)
    }
    """
    result, _ = run(src, input="I love this so much", adapter=Scripted())
    assert result.value == "positive (5 words)"


# ---------- eval_ail — meta-execution ----------


def test_eval_ail_runs_generated_program():
    src = """
    fn make_program() -> Text {
        return "fn double(n: Number) -> Number { return n * 2 } entry main(x: Text) { return double(to_number(x)) }"
    }
    entry main(input: Text) {
        code = make_program()
        return eval_ail(code, "21")
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 42.0
    assert result.confidence == 1.0


def test_eval_ail_returns_parse_error_on_bad_source():
    src = """
    entry main(input: Text) {
        return eval_ail("this is not valid ail {{{", "x")
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert "PARSE_ERROR" in str(result.value)
    assert result.confidence == 0.0


def test_eval_ail_handles_invalid_program_gracefully():
    """eval_ail with a program that has no entry returns PARSE_ERROR."""
    src = """
    entry main(input: Text) {
        return eval_ail("fn noop() -> Number { return 1 }", "x")
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert "PARSE_ERROR" in str(result.value)
    assert result.confidence == 0.0


def test_split_empty_delimiter_gives_characters():
    """split('hello', '') should give ['h','e','l','l','o']."""
    src = """
    entry main(x: Text) {
        return split("hello", "")
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == ['h', 'e', 'l', 'l', 'o']


# ---------- Result type ----------


def test_ok_and_unwrap():
    src = """
    entry main(x: Text) { return unwrap(ok(42)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 42


def test_error_and_unwrap_error():
    src = """
    entry main(x: Text) { return unwrap_error(error("oops")) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "oops"


def test_is_ok_true_for_ok():
    src = """
    entry main(x: Text) { return is_ok(ok(1)) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is True


def test_is_ok_false_for_error():
    src = """
    entry main(x: Text) { return is_ok(error("bad")) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is False


def test_is_error_true_for_error():
    src = """
    entry main(x: Text) { return is_error(error("bad")) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is True


def test_unwrap_or_uses_default_on_error():
    src = """
    entry main(x: Text) { return unwrap_or(error("nope"), 99) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 99


def test_unwrap_or_uses_value_on_ok():
    src = """
    entry main(x: Text) { return unwrap_or(ok(7), 99) }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 7


def test_to_number_returns_result_error_on_bad_input():
    src = """
    entry main(x: Text) {
        n = to_number("abc")
        return is_error(n)
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value is True


def test_to_number_returns_number_on_good_input():
    src = """
    entry main(x: Text) {
        n = to_number("42")
        return n + 1
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == 43.0


def test_result_in_fn_pipeline():
    """A fn returns error, caller handles it with is_ok/unwrap_error."""
    src = """
    fn safe_divide(a: Number, b: Number) -> Text {
        if b == 0 { return error("division by zero") }
        return ok(a / b)
    }
    entry main(x: Text) {
        r = safe_divide(10, 0)
        if is_error(r) {
            return join(["Failed: ", unwrap_error(r)], "")
        }
        return unwrap(r)
    }
    """
    result, _ = run(src, input="", adapter=MockAdapter())
    assert result.value == "Failed: division by zero"
