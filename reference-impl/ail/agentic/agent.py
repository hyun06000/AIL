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


def _diagnose_and_repair(project: Project, spec, *, max_attempts: int) -> int:
    """When the declared tests fail against the current app.ail, ask the
    chat backend to patch the program. Re-run tests; loop up to
    `max_attempts` repair cycles.

    Returns the number of tests that passed after the final repair
    attempt. The caller decides whether that's good enough.
    """
    from .chat import chat_apply  # local import — chat is optional path
    last_passed = 0
    last_total = len(spec.tests)
    for attempt in range(1, max_attempts + 1):
        # Build the repair request from the most recent failures recorded
        # in the ledger (the prior _run_tests call appended them).
        failures = _recent_test_failures(project, limit=last_total)
        if not failures:
            return last_passed
        request = _format_repair_request(failures)
        print(f"[{project.root.name}] auto-fix attempt {attempt}/"
              f"{max_attempts} — calling chat backend on {len(failures)} "
              f"failing test(s)...", file=sys.stderr)
        project.append_ledger({
            "event": "auto_fix_attempt",
            "attempt": attempt,
            "failing_count": len(failures),
        })
        try:
            result = chat_apply(project, request, rerun_tests=False)
        except Exception as e:
            print(f"[{project.root.name}] auto-fix call failed: "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
            project.append_ledger({
                "event": "auto_fix_call_failed",
                "attempt": attempt,
                "error": f"{type(e).__name__}: {e}",
            })
            return last_passed
        if not result["changed"]:
            print(f"[{project.root.name}] auto-fix: model declined to "
                  f"change anything; giving up.", file=sys.stderr)
            return last_passed
        # Re-run the tests against the patched program.
        last_passed, last_total = _run_tests(project, spec.tests)
        project.append_ledger({
            "event": "auto_fix_revalidated",
            "attempt": attempt, "passed": last_passed, "total": last_total,
        })
        if last_passed == last_total:
            print(f"[{project.root.name}] auto-fix succeeded after "
                  f"{attempt} attempt(s)", file=sys.stderr)
            return last_passed
    return last_passed


def _recent_test_failures(project: Project, *, limit: int) -> list[dict]:
    """Read the tail of the ledger and return the most recent contiguous
    block of test_run records, filtered to failures."""
    import json as _json
    if not project.ledger_path.exists():
        return []
    lines = project.ledger_path.read_text(encoding="utf-8").splitlines()
    # Walk backwards collecting test_run records until we hit a non-test_run
    # event (which marks the boundary of the most recent run).
    block: list[dict] = []
    for line in reversed(lines):
        try:
            rec = _json.loads(line)
        except Exception:
            continue
        if rec.get("event") == "test_run":
            block.append(rec)
            if len(block) >= limit:
                break
        elif block:
            # We've passed the start of the most recent test block.
            break
    block.reverse()
    return [r for r in block if not r.get("passed")]


def _format_repair_request(failures: list[dict]) -> str:
    """Compose the natural-language message handed to chat_apply."""
    lines = [
        "The current app.ail fails some of the test cases declared in "
        "INTENT.md's `## Tests` section. Update app.ail (and INTENT.md "
        "if necessary) so all declared tests pass. Do not change the "
        "test cases themselves — they are the contract from the user.",
        "",
        "Failing tests:",
    ]
    for f in failures:
        inp = repr(f.get("input", ""))
        expected = "succeed" if f.get("expect_ok") else "error"
        observed = ("ran without error" if f.get("ran_ok")
                    else (f.get("error") or "ran with error"))
        lines.append(f"  - input={inp}, expected to {expected}, observed: {observed}")
    return "\n".join(lines)


def bring_up(
    project: Project,
    *,
    max_retries: int = 3,
    require_tests_pass: bool = True,
    serve: bool = True,
    port_override: Optional[int] = None,
    watch: bool = True,
    auto_fix_attempts: int = 0,
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
            print(f"\nWhat to try:", file=sys.stderr)
            print(f"  1. The task in INTENT.md may need `intent` (LLM "
                  f"judgment) rather than `pure fn` (pure computation). "
                  f"Add a line like 'Use a language model to analyze' "
                  f"and re-run.", file=sys.stderr)
            print(f"  2. Use a stronger author model — set "
                  f"ANTHROPIC_API_KEY (or OPENAI_API_KEY) and re-run.",
                  file=sys.stderr)
            print(f"  3. Pass --auto-fix 2 so the agent retries with "
                  f"the parse error fed back in.", file=sys.stderr)
            print(f"  4. Write {project.APP_FILE} by hand and re-run "
                  f"`ail up` — the agent will skip authoring when the "
                  f"file has content.", file=sys.stderr)
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
        if passed < total and auto_fix_attempts > 0:
            passed = _diagnose_and_repair(
                project, spec, max_attempts=auto_fix_attempts,
            )
        if require_tests_pass and passed < total:
            print(f"[{project.root.name}] aborting — tests failed. "
                  f"Edit INTENT.md or delete app.ail to re-author "
                  f"(or pass --auto-fix N to let the agent retry).",
                  file=sys.stderr)
            return 2
    else:
        print(f"[{project.root.name}] no tests declared", file=sys.stderr)

    if not serve:
        return 0

    # Defer importing server so non-serving callers don't pay http stdlib cost.
    from .server import serve_project
    port = port_override if port_override is not None else spec.port
    return serve_project(project, port=port, watch=watch)
