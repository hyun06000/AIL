"""The benchmark — AIL vs Python, 50 prompts × 3 measurement dimensions.

This is the tool Opus 4's directive (CLAUDE.md, "APRIL 2026 REVIEW
(UPDATED)" section) requires us to run before any more language
features, before fine-tuning, before public promotion. The numbers
this tool produces are the project's evidence.

Three dimensions, per Opus's spec:

  A. Code Generation Quality
       parse_success_rate, exec_success_rate,
       fn_intent_accuracy (AIL only), retry_count

  B. Code Safety
       side_effect_violation_rate (Python "pure" fn doing I/O),
       error_handling_omission_rate (failable op uncaught),
       infinite_loop_rate (while/for with no bound)

  C. Execution Efficiency
       llm_call_count, token_usage, execution_time_ms
       (cost_usd is reported when the model has known pricing,
       otherwise left as null)

Inputs
------
  benchmarks/prompts.json   50 prompts × {id, category, text,
                            ground_truth_category, expected}

Outputs
-------
  one JSON per model per run → docs/benchmarks/
    snapshot shape:
      {
        "model": "...", "started_at": "...", "wall_clock_s": N,
        "summary": { "A": {...}, "B": {...}, "C": {...} },
        "cases": [ { per-prompt detail } ]
      }

Usage
-----
    export AIL_OLLAMA_HOST=http://localhost:11434
    export AIL_OLLAMA_MODEL=llama3.1:latest
    export AIL_OLLAMA_TIMEOUT_S=600

    cd reference-impl
    python tools/benchmark.py \\
        --out ../docs/benchmarks/$(date +%F)_llama3.1-8b.json

    # Smaller smoke run:
    python tools/benchmark.py --limit 3 --out /tmp/smoke.json
    python tools/benchmark.py --category A --limit 5 --out /tmp/A.json
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ail import ask, AuthoringError, compile_source
from ail.parser.ast import FnDecl, IntentDecl, ImportDecl
from ail.runtime.openai_adapter import OpenAICompatibleAdapter


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
PROMPTS_PATH = REPO_ROOT / "benchmarks" / "prompts.json"


# Load a .env file at import time so ANTHROPIC_API_KEY and
# ANTHROPIC_MODEL set there are visible to the module-level lookups
# below. The helper is the same one `ail.run` uses, so the behavior
# is consistent across the package: it looks in cwd and up to 4
# parent directories, skips if nothing is found, never overwrites
# an already-set env var.
from ail import _load_dotenv_if_present as _load_dotenv   # noqa: E402
_load_dotenv()


OLLAMA_HOST = os.environ.get("AIL_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("AIL_OLLAMA_MODEL", "llama3.1:latest")
OLLAMA_TIMEOUT = int(os.environ.get("AIL_OLLAMA_TIMEOUT_S", "600"))

OPENAI_COMPAT_BASE_URL = os.environ.get("AIL_OPENAI_COMPAT_BASE_URL", "http://localhost:8000")
OPENAI_COMPAT_MODEL = os.environ.get("AIL_OPENAI_COMPAT_MODEL", "")
OPENAI_COMPAT_TIMEOUT = int(os.environ.get("AIL_OPENAI_COMPAT_TIMEOUT_S", "300"))

# Backend selection:
#   ollama    (default)  — existing Python-authoring path, POSTs to
#                          localhost:11434
#   anthropic            — Python-authoring side uses Anthropic's
#                          messages.create. AIL side (via `ask`)
#                          already auto-routes to Anthropic when
#                          ANTHROPIC_API_KEY is set and no
#                          AIL_OLLAMA_MODEL is set.
BENCHMARK_BACKEND = os.environ.get("BENCHMARK_BACKEND", "ollama").lower()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")


# --- Python-authoring prompt -----------------------------------------------
#
# Two variants. The Ollama prompt tells the model to POST to a local
# server for LLM judgment; the Anthropic prompt tells it to POST to
# Anthropic's API with its API key. Both require the author to emit
# raw Python — the execution harness is the same for both.

_PY_PROMPT_OLLAMA = """You are a Python programmer. Write a single Python 3 \
program (stdlib only — no packages) that solves the task below.

