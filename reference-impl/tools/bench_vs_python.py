"""Head-to-head benchmark: AIL vs "Python + direct-HTTP LLM call".

For each natural-language task the same model is asked to write:

  1. an AIL program   (via `ail ask`)
  2. a Python program (via a direct prompt: "Write Python code that
     posts to the Ollama server for LLM judgment and uses plain
     Python for computation")

Both programs are executed, outputs captured, and three scores
reported per side:

  - parse rate         : did the program we got actually run?
  - routing correctness: for a task that needs judgment, did the
                         program ACTUALLY call the LLM — or did it
                         hardcode a heuristic that happens to work
                         for the test input? (The AIL-vs-Python
                         point: Python's "success" often comes from
                         the AI author skipping the LLM entirely.)
  - answer correctness : for pure_fn tasks, does the output match
                         the expected answer.

Results go to a JSON report so runs across models / prompt changes /
fine-tuned weights can be diffed over time.

Usage
-----
    export AIL_OLLAMA_HOST=http://10.0.0.1:11434
    export AIL_OLLAMA_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
    export AIL_OLLAMA_TIMEOUT_S=600

    python tools/bench_vs_python.py --limit 3 --json-out /tmp/bench.json

    # Filter by category:
    python tools/bench_vs_python.py --category hybrid --limit 5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, asdict, field
from typing import Any, Optional

from ail import ask, AuthoringError, compile_source
from ail.parser.ast import FnDecl, IntentDecl, ImportDecl

# Reuse the existing 50-case corpus rather than duplicating it.
from bench_authoring import CASES


# ---------- Python-side harness ------------------------------------------
#
# The prompt asks the model to write a stdlib-only Python program. For
# judgment subtasks it should POST directly to the Ollama server. The
# prompt deliberately mirrors the freedom AIL's author prompt grants —
# no framework, no library, just the task and the tools.

OLLAMA_HOST = os.environ.get("AIL_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("AIL_OLLAMA_MODEL", "llama3.1:latest")
OLLAMA_TIMEOUT = int(os.environ.get("AIL_OLLAMA_TIMEOUT_S", "300"))


PYTHON_AUTHOR_PROMPT = """You are a Python programmer. Write a single Python 3 \
program (no external packages — only the standard library) that solves the \
task below.

When the task requires LLM judgment (sentiment analysis, topic \
classification, summarization, translation, extraction, etc.), POST to \
the Ollama server directly using urllib.request. The server is at \
%(host)s and the model name is %(model)s. Use the /api/chat endpoint, \
set "stream": false, and parse the "message"."content" field of the JSON \
response.

When the task requires computation (counting, parsing, arithmetic, \
sorting, searching), write plain Python — do NOT call the LLM for that.

The program prints ONLY the final answer to stdout — no explanation, no \
logging. Any input data is embedded in the task description below.

Output format: raw Python code only. No markdown fences. No preamble.

