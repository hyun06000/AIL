"""Provenance: every value knows where it came from.

An Origin is a first-class runtime property attached to every ConfidentValue.
It records the operation that produced the value and links to the origins of
the inputs that fed into that operation. The result is a tree: walking it
yields the full lineage of how a value was computed.

Why this is AI-native:

- A human reading code can trace provenance by reading. An AI reading a value
  at runtime cannot — unless the value itself carries its history. Provenance
  makes "where did this number come from?" a query, not an inference.
- Combined with confidence, this gives every value a past (origin) and a
  present (confidence). Together they answer: should I trust this?
- It makes `evolve` auditable. An evolved intent's outputs carry an origin
  noting the version that produced them; rollbacks can be reasoned about.
- It is the foundation for purity contracts (Phase 2) — we can prove at
  runtime that a value never passed through a non-pure operation.

Design decisions:

- Origins are immutable (frozen dataclass) and hashable. Sharing across values
  is safe; deduplication is possible later.
- Origin nodes are only created at *observable* boundaries: literals,
  entry inputs, fn calls, intent calls, builtin calls. Binary and unary
  operations on tracked values do not create new origin nodes — they
  inherit from their dominant parent. This keeps the tree bounded.
- A literal's origin is the sentinel `LITERAL_ORIGIN`, shared by all
  literals, so we don't allocate per-literal.
- Timestamps use ISO-8601 UTC (`at` field). Optional; populated only for
  intent calls where time-of-inference matters for audit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# Origin kinds — kept as string constants to ensure stable AIL-visible values.
LITERAL = "literal"
INPUT = "input"
FN = "fn"
INTENT = "intent"
BUILTIN = "builtin"
ATTEMPT = "attempt"


@dataclass(frozen=True)
class Origin:
    """The provenance record for a single computed value.

    `kind` identifies the category of operation that produced the value.
    `name` is the human-readable identifier (fn/intent/builtin/param name).
    `parents` is a tuple of the origins of inputs that fed into this value.
    `model_id` is populated when kind == "intent" so the specific model is
    auditable.
    `at` is an ISO-8601 timestamp, populated for intent calls.
    """
    kind: str
    name: Optional[str] = None
    parents: tuple = ()
    model_id: Optional[str] = None
    at: Optional[str] = None

    def has_kind(self, kind: str) -> bool:
        """True if this origin or any ancestor has the given kind."""
        if self.kind == kind:
            return True
        return any(p.has_kind(kind) for p in self.parents)

    def lineage(self) -> list["Origin"]:
        """Depth-first post-order walk of this origin tree."""
        result: list[Origin] = []
        for p in self.parents:
            result.extend(p.lineage())
        result.append(self)
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict — what AIL code sees through origin_of()."""
        d: dict[str, Any] = {"kind": self.kind}
        if self.name is not None:
            d["name"] = self.name
        if self.model_id is not None:
            d["model_id"] = self.model_id
        if self.at is not None:
            d["at"] = self.at
        if self.parents:
            d["parents"] = [p.to_dict() for p in self.parents]
        return d


# Sentinel shared by all literal-origin values (saves allocations).
LITERAL_ORIGIN = Origin(kind=LITERAL)


def input_origin(param_name: str) -> Origin:
    """Origin for an entry-point parameter binding."""
    return Origin(kind=INPUT, name=param_name)


def fn_origin(name: str, parents: tuple) -> Origin:
    return Origin(kind=FN, name=name, parents=parents)


def intent_origin(name: str, parents: tuple,
                  model_id: Optional[str] = None) -> Origin:
    return Origin(
        kind=INTENT,
        name=name,
        parents=parents,
        model_id=model_id,
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def builtin_origin(name: str, parents: tuple) -> Origin:
    return Origin(kind=BUILTIN, name=name, parents=parents)


def attempt_origin(selected_index: int, selected_parent: "Origin") -> Origin:
    """Origin for the result of an attempt block.

    `name` is the 0-based index of the try that won. The single parent is
    the origin of that try's result, preserving the upstream lineage.
    """
    return Origin(kind=ATTEMPT, name=str(selected_index),
                  parents=(selected_parent,))


def parents_of(values) -> tuple:
    """Extract origin parents from an iterable of ConfidentValues.

    Accepts anything with a `.origin` attribute. Missing origins default to
    LITERAL_ORIGIN. We filter out LITERAL_ORIGIN parents to keep trees small
    — a literal parent carries no useful information beyond "a constant".
    """
    out = []
    for v in values:
        o = getattr(v, "origin", None)
        if o is None or o is LITERAL_ORIGIN:
            continue
        out.append(o)
    return tuple(out)
