"""AIL MVP — a working subset of AIL.

Public API:
    from ail_mvp import run, compile_source, MockAdapter, AnthropicAdapter

    # Run an AIL file:
    result, trace = run("path/to/program.ail", input="hello")

    # Or with an explicit adapter (for tests):
    adapter = MockAdapter(responses={"greet": "안녕"})
    result, trace = run("path/to/program.ail", input="hello", adapter=adapter)
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from .parser import parse
from .runtime import Executor, ConfidentValue, MockAdapter
from .runtime.model import ModelAdapter

__version__ = "0.1.0"


def compile_source(source: str):
    """Parse source to a Program AST."""
    return parse(source)


def _default_adapter() -> ModelAdapter:
    """Try Anthropic if env var is present, else Mock."""
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from .runtime.anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter()
        except ImportError:
            pass
    return MockAdapter()


def run(
    source_or_path: str,
    *,
    input: Any = None,
    inputs: Optional[dict[str, Any]] = None,
    adapter: Optional[ModelAdapter] = None,
    ask_human=None,
) -> tuple[ConfidentValue, "Trace"]:
    """Run an AIL program. Returns (result, trace).

    `source_or_path` can be a path to a .ail file or a source string.
    `input` is a convenience alias for the first entry parameter.
    `inputs` is a dict of all entry parameters.
    """
    text: str
    # Only treat as a path if it looks like one (short, no newlines) to avoid
    # OSError on long source strings.
    looks_like_path = (
        len(source_or_path) < 4096
        and "\n" not in source_or_path
        and "{" not in source_or_path
    )
    if looks_like_path:
        try:
            p = Path(source_or_path)
            if p.exists() and p.is_file():
                text = p.read_text(encoding="utf-8")
            else:
                text = source_or_path
        except (OSError, ValueError):
            text = source_or_path
    else:
        text = source_or_path

    program = parse(text)
    entry = program.entry()
    if entry is None:
        raise ValueError("program has no entry declaration")

    resolved_inputs: dict[str, Any] = dict(inputs or {})
    if input is not None and entry.params:
        first_param_name = entry.params[0][0]
        resolved_inputs.setdefault(first_param_name, input)

    adapter = adapter or _default_adapter()
    executor = Executor(program, adapter, ask_human=ask_human)
    result = executor.run_entry(resolved_inputs)
    return result, executor.trace


__all__ = ["run", "compile_source", "MockAdapter", "__version__"]