TASK:
%(task)s
"""


def _ask_model_for_python(task: str) -> str:
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "user",
             "content": PYTHON_AUTHOR_PROMPT % {
                 "host": OLLAMA_HOST,
                 "model": OLLAMA_MODEL,
                 "task": task}},
        ],
        "stream": False,
        "options": {"temperature": 0.0},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("message", {}).get("content", "")


_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_python(raw: str) -> str:
    m = _FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


def _run_python(code: str, timeout: int = 60) -> dict:
    workdir = tempfile.mkdtemp(prefix="ail_bench_py_")
    path = os.path.join(workdir, "program.py")
    with open(path, "w") as f:
        f.write(code)
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "returncode": r.returncode,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "elapsed_s": time.perf_counter() - t0,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "returncode": -1,
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\n[TIMEOUT after {timeout}s]",
            "elapsed_s": time.perf_counter() - t0,
        }


# Signal that the Python program intends to route through the LLM.
# Crude but adequate for v1: if the program contains an HTTP call to
# Ollama, count it as "used intent". False positives are rare — no
# correct stdlib-only Python solution for a judgment task reaches
# urllib by accident. False negatives (model calls via some exotic
# route we don't grep for) are rarer still on stdlib-only constraint.
_LLM_CALL_PATTERNS = (
    r"urllib\.request",
    r"http\.client",
    r"127\.0\.0\.1:\s*11434",
    r"localhost:\s*11434",
    r"10\.0\.0\.1:\s*11434",
    r"/api/chat",
    r"/api/generate",
    r"ollama",
)

def python_uses_llm(code: str) -> bool:
    for pat in _LLM_CALL_PATTERNS:
        if re.search(pat, code, re.IGNORECASE):
            return True
    return False


# ---------- AIL-side structural analysis (mirrors bench_authoring) -------

def ail_uses_llm(source: str, trace_entries) -> bool:
    """True iff the authored AIL program routes at least one subtask
    through an LLM — either a locally declared intent, an import from
    an intent-bearing stdlib module, or an actual intent_call in the
    trace. Same logic the existing author bench uses so numbers are
    comparable."""
    try:
        prog = compile_source(source)
    except Exception:
        return any(e.kind == "intent_call" for e in trace_entries)
    if any(e.kind == "intent_call" for e in trace_entries):
        return True
    intent_only_stdlibs = {"stdlib/language", "stdlib/core"}
    for d in prog.declarations:
        if isinstance(d, IntentDecl):
            return True
        if isinstance(d, ImportDecl) and getattr(d, "module", "") in intent_only_stdlibs:
            return True
    return False


def ail_declares_fn(source: str) -> bool:
    try:
        prog = compile_source(source)
    except Exception:
        return False
    return any(isinstance(d, FnDecl) for d in prog.declarations)


# ---------- Routing correctness decision --------------------------------

def _routing_ok(category: str, used_llm: bool, used_fn: bool) -> bool:
    if category == "pure_fn":
        return not used_llm
    if category == "pure_intent":
        return used_llm
    if category == "hybrid":
        return used_llm and used_fn
    return False


# ---------- One case, both sides ----------------------------------------

@dataclass
class SideResult:
    parsed: bool
    routing_ok: bool
    answer_ok: bool
    used_llm: bool
    value: Optional[str]
    source: str
    elapsed_s: float
    error: Optional[str] = None


@dataclass
class CaseResult:
    name: str
    prompt: str
    category: str
    ail: SideResult
    python: SideResult


def _run_ail(case) -> SideResult:
    t0 = time.perf_counter()
    try:
        r = ask(case.prompt, max_retries=2)
    except AuthoringError as e:
        partial = e.partial
        return SideResult(
            parsed=False, routing_ok=False, answer_ok=False, used_llm=False,
            value=None, source=(partial.ail_source if partial else ""),
            elapsed_s=time.perf_counter() - t0,
            error=(partial.errors[-1] if partial and partial.errors
                   else f"{type(e).__name__}: {e}"),
        )
    except Exception as e:
        return SideResult(
            parsed=False, routing_ok=False, answer_ok=False, used_llm=False,
            value=None, source="", elapsed_s=time.perf_counter() - t0,
            error=f"{type(e).__name__}: {e}",
        )
    used_llm = ail_uses_llm(r.ail_source, r.trace.entries)
    used_fn = ail_declares_fn(r.ail_source)
    return SideResult(
        parsed=True,
        routing_ok=_routing_ok(case.category, used_llm, used_fn),
        answer_ok=(case.answer_ok(r.value) if case.category == "pure_fn" else True),
        used_llm=used_llm,
        value=str(r.value), source=r.ail_source,
        elapsed_s=time.perf_counter() - t0,
    )


def _run_python_side(case) -> SideResult:
    t0 = time.perf_counter()
    try:
        raw = _ask_model_for_python(case.prompt)
    except Exception as e:
        return SideResult(
            parsed=False, routing_ok=False, answer_ok=False, used_llm=False,
            value=None, source="", elapsed_s=time.perf_counter() - t0,
            error=f"author_call_failed: {type(e).__name__}: {e}",
        )
    code = _extract_python(raw)
    exec_report = _run_python(code)
    parsed = exec_report["returncode"] == 0
    used_llm = python_uses_llm(code)
    used_fn = True   # plain Python always "has fn" — every non-LLM call is "fn-like"
    stdout = exec_report["stdout"].strip()
    return SideResult(
        parsed=parsed,
        routing_ok=_routing_ok(case.category, used_llm, used_fn),
        answer_ok=(case.answer_ok(stdout) if case.category == "pure_fn" else parsed),
        used_llm=used_llm,
        value=stdout[:200], source=code,
        elapsed_s=time.perf_counter() - t0,
        error=(exec_report["stderr"][:200] if not parsed else None),
    )


def run_case(case) -> CaseResult:
    ail = _run_ail(case)
    python = _run_python_side(case)
    return CaseResult(name=case.name, prompt=case.prompt,
                      category=case.category, ail=ail, python=python)


# ---------- Reporting ----------------------------------------------------

def _summarize(results: list[CaseResult]) -> dict:
    def rate(predicate):
        total = len(results)
        if total == 0:
            return (0, 0, 0.0)
        n = sum(1 for r in results if predicate(r))
        return (n, total, 100 * n / total)

    return {
        "model": OLLAMA_MODEL,
        "host": OLLAMA_HOST,
        "total": len(results),
        "ail": {
            "parsed": rate(lambda r: r.ail.parsed),
            "routing_ok": rate(lambda r: r.ail.routing_ok),
            "answer_ok": rate(lambda r: r.category == "pure_fn" and r.ail.answer_ok and r.ail.parsed),
        },
        "python": {
            "parsed": rate(lambda r: r.python.parsed),
            "routing_ok": rate(lambda r: r.python.routing_ok),
            "answer_ok": rate(lambda r: r.category == "pure_fn" and r.python.answer_ok and r.python.parsed),
        },
    }


def _print_line(r: CaseResult) -> None:
    def g(side):
        return (("P" if side.parsed else "·")
                + ("R" if side.routing_ok else "·")
                + ("A" if side.answer_ok else "·"))
    a_val = (repr(r.ail.value)[:22] if r.ail.value else "(err)")
    p_val = (repr(r.python.value)[:22] if r.python.value else "(err)")
    print(f"  {r.category:12s} {r.name:26s}  AIL[{g(r.ail)}] "
          f"{a_val:24s}  Py[{g(r.python)}] {p_val:24s}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=("pure_fn", "pure_intent", "hybrid"))
    parser.add_argument("--limit", type=int, default=None,
                        help="Only run first N cases (after category filter)")
    parser.add_argument("--json-out", type=str, default=None,
                        help="Write detailed JSON report to this path")
    args = parser.parse_args()

    cases = list(CASES)
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} cases against {OLLAMA_MODEL} at {OLLAMA_HOST}")
    print(f"Glyphs: [P]arse [R]oute [A]nswer  — `·` = failed\n")

    results: list[CaseResult] = []
    t0 = time.perf_counter()
    for c in cases:
        r = run_case(c)
        results.append(r)
        _print_line(r)

    print()
    print("=" * 72)
    summary = _summarize(results)
    total = summary["total"]
    for side_name in ("ail", "python"):
        s = summary[side_name]
        print(f"{side_name.upper():6s} parse {s['parsed'][0]:2d}/{total} ({s['parsed'][2]:.0f}%)  "
              f"route {s['routing_ok'][0]:2d}/{total} ({s['routing_ok'][2]:.0f}%)  "
              f"answer {s['answer_ok'][0]:2d}/{total} ({s['answer_ok'][2]:.0f}%)")
    print("=" * 72)
    print(f"Wall clock: {time.perf_counter() - t0:.1f}s")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({
                "summary": summary,
                "cases": [
                    {"name": r.name, "prompt": r.prompt, "category": r.category,
                     "ail": asdict(r.ail), "python": asdict(r.python)}
                    for r in results
                ],
            }, f, indent=2, ensure_ascii=False)
        print(f"JSON report: {args.json_out}")

    all_ok = all(r.ail.parsed and r.ail.routing_ok and r.ail.answer_ok
                 for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
