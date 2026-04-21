"""Tests for the parse_json builtin.

parse_json exists so AIL programs can extract structured data from
HTTP response bodies (and any other JSON text) without inventing
line-scanning helpers. Added 2026-04-22 after HEAAL E2 showed that
Sonnet's manual JSON parsing failed on compact API responses.
"""
from ail import run, MockAdapter


def _run_ok(source: str, input_text: str = ""):
    result, _ = run(source, input=input_text, adapter=MockAdapter())
    return result.value


def test_parse_json_accepts_object():
    src = '''
pure fn get_lang(body: Text) -> Text {
    r = parse_json(body)
    if is_error(r) { return "err" }
    return get(unwrap(r), "language")
}
entry main(x: Text) {
    return get_lang("{\\"language\\": \\"Python\\"}")
}
'''
    assert _run_ok(src) == "Python"


def test_parse_json_accepts_array():
    src = '''
pure fn head(body: Text) -> Text {
    r = parse_json(body)
    if is_error(r) { return "err" }
    return get(unwrap(r), 0)
}
entry main(x: Text) {
    return head("[\\"first\\", \\"second\\"]")
}
'''
    assert _run_ok(src) == "first"


def test_parse_json_returns_error_on_garbage():
    src = '''
pure fn describe(body: Text) -> Text {
    r = parse_json(body)
    if is_error(r) { return unwrap_error(r) }
    return "OK"
}
entry main(x: Text) {
    return describe("this is not json")
}
'''
    msg = _run_ok(src)
    assert msg != "OK"
    assert len(msg) > 0


def test_parse_json_is_pure():
    # Calling from inside a pure fn must not raise PurityError.
    src = '''
pure fn validate(body: Text) -> Boolean {
    return is_ok(parse_json(body))
}
entry main(x: Text) { return validate("{\\"a\\": 1}") }
'''
    assert _run_ok(src) is True


def test_parse_json_nested_object():
    src = '''
pure fn extract(body: Text) -> Text {
    r = parse_json(body)
    if is_error(r) { return "err" }
    root = unwrap(r)
    slideshow = get(root, "slideshow")
    return get(slideshow, "author")
}
entry main(x: Text) {
    return extract("{\\"slideshow\\": {\\"author\\": \\"Yours Truly\\"}}")
}
'''
    assert _run_ok(src) == "Yours Truly"
