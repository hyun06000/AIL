"""Project — the on-disk layout of an AIL agentic project.

  my-app/
  ├── INTENT.md           ← human-edited
  ├── app.ail             ← AI-owned, generated from INTENT.md
  └── .ail/
      ├── tests.json      ← extracted from INTENT.md by the agent
      ├── ledger.jsonl    ← every authoring decision, test run, request
      └── state/          ← cross-session evolve state (placeholder)

The Project class holds paths and convenience helpers. It does not
itself run the agent loop — see agent.py for that.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .intent_md import IntentSpec, parse_intent_md, render_intent_template


@dataclass
class Project:
    root: Path

    # Conventional file names. Constants on the class so they're easy
    # to override in tests if we ever want to.
    INTENT_FILE = "INTENT.md"
    APP_FILE = "app.ail"
    STATE_DIR = ".ail"
    TESTS_FILE = "tests.json"
    LEDGER_FILE = "ledger.jsonl"

    @classmethod
    def init(cls, root: Path | str, name: Optional[str] = None) -> "Project":
        """Create a fresh project on disk. Refuses to overwrite an
        existing INTENT.md so a `ail init` typo doesn't clobber work.
        """
        root = Path(root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        proj = cls(root)
        if proj.intent_path.exists():
            raise FileExistsError(
                f"{proj.intent_path} already exists — refusing to overwrite. "
                f"Edit it directly or remove it before re-init."
            )
        display_name = name or root.name
        proj.intent_path.write_text(
            render_intent_template(display_name), encoding="utf-8"
        )
        proj.state_dir.mkdir(exist_ok=True)
        (proj.state_dir / "state").mkdir(exist_ok=True)
        proj.append_ledger({"event": "init", "name": display_name})
        return proj

    @classmethod
    def at(cls, root: Path | str) -> "Project":
        """Open an existing project. Verifies INTENT.md is present."""
        root = Path(root).expanduser().resolve()
        proj = cls(root)
        if not proj.intent_path.exists():
            raise FileNotFoundError(
                f"No INTENT.md at {proj.intent_path}. "
                f"Run `ail init <name>` to scaffold a project, or `cd` "
                f"into an existing one before `ail up`."
            )
        proj.state_dir.mkdir(exist_ok=True)
        return proj

    # ---------- paths ----------

    @property
    def intent_path(self) -> Path:
        return self.root / self.INTENT_FILE

    @property
    def app_path(self) -> Path:
        return self.root / self.APP_FILE

    @property
    def state_dir(self) -> Path:
        return self.root / self.STATE_DIR

    @property
    def tests_path(self) -> Path:
        return self.state_dir / self.TESTS_FILE

    @property
    def ledger_path(self) -> Path:
        return self.state_dir / self.LEDGER_FILE

    # ---------- spec + source ----------

    def read_intent(self) -> IntentSpec:
        text = self.intent_path.read_text(encoding="utf-8")
        return parse_intent_md(text, default_name=self.root.name)

    def read_app_source(self) -> str:
        if not self.app_path.exists():
            return ""
        return self.app_path.read_text(encoding="utf-8")

    def write_app_source(self, source: str) -> None:
        text = source if source.endswith("\n") else source + "\n"
        self.app_path.write_text(text, encoding="utf-8")

    def write_tests(self, spec: IntentSpec) -> None:
        payload = [
            {"input": t.input, "expect_ok": t.expect_ok, "raw": t.raw}
            for t in spec.tests
        ]
        self.tests_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ---------- ledger ----------

    def append_ledger(self, event: dict[str, Any]) -> None:
        record = dict(event)
        record.setdefault("ts", time.time())
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
