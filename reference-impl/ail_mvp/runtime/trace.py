"""Trace ledger for the MVP.

Real AIRT writes to an append-only store. The MVP keeps traces in memory
and can dump them as structured JSON. Every intent invocation, context
resolution, constraint check, and model call appears as an entry.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class TraceEntry:
    timestamp: float
    kind: str                    # intent_call | model_call | constraint_check | perform | branch | context_push | ...
    payload: dict[str, Any]
    depth: int = 0


class Trace:
    def __init__(self):
        self.entries: list[TraceEntry] = []
        self._depth = 0

    def enter(self) -> None:
        self._depth += 1

    def exit(self) -> None:
        self._depth = max(0, self._depth - 1)

    def record(self, kind: str, **payload: Any) -> None:
        self.entries.append(TraceEntry(
            timestamp=time.time(),
            kind=kind,
            payload=payload,
            depth=self._depth,
        ))

    def to_list(self) -> list[dict[str, Any]]:
        return [
            {"ts": e.timestamp, "depth": e.depth, "kind": e.kind, **e.payload}
            for e in self.entries
        ]

    def to_json(self, indent: int = 2) -> str:
        # fall back to str for non-serializable values
        return json.dumps(self.to_list(), indent=indent, default=str, ensure_ascii=False)

    def pretty(self) -> str:
        lines: list[str] = []
        for e in self.entries:
            prefix = "  " * e.depth
            # Concise one-line per entry
            payload_str = ", ".join(f"{k}={_fmt(v)}" for k, v in e.payload.items())
            lines.append(f"{prefix}[{e.kind}] {payload_str}")
        return "\n".join(lines)


def _fmt(v: Any, maxlen: int = 80) -> str:
    s = str(v)
    if len(s) > maxlen:
        return s[: maxlen - 3] + "..."
    return s
