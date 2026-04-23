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

def make_logger(style: str = "friendly", language: str = "en") -> "Logger":
    style = (style or "friendly").lower()
    if style == "compact":
        return CompactLogger()
    return FriendlyLogger(language=language)


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


# All FriendlyLogger strings, keyed by (language, key). Korean is not
# pluralized — the same phrase covers both singular and plural counts.
# English uses the `{n}` count as the plural signal (we test inline).
_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "reading_intent":    "Reading INTENT.md",
        "behavior_count":    "{n} behavior rule{s}",
        "test_count":        "{n} test case{s}",
        "authoring_start":   "Writing the program",
        "authoring_using":   "using {model}",
        "authoring_done":    "Program ready",
        "authoring_saved":   "saved to {name}",
        "using_existing":    "Using existing {name}",
        "existing_bytes":    "{n} bytes on disk",
        "tests_start":       "Running tests",
        "expect_succeed":    "succeed",
        "expect_error":      "error",
        "observed_succeed":  "succeeded",
        "observed_error":    "errored",
        "empty_input":       "empty input",
        "expected_to":       "expected to {verb}",
        "all_passed":        "{n} of {t} passed",
        "some_failed":       "{n} of {t} passed — {f} still failing",
        "no_tests":          "(no tests declared)",
        "tests_aborted_1":   "Tests didn't pass — not starting the service.",
        "tests_aborted_2":   "Edit INTENT.md or app.ail, or re-run with --auto-fix N.",
        "watching":          "Watching INTENT.md and app.ail for edits.",
        "schedule_armed":    "Recurring tick every {s:g}s — stored to .ail/ledger.jsonl.",
        "intent_changed":    "INTENT.md changed — re-reading ({t} tests){suffix}",
        "also_app":          " (app.ail changed too)",
        "app_changed":       "app.ail changed — re-checking",
        "watcher_warning":
            "Heads up: {f} of {t} tests now failing. The service is still "
            "running, but requests may misbehave until the next edit fixes it.",
        "serving_header":    "Service is live",
        "serving_open_1":    "Open that URL in a browser to use it — there's a",
        "serving_open_2":    "text box waiting for you.",
        "serving_edit_1":    "Edit INTENT.md and save: the service updates itself.",
        "serving_edit_2":    "No restart. No re-run. The tab you just opened keeps",
        "serving_edit_3":    "working.",
        "serving_stop":      "Press Ctrl-C here to stop the service.",
        "shutting_down":     "Shutting down.",
        "bind_failed_1":     "Could not open http://{host}:{port}/",
        "bind_failed_2":
            "Another ail project on the same port? Change the port in "
            "INTENT.md's Deployment section, or pass --port.",
        "auto_fix_attempt":
            "Trying to fix the program (attempt {a} of {m}, {f} "
            "test{s} failing)…",
        "auto_fix_call_failed": "The AI couldn't propose a fix: {error}",
        "auto_fix_declined":
            "The AI decided nothing needed to change. Leaving the program as is.",
        "auto_fix_succeeded":  "Fixed after {a} attempt{s}.",
    },
    "ko": {
        "reading_intent":    "INTENT.md 읽는 중",
        "behavior_count":    "동작 규칙 {n}개",
        "test_count":        "테스트 {n}개",
        "authoring_start":   "프로그램 쓰는 중",
        "authoring_using":   "사용하는 AI: {model}",
        "authoring_done":    "프로그램 준비 완료",
        "authoring_saved":   "저장됨: {name}",
        "using_existing":    "기존 {name} 사용",
        "existing_bytes":    "디스크에 {n} 바이트",
        "tests_start":       "테스트 돌리는 중",
        "expect_succeed":    "성공",
        "expect_error":      "에러",
        "observed_succeed":  "성공",
        "observed_error":    "에러",
        "empty_input":       "빈 입력",
        "expected_to":       "{verb} 기대",
        "all_passed":        "{t}개 중 {n}개 통과",
        "some_failed":       "{t}개 중 {n}개 통과 — {f}개 아직 실패",
        "no_tests":          "(선언된 테스트 없음)",
        "tests_aborted_1":   "테스트가 통과하지 못해서 서비스를 시작하지 않아요.",
        "tests_aborted_2":
            "INTENT.md나 app.ail을 수정해 보거나, --auto-fix N 옵션을 붙여 "
            "다시 실행해 보세요.",
        "watching":          "INTENT.md와 app.ail의 변경을 지켜보는 중.",
        "schedule_armed":    "{s:g}초마다 자동 실행 — 기록은 .ail/ledger.jsonl에 남아요.",
        "intent_changed":    "INTENT.md가 바뀌었어요 — 다시 읽는 중 (테스트 {t}개){suffix}",
        "also_app":          " (app.ail도 함께 바뀜)",
        "app_changed":       "app.ail이 바뀌었어요 — 다시 확인하는 중",
        "watcher_warning":
            "주의: 테스트 {t}개 중 {f}개가 지금 실패해요. 서비스는 계속 "
            "돌아가지만, 다음 편집이 고칠 때까지 요청이 이상하게 동작할 수 있어요.",
        "serving_header":    "서비스 준비 완료",
        "serving_open_1":    "브라우저에서 이 주소를 열어 보세요 — 입력창이",
        "serving_open_2":    "기다리고 있어요.",
        "serving_edit_1":    "INTENT.md를 편집하고 저장하면 서비스가 스스로 갱신됩니다.",
        "serving_edit_2":    "재시작이 필요 없고, 방금 연 탭도 계속",
        "serving_edit_3":    "작동합니다.",
        "serving_stop":      "여기서 Ctrl-C를 누르면 서비스가 멈춰요.",
        "shutting_down":     "종료 중.",
        "bind_failed_1":     "http://{host}:{port}/ 를 열 수 없어요",
        "bind_failed_2":
            "같은 포트에서 이미 다른 ail 프로젝트가 돌고 있나요? INTENT.md의 "
            "Deployment 섹션에서 포트를 바꾸거나 --port 옵션으로 지정하세요.",
        "auto_fix_attempt":
            "프로그램을 고치는 중 ({a}/{m}번째 시도, 테스트 {f}개 실패)…",
        "auto_fix_call_failed": "AI가 수정안을 내놓지 못했어요: {error}",
        "auto_fix_declined":
            "AI가 바꿀 게 없다고 판단했어요. 프로그램은 그대로 둡니다.",
        "auto_fix_succeeded":  "{a}번 시도 후 고쳤어요.",
    },
}


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
    """Breathing room, sentences, ✓ / ✗ marks. The default.

    Localized: constructor takes a language hint (typically derived
    from INTENT.md via detect_language). English and Korean are
    first-class; unknown languages fall back to English.
    """

    def __init__(self, language: str = "en") -> None:
        self._lang = language if language in _STRINGS else "en"

    def _s(self, key: str, **kw) -> str:
        template = _STRINGS[self._lang].get(key) or _STRINGS["en"][key]
        # `{s}` is the English plural suffix; resolved here so call
        # sites can pass `n=...` and get correct pluralization.
        if "{s}" in template and "s" not in kw:
            kw["s"] = "s" if kw.get("n", kw.get("t", kw.get("a", 0))) != 1 else ""
        return template.format(**kw) if kw else template

    def header(self, project_name: str) -> None:
        _w()
        _w(f"  {project_name}")
        _w(f"  {'─' * max(len(project_name), 30)}")
        _w()

    def reading_intent(self, behavior: int, tests: int) -> None:
        _w(f"  {self._s('reading_intent')}")
        parts = []
        if behavior:
            parts.append(self._s("behavior_count", n=behavior))
        if tests:
            parts.append(self._s("test_count", n=tests))
        if parts:
            _w(f"     {' · '.join(parts)}")
        _w()

    def authoring_start(self, adapter_desc: str) -> None:
        _w(f"  {self._s('authoring_start')}")
        _w(f"     {self._s('authoring_using', model=adapter_desc)}")
        _w()

    def authoring_done(self, path: Path) -> None:
        _w(f"  {self._s('authoring_done')}")
        _w(f"     {self._s('authoring_saved', name=path.name)}")
        _w()

    def using_existing(self, path: Path, size: int) -> None:
        _w(f"  {self._s('using_existing', name=path.name)}")
        _w(f"     {self._s('existing_bytes', n=size)}")
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
        _w(f"  {self._s('tests_start')}")

    def test_result(self, *, input_text: str, expect_ok: bool,
                    ran_ok: bool, passed: bool) -> None:
        mark = "✓" if passed else "✗"
        expect = self._s("expect_succeed" if expect_ok else "expect_error")
        observed = self._s("observed_succeed" if ran_ok else "observed_error")
        shown = repr(input_text) if input_text else self._s("empty_input")
        if len(shown) > 40:
            shown = shown[:37] + "..."
        expect_phrase = self._s("expected_to", verb=expect)
        _w(f"     {mark} {shown:<42} {expect_phrase:<20} → {observed}")

    def tests_summary(self, passed: int, total: int) -> None:
        _w()
        if total == 0:
            _w(f"     {self._s('no_tests')}")
        elif passed == total:
            _w(f"     {self._s('all_passed', n=passed, t=total)}")
        else:
            _w(f"     {self._s('some_failed', n=passed, t=total, f=total-passed)}")
        _w()

    def tests_aborted(self) -> None:
        _w(f"  {self._s('tests_aborted_1')}")
        _w(f"     {self._s('tests_aborted_2')}")
        _w()

    def watcher_watching(self) -> None:
        _w(f"  {self._s('watching')}")
        _w()

    def schedule_armed(self, seconds: float) -> None:
        _w(f"  {self._s('schedule_armed', s=seconds)}")
        _w()

    def watcher_intent_changed(self, tests: int, also_app: bool) -> None:
        _w()
        suffix = self._s("also_app") if also_app else ""
        _w(f"  {self._s('intent_changed', t=tests, suffix=suffix)}")

    def watcher_app_changed(self) -> None:
        _w()
        _w(f"  {self._s('app_changed')}")

    def watcher_warning(self, failed: int, total: int) -> None:
        _w(f"     {self._s('watcher_warning', f=failed, t=total)}")
        _w()

    def serving(self, host: str, port: int) -> None:
        url = f"http://{host}:{port}/"
        _w(f"  {self._s('serving_header')}")
        _w(f"     {url}")
        _w(f"     {self._s('serving_open_1')}")
        _w(f"     {self._s('serving_open_2')}")
        _w()
        _w(f"     {self._s('serving_edit_1')}")
        _w(f"     {self._s('serving_edit_2')}")
        _w(f"     {self._s('serving_edit_3')}")
        _w()
        _w(f"     {self._s('serving_stop')}")
        _w()

    def shutting_down(self) -> None:
        _w()
        _w(f"  {self._s('shutting_down')}")

    def port_bind_failed(self, host: str, port: int, reason: str) -> None:
        _w()
        _w(f"  {self._s('bind_failed_1', host=host, port=port)}")
        _w(f"     {reason}")
        _w(f"     {self._s('bind_failed_2')}")
        _w()

    def auto_fix_attempt(self, attempt: int, max_attempts: int,
                         failing: int) -> None:
        _w()
        _w(f"  {self._s('auto_fix_attempt', a=attempt, m=max_attempts, f=failing, n=failing)}")

    def auto_fix_call_failed(self, error: str) -> None:
        _w(f"     {self._s('auto_fix_call_failed', error=error)}")

    def auto_fix_model_declined(self) -> None:
        _w(f"     {self._s('auto_fix_declined')}")

    def auto_fix_succeeded(self, attempts: int) -> None:
        _w(f"  {self._s('auto_fix_succeeded', a=attempts, n=attempts)}")
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

    def schedule_armed(self, seconds: float) -> None:
        _w(f"{self._tag()}schedule every {seconds:g}s")

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
