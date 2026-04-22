"""Terminal UI for `ail init` / `ail up` / `ail chat`.

Two styles:

  friendly (default) — wide layout, sentences the user can read,
                       check/cross marks for tests, breathing room.
                       Designed for someone who does not code.

  compact            — terse dev-style one-liners, the original v1.9.0
                       output. Opt in with `ail up --log compact`.

Emit on stderr so stdout stays available for program output (especially
important for `ail ask` and for HTTP health probes). The ledger
(.ail/ledger.jsonl) is the machine-readable surface and is unchanged
across styles.

Every call has both a friendly and a compact implementation; adding
a new event means adding both. The signatures stay narrow on purpose
— callers pass semantic values, not pre-formatted strings, so we can
freely change presentation later.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional


# --------------------------------------------------------- factory

def make_logger(style: str = "friendly") -> "Logger":
    style = (style or "friendly").lower()
    if style == "compact":
        return CompactLogger()
    return FriendlyLogger()


def detect_language(text: str) -> str:
    """Two-bucket language hint: 'ko' if the text contains any Hangul
    syllable, otherwise 'en'. Good enough to pick the right fallback
    message; the diagnosis LLM does the proper multilingual work."""
    if not text:
        return "en"
    for ch in text:
        # Hangul Syllables block U+AC00..U+D7A3
        if "\uac00" <= ch <= "\ud7a3":
            return "ko"
    return "en"


def _static_authoring_fallback(language: str) -> list[str]:
    """Plain-language fallback used only when the diagnose LLM call
    itself failed (no API key, network down, etc.). No code keywords,
    no command-line snippets — the audience is a non-developer.
    """
    if language == "ko":
        return [
            "AI가 이번에는 프로그램을 만들지 못했어요. 보통 다음 중 한 가지를",
            "고치면 다음 시도가 통과합니다.",
            "",
            "  • 만들고 싶은 일이 \"글의 뜻을 이해하는 일\"이라면, INTENT.md의",
            "    동작 설명에 \"AI가 이해해서 처리한다\" 같은 한 줄을 추가하세요.",
            "  • 설명이 추상적일수록 AI가 어려워합니다. 구체적인 예시 한두 개를",
            "    더해 보세요.",
            "  • 다시 한 번만 시도해도 통과할 때가 있습니다.",
        ]
    return [
        "The AI couldn't build it this time. Usually one of these helps",
        "the next try go through:",
        "",
        "  • If the task is \"understand what the text means\" (translate,",
        "    summarize, classify), add a line to your INTENT.md saying",
        "    something like \"the AI should read and understand it\".",
        "  • Vague descriptions are harder. Add one or two concrete",
        "    examples of what should happen.",
        "  • Sometimes simply trying again works.",
    ]


# --------------------------------------------------------- base

class Logger:
    """Shared interface. Subclasses implement every method."""

    # high-level sections
    def header(self, project_name: str) -> None: ...
    def reading_intent(self, behavior: int, tests: int) -> None: ...

    # authoring
    def authoring_start(self, adapter_desc: str) -> None: ...
    def authoring_done(self, path: Path) -> None: ...
    def using_existing(self, path: Path, size: int) -> None: ...
    def authoring_failed(self, *, adapter_desc: str,
                         diagnosis: Optional[str],
                         ledger_path: Path,
                         attempts: int) -> None: ...

    # tests
    def tests_start(self, count: int) -> None: ...
    def test_result(self, *, input_text: str, expect_ok: bool,
                    ran_ok: bool, passed: bool) -> None: ...
    def tests_summary(self, passed: int, total: int) -> None: ...
    def tests_aborted(self) -> None: ...

    # watcher
    def watcher_watching(self) -> None: ...
    def watcher_intent_changed(self, tests: int, also_app: bool) -> None: ...
    def watcher_app_changed(self) -> None: ...
    def watcher_warning(self, failed: int, total: int) -> None: ...

    # server
    def serving(self, host: str, port: int) -> None: ...
    def shutting_down(self) -> None: ...
    def port_bind_failed(self, host: str, port: int, reason: str) -> None: ...

    # auto-fix
    def auto_fix_attempt(self, attempt: int, max_attempts: int,
                         failing: int) -> None: ...
    def auto_fix_call_failed(self, error: str) -> None: ...
    def auto_fix_model_declined(self) -> None: ...
    def auto_fix_succeeded(self, attempts: int) -> None: ...


# --------------------------------------------------------- friendly

def _w(s: str = "") -> None:
    print(s, file=sys.stderr)


class FriendlyLogger(Logger):
    """Breathing room, sentences, ✓ / ✗ marks. The default."""

    def header(self, project_name: str) -> None:
        _w()
        _w(f"  {project_name}")
        _w(f"  {'─' * max(len(project_name), 30)}")
        _w()

    def reading_intent(self, behavior: int, tests: int) -> None:
        _w(f"  Reading INTENT.md")
        parts = []
        if behavior:
            parts.append(f"{behavior} behavior rule{'s' if behavior != 1 else ''}")
        if tests:
            parts.append(f"{tests} test case{'s' if tests != 1 else ''}")
        if parts:
            _w(f"     {' · '.join(parts)}")
        _w()

    def authoring_start(self, adapter_desc: str) -> None:
        _w(f"  Writing the program")
        _w(f"     using {adapter_desc}")
        _w()

    def authoring_done(self, path: Path) -> None:
        _w(f"  Program ready")
        _w(f"     saved to {path.name}")
        _w()

    def using_existing(self, path: Path, size: int) -> None:
        _w(f"  Using existing {path.name}")
        _w(f"     {size} bytes on disk")
        _w()

    def authoring_failed(self, *, adapter_desc: str,
                         diagnosis: Optional[str],
                         ledger_path: Path,
                         attempts: int,
                         language: str = "en",
                         attempt_path: Optional[Path] = None) -> None:
        _w()
        header = {
            "ko": "프로그램을 만들지 못했어요",
            "en": "Could not build the program",
        }.get(language, "Could not build the program")
        tried = {
            "ko": f"시도한 AI: {adapter_desc}",
            "en": f"tried {adapter_desc}",
        }.get(language, f"tried {adapter_desc}")
        _w(f"  {header}")
        _w(f"     {tried}")
        _w()
        if diagnosis and diagnosis.strip():
            for line in diagnosis.strip().splitlines():
                _w(f"     {line}")
        else:
            for line in _static_authoring_fallback(language):
                _w(f"     {line}")
        _w()
        if attempt_path is not None:
            attempt_label = {
                "ko": "AI가 마지막으로 쓴 코드 (실패한 것)",
                "en": "AI's last attempt (failed)",
            }.get(language, "AI's last attempt (failed)")
            _w(f"     {attempt_label}: {attempt_path}")
        log_label = {
            "ko": "기술자용 상세 기록",
            "en": "Full log",
        }.get(language, "Full log")
        _w(f"     {log_label}: {ledger_path}")
        _w()

    def tests_start(self, count: int) -> None:
        _w(f"  Running tests")

    def test_result(self, *, input_text: str, expect_ok: bool,
                    ran_ok: bool, passed: bool) -> None:
        mark = "✓" if passed else "✗"
        expect = "succeed" if expect_ok else "error"
        observed = "succeeded" if ran_ok else "errored"
        shown = repr(input_text) if input_text else "empty input"
        if len(shown) > 40:
            shown = shown[:37] + "..."
        _w(f"     {mark} {shown:<42} expected to {expect:<8} → {observed}")

    def tests_summary(self, passed: int, total: int) -> None:
        _w()
        if total == 0:
            _w(f"     (no tests declared)")
        elif passed == total:
            _w(f"     {passed} of {total} passed")
        else:
            _w(f"     {passed} of {total} passed — {total - passed} still failing")
        _w()

    def tests_aborted(self) -> None:
        _w(f"  Tests didn't pass — not starting the service.")
        _w(f"     Edit INTENT.md or app.ail, or re-run with --auto-fix N.")
        _w()

    def watcher_watching(self) -> None:
        _w(f"  Watching INTENT.md and app.ail for edits.")
        _w()

    def watcher_intent_changed(self, tests: int, also_app: bool) -> None:
        _w()
        suffix = " (app.ail changed too)" if also_app else ""
        _w(f"  INTENT.md changed — re-reading ({tests} tests){suffix}")

    def watcher_app_changed(self) -> None:
        _w()
        _w(f"  app.ail changed — re-checking")

    def watcher_warning(self, failed: int, total: int) -> None:
        _w(f"     Heads up: {failed} of {total} tests now failing. "
           f"The service is still running, but requests may misbehave "
           f"until the next edit fixes it.")
        _w()

    def serving(self, host: str, port: int) -> None:
        _w(f"  Service is live")
        _w(f"     http://{host}:{port}/")
        _w(f"     Send text in the request body to get a result.")
        _w(f"     Press Ctrl-C to stop.")
        _w()

    def shutting_down(self) -> None:
        _w()
        _w(f"  Shutting down.")

    def port_bind_failed(self, host: str, port: int, reason: str) -> None:
        _w()
        _w(f"  Could not open http://{host}:{port}/")
        _w(f"     {reason}")
        _w(f"     Another ail project on the same port? Change the port "
           f"in INTENT.md's Deployment section, or pass --port.")
        _w()

    def auto_fix_attempt(self, attempt: int, max_attempts: int,
                         failing: int) -> None:
        _w()
        _w(f"  Trying to fix the program (attempt {attempt} of "
           f"{max_attempts}, {failing} test{'s' if failing != 1 else ''} "
           f"failing)…")

    def auto_fix_call_failed(self, error: str) -> None:
        _w(f"     The AI couldn't propose a fix: {error}")

    def auto_fix_model_declined(self) -> None:
        _w(f"     The AI decided nothing needed to change. Leaving the "
           f"program as is.")

    def auto_fix_succeeded(self, attempts: int) -> None:
        _w(f"  Fixed after {attempts} attempt{'s' if attempts != 1 else ''}.")
        _w()


# --------------------------------------------------------- compact

class CompactLogger(Logger):
    """Original v1.9.0 output — terse one-liners with [project] prefix.
    Opt-in with --log compact. Keeps existing logs/test scripts happy.
    """

    def __init__(self) -> None:
        self._project: Optional[str] = None

    def _tag(self) -> str:
        return f"[{self._project}] " if self._project else ""

    def header(self, project_name: str) -> None:
        self._project = project_name

    def reading_intent(self, behavior: int, tests: int) -> None:
        _w(f"{self._tag()}reading INTENT.md "
           f"({behavior} behavior bullets, {tests} tests)")

    def authoring_start(self, adapter_desc: str) -> None:
        _w(f"{self._tag()}app.ail empty — authoring via {adapter_desc}...")

    def authoring_done(self, path: Path) -> None:
        _w(f"{self._tag()}wrote {path}")

    def using_existing(self, path: Path, size: int) -> None:
        _w(f"{self._tag()}using existing app.ail ({size} bytes)")

    def authoring_failed(self, *, adapter_desc: str,
                         diagnosis: Optional[str],
                         ledger_path: Path,
                         attempts: int,
                         language: str = "en",
                         attempt_path: Optional[Path] = None) -> None:
        # Compact mode ignores language — output is for scripts.
        _w(f"{self._tag()}author failed ({adapter_desc})")
        if diagnosis and diagnosis.strip():
            for line in diagnosis.strip().splitlines():
                _w(f"  {line}")
        if attempt_path is not None:
            _w(f"{self._tag()}attempt: {attempt_path}")
        _w(f"{self._tag()}log: {ledger_path}")

    def tests_start(self, count: int) -> None:
        _w(f"{self._tag()}running {count} tests...")

    def test_result(self, *, input_text: str, expect_ok: bool,
                    ran_ok: bool, passed: bool) -> None:
        status = "PASS" if passed else "FAIL"
        _w(f"  [{status}] input={input_text!r} "
           f"expect_ok={expect_ok} ran_ok={ran_ok}")

    def tests_summary(self, passed: int, total: int) -> None:
        _w(f"{self._tag()}tests: {passed}/{total} passed")

    def tests_aborted(self) -> None:
        _w(f"{self._tag()}aborting — tests failed. Edit INTENT.md or "
           f"delete app.ail to re-author (or pass --auto-fix N).")

    def watcher_watching(self) -> None:
        _w(f"{self._tag()}watching INTENT.md and app.ail for edits")

    def watcher_intent_changed(self, tests: int, also_app: bool) -> None:
        suffix = " + app.ail changed" if also_app else ""
        _w(f"[watcher] INTENT.md changed — re-extracting tests{suffix}")

    def watcher_app_changed(self) -> None:
        _w(f"[watcher] app.ail changed — revalidating")

    def watcher_warning(self, failed: int, total: int) -> None:
        _w(f"[watcher] WARNING: {failed}/{total} tests now failing — "
           f"server keeps running, but new requests may misbehave. "
           f"Edit INTENT.md or app.ail to fix.")

    def serving(self, host: str, port: int) -> None:
        _w(f"{self._tag()}serving on http://{host}:{port}/  "
           f"(POST text body, Ctrl-C to stop)")

    def shutting_down(self) -> None:
        _w(f"\n{self._tag()}shutting down")

    def port_bind_failed(self, host: str, port: int, reason: str) -> None:
        _w(f"could not bind {host}:{port} — {reason}")
        _w(f"another `ail up` on the same port? change `## Deployment` "
           f"in INTENT.md or pass --port to ail up.")

    def auto_fix_attempt(self, attempt: int, max_attempts: int,
                         failing: int) -> None:
        _w(f"{self._tag()}auto-fix attempt {attempt}/{max_attempts} — "
           f"calling chat backend on {failing} failing test(s)...")

    def auto_fix_call_failed(self, error: str) -> None:
        _w(f"{self._tag()}auto-fix call failed: {error}")

    def auto_fix_model_declined(self) -> None:
        _w(f"{self._tag()}auto-fix: model declined to change anything; "
           f"giving up.")

    def auto_fix_succeeded(self, attempts: int) -> None:
        _w(f"{self._tag()}auto-fix succeeded after "
           f"{attempts} attempt(s)")
