"""AIL MVP — a working subset of AIL.

Public API:
    from ail import run, compile_source, MockAdapter, AnthropicAdapter

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

__version__ = "1.8.6"


def compile_source(source: str):
    """Parse source to a Program AST."""
    return parse(source)


def _default_adapter() -> ModelAdapter:
    """Pick an adapter based on the environment.

    Preference order:
      1. `AIL_OLLAMA_MODEL` set → OllamaAdapter (local, no API key)
      2. `ANTHROPIC_API_KEY` set → AnthropicAdapter
      3. MockAdapter (offline)

    Before checking the environment, load a .env file from the current
    working directory or from the parent directories up to a reasonable
    depth. Missing the file is not an error.
    """
    _load_dotenv_if_present()
    import os
    if os.environ.get("AIL_OLLAMA_MODEL"):
        from .runtime.ollama_adapter import OllamaAdapter
        return OllamaAdapter()
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from .runtime.anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter()
        except ImportError:
            pass
    return MockAdapter()


def _load_dotenv_if_present() -> None:
    """Populate os.environ from a .env file if one exists.

    Searches: the current working directory, then its parents up to 4 levels.
    Only processes simple KEY=VALUE lines; existing env vars are not
    overwritten. Missing files are silently ignored.
    """
    import os
    searched = [Path.cwd()] + list(Path.cwd().parents)[:4]
    for base in searched:
        candidate = base / ".env"
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                return
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
            return


def run(
    source_or_path: str,
    *,
    input: Any = None,
    inputs: Optional[dict[str, Any]] = None,
    adapter: Optional[ModelAdapter] = None,
    ask_human=None,
    metric_fn=None,
    approve_review=None,
    calibrator=None,
) -> tuple[ConfidentValue, "Trace"]:
    """Run an AIL program. Returns (result, trace).

    `source_or_path` can be a path to a .ail file or a source string.
    `input` is a convenience alias for the first entry parameter.
    `inputs` is a dict of all entry parameters.
    `metric_fn(intent_name, value, confidence) -> (metric, rollback)`
       supplies feedback for evolving intents AND updates the
       confidence calibrator. The metric signal (in [0, 1]) is
       interpreted as ground truth for calibration bucketing.
    `approve_review(info) -> bool` handles `require review_by: human`
       gates. Returns True to approve, False to hold.
    `calibrator` — optional Calibrator instance to share across
       multiple run() invocations (useful for programs that run a
       pipeline many times and want calibration to accumulate).
       When None, the executor builds a default one that honors
       AIL_CALIBRATION_PATH for persistence.
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
    executor = Executor(
        program, adapter, ask_human=ask_human,
        metric_fn=metric_fn, approve_review=approve_review,
        calibrator=calibrator,
    )
    result = executor.run_entry(resolved_inputs)
    return result, executor.trace


from .authoring import ask, AskResult, AuthoringError

__all__ = [
    "run", "compile_source", "MockAdapter",
    "ask", "AskResult", "AuthoringError",
    "__version__",
]
