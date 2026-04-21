"""HEAAL E2 runner — long tasks with effects.

For each prompt in prompts.json, invokes `ail ask` (via the ail.ask
Python API) with the configured authoring backend + anti_python prompt
variant, captures the AIL source the author emits, runs it (which
includes real http.get / file.read / file.write effect calls), and
scores the outcome against the prompt's expected_* declarations.

Usage:
    AIL_AUTHOR_PROMPT_VARIANT=anti_python \
    BENCHMARK_BACKEND=anthropic \
    ANTHROPIC_MODEL=claude-sonnet-4-5 \
    python benchmarks/heaal_e2/run_e2.py --out docs/benchmarks/2026-04-22_heaal_E2.json

Always run benchmarks/heaal_e2/setup_fixtures.py first (this runner
calls it automatically via --setup).
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
REF_IMPL = ROOT / "reference-impl"
sys.path.insert(0, str(REF_IMPL))

from ail import _load_dotenv_if_present, AuthoringError  # noqa: E402
from ail.authoring import ask  # noqa: E402

_load_dotenv_if_present()


def _load_anthropic_adapter():
    import os
    backend = os.environ.get("BENCHMARK_BACKEND", "ollama").lower()
    if backend == "anthropic":
        try:
            import anthropic  # noqa: F401
            from ail.runtime.anthropic_adapter import AnthropicAdapter
        except ImportError:
            sys.exit("BENCHMARK_BACKEND=anthropic but anthropic package missing. "
                     "Install 'ail-interpreter[anthropic]'.")
        return AnthropicAdapter(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
    return None  # default (ollama/openai_compat) will be used by ask()


def score(prompt: dict, value: Any, err: str | None) -> dict:
    if err:
        return {"ok": False, "reason": f"runtime_error: {err[:200]}"}
    val_str = "" if value is None else str(value)
    reasons_failed = []

    if "expected_exact" in prompt:
        got = val_str.strip()
        want = prompt["expected_exact"]
        match = got == want
        if not match:
            # Numeric tolerance: 78 and 78.0 should both satisfy "78".
            try:
                if float(got) == float(want):
                    match = True
            except ValueError:
                pass
        # Case-insensitive tolerance for short plain-word answers like "done".
        if not match and len(want) <= 12 and got.lower() == want.lower():
            match = True
        if not match:
            reasons_failed.append(
                f"expected_exact: got {got[:80]!r}, "
                f"expected {want!r}")
    if "expected_contains" in prompt:
        if prompt["expected_contains"] not in val_str:
            reasons_failed.append(
                f"expected_contains: {prompt['expected_contains']!r} not in "
                f"{val_str[:120]!r}")
    if "expected_pattern" in prompt:
        if not re.search(prompt["expected_pattern"], val_str):
            reasons_failed.append(
                f"expected_pattern: /{prompt['expected_pattern']}/ "
                f"did not match {val_str[:120]!r}")

    # File verifications — each needs the file to exist and satisfy its check
    for key in ("verify_file", "verify_files"):
        if key not in prompt:
            continue
        checks = prompt[key] if isinstance(prompt[key], list) else [prompt[key]]
        for check in checks:
            p = Path(check["path"])
            if not p.exists():
                reasons_failed.append(f"verify_file: {p} does not exist")
                continue
            content = p.read_text(encoding="utf-8", errors="replace")
            if "contains" in check and check["contains"] not in content:
                reasons_failed.append(
                    f"verify_file {p}: missing {check['contains']!r}")
            if "pattern" in check and not re.search(check["pattern"], content):
                reasons_failed.append(
                    f"verify_file {p}: pattern /{check['pattern']}/ not found")
            if "min_lines" in check:
                nonempty = [l for l in content.splitlines() if l.strip()]
                if len(nonempty) < check["min_lines"]:
                    reasons_failed.append(
                        f"verify_file {p}: only {len(nonempty)} non-empty "
                        f"lines, wanted ≥ {check['min_lines']}")

    if reasons_failed:
        return {"ok": False, "reason": " | ".join(reasons_failed)}

    # When the prompt only has expected_kind (judgment-based), we accept any
    # non-empty string — scoring is best-effort for E2 subjective tasks.
    if "expected_kind" in prompt and not (
            "expected_exact" in prompt or "expected_contains" in prompt
            or "expected_pattern" in prompt):
        if not val_str.strip():
            return {"ok": False, "reason": "empty value for judgment task"}

    return {"ok": True}


# -------------------------------------------------------------------
# Python-side authoring + execution (for the no-harness comparison)
# -------------------------------------------------------------------

_PY_PROMPT_TEMPLATE = """You are a Python programmer. Write a single Python 3 \
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
sorting, searching, file I/O), write plain Python — do NOT call the \
API for that. File paths referenced in the task are real and the \
program runs on a machine where they exist.

