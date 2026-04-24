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

from .. import _default_adapter, run as ail_run
from ..authoring import ask, AuthoringError
from .intent_md import IntentSpec, TestCase
from .project import Project
from .ui import Logger, make_logger


def _describe_adapter() -> str:
    """Identify the current author model so the log line makes clear
    *which* model is doing the authoring. Non-developers otherwise
    can't tell whether `ail up` used their paid API key or the local
    fine-tune."""
    try:
        adapter = _default_adapter()
    except Exception as e:
        return f"(adapter unavailable: {type(e).__name__})"
    name = getattr(adapter, "name", adapter.__class__.__name__)
    model = getattr(adapter, "model", None)
    return f"{name}/{model}" if model else name


def _author_app(project: Project, spec: IntentSpec, *, max_retries: int) -> str:
    """Use `ask()` to author AIL from the INTENT.md-derived goal.

    Discards the executed-value side of AskResult and keeps only
    `.ail_source`. Empty input is passed during the smoke-test so the
    program at least proves it parses + executes once.
    """
    goal = spec.authoring_goal()
    adapter_desc = _describe_adapter()
    project.append_ledger({
        "event": "author_start",
        "goal_chars": len(goal),
        "author_model": adapter_desc,
    })
    try:
        result = ask(goal, max_retries=max_retries, input_text="")
    except AuthoringError as e:
        partial = e.partial.ail_source if e.partial else ""
        project.append_ledger({
            "event": "author_failed",
            "error": str(e),
            "partial_chars": len(partial),
            "author_model": adapter_desc,
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

    Four signals AIL can use to communicate error from an entry main:
      1. A Result-shaped dict with ok=False — the program returned
         a Result error directly.
      2. A string prefixed UNWRAP_ERROR: — `unwrap()` on an error
         Result was hit at runtime.
      3. A Python exception escaping ail_run() — handled by the caller.
      4. A string whose log body contains a line starting with "❌"
         (hyun06000 field test 2026-04-24) — the program self-reports
         a failure in its log buffer while still returning "OK" at the
         entry level. Auto-fix needs this signal to fire on silently-
         swallowed sub-step failures; without it the agent never
         realizes its own program failed.
    """
    if isinstance(value, dict) and value.get("_result") and not value.get("ok"):
        return True
    if isinstance(value, str):
        if value.startswith("UNWRAP_ERROR"):
            return True
        for line in value.splitlines():
            if line.lstrip().startswith("❌"):
                return True
    return False


def _run_tests(project: Project, tests: list[TestCase],
               logger: Optional[Logger] = None) -> tuple[int, int]:
    """Run every test case against the saved app.ail. Returns (passed, total).

    A test passes when the observed run shape (success / error) matches
    `expect_ok`. Content of the success-side value is not validated in
    v0 — content matching needs an LLM judge and is deferred.
    """
    # The watcher and chat paths call this without a logger; use a
    # default compact logger in that case so output doesn't vanish.
    logger = logger or make_logger("compact")
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
        logger.test_result(
            input_text=t.input, expect_ok=t.expect_ok,
            ran_ok=ran_ok, passed=ok,
        )
    return passed, len(tests)


def _print_authoring_failure(project: Project, err: AuthoringError,
                              adapter_desc: str,
                              logger: Logger) -> None:
    """Render an authoring failure in a way a non-developer can act on.

    Calls diagnose_authoring_failure() to translate the parse error
    into plain language in the user's own INTENT.md language. Falls
    back to a concise static tip list if the diagnosis call itself
    fails (network down, no API key at all, etc.).

    Also writes the failed AIL attempt to .ail/attempts/ so a developer
    (or a future meta-author AI) can inspect what the model produced.
    """
    from .diagnosis import diagnose_authoring_failure
    intent_text = project.intent_path.read_text(encoding="utf-8")
    last_src = err.partial.ail_source if err.partial else ""
    errors = list(err.partial.errors) if err.partial else [str(err)]

    # Persist the failed source first so a crash in diagnose() can't
    # cost us the artefact.
    attempt_path = None
    if last_src.strip():
        try:
            attempt_path = project.save_failed_attempt(
                source=last_src, errors=errors,
                author_model=adapter_desc, kind="author",
            )
        except Exception as se:
            project.append_ledger({
                "event": "attempt_save_failed",
                "error": f"{type(se).__name__}: {se}",
            })
        else:
            project.append_ledger({
                "event": "attempt_saved",
                "path": str(attempt_path.relative_to(project.root)),
                "kind": "author",
                "source_chars": len(last_src),
            })

    project.append_ledger({
        "event": "author_failed_diagnose_attempt",
        "author_model": adapter_desc,
        "errors": errors[-3:],
        "last_source_chars": len(last_src),
        "attempt_file": (
            str(attempt_path.relative_to(project.root))
            if attempt_path else None
        ),
    })

    diagnosis = None
    try:
        diagnosis = diagnose_authoring_failure(
            intent_md=intent_text,
            last_ail_source=last_src,
            errors=errors,
        )
    except Exception as de:
        project.append_ledger({
            "event": "diagnose_failed",
            "error": f"{type(de).__name__}: {de}",
        })

    if diagnosis and diagnosis.strip():
        project.append_ledger({
            "event": "diagnose_shown",
            "chars": len(diagnosis),
        })

    from .ui import detect_language
    logger.authoring_failed(
        adapter_desc=adapter_desc,
        diagnosis=diagnosis,
        ledger_path=project.ledger_path,
        attempts=len(errors),
        language=detect_language(intent_text),
        attempt_path=attempt_path,
    )


def _diagnose_and_repair(project: Project, spec, *, max_attempts: int,
                          logger: Optional[Logger] = None) -> int:
    """When the declared tests fail against the current app.ail, ask the
    chat backend to patch the program. Re-run tests; loop up to
    `max_attempts` repair cycles.

    Returns the number of tests that passed after the final repair
    attempt. The caller decides whether that's good enough.
    """
    from .chat import chat_apply  # local import — chat is optional path
    logger = logger or make_logger("compact")
    last_passed = 0
    last_total = len(spec.tests)
    for attempt in range(1, max_attempts + 1):
        failures = _recent_test_failures(project, limit=last_total)
        if not failures:
            return last_passed
        request = _format_repair_request(failures)
        logger.auto_fix_attempt(attempt, max_attempts, len(failures))
        project.append_ledger({
            "event": "auto_fix_attempt",
            "attempt": attempt,
            "failing_count": len(failures),
        })
        try:
            result = chat_apply(project, request, rerun_tests=False)
        except Exception as e:
            logger.auto_fix_call_failed(f"{type(e).__name__}: {e}")
            project.append_ledger({
                "event": "auto_fix_call_failed",
                "attempt": attempt,
                "error": f"{type(e).__name__}: {e}",
            })
            return last_passed
        if not result["changed"]:
            logger.auto_fix_model_declined()
            return last_passed
        last_passed, last_total = _run_tests(project, spec.tests, logger)
        project.append_ledger({
            "event": "auto_fix_revalidated",
            "attempt": attempt, "passed": last_passed, "total": last_total,
        })
        if last_passed == last_total:
            logger.auto_fix_succeeded(attempt)
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
    logger: Optional[Logger] = None,
    log_style: str = "friendly",
) -> int:
    """Execute the v0 state machine for `ail up`. Returns process exit code.

    `serve=False` returns after authoring + tests (useful in CI / tests
    of the agent itself).
    """
    # Detect the INTENT.md language BEFORE creating the logger so the
    # whole session localizes, not just the authoring-failure path.
    # Korean INTENT → Korean logs; anything else → English.
    from .ui import detect_language as _detect
    intent_text_for_lang = ""
    try:
        intent_text_for_lang = project.intent_path.read_text(encoding="utf-8")
    except Exception:
        pass
    lang = _detect(intent_text_for_lang)
    logger = logger or make_logger(log_style, language=lang)
    logger.header(project.root.name)

    # Bind the state effect directory BEFORE tests run, so the test
    # cases exercise the same persistent storage the served program
    # will see. Use setdefault so an outer shell that pre-sets
    # AIL_STATE_DIR (e.g. for isolated CI) still wins.
    import os as _os
    keyval_dir = project.state_dir / "state" / "keyval"
    try:
        keyval_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    _os.environ.setdefault("AIL_STATE_DIR", str(keyval_dir))

    spec = project.read_intent()
    logger.reading_intent(len(spec.behavior), len(spec.tests))
    project.write_tests(spec)

    # Author or reuse app.ail.
    if not project.read_app_source().strip():
        adapter_desc = _describe_adapter()
        logger.authoring_start(adapter_desc)
        try:
            source = _author_app(project, spec, max_retries=max_retries)
        except AuthoringError as e:
            _print_authoring_failure(project, e, adapter_desc, logger)
            return 1
        project.write_app_source(source)
        logger.authoring_done(project.app_path)
    else:
        logger.using_existing(
            project.app_path, project.app_path.stat().st_size,
        )

    # Run tests.
    if spec.tests:
        logger.tests_start(len(spec.tests))
        passed, total = _run_tests(project, spec.tests, logger)
        logger.tests_summary(passed, total)
        if passed < total and auto_fix_attempts > 0:
            passed = _diagnose_and_repair(
                project, spec, max_attempts=auto_fix_attempts, logger=logger,
            )
        if require_tests_pass and passed < total:
            logger.tests_aborted()
            return 2
    else:
        logger.tests_summary(0, 0)

    if not serve:
        return 0

    # Defer importing server so non-serving callers don't pay http stdlib cost.
    from .server import serve_project
    port = port_override if port_override is not None else spec.port
    return serve_project(project, port=port, watch=watch, logger=logger)
