"""Import resolution for AIL programs.

Resolves an ImportDecl's `source` (e.g. "stdlib/language", "./helpers")
into a parsed Program whose declarations can be merged into the caller's
namespace.

Resolution rules:

  "stdlib/<name>"
      -> <ail package>/stdlib/<name>.ail

  "./path/to/foo" or "../foo"
      -> relative to the importing program's directory (not yet supported
         in MVP; raises ImportResolutionError)

  "org://..." or any URL scheme
      -> not supported; raises ImportResolutionError

The resolver caches parsed stdlib modules by name so importing the same
module from many places costs one parse.
"""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..parser.ast import Program


class ImportResolutionError(Exception):
    """Raised when an import cannot be resolved to a parseable program."""


# Directory containing bundled stdlib modules
_STDLIB_DIR = Path(__file__).parent

_stdlib_cache: dict[str, "Program"] = {}


def resolve(source: str, importing_from: Path | None = None) -> "Program":
    """Return the parsed Program referred to by `source`.

    `importing_from` is the directory of the .ail file that issued the
    import, used for relative paths. None means "no relative resolution
    possible" — the MVP only supports stdlib imports in that case.
    """
    from ..parser import parse

    if source.startswith("stdlib/"):
        name = source[len("stdlib/"):]
        if name in _stdlib_cache:
            return _stdlib_cache[name]
        path = _STDLIB_DIR / f"{name}.ail"
        if not path.is_file():
            raise ImportResolutionError(
                f"stdlib module '{name}' not found at {path}"
            )
        try:
            program = parse(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ImportResolutionError(
                f"failed to parse stdlib/{name}: {e}"
            ) from e
        _stdlib_cache[name] = program
        return program

    if source.startswith("./") or source.startswith("../"):
        # Project-local import. `importing_from` is the directory of
        # the .ail file that issued this import (passed down from the
        # executor's constructor). Each program the authoring agent
        # writes becomes a reusable tool as long as other programs in
        # the project can import from it.
        # PRINCIPLES.md §6 (2026-04-24, user): "코딩을 할수록
        # 에이전트가 사용할 수 있는 도구의 양이 늘어나야 함."
        if importing_from is None:
            raise ImportResolutionError(
                "relative import '" + source + "' has no base directory "
                "(executor received no project_root). Pass project_root "
                "to run() or Executor so './x' can resolve."
            )
        rel = source[2:] if source.startswith("./") else source
        target = (importing_from / rel).resolve()
        if target.suffix != ".ail":
            target = target.with_suffix(".ail")
        # Confine relative imports to the project tree so `../../../etc`
        # can't escape into the host filesystem.
        base = importing_from.resolve()
        try:
            target.relative_to(base)
        except ValueError:
            raise ImportResolutionError(
                f"relative import '{source}' escapes the project root "
                f"({base}); only intra-project paths are allowed."
            )
        if not target.is_file():
            raise ImportResolutionError(
                f"relative import '{source}' resolves to {target}, "
                "but that file does not exist."
            )
        try:
            program = parse(target.read_text(encoding="utf-8"))
        except Exception as e:
            raise ImportResolutionError(
                f"failed to parse {target}: {e}"
            ) from e
        return program

    if "://" in source:
        raise ImportResolutionError(
            f"URL-style imports like '{source}' are not supported in MVP."
        )

    raise ImportResolutionError(
        f"could not resolve import source '{source}'. "
        "Expected 'stdlib/<name>', a relative path, or a URL."
    )


def available_stdlib_modules() -> list[str]:
    """Return the names of all bundled stdlib .ail modules."""
    return sorted(p.stem for p in _STDLIB_DIR.glob("*.ail"))


def _clear_cache() -> None:
    """For tests only."""
    _stdlib_cache.clear()
