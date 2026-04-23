"""Background scheduler for agentic projects.

An AIL program can call `perform schedule.every(seconds)` from inside
`entry main`. That effect only *registers* a cadence — it writes
`{"seconds": N}` into the schedule file pointed at by AIL_SCHEDULE_FILE.
The loop that actually re-invokes the entry on that cadence lives here.

Design choices:

- One thread per project. Polls the schedule file every ~0.5s for
  changes. When the seconds value changes, the recurring invocation
  cadence updates on the next tick — no restart needed.
- Each tick re-invokes `entry main("")` in-process (same interpreter
  the server uses) and records the outcome to the ledger with
  `event: "schedule_tick"`. Success or failure of the tick doesn't
  stop the schedule; a dashboard whose upstream is flaky keeps trying.
- Entry can write results to state via `perform state.write(...)`,
  so GET / (which runs entry fresh each time) sees the latest output.
- Stop() is cooperative via a threading.Event. The server calls it
  on shutdown before closing the HTTPServer.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional


class Scheduler:
    """Polls a schedule file and drives recurring entry invocations.

    Use:
        sched = Scheduler(project, schedule_file, invoke_fn)
        sched.start()
        ... later ...
        sched.stop()

    `invoke_fn()` is a zero-arg callable that re-runs the project's
    entry; the server passes in a closure that calls `ail_run` with
    empty input and writes the outcome to the ledger.
    """

    # Poll interval for the schedule-file watcher itself. Separate
    # from the user-declared cadence (which can be minutes or days).
    POLL_SECONDS = 0.5

    def __init__(
        self,
        *,
        schedule_file: Path,
        invoke: "callable",
        logger=None,
    ):
        self._schedule_file = Path(schedule_file)
        self._invoke = invoke
        self._logger = logger
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # State of the currently active schedule. _seconds=None means
        # the file hasn't appeared yet or is invalid.
        self._seconds: Optional[float] = None
        self._next_tick: float = 0.0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="ail-scheduler", daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._check_schedule()
            if self._seconds is not None and time.time() >= self._next_tick:
                self._tick()
                self._next_tick = time.time() + self._seconds
            # Cooperative sleep — wakes early on stop().
            self._stop.wait(self.POLL_SECONDS)

    def _check_schedule(self) -> None:
        """Re-read the schedule file; update active cadence if changed."""
        try:
            if not self._schedule_file.is_file():
                return
            payload = json.loads(
                self._schedule_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        raw = payload.get("seconds") if isinstance(payload, dict) else None
        try:
            seconds = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return
        if seconds is None or seconds <= 0:
            return

        if seconds != self._seconds:
            self._seconds = seconds
            # First tick fires one cadence-interval from now, not
            # immediately — the request that registered the schedule
            # already ran the work once.
            self._next_tick = time.time() + seconds
            if self._logger is not None:
                try:
                    self._logger.schedule_armed(seconds)
                except AttributeError:
                    pass

    def _tick(self) -> None:
        try:
            self._invoke()
        except Exception:
            # The invoke closure records failures to the ledger itself;
            # even if it doesn't, we can't crash the scheduler thread.
            pass