Print ONLY the final answer to stdout on the LAST line. Any file \
writes that the task asks for must happen as side effects before \
that final print. No markdown fences, no prose.

TASK:
%(task)s
"""


def _anthropic_client():
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic package required for Python-side generation")
    return anthropic.Anthropic(), os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")


def ask_python(task: str) -> tuple[str, dict]:
    client, model = _anthropic_client()
    resp = client.messages.create(
        model=model, max_tokens=1024, temperature=0.0,
        messages=[{"role": "user",
                   "content": _PY_PROMPT_TEMPLATE % {"model": model, "task": task}}],
    )
    text = resp.content[0].text if resp.content else ""
    # Strip any fences the model emitted despite the instruction
    text = re.sub(r"^```(?:python)?\s*\n", "", text.strip())
    text = re.sub(r"\n```\s*$", "", text)
    return text, {
        "prompt_tokens": resp.usage.input_tokens,
        "completion_tokens": resp.usage.output_tokens,
    }


def run_python(code: str, timeout: int = 60) -> dict:
    d = tempfile.mkdtemp(prefix="heaal_e2_py_")
    path = os.path.join(d, "prog.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([sys.executable, path],
                           capture_output=True, text=True, timeout=timeout)
        return {"returncode": r.returncode, "stdout": r.stdout,
                "stderr": r.stderr, "timed_out": False,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
    except subprocess.TimeoutExpired as e:
        return {"returncode": -1, "stdout": e.stdout or "",
                "stderr": (e.stderr or "") + f"\n[TIMEOUT {timeout}s]",
                "timed_out": True,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}


# Heuristics for safety-property analysis on Python source
_PY_FAILABLE_PATTERNS = (
    r"\bint\s*\(", r"\bfloat\s*\(", r"\bopen\s*\(",
    r"urllib\.request\.", r"\bjson\.loads\s*\(",
)

def python_lacks_error_handling(code: str) -> bool:
    """True if the program uses any failable operation without a try/except.

    Matches the measurement used in the AIL-track benchmark.py:
    at least one failable call appears outside any `try:` block.
    """
    if not any(re.search(p, code) for p in _PY_FAILABLE_PATTERNS):
        return False  # no failable ops at all
    # Strip out try blocks (naive but effective at this scale)
    stripped = re.sub(r"try\s*:[\s\S]*?except[^\n]*:[\s\S]*?(?=\n\S|\Z)",
                      "", code)
    return any(re.search(p, stripped) for p in _PY_FAILABLE_PATTERNS)


def python_calls_llm(code: str) -> bool:
    return bool(re.search(r"urllib\.request|anthropic|api\.anthropic\.com", code))


def score_python(prompt: dict, stdout: str, stderr: str, returncode: int, timed_out: bool) -> dict:
    if timed_out:
        return {"ok": False, "reason": "python_timeout"}
    if returncode != 0:
        short = (stderr or "").strip().splitlines()[-1:] if stderr else [""]
        return {"ok": False, "reason": f"python_crash (rc={returncode}): {short[0][:120]}"}
    # stdout last non-empty line is "the answer"
    lines = [l for l in stdout.strip().splitlines() if l.strip()]
    value = lines[-1] if lines else ""
    # Reuse score() with the captured value
    return score(prompt, value, err=None)


def run_python_side(prompt: dict) -> dict:
    t0 = time.monotonic()
    try:
        code, toks = ask_python(prompt["text"])
    except Exception as e:
        return {
            "source": "", "value": None,
            "returncode": None, "stdout": "", "stderr": "",
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
            "author_prompt_tokens": 0, "author_completion_tokens": 0,
            "error_handling_missing": False,
            "uses_llm": False,
            "score": {"ok": False, "reason": f"python_authoring: {e}"},
        }
    exec_r = run_python(code)
    s = score_python(prompt, exec_r["stdout"], exec_r["stderr"],
                     exec_r["returncode"], exec_r["timed_out"])
    lines = [l for l in exec_r["stdout"].strip().splitlines() if l.strip()]
    value = lines[-1] if lines else ""
    return {
        "source": code,
        "value": value,
        "returncode": exec_r["returncode"],
        "stdout_tail": exec_r["stdout"][-500:],
        "stderr_tail": exec_r["stderr"][-500:],
        "elapsed_ms": exec_r["elapsed_ms"],
        "timed_out": exec_r["timed_out"],
        "author_prompt_tokens": toks.get("prompt_tokens", 0),
        "author_completion_tokens": toks.get("completion_tokens", 0),
        "error_handling_missing": python_lacks_error_handling(code),
        "uses_llm": python_calls_llm(code),
        "score": s,
    }


def run_case(prompt: dict, adapter) -> dict:
    t0 = time.monotonic()
    source = ""
    value = None
    err = None
    retries = 0
    author_toks = (0, 0)
    try:
        res = ask(prompt["text"], adapter=adapter, max_retries=3)
        source = res.ail_source
        value = res.value
        retries = res.retries
        author_toks = (res.author_prompt_tokens, res.author_completion_tokens)
    except AuthoringError as e:
        err = f"AuthoringError: {e}"
        if e.partial is not None:
            source = e.partial.ail_source or ""
            retries = e.partial.retries
            author_toks = (e.partial.author_prompt_tokens,
                           e.partial.author_completion_tokens)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    s = score(prompt, value, err)
    return {
        "id": prompt["id"],
        "category": prompt["category"],
        "effects_declared": prompt.get("effects", []),
        "text": prompt["text"],
        "ail": {
            "source": source,
            "value": value if isinstance(value, (str, int, float, bool, list, dict)) or value is None else str(value),
            "retries": retries,
            "error": err,
            "elapsed_ms": elapsed_ms,
            "author_prompt_tokens": author_toks[0],
            "author_completion_tokens": author_toks[1],
        },
        "score": s,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompts", type=Path,
                   default=Path(__file__).parent / "prompts.json")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--skip-setup", action="store_true",
                   help="Do not re-run setup_fixtures.py")
    p.add_argument("--only", type=str, default=None,
                   help="Run only tasks whose id matches this substring")
    args = p.parse_args()

    if not args.skip_setup:
        setup = Path(__file__).parent / "setup_fixtures.py"
        subprocess.check_call([sys.executable, str(setup)])

    data = json.loads(args.prompts.read_text(encoding="utf-8"))
    prompts = data["prompts"]
    if args.only:
        prompts = [pr for pr in prompts if args.only in pr["id"]]

    adapter = _load_anthropic_adapter()

    import os
    print(f"HEAAL E2 — {len(prompts)} prompts | backend={os.environ.get('BENCHMARK_BACKEND', 'default')} | "
          f"variant={os.environ.get('AIL_AUTHOR_PROMPT_VARIANT', 'default')}")
    results = []
    for pr in prompts:
        print(f"\n  [{pr['id']}] {pr['category']:<22}")

        # AIL side — reset fixtures + output dir before each case
        subprocess.check_call([sys.executable, str(Path(__file__).parent / "setup_fixtures.py")],
                              stdout=subprocess.DEVNULL)
        r = run_case(pr, adapter)
        ail_mark = "✅" if r["score"]["ok"] else "❌"
        print(f"      AIL    {ail_mark} retries={r['ail']['retries']} t={r['ail']['elapsed_ms']}ms")
        if not r["score"]["ok"]:
            print(f"             reason: {r['score']['reason'][:110]}")

        # Python side — reset fixtures again so the Python sees pristine inputs
        subprocess.check_call([sys.executable, str(Path(__file__).parent / "setup_fixtures.py")],
                              stdout=subprocess.DEVNULL)
        py = run_python_side(pr)
        py_mark = "✅" if py["score"]["ok"] else "❌"
        print(f"      Python {py_mark} t={py['elapsed_ms']}ms  err_handling_missing={py['error_handling_missing']}  uses_llm={py['uses_llm']}")
        if not py["score"]["ok"]:
            print(f"             reason: {py['score']['reason'][:110]}")
        r["python"] = py
        results.append(r)

    # Summary — both sides
    n = len(results)
    ail_passed = sum(1 for r in results if r["score"]["ok"])
    py_passed = sum(1 for r in results if r["python"]["score"]["ok"])
    ail_parsed = sum(1 for r in results if r["ail"]["source"] and not r["ail"]["error"])
    py_ran = sum(1 for r in results if r["python"]["returncode"] == 0)
    ail_retries = sum(r["ail"]["retries"] for r in results)
    ail_ptok = sum(r["ail"]["author_prompt_tokens"] for r in results)
    ail_ctok = sum(r["ail"]["author_completion_tokens"] for r in results)
    py_ptok = sum(r["python"]["author_prompt_tokens"] for r in results)
    py_ctok = sum(r["python"]["author_completion_tokens"] for r in results)
    py_err_miss = sum(1 for r in results if r["python"]["error_handling_missing"])
    py_used_llm = sum(1 for r in results if r["python"]["uses_llm"])
    needs_judgment = sum(1 for p in prompts if "intent" in p["category"] or p["category"] == "research_style" or "intent" in str(p.get("effects", [])))

    print("\n=== E2 SUMMARY — AIL vs Python side-by-side (same Sonnet, no external harness) ===")
    print(f"  tasks passed          : AIL {ail_passed}/{n}   Python {py_passed}/{n}")
    print(f"  programs completed    : AIL {ail_parsed}/{n}   Python {py_ran}/{n} (rc==0)")
    print(f"  avg retries (AIL only): {ail_retries/n:.2f}")
    print(f"  Python err-handling missing: {py_err_miss}/{n}  ({py_err_miss/n*100:.0f}%)")
    print(f"  Python calls LLM      : {py_used_llm}/{n}")
    print(f"  author tokens (AIL)   : prompt={ail_ptok}  completion={ail_ctok}")
    print(f"  author tokens (Py)    : prompt={py_ptok}  completion={py_ctok}")

    out = {
        "corpus": "heaal_e2",
        "model": os.environ.get("ANTHROPIC_MODEL") or os.environ.get("AIL_OPENAI_COMPAT_MODEL") or os.environ.get("AIL_OLLAMA_MODEL"),
        "author_prompt_variant": os.environ.get("AIL_AUTHOR_PROMPT_VARIANT", "default"),
        "summary": {
            "total": n,
            "ail_passed": ail_passed,
            "python_passed": py_passed,
            "ail_programs_completed": ail_parsed,
            "python_programs_completed": py_ran,
            "avg_retries_ail": ail_retries / n,
            "python_error_handling_missing": py_err_miss,
            "python_calls_llm": py_used_llm,
            "ail_author_prompt_tokens": ail_ptok,
            "ail_author_completion_tokens": ail_ctok,
            "python_author_prompt_tokens": py_ptok,
            "python_author_completion_tokens": py_ctok,
        },
        "cases": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
