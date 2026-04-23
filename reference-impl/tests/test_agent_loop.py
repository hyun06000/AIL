"""Tests for the ReAct-style agent reasoning loop pattern.

Canonical bounded agent loop in AIL 1.8 (no new syntax):

    intent decide(state: Text) -> Text {
        goal: "Return 'DONE: result' or 'CONTINUE: next_state'"
    }

    entry main(input: Text) {
        state = "start"
        for step in range(MAX_STEPS) {
            decision = decide(state)
            if starts_with(decision, "DONE") { return decision }
            state = decision
        }
        return "max steps reached"
    }

Key constraints:
- intent declared at top level (not inside for body)
- range(N) single-arg produces [0..N-1]
- starts_with for signal detection
- early return exits the loop
- state accumulates across iterations
"""
from __future__ import annotations
import pytest
from ail import run
from ail.runtime.model import MockAdapter, ModelResponse


class ScriptedAdapter(MockAdapter):
    """Returns scripted responses in sequence, then repeats the last one."""
    def __init__(self, responses: list[str]):
        super().__init__()
        self._responses = responses
        self._idx = 0

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None) -> ModelResponse:
        val = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return ModelResponse(value=val, confidence=0.9,
                             model_id="scripted", raw={})


def _run(src, adapter=None, input_val=""):
    r, _ = run(src, input=input_val, adapter=adapter or MockAdapter())
    return r.value


# ---------------------------------------------------------------------------
# range(N) single-argument form
# ---------------------------------------------------------------------------

def test_range_single_arg_length():
    assert _run("entry main(input: Text) { return length(range(5)) }") == 5


def test_range_single_arg_starts_at_zero():
    src = "entry main(input: Text) { r = range(3)\n return get(r, 0) }"
    val = _run(src)
    assert val == 0


def test_range_two_arg_unchanged():
    assert _run("entry main(input: Text) { return length(range(2, 7)) }") == 5


# ---------------------------------------------------------------------------
# Loop terminates early on DONE signal
# ---------------------------------------------------------------------------

LOOP_SRC = """
intent decide(state: Text) -> Text {
    goal: "Return DONE: result or CONTINUE: next_state"
}

entry main(input: Text) {
    state = "start"
    for step in range(10) {
        decision = decide(state)
        if starts_with(decision, "DONE") {
            return decision
        }
        state = decision
    }
    return "max steps reached"
}
"""


def test_loop_exits_on_done():
    adapter = ScriptedAdapter(["CONTINUE: step2", "CONTINUE: step3", "DONE: found it"])
    result = _run(LOOP_SRC, adapter)
    assert str(result).startswith("DONE:")


def test_loop_reaches_max():
    adapter = ScriptedAdapter(["CONTINUE: still going"])
    result = _run(LOOP_SRC, adapter)
    assert "max steps reached" in str(result)


def test_loop_done_on_first_step():
    adapter = ScriptedAdapter(["DONE: immediate"])
    result = _run(LOOP_SRC, adapter)
    assert str(result).startswith("DONE:")


# ---------------------------------------------------------------------------
# State accumulates across iterations
# ---------------------------------------------------------------------------

LOG_SRC = """
intent decide(state: Text) -> Text {
    goal: "Return DONE: result or CONTINUE: next_state"
}

entry main(input: Text) {
    state = "start"
    log = "=== agent run ===\\n"
    for step in range(5) {
        decision = decide(state)
        log = log + "step " + to_text(step) + ": " + decision + "\\n"
        if starts_with(decision, "DONE") {
            return log
        }
        state = decision
    }
    return log
}
"""


def test_log_accumulates():
    adapter = ScriptedAdapter(["CONTINUE: s1", "DONE: done"])
    result = _run(LOG_SRC, adapter)
    r = str(result)
    assert "step 0" in r
    assert "step 1" in r
    assert "step 2" not in r  # exited at step 1


def test_log_includes_state_transitions():
    adapter = ScriptedAdapter(["CONTINUE: phase2", "CONTINUE: phase3", "DONE: complete"])
    result = _run(LOG_SRC, adapter)
    r = str(result)
    assert "phase2" in r or "CONTINUE" in r
