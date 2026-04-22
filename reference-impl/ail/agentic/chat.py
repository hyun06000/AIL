"""ail chat — natural-language project edits.

Single-shot v1: the user types a request in plain language, the
authoring backend reads (current INTENT.md + current app.ail + the
request), returns updated versions of either or both files, and the
agent saves them and re-runs the declared tests.

No multi-turn history, no streaming, no diff display in v1. The
ledger captures every edit so a future version can build on top.

Output contract from the model: a JSON object with three keys —
  {
    "intent_md": "...full updated INTENT.md...   (or null if unchanged)",
    "app_ail":   "...full updated app.ail...     (or null if unchanged)",
    "summary":   "one-sentence description of the change"
  }

We return whole-file replacements rather than diffs because:
  (1) Models produce them more reliably than hunk-based diffs.
  (2) The agent doesn't need to know about merge conflicts.
  (3) The ledger keeps the previous versions implicitly via git
      (the user can `git diff` to see the change).
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Optional

from ..authoring import _default_adapter, _load_reference_card
from ..runtime.model import ModelAdapter
from .agent import _run_tests
from .project import Project


_CHAT_GOAL = (
    "Edit an AIL agentic project to fulfill the user's request. "
    "Return a JSON object with three keys: 'intent_md' (full updated "
    "INTENT.md as a string, or null if unchanged), 'app_ail' (full "
    "updated app.ail as a string, or null if unchanged), and 'summary' "
    "(one short sentence describing what you changed). "
    "If the request only needs a code change, leave intent_md null and "
    "vice versa. If it needs both, update both — keeping them coherent "
    "so the test cases in INTENT.md still match what app.ail does."
)

_CHAT_CONSTRAINTS = [
    "Output exactly one JSON object — no prose before or after.",
    "Both intent_md and app_ail (when non-null) must be the FULL file "
    "contents, not a diff or a fragment.",
    "If you update INTENT.md's ## Tests section, app.ail must change to "
    "match — the agent re-runs tests immediately.",
    "Preserve any existing AIL code that already does the right thing; "
    "only change what the user's request asks for.",
]


def chat_apply(
    project: Project,
    request: str,
    *,
    adapter: Optional[ModelAdapter] = None,
    rerun_tests: bool = True,
) -> dict[str, Any]:
    """Apply one natural-language edit. Returns a dict describing the change.

    The dict contains:
      changed:    list of file basenames that were updated
      summary:    the model's one-sentence summary
      tests:      {"passed": int, "total": int} — only present if
                  rerun_tests=True and tests were re-executed.
    """
    adapter = adapter or _default_adapter()
    reference_card = _load_reference_card()
    intent_text = project.intent_path.read_text(encoding="utf-8")
    app_text = project.read_app_source()

    project.append_ledger({
        "event": "chat_request",
        "request_chars": len(request),
        "request_preview": request[:200],
    })

    response = adapter.invoke(
        goal=_CHAT_GOAL,
        constraints=_CHAT_CONSTRAINTS,
        context={
            "_intent_name": "__agentic_chat__",
            "reference_card": reference_card,
            "current_intent_md": intent_text,
            "current_app_ail": app_text,
        },
        inputs={"request": request},
        expected_type=("JSON object {intent_md: Text|null, "
                       "app_ail: Text|null, summary: Text}"),
        examples=_chat_examples(),
    )

    payload = _coerce_to_chat_payload(response.value)
    new_intent = payload.get("intent_md")
    new_app = payload.get("app_ail")
    summary = (payload.get("summary") or "").strip()

    changed: list[str] = []
    if isinstance(new_intent, str) and new_intent.strip():
        project.intent_path.write_text(
            new_intent if new_intent.endswith("\n") else new_intent + "\n",
            encoding="utf-8",
        )
        changed.append(project.INTENT_FILE)
    if isinstance(new_app, str) and new_app.strip():
        project.write_app_source(new_app)
        changed.append(project.APP_FILE)

    project.append_ledger({
        "event": "chat_applied",
        "changed": changed,
        "summary": summary,
    })

    out: dict[str, Any] = {"changed": changed, "summary": summary}

    if rerun_tests and changed:
        # Re-extract tests in case INTENT.md changed.
        spec = project.read_intent()
        project.write_tests(spec)
        if spec.tests:
            print(f"[chat] re-running {len(spec.tests)} tests after edit",
                  file=sys.stderr)
            passed, total = _run_tests(project, spec.tests)
            out["tests"] = {"passed": passed, "total": total}
            project.append_ledger({
                "event": "chat_revalidated",
                "passed": passed, "total": total,
            })

    return out


# ---------------- helpers ----------------

def _coerce_to_chat_payload(raw: Any) -> dict[str, Any]:
    """Tolerate the small-model variants of how a JSON object can come back.

    Accepts:
      - a real dict already
      - a JSON-as-string (with or without code fences)
      - a dict whose intent_md/app_ail values are themselves JSON-string
        wrapped (small models love double-encoding)
    """
    if isinstance(raw, dict):
        d = raw
    elif isinstance(raw, str):
        d = _parse_json_loosely(raw)
    else:
        raise ValueError(
            f"chat backend returned unexpected shape: {type(raw).__name__}"
        )

    out: dict[str, Any] = {}
    for k in ("intent_md", "app_ail", "summary"):
        v = d.get(k)
        if isinstance(v, str) and v.strip().startswith("{") and k != "summary":
            # Model double-encoded the field. Try to unwrap.
            try:
                inner = _parse_json_loosely(v)
                if isinstance(inner, dict) and k in inner:
                    v = inner[k]
            except Exception:
                pass
        out[k] = v
    return out


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _parse_json_loosely(text: str) -> dict[str, Any]:
    """JSON parser tolerant of code fences and surrounding prose."""
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else text
    return json.loads(candidate)


def _chat_examples() -> list[tuple[list[dict[str, Any]], Any]]:
    """Tiny example set so the model knows the JSON shape.

    Returned as `(inputs_list, output)` tuples matching the adapter
    contract — the AnthropicAdapter (and others) iterate examples via
    `for inp, out in examples[:5]`. Returning dicts here would crash
    every chat call with `ValueError: too many values to unpack`. The
    same shape mismatch was fixed in diagnosis.py at v1.9.2; this
    parallel hole survived until v1.9.6 testing exposed it during
    auto-fix retries.
    """
    return [
        (
            [{
                "request": "make the empty-input error message Korean",
                "current_intent_md": "# greeter\n\n## Tests\n- \"\" → error\n",
                "current_app_ail": (
                    "entry main(input: Text) {\n"
                    "    if length(input) == 0 { return error(\"empty\") }\n"
                    "    return input\n}\n"
                ),
            }],
            {
                "intent_md": None,
                "app_ail": (
                    "entry main(input: Text) {\n"
                    "    if length(input) == 0 { return error(\"빈 입력\") }\n"
                    "    return input\n}\n"
                ),
                "summary": "Translated the empty-input error message to Korean.",
            },
        ),
    ]