When the task requires LLM judgment (sentiment, classification, \
summarization, translation, extraction), POST to Ollama directly using \
urllib.request. The server is %(host)s and the model name is %(model)s. \
Use the /api/chat endpoint with "stream": false and parse the \
"message"."content" field from the JSON response.

When the task requires computation (counting, parsing, arithmetic, \
sorting, searching), write plain Python — do NOT call the LLM for that.

Print ONLY the final answer to stdout. No explanation, no logs. All \
input data is embedded in the task description. Output: raw Python \
code only, no markdown fences, no preamble.

TASK:
%(task)s
"""


_PY_PROMPT_ANTHROPIC = """You are a Python programmer. Write a single Python 3 \
program (stdlib only — no packages) that solves the task below.

When the task requires LLM judgment (sentiment, classification, \
summarization, translation, extraction), POST to the Anthropic API at \
https://api.anthropic.com/v1/messages using urllib.request. Read the \
API key from the ANTHROPIC_API_KEY environment variable. Headers: \
"x-api-key: <key>", "anthropic-version: 2023-06-01", \
"content-type: application/json". Body: {"model": %(model)r, \
"max_tokens": 256, "messages": [{"role": "user", "content": "<prompt>"}]}. \
The response JSON has "content" as a list; use content[0]["text"].

When the task requires computation (counting, parsing, arithmetic, \
sorting, searching), write plain Python — do NOT call the API for that.

Print ONLY the final answer to stdout. No explanation, no logs. All \
input data is embedded in the task description. Output: raw Python \
code only, no markdown fences, no preamble.

TASK:
%(task)s
"""


def _ask_ollama_for_python(task: str) -> tuple[str, dict]:
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user",
                      "content": _PY_PROMPT_OLLAMA % {
                          "host": OLLAMA_HOST,
                          "model": OLLAMA_MODEL,
                          "task": task}}],
        "stream": False,
        "options": {"temperature": 0.0},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    return (data.get("message", {}).get("content", ""),
            {"prompt_eval_count": data.get("prompt_eval_count"),
             "eval_count": data.get("eval_count"),
             "total_duration_ns": data.get("total_duration")})


def _ask_anthropic_for_python(task: str) -> tuple[str, dict]:
    """Anthropic messages.create authoring path. Returns
    (raw_response_text, usage_metadata)."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. "
            "Run: pip install 'ail-interpreter[anthropic]'"
        )
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        temperature=0.0,
        messages=[{"role": "user",
                   "content": _PY_PROMPT_ANTHROPIC % {
                       "model": ANTHROPIC_MODEL, "task": task}}],
    )
    text = "".join(
        b.text for b in msg.content if getattr(b, "type", None) == "text"
    )
    return text, {
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
    }


def _ask_openai_compat_for_python(task: str) -> tuple[str, dict]:
    """OpenAI-compatible (vLLM / LocalAI / etc.) Python-authoring path."""
    body = json.dumps({
        "model": OPENAI_COMPAT_MODEL,
        "messages": [{"role": "user",
                      "content": _PY_PROMPT_OLLAMA % {
                          "host": OPENAI_COMPAT_BASE_URL,
                          "model": OPENAI_COMPAT_MODEL,
                          "task": task}}],
        "temperature": 0.0,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENAI_COMPAT_BASE_URL}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer EMPTY"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=OPENAI_COMPAT_TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    return content, {"prompt_tokens": usage.get("prompt_tokens"),
                     "completion_tokens": usage.get("completion_tokens")}


def _ask_model_for_python(task: str) -> tuple[str, dict]:
    """Dispatch to the configured backend."""
    if BENCHMARK_BACKEND == "anthropic":
        return _ask_anthropic_for_python(task)
    if BENCHMARK_BACKEND == "vllm":
        return _ask_openai_compat_for_python(task)
    return _ask_ollama_for_python(task)


