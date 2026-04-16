"""Context system for the AIL runtime.

Implements the semantics described in spec/02-context.md to the extent the
MVP needs: field resolution with inheritance, override tracking, scope
stacking via `with context`.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

from ..parser.ast import ContextDecl, Expr


@dataclass
class ResolvedContext:
    """A context fully resolved against a program — fields flattened with
    provenance (which context declaration provided each field).
    """
    name: str
    chain: list[str]                         # ancestor chain, root first
    fields: dict[str, Any]                   # resolved values
    provenance: dict[str, str]               # field -> context name that supplied it
    overrides: set[str]                      # fields that were marked override

    def has(self, key: str) -> bool:
        return key in self.fields

    def get(self, key: str, default: Any = None) -> Any:
        return self.fields.get(key, default)


class ContextResolver:
    """Resolves context declarations against a program."""

    def __init__(self, evaluator):
        # evaluator is used to reduce expression AST nodes to Python values
        # without needing a full scope — context field exprs are constant
        self.evaluator = evaluator

    def resolve(self, decl: ContextDecl, all_decls: dict[str, ContextDecl]) -> ResolvedContext:
        chain: list[str] = []
        self._build_chain(decl, all_decls, chain)

        fields: dict[str, Any] = {}
        provenance: dict[str, str] = {}
        overrides: set[str] = set()

        for ancestor_name in chain:
            ancestor = all_decls[ancestor_name]
            for key, expr in ancestor.fields.items():
                # later ancestors overwrite earlier (root-to-leaf walk)
                value = self.evaluator.eval_const(expr)
                fields[key] = value
                provenance[key] = ancestor_name
                if key in ancestor.overrides:
                    overrides.add(key)

        return ResolvedContext(
            name=decl.name, chain=chain, fields=fields,
            provenance=provenance, overrides=overrides,
        )

    def _build_chain(
        self, decl: ContextDecl, all_decls: dict[str, ContextDecl], out: list[str]
    ) -> None:
        if decl.extends:
            if decl.extends not in all_decls:
                raise NameError(f"context '{decl.name}' extends unknown '{decl.extends}'")
            self._build_chain(all_decls[decl.extends], all_decls, out)
        out.append(decl.name)


class ContextStack:
    """The stack of active contexts during execution."""

    def __init__(self):
        self.frames: list[ResolvedContext] = []

    def push(self, ctx: ResolvedContext) -> None:
        self.frames.append(ctx)

    def pop(self) -> ResolvedContext:
        return self.frames.pop()

    def active(self) -> Optional[ResolvedContext]:
        return self.frames[-1] if self.frames else None

    def get(self, key: str, default: Any = None) -> Any:
        """Inner-to-outer resolution."""
        for frame in reversed(self.frames):
            if frame.has(key):
                return frame.get(key)
        return default

    def has(self, key: str) -> bool:
        return any(f.has(key) for f in self.frames)

    def description(self) -> dict[str, Any]:
        """For trace output."""
        if not self.frames:
            return {"active": None, "chain": []}
        active = self.active()
        return {
            "active": active.name,
            "chain": active.chain,
            "fields": active.fields,
            "overrides": sorted(active.overrides),
        }
