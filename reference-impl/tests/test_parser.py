"""Tests for the AIL parser."""
from __future__ import annotations

import pytest

from ail_mvp import compile_source
from ail_mvp.parser.ast import (
    ContextDecl, IntentDecl, EntryDecl, EffectDecl,
    Literal, Identifier, BinaryOp,
)


def test_parse_empty_program():
    prog = compile_source("")
    assert prog.declarations == []


def test_parse_minimal_intent():
    src = """
    intent greet(name: Text) -> Text {
        goal: Text warm greeting
    }
    """
    prog = compile_source(src)
    intent = prog.intent_by_name("greet")
    assert intent is not None
    assert intent.params == [("name", "Text")]
    assert intent.return_type == "Text"


def test_parse_context_with_extends_and_override():
    src = """
    context base {
        register: "neutral"
        cost: 10
    }

    context strict extends base {
        override register: "formal"
        extra_field: "added"
    }
    """
    prog = compile_source(src)
    strict = prog.context_by_name("strict")
    assert strict is not None
    assert strict.extends == "base"
    assert "register" in strict.overrides
    assert "extra_field" not in strict.overrides


def test_parse_entry_with_with_context():
    src = """
    context job {
        register: "formal"
    }

    intent go(x: Text) -> Text {
        goal: Text
    }

    entry main(x: Text) {
        with context job:
            y = go(x)
        return y
    }
    """
    prog = compile_source(src)
    entry = prog.entry()
    assert entry is not None
    assert entry.name == "main"
    assert len(entry.body) == 2  # with-block + return


def test_parse_branch_with_otherwise():
    src = """
    intent classify(x: Text) -> Text {
        goal: label
    }

    entry main(x: Text) {
        c = classify(x)
        branch c {
            [c == "a"]       => r = 1
            [otherwise]      => r = 0
        }
        return r
    }
    """
    prog = compile_source(src)
    entry = prog.entry()
    assert entry is not None
    # branch statement should be 2nd stmt
    from ail_mvp.parser.ast import BranchStmt
    branch = entry.body[1]
    assert isinstance(branch, BranchStmt)
    assert len(branch.arms) == 2


def test_parse_perform_in_assignment():
    """Regression: `x = perform effect(...)` must parse as Assignment(PerformExpr)."""
    src = """
    intent i(x: Text) -> Text {
        goal: Text
        on_low_confidence(threshold: 0.5) {
            a = perform human_ask("are you sure?")
            return a
        }
    }

    entry main(x: Text) {
        return i(x)
    }
    """
    prog = compile_source(src)
    intent = prog.intent_by_name("i")
    assert intent is not None
    assert intent.low_confidence_handler is not None


def test_parse_evolve_block_full():
    """A valid evolve block is parsed into a fully structured declaration."""
    src = """
    intent i(x: Text) -> Text { goal: Text }

    evolve i {
        metric: user_score(sampled: 0.1)
        when metric < 0.7 {
            retune confidence_threshold: within [0.5, 0.9]
        }
        rollback_on: metric_drop > 0.15
        history: keep_last 10
    }

    entry main(x: Text) { return i(x) }
    """
    from ail_mvp.parser.ast import EvolveDecl
    prog = compile_source(src)
    evolves = [d for d in prog.declarations if isinstance(d, EvolveDecl)]
    assert len(evolves) == 1
    ev = evolves[0]
    assert ev.intent_name == "i"
    assert ev.history_keep == 10
    assert ev.metric_sample_rate == 0.1
    assert ev.action.kind == "retune"
    assert ev.action.target == "confidence_threshold"
    assert ev.action.range_lo == 0.5
    assert ev.action.range_hi == 0.9


def test_parse_evolve_missing_required_fields_rejected():
    """An evolve block without rollback_on MUST be rejected (spec/04 §2)."""
    from ail_mvp.parser.parser import ParseError
    src = """
    intent i(x: Text) -> Text { goal: Text }
    evolve i {
        metric: m
        when metric < 0.7 {
            retune t: within [0.1, 0.9]
        }
        history: keep_last 5
    }
    entry main(x: Text) { return i(x) }
    """
    with pytest.raises(ParseError, match="rollback_on"):
        compile_source(src)


def test_parse_evolve_with_bounded_by_and_review():
    """bounded_by and require review_by are parsed when present."""
    src = """
    intent i(x: Text) -> Text { goal: Text }
    evolve i {
        metric: m
        when m < 0.7 {
            retune threshold: within [0.1, 0.9]
            bounded_by {
                threshold: [0.2, 0.95]
                latency: <= 2000
            }
        }
        rollback_on: m < 0.5
        history: keep_last 3
        require review_by: human
    }
    entry main(x: Text) { return i(x) }
    """
    from ail_mvp.parser.ast import EvolveDecl
    prog = compile_source(src)
    ev = [d for d in prog.declarations if isinstance(d, EvolveDecl)][0]
    assert ev.review_by == "human"
    assert "threshold" in ev.bounded_by
    assert ev.bounded_by["threshold"] == (0.2, 0.95)
    assert ev.bounded_by["latency"][1] == 2000.0


def test_comments_are_ignored():
    src = """
    // line comment
    /* block
       comment */
    intent i(x: Text) -> Text { goal: Text }
    entry main(x: Text) { return i(x) }
    """
    prog = compile_source(src)
    assert prog.intent_by_name("i") is not None
    assert prog.entry() is not None