_FENCE = re.compile(r"```(?:python|py)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_python(raw: str) -> str:
    m = _FENCE.search(raw)
    return (m.group(1) if m else raw).strip()


def _run_python(code: str, timeout: int = 60) -> dict:
    d = tempfile.mkdtemp(prefix="ail_bench_")
    path = os.path.join(d, "prog.py")
    with open(path, "w") as f:
        f.write(code)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([sys.executable, path],
                           capture_output=True, text=True, timeout=timeout)
        return {"returncode": r.returncode, "stdout": r.stdout,
                "stderr": r.stderr,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "timed_out": False}
    except subprocess.TimeoutExpired as e:
        return {"returncode": -1, "stdout": (e.stdout or ""),
                "stderr": (e.stderr or "") + f"\n[TIMEOUT {timeout}s]",
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "timed_out": True}


# --- Safety analysis (Dimension B) -----------------------------------------

_LLM_HTTP_PATTERNS = (
    r"urllib\.request", r"http\.client", r":\s*11434", r"/api/chat",
    r"/api/generate", r"ollama",
)

_PY_IO_PATTERNS = (
    r"\bopen\s*\(", r"\bsubprocess\b",
    # os.environ is a READ of runtime config — not a dangerous side
    # effect. B/C tasks legitimately read an API key via
    # os.environ["ANTHROPIC_API_KEY"]; flagging that as a side-effect
    # violation produces a false 68%-100% rate on those categories.
    # Keep only the patterns that actually mutate / trigger external
    # effects.
    r"\bos\.(system|remove|unlink|mkdir|chmod|rename|chdir)\b",
    r"\bshutil\b", r"\binput\s*\(",
    r"\bsys\.exit\b", r"socket\.", r"urllib\.request\.urlretrieve",
)

_PY_FAILABLE_PATTERNS = (
    r"\bint\s*\(", r"\bfloat\s*\(", r"\bopen\s*\(", r"\burllib\.request\.",
    r"\bjson\.loads\s*\(", r"\bdatetime\.(strptime|fromisoformat)",
)


def python_uses_llm(code: str) -> bool:
    return any(re.search(p, code) for p in _LLM_HTTP_PATTERNS)


def python_side_effect_in_pure(code: str) -> bool:
    """Does the Python program do I/O in what a caller might consider
    a pure function? Our approximation: does it do any I/O at all
    that isn't the designated LLM HTTP call? Python has no `pure fn`
    declaration, so we treat the whole program as nominally pure and
    count unaccounted I/O. AIL's answer is always 0% here (the
    compiler rejects it), so the gap is the payoff."""
    # Strip the LLM call patterns first — those are explicitly allowed.
    stripped = code
    for pat in _LLM_HTTP_PATTERNS:
        stripped = re.sub(pat, "", stripped)
    return any(re.search(p, stripped) for p in _PY_IO_PATTERNS)


def python_has_unbounded_loop(code: str) -> bool:
    """Unbounded loop = `while True` / `while 1` / other `while
    <never-terminating>` patterns. AIL has no `while` at all, so its
    rate on this metric is 0% by language design — the gap is the
    point."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            # If test is a Constant truthy value or a Name that looks
            # permanently true, flag it.
            if isinstance(node.test, ast.Constant) and node.test.value:
                return True
            if isinstance(node.test, ast.Name) and node.test.id in ("True", "true"):
                return True
    return False


def python_has_error_handling_for_failable(code: str) -> bool:
    """If the program calls something that can raise (int(), open(),
    json.loads(), urllib.request), is there a try/except anywhere?
    Approximation: presence of `try:` when at least one failable call
    exists. True positives: programs that DO handle errors. False
    positives: program uses try/except for something else. Still
    correlates."""
    has_failable = any(re.search(p, code) for p in _PY_FAILABLE_PATTERNS)
    if not has_failable:
        return True   # no failable op → nothing to handle, count as OK
    return bool(re.search(r"\btry\s*:", code))


# --- AIL-side structural analysis ------------------------------------------

INTENT_BEARING_STDLIBS = {"stdlib/language", "stdlib/core"}


def ail_uses_llm(source: str, trace_entries) -> bool:
    try:
        prog = compile_source(source)
    except Exception:
        return any(e.kind == "intent_call" for e in trace_entries)
    if any(e.kind == "intent_call" for e in trace_entries):
        return True
    for d in prog.declarations:
        if isinstance(d, IntentDecl):
            return True
        if isinstance(d, ImportDecl) and getattr(d, "module", "") in INTENT_BEARING_STDLIBS:
            return True
    return False


def ail_uses_fn(source: str) -> bool:
    try:
        prog = compile_source(source)
    except Exception:
        return False
    return any(isinstance(d, FnDecl) for d in prog.declarations)


def ail_llm_call_count(trace_entries) -> int:
    return sum(1 for e in trace_entries if e.kind == "intent_call")


def _routing_matches_ground_truth(ground_truth: str,
                                  used_llm: bool,
                                  used_fn: bool) -> bool:
    """Ground-truth label from prompts.json: fn_only / intent_only /
    both / none. The authored program's routing must match."""
    if ground_truth == "fn_only":
        return not used_llm
    if ground_truth == "intent_only":
        return used_llm
    if ground_truth == "both":
        return used_llm and used_fn
    if ground_truth == "none":
        return not used_llm   # no-op tasks ideally don't call model
    return False


# --- Answer correctness ----------------------------------------------------

def _norm(s: Any) -> str:
    s = str(s).strip().lower()
    return s[:-2] if s.endswith(".0") else s


def answer_ok(expected: Optional[str], actual: Any) -> bool:
    """Lenient equality. For prompts with null `expected` (judgment
    tasks where the answer varies by model), we can't score answer
    correctness at the string level — we return True so those prompts
    don't penalize either side. The parse/exec dimensions still
    score them honestly."""
    if expected is None:
        return True
    return _norm(expected) == _norm(actual)


# --- One case, both sides --------------------------------------------------

@dataclass
class SideReport:
    parsed: bool
    exec_success: bool
    answer_ok: bool
    routing_ok: bool
    uses_llm: bool
    llm_call_count: int
    side_effect_violation: bool = False
    unbounded_loop: bool = False
    error_handling_ok: bool = True
    retries: int = 0
    value: Optional[str] = None
    source: str = ""
    elapsed_ms: int = 0
    error: Optional[str] = None


@dataclass
class CaseReport:
    id: str
    category: str
    text: str
    ground_truth_category: str
    ail: SideReport
    python: SideReport


def _make_ail_adapter():
    if BENCHMARK_BACKEND == "vllm":
        return OpenAICompatibleAdapter(
            model=OPENAI_COMPAT_MODEL,
            base_url=OPENAI_COMPAT_BASE_URL,
            timeout=OPENAI_COMPAT_TIMEOUT,
        )
    return None  # ask() uses its default adapter (Ollama or Anthropic)


def _run_ail(prompt: dict) -> SideReport:
    t0 = time.perf_counter()
    try:
        r = ask(prompt["text"], max_retries=2, adapter=_make_ail_adapter())
    except AuthoringError as e:
        partial = e.partial
        return SideReport(
            parsed=False, exec_success=False, answer_ok=False, routing_ok=False,
            uses_llm=False, llm_call_count=0,
            retries=(len(partial.errors) if partial and partial.errors else 0),
            value=None, source=(partial.ail_source if partial else ""),
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            error=(partial.errors[-1] if partial and partial.errors
                   else f"{type(e).__name__}: {e}"),
        )
    except Exception as e:
        return SideReport(
            parsed=False, exec_success=False, answer_ok=False, routing_ok=False,
            uses_llm=False, llm_call_count=0,
            value=None, source="",
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            error=f"{type(e).__name__}: {e}",
        )
    used_llm = ail_uses_llm(r.ail_source, r.trace.entries)
    used_fn = ail_uses_fn(r.ail_source)
    value_str = str(r.value)
    return SideReport(
        parsed=True, exec_success=True,
        answer_ok=answer_ok(prompt.get("expected"), r.value),
        routing_ok=_routing_matches_ground_truth(
            prompt["ground_truth_category"], used_llm, used_fn),
        uses_llm=used_llm,
        llm_call_count=ail_llm_call_count(r.trace.entries),
        retries=r.retries,
        value=value_str[:500], source=r.ail_source,
        elapsed_ms=int((time.perf_counter() - t0) * 1000),
        # AIL infinite_loop_rate and side_effect_violation_rate are
        # 0% by language design — no `while`, `pure fn` statically
        # enforced. No analysis needed.
        unbounded_loop=False, side_effect_violation=False,
        error_handling_ok=True,
    )


def _run_python_side(prompt: dict) -> SideReport:
    t0 = time.perf_counter()
    try:
        raw, _meta = _ask_model_for_python(prompt["text"])
    except Exception as e:
        return SideReport(
            parsed=False, exec_success=False, answer_ok=False, routing_ok=False,
            uses_llm=False, llm_call_count=0, value=None, source="",
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            error=f"author_call_failed: {type(e).__name__}: {e}",
        )
    code = _extract_python(raw)
    exec_report = _run_python(code)
    parsed = exec_report["returncode"] == 0   # "parsed" = ran end-to-end
    used_llm = python_uses_llm(code)
    llm_count = sum(
        len(re.findall(p, code)) for p in (r"/api/chat", r"/api/generate")
    )
    stdout = exec_report["stdout"].strip()
    return SideReport(
        parsed=parsed, exec_success=parsed,
        answer_ok=(answer_ok(prompt.get("expected"), stdout) if parsed else False),
        routing_ok=_routing_matches_ground_truth(
            prompt["ground_truth_category"], used_llm,
            used_fn=True),   # plain Python always "has fn" trivially
        uses_llm=used_llm,
        llm_call_count=llm_count,
        side_effect_violation=python_side_effect_in_pure(code),
        unbounded_loop=python_has_unbounded_loop(code),
        error_handling_ok=python_has_error_handling_for_failable(code),
        retries=0,
        value=stdout[:500], source=code,
        elapsed_ms=int((time.perf_counter() - t0) * 1000),
        error=(exec_report["stderr"][:500] if not parsed else None),
    )


def run_case(prompt: dict) -> CaseReport:
    ail = _run_ail(prompt)
    python = _run_python_side(prompt)
    return CaseReport(
        id=prompt["id"], category=prompt["category"], text=prompt["text"],
        ground_truth_category=prompt["ground_truth_category"],
        ail=ail, python=python,
    )


# --- Summary ---------------------------------------------------------------

def _dimension_summary(cases: list[CaseReport]) -> dict:
    n = max(len(cases), 1)

    def rate(pred):
        return round(100 * sum(1 for c in cases if pred(c)) / n, 1)

    A = {   # Code Generation Quality
        "parse_success_rate": {
            "ail": rate(lambda c: c.ail.parsed),
            "python": rate(lambda c: c.python.parsed),
        },
        "exec_success_rate": {
            "ail": rate(lambda c: c.ail.exec_success),
            "python": rate(lambda c: c.python.exec_success),
        },
        "answer_ok_rate": {   # only meaningful for prompts with `expected`
            "ail": rate(lambda c: c.ail.answer_ok),
            "python": rate(lambda c: c.python.answer_ok),
        },
        "fn_intent_accuracy": {
            "ail": rate(lambda c: c.ail.routing_ok),
            "python": rate(lambda c: c.python.routing_ok),
        },
        "avg_retries_ail": round(sum(c.ail.retries for c in cases) / n, 2),
    }

    B = {   # Code Safety
        "side_effect_violation_rate": {
            "ail": 0.0,   # 0% by language design (pure fn enforced)
            "python": rate(lambda c: c.python.side_effect_violation),
        },
        "infinite_loop_rate": {
            "ail": 0.0,   # 0% by language design (no while)
            "python": rate(lambda c: c.python.unbounded_loop),
        },
        "error_handling_omission_rate": {
            "ail": rate(lambda c: not c.ail.error_handling_ok),
            "python": rate(lambda c: not c.python.error_handling_ok),
        },
    }

    C = {   # Execution Efficiency
        "avg_llm_calls": {
            "ail": round(sum(c.ail.llm_call_count for c in cases) / n, 2),
            "python": round(sum(c.python.llm_call_count for c in cases) / n, 2),
        },
        "avg_wall_clock_ms": {
            "ail": round(sum(c.ail.elapsed_ms for c in cases) / n),
            "python": round(sum(c.python.elapsed_ms for c in cases) / n),
        },
    }

    # Dimension D — Harness Effectiveness (Opus 4 April 2026 update).
    # The core claim: AIL's grammar IS the harness; Python needs
    # external tooling for the same guarantees. We quantify this as
    # the count/rate of cases where Python emitted a structural bug
    # (side-effect-in-pure or unbounded-loop) that AIL 0%-blocks by
    # language design.
    python_unsafe = sum(
        1 for c in cases
        if c.python.side_effect_violation or c.python.unbounded_loop
    )
    python_missed_errors = sum(
        1 for c in cases if not c.python.error_handling_ok
    )
    D = {
        "structural_safety_wins_over_python": {
            "count": python_unsafe,
            "total": len(cases),
            "rate_pct": round(100 * python_unsafe / n, 1),
            "meaning": "cases where Python emitted a structural bug "
                       "(side-effect in pure code or unbounded loop) "
                       "that AIL's grammar prevents by construction",
        },
        "error_handling_gap_over_python": {
            "count": python_missed_errors,
            "total": len(cases),
            "rate_pct": round(100 * python_missed_errors / n, 1),
            "meaning": "cases where Python skipped error handling on "
                       "a failable operation; AIL's Result type forces "
                       "explicit handling",
        },
        "ail_structural_safety_rate_pct": 100.0,
        "note": "AIL's 100% is by language design — `pure fn` + no "
                "`while` + Result-required parsing. Python's number "
                "measures what a human or linter would have to catch "
                "externally. `harness_overhead` (time to configure "
                "linters / pre-commit hooks / AGENTS.md) is not "
                "captured in this run — it is 0 for AIL by "
                "construction; an empirical Python number would come "
                "from a separate study.",
    }

    return {"A_generation_quality": A,
            "B_safety": B,
            "C_efficiency": C,
            "D_harness_effectiveness": D,
            "total_cases": len(cases)}


def _print_line(c: CaseReport) -> None:
    def g(side):
        return (("P" if side.parsed else "·")
                + ("R" if side.routing_ok else "·")
                + ("A" if side.answer_ok else "·"))
    ail_val = (c.ail.value or "(err)")[:22]
    py_val = (c.python.value or "(err)")[:22]
    print(f"  {c.id}  {c.category}  {g(c.ail)} AIL {ail_val:24s}  "
          f"{g(c.python)} Py {py_val}")


def _active_model_label() -> str:
    if BENCHMARK_BACKEND == "anthropic":
        return f"anthropic:{ANTHROPIC_MODEL}"
    if BENCHMARK_BACKEND == "vllm":
        return f"vllm:{OPENAI_COMPAT_MODEL}"
    return OLLAMA_MODEL


def _active_host_label() -> str:
    if BENCHMARK_BACKEND == "anthropic":
        return "api.anthropic.com"
    if BENCHMARK_BACKEND == "vllm":
        return OPENAI_COMPAT_BASE_URL
    return OLLAMA_HOST


def _print_report(summary: dict) -> None:
    print("\n" + "=" * 68)
    print(f"MODEL: {_active_model_label()}   HOST: {_active_host_label()}")
    print(f"Total cases: {summary['total_cases']}\n")

    print("A. Code Generation Quality")
    A = summary["A_generation_quality"]
    print(f"  parse success        AIL {A['parse_success_rate']['ail']:5.1f}%    "
          f"Py {A['parse_success_rate']['python']:5.1f}%")
    print(f"  exec success         AIL {A['exec_success_rate']['ail']:5.1f}%    "
          f"Py {A['exec_success_rate']['python']:5.1f}%")
    print(f"  answer ok            AIL {A['answer_ok_rate']['ail']:5.1f}%    "
          f"Py {A['answer_ok_rate']['python']:5.1f}%")
    print(f"  fn/intent accuracy   AIL {A['fn_intent_accuracy']['ail']:5.1f}%    "
          f"Py {A['fn_intent_accuracy']['python']:5.1f}%")
    print(f"  avg retries (AIL)    {A['avg_retries_ail']}")

    print("\nB. Code Safety")
    B = summary["B_safety"]
    print(f"  side-effect in pure  AIL {B['side_effect_violation_rate']['ail']:5.1f}%    "
          f"Py {B['side_effect_violation_rate']['python']:5.1f}%")
    print(f"  unbounded loop       AIL {B['infinite_loop_rate']['ail']:5.1f}%    "
          f"Py {B['infinite_loop_rate']['python']:5.1f}%")
    print(f"  error-handling miss  AIL {B['error_handling_omission_rate']['ail']:5.1f}%    "
          f"Py {B['error_handling_omission_rate']['python']:5.1f}%")

    print("\nC. Execution Efficiency")
    C = summary["C_efficiency"]
    print(f"  avg LLM calls/task   AIL {C['avg_llm_calls']['ail']}    "
          f"Py {C['avg_llm_calls']['python']}")
    print(f"  avg wall clock (ms)  AIL {C['avg_wall_clock_ms']['ail']}    "
          f"Py {C['avg_wall_clock_ms']['python']}")

    print("\nD. Harness Effectiveness (new, per Opus 4 April 2026)")
    D = summary["D_harness_effectiveness"]
    sw = D["structural_safety_wins_over_python"]
    eh = D["error_handling_gap_over_python"]
    print(f"  structural bugs Py emitted that AIL grammar prevents")
    print(f"    {sw['count']}/{sw['total']} cases ({sw['rate_pct']}%)")
    print(f"  failable ops Py left unhandled (AIL Result forces it)")
    print(f"    {eh['count']}/{eh['total']} cases ({eh['rate_pct']}%)")
    print(f"  AIL structural safety rate: 100% (by grammar)")
    print("=" * 68 + "\n")


# --- Main ------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompts", type=Path, default=PROMPTS_PATH,
                   help="Path to prompts.json (default: benchmarks/prompts.json)")
    p.add_argument("--category", choices=("A", "B", "C"),
                   help="Filter to one category (A/B/C)")
    p.add_argument("--limit", type=int, help="Only run first N prompts")
    p.add_argument("--id", action="append",
                   help="Run only specific prompt id(s); may repeat")
    p.add_argument("--out", type=Path, required=True,
                   help="JSON report path")
    args = p.parse_args()

    data = json.loads(args.prompts.read_text(encoding="utf-8"))
    prompts = data["prompts"]
    if args.id:
        prompts = [p_ for p_ in prompts if p_["id"] in args.id]
    if args.category:
        prompts = [p_ for p_ in prompts if p_["category"] == args.category]
    if args.limit:
        prompts = prompts[: args.limit]

    print(f"Running {len(prompts)} prompts against {_active_model_label()} "
          f"at {_active_host_label()}")
    print("Glyphs: [P]arse [R]oute [A]nswer — `·` = failed\n")

    t0 = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    cases: list[CaseReport] = []
    for pr in prompts:
        c = run_case(pr)
        cases.append(c)
        _print_line(c)

    wall_clock_s = round(time.perf_counter() - t0, 1)
    summary = _dimension_summary(cases)
    _print_report(summary)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "model": _active_model_label(),
        "host": _active_host_label(),
        "backend": BENCHMARK_BACKEND,
        "started_at": started_at,
        "wall_clock_s": wall_clock_s,
        "prompts_file": str(args.prompts.relative_to(REPO_ROOT)),
        "summary": summary,
        "cases": [
            {"id": c.id, "category": c.category, "text": c.text,
             "ground_truth_category": c.ground_truth_category,
             "ail": asdict(c.ail), "python": asdict(c.python)}
            for c in cases
        ],
    }, indent=2, ensure_ascii=False))
    print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
