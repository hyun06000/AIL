"""File watcher for `ail up` — polls INTENT.md and app.ail for changes,
re-extracts tests + re-runs them on edit, all without restarting the
HTTP server.

Stdlib polling rather than a watchdog dependency. ~1 second resolution
is fine for the editor-save use case; we are not trying to react to
high-frequency churn.

Hot-swap semantics: the server reads app.ail from disk on every
request, so a file change is picked up by the next incoming POST
without any in-process state shuffling. The watcher's job is to
*notice* the change and re-validate (re-run declared tests). If the
new code fails its own tests, we log a warning but do NOT take the
server offline — the design choice is "non-developer prefers a
running service that warns over a 502".
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .agent import _run_tests
from .project import Project


class Watcher:
    """Background polling watcher. Lifetime is bound by the calling
    server: call .start() once, .stop() before exit."""

    POLL_INTERVAL_S = 1.0

    def __init__(self, project: Project, logger=None):
        from .ui import make_logger
        self.project = project
        self.logger = logger or make_logger("compact")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Initial mtimes — what we observed at start. The first time
        # the loop sees a different value for either file we consider
        # it an edit.
        self._intent_mtime = self._mtime(project.intent_path)
        self._app_mtime = self._mtime(project.app_path)

    @staticmethod
    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="ail-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2 * self.POLL_INTERVAL_S)
            self._thread = None

    # ---------------- internal loop ----------------

    def _loop(self) -> None:
        while not self._stop.wait(self.POLL_INTERVAL_S):
            try:
                self._tick()
            except Exception as e:
                # Never let watcher exceptions kill the server.
                print(f"[watcher] unhandled error: {type(e).__name__}: {e}",
                      file=sys.stderr)
                self.project.append_ledger({
                    "event": "watcher_error",
                    "error": f"{type(e).__name__}: {e}",
                })

    def _tick(self) -> None:
        intent_mt = self._mtime(self.project.intent_path)
        app_mt = self._mtime(self.project.app_path)

        if intent_mt > self._intent_mtime:
            self._intent_mtime = intent_mt
            # If app.ail also changed in the same tick we'll handle
            # it together below — re-running tests once covers both.
            self._on_intent_changed(also_app=app_mt > self._app_mtime)
            self._app_mtime = app_mt
            return

        if app_mt > self._app_mtime:
            self._app_mtime = app_mt
            self._on_app_changed()

    def _on_intent_changed(self, *, also_app: bool) -> None:
        spec = self.project.read_intent()
        self.logger.watcher_intent_changed(len(spec.tests), also_app)
        self.project.write_tests(spec)
        self.project.append_ledger({
            "event": "watcher_intent_changed",
            "tests": len(spec.tests),
            "behavior_bullets": len(spec.behavior),
            "also_app": also_app,
        })
        self._revalidate(spec.tests, why="intent_md_edit")

    def _on_app_changed(self) -> None:
        self.logger.watcher_app_changed()
        spec = self.project.read_intent()
        self.project.append_ledger({"event": "watcher_app_changed"})
        self._revalidate(spec.tests, why="app_ail_edit")

    def _revalidate(self, tests, *, why: str) -> None:
        if not tests:
            return
        passed, total = _run_tests(self.project, tests, self.logger)
        if passed < total:
            self.logger.watcher_warning(total - passed, total)
        self.project.append_ledger({
            "event": "watcher_revalidated",
            "why": why, "passed": passed, "total": total,
        })
