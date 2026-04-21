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
import re
import subprocess
import sys
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
        print(f"\n  [{pr['id']}] {pr['category']:<22}  ", end="", flush=True)
        r = run_case(pr, adapter)
        results.append(r)
        if r["score"]["ok"]:
            print(f"✅ retries={r['ail']['retries']} t={r['ail']['elapsed_ms']}ms")
        else:
            print(f"❌ {r['score']['reason'][:100]}")

    # Summary
    n = len(results)
    passed = sum(1 for r in results if r["score"]["ok"])
    parsed = sum(1 for r in results if r["ail"]["source"] and not r["ail"]["error"])
    tot_retries = sum(r["ail"]["retries"] for r in results)
    tot_author_ptok = sum(r["ail"]["author_prompt_tokens"] for r in results)
    tot_author_ctok = sum(r["ail"]["author_completion_tokens"] for r in results)
    print("\n=== E2 SUMMARY ===")
    print(f"  tasks passed:          {passed}/{n}  ({passed/n*100:.0f}%)")
    print(f"  programs completed:    {parsed}/{n}  (no authoring error)")
    print(f"  avg retries:           {tot_retries/n:.2f}")
    print(f"  total author tokens:   prompt={tot_author_ptok}  completion={tot_author_ctok}")

    out = {
        "corpus": "heaal_e2",
        "model": os.environ.get("ANTHROPIC_MODEL") or os.environ.get("AIL_OPENAI_COMPAT_MODEL") or os.environ.get("AIL_OLLAMA_MODEL"),
        "author_prompt_variant": os.environ.get("AIL_AUTHOR_PROMPT_VARIANT", "default"),
        "summary": {
            "total": n,
            "passed": passed,
            "programs_completed": parsed,
            "avg_retries": tot_retries / n,
            "total_author_prompt_tokens": tot_author_ptok,
            "total_author_completion_tokens": tot_author_ctok,
        },
        "cases": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
