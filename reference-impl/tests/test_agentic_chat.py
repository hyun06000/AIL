"""ail chat tests — drive the chat_apply() function with a stub adapter
that returns a known JSON payload, so we don't hit a real model."""
import json
from dataclasses import dataclass
from typing import Any

from ail.agentic.chat import chat_apply, _coerce_to_chat_payload
from ail.agentic.project import Project


@dataclass
class _StubResponse:
    value: Any
    raw: dict = None


class _StubAdapter:
    """Returns a pre-canned response on every invoke()."""
    name = "stub"

    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def invoke(self, *, goal, constraints, context, inputs, expected_type, examples):
        self.calls.append({"goal": goal, "inputs": inputs})
        return _StubResponse(value=self._payload, raw={})


SIMPLE_INTENT = """# demo

A simple echo service.

## Tests
- "hello" → succeed
- "" → 에러

## Deployment
- 포트 8080
"""

SIMPLE_APP = """\
entry main(input: Text) {
    if length(input) == 0 { return error("empty") }
    return ok(input)
}
"""


def _project(tmp_path):
    proj = Project.init(tmp_path / "demo")
    proj.intent_path.write_text(SIMPLE_INTENT, encoding="utf-8")
    proj.write_app_source(SIMPLE_APP)
    return proj


def test_chat_changes_app_ail_only(tmp_path):
    new_app = """\
entry main(input: Text) {
    if length(input) == 0 { return error("빈 입력") }
    return ok(input)
}
"""
    adapter = _StubAdapter({
        "intent_md": None,
        "app_ail": new_app,
        "summary": "Translated error to Korean",
    })
    proj = _project(tmp_path)
    result = chat_apply(proj, "make error Korean", adapter=adapter)
    assert result["changed"] == ["app.ail"]
    assert "Translated" in result["summary"]
    assert "빈 입력" in proj.read_app_source()
    # Tests still pass
    assert result["tests"]["passed"] == result["tests"]["total"] == 2


def test_chat_changes_intent_md_only(tmp_path):
    new_intent = SIMPLE_INTENT.replace("포트 8080", "포트 9999")
    assert "9999" in new_intent  # sanity: substitution actually happened
    adapter = _StubAdapter({
        "intent_md": new_intent,
        "app_ail": None,
        "summary": "Changed port to 9999",
    })
    proj = _project(tmp_path)
    result = chat_apply(proj, "use port 9999", adapter=adapter)
    assert result["changed"] == ["INTENT.md"]
    spec = proj.read_intent()
    assert spec.port == 9999


def test_chat_changes_both_files(tmp_path):
    new_intent = SIMPLE_INTENT.replace(
        '## Tests\n- "hello" → succeed\n- "" → 에러',
        '## Tests\n- "hello" → succeed\n- "world" → succeed\n- "" → 에러',
    )
    new_app = SIMPLE_APP  # unchanged behavior, still passes both
    adapter = _StubAdapter({
        "intent_md": new_intent,
        "app_ail": new_app,
        "summary": "Added a test",
    })
    proj = _project(tmp_path)
    result = chat_apply(proj, "add another test", adapter=adapter)
    assert set(result["changed"]) == {"INTENT.md", "app.ail"}
    spec = proj.read_intent()
    assert len(spec.tests) == 3


def test_chat_no_change_when_both_null(tmp_path):
    adapter = _StubAdapter({
        "intent_md": None,
        "app_ail": None,
        "summary": "Looks fine to me",
    })
    proj = _project(tmp_path)
    result = chat_apply(proj, "is this OK?", adapter=adapter)
    assert result["changed"] == []
    # No re-run when nothing changed
    assert "tests" not in result


def test_chat_logs_to_ledger(tmp_path):
    adapter = _StubAdapter({
        "intent_md": None,
        "app_ail": SIMPLE_APP + "\n// edit\n",
        "summary": "Added a comment",
    })
    proj = _project(tmp_path)
    chat_apply(proj, "add a comment", adapter=adapter)
    records = [
        json.loads(line)
        for line in proj.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(r.get("event") == "chat_request" for r in records)
    assert any(r.get("event") == "chat_applied" for r in records)
    assert any(r.get("event") == "chat_revalidated" for r in records)


def test_chat_payload_coercion_handles_string_response():
    """Some adapters wrap JSON in a string — chat_apply must tolerate."""
    raw = json.dumps({"intent_md": None, "app_ail": "x", "summary": "ok"})
    payload = _coerce_to_chat_payload(raw)
    assert payload["intent_md"] is None
    assert payload["app_ail"] == "x"
    assert payload["summary"] == "ok"


def test_chat_payload_coercion_handles_code_fence():
    raw = "```json\n{\"intent_md\": null, \"app_ail\": \"x\", \"summary\": \"ok\"}\n```"
    payload = _coerce_to_chat_payload(raw)
    assert payload["app_ail"] == "x"
