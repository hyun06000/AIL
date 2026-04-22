"""INTENT.md parser tests — covers section detection (English + Korean),
test bullet shape recognition, port extraction, and the rendered
template's round-trip parseability.
"""
from ail.agentic.intent_md import (
    DEFAULT_PORT,
    parse_intent_md,
    render_intent_template,
)


SAMPLE_KO = """# Summarizer

받은 텍스트를 한 문장으로 요약하는 서비스.

## 동작
- 영어/한국어 둘 다 지원
- 빈 입력 → 에러
- 10자 미만 → 에러

## 테스트
- "Long article about cats..." → 한 문장 요약
- "" → 에러
- "hi" → 에러

## 배포
- 포트 9090
"""

SAMPLE_EN = """# greeter

Greets the user by name.

## Behavior
- Detect language and respond in same language
- Empty input -> error

## Tests
- "Alice" → friendly greeting
- "" → error
- "Bob" → succeed

## Deployment
- port 8123
"""


def test_korean_sections_recognized():
    spec = parse_intent_md(SAMPLE_KO)
    assert spec.name == "Summarizer"
    assert "받은 텍스트를" in spec.preamble
    assert len(spec.behavior) == 3
    assert len(spec.tests) == 3
    assert spec.tests[0].input == "Long article about cats..."
    assert spec.tests[0].expect_ok is True
    assert spec.tests[1].input == ""
    assert spec.tests[1].expect_ok is False
    assert spec.port == 9090


def test_english_sections_recognized():
    spec = parse_intent_md(SAMPLE_EN)
    assert spec.name == "greeter"
    assert spec.behavior[0].startswith("Detect language")
    assert spec.tests[0].input == "Alice"
    assert spec.tests[0].expect_ok is True
    assert spec.tests[1].expect_ok is False  # "error"
    assert spec.tests[2].expect_ok is True   # "succeed"
    assert spec.port == 8123


def test_default_port_when_deployment_missing():
    text = "# x\n\nDoes a thing.\n"
    spec = parse_intent_md(text)
    assert spec.port == DEFAULT_PORT


def test_authoring_goal_includes_behavior_and_tests():
    spec = parse_intent_md(SAMPLE_KO)
    goal = spec.authoring_goal()
    assert "받은 텍스트를" in goal
    assert "Behavior requirements:" in goal
    assert "영어/한국어 둘 다 지원" in goal
    # Tests appear with the must succeed/error shape
    assert "must succeed" in goal
    assert "must error" in goal


def test_template_round_trips():
    text = render_intent_template("demo")
    spec = parse_intent_md(text)
    assert spec.name == "demo"
    assert spec.port == DEFAULT_PORT
    # Template includes a sample empty-input error case
    assert any(t.input == "" and not t.expect_ok for t in spec.tests)


def test_unknown_headers_dont_crash():
    text = """# x

Does a thing.

## Random Header
- not a real section
- still parses

## Tests
- "ok" → success
"""
    spec = parse_intent_md(text)
    assert len(spec.tests) == 1
    assert spec.tests[0].input == "ok"


def test_no_title_falls_back_to_default_name():
    text = "Just a description.\n\n## Tests\n- \"hi\" → ok\n"
    spec = parse_intent_md(text, default_name="myapp")
    assert spec.name == "myapp"
