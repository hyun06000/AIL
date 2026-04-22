"""Agent loop — read INTENT.md → author/load app.ail → run tests → serve.

The v0 agent is intentionally minimal:
  1. Parse INTENT.md (intent_md.parse_intent_md)
  2. If app.ail is empty or missing, call the existing `ask()` author
     pipeline with the INTENT.md-derived authoring goal. Save the
     produced AIL source to app.ail.
  3. Run the test cases extracted from ## Tests against app.ail.
     Each test is a (input, expect_ok) pair; the test passes if the
     observed success-or-error matches the expected shape.
  4. If all tests pass, hand off to server.serve().
  5. Append every step to .ail/ledger.jsonl for cross-session audit.

No file watching, no live reload, no autonomous diagnosis — those are
v1 work. v0 is just the smallest closure of the design.
"""
from __future__ import annotations

import sys
from typing import Any, Optional

from .. import run as ail_run
from ..authoring import ask, AuthoringError
from .intent_md import IntentSpec, TestCase
from .project import Project


def _author_app(project: Project, spec: IntentSpec, *, max_retries: int) -> str:
    """Use `ask()` to author AIL from the INTENT.md-derived goal.

    Discards the executed-value side of AskResult and keeps only
    `.ail_source`. Empty input is passed during the smoke-test so the
    program at least proves it parses + executes once.
    """
    goal = spec.authoring_goal()
    project.append_ledger({"event": "author_start", "goal_chars": len(goal)})
    try:
        result = ask(goal, max_retries=max_retries, input_text="")
    except AuthoringError as e:
        partial = e.partial.ail_source if e.partial else ""
        project.append_ledger({
            "event": "author_failed",
            "error": str(e),
            "partial_chars": len(partial),
        })
        raise
    project.append_ledger({
        "event": "author_done",
        "source_chars": len(result.ail_source),
        "retries": result.retries,
        "author_model": result.author_model,
    })
    return result.ail_source


def _looks_like_error(value: Any) -> bool:
    """Decide whether the program's return value represents an error.

    Three signals AIL can use to communicate error from an entry main:
      1. A Result-shaped dict with ok=False — the program returned
         a Result error directly.
      2. A string prefixed UNWRAP_ERROR: — `unwrap()` on an error
         Result was hit at runtime (the runtime returns this sentinel
         instead of raising).
      3. A Python exception escaping ail_run() — handled by the caller.
    """
    if isinstance(value, dict) and value.get("_result") and not value.get("ok"):
        return True
    if isinstance(value, str) and value.startswith("UNWRAP_ERROR"):
        return True
    return False


def _run_tests(project: Project, tests: list[TestCase]) -> tuple[int, int]:
    """Run every test case against the saved app.ail. Returns (passed, total).

    A test passes when the observed run shape (success / error) matches
    `expect_ok`. Content of the success-side value is not validated in
    v0 — content matching needs an LLM judge and is deferred.
    """
    passed = 0
    for t in tests:
        try:
            result, _ = ail_run(str(project.app_path), input=t.input)
            errored = _looks_like_error(result.value)
            ran_ok = not errored
            value_repr = repr(result.value)[:200]
            err = None
        except Exception as e:
            ran_ok = False
            value_repr = ""
            err = f"{type(e).__name__}: {e}"

        ok = (ran_ok == t.expect_ok)
        passed += int(ok)
        project.append_ledger({
            "event": "test_run",
            "input": t.input,
            "expect_ok": t.expect_ok,
            "ran_ok": ran_ok,
            "passed": ok,
            "value": value_repr,
            "error": err,
        })
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] input={t.input!r} expect_ok={t.expect_ok} "
              f"ran_ok={ran_ok}", file=sys.stderr)
    return passed, len(tests)


def bring_up(
    project: Project,
    *,
    max_retries: int = 3,
    require_tests_pass: bool = True,
    serve: bool = True,
    port_override: Optional[int] = None,
) -> int:
    """Execute the v0 state machine for `ail up`. Returns process exit code.

    `serve=False` returns after authoring + tests (useful in CI / tests
    of the agent itself).
    """
    spec = project.read_intent()
    print(f"[{project.root.name}] reading INTENT.md "
          f"({len(spec.behavior)} behavior bullets, {len(spec.tests)} tests)",
          file=sys.stderr)

    project.write_tests(spec)

    # Author or reuse app.ail.
    if not project.read_app_source().strip():
        print(f"[{project.root.name}] app.ail empty — authoring via "
              f"`ail ask`...", file=sys.stderr)
        try:
            source = _author_app(project, spec, max_retries=max_retries)
        except AuthoringError as e:
            print(f"author failed: {e}", file=sys.stderr)
            return 1
        project.write_app_source(source)
        print(f"[{project.root.name}] wrote {project.app_path}", file=sys.stderr)
    else:
        print(f"[{project.root.name}] using existing app.ail "
              f"({project.app_path.stat().st_size} bytes)", file=sys.stderr)

    # Run tests.
    if spec.tests:
        print(f"[{project.root.name}] running {len(spec.tests)} tests...",
              file=sys.stderr)
        passed, total = _run_tests(project, spec.tests)
        print(f"[{project.root.name}] tests: {passed}/{total} passed",
              file=sys.stderr)
        if require_tests_pass and passed < total:
            print(f"[{project.root.name}] aborting — tests failed. "
                  f"Edit INTENT.md or delete app.ail to re-author.",
                  file=sys.stderr)
            return 2
    else:
        print(f"[{project.root.name}] no tests declared", file=sys.stderr)

    if not serve:
        return 0

    # Defer importing server so non-serving callers don't pay http stdlib cost.
    from .server import serve_project
    port = port_override if port_override is not None else spec.port
    return serve_project(project, port=port)
