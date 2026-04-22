"""HEAAL Score — compute a single-number readout from a benchmark JSON,
plus a terminal table and an HTML dashboard.

Consumes the benchmark JSON format that `tools/benchmark.py` already
produces. Does not run the benchmark itself — use:

    python tools/heaal_score.py <path-to-benchmark.json> [--html OUT.html]

Formula (weights chosen to be driven by actual measurements rather
than by language-design constants — see docs/heaal.md for rationale):

                                          weight
    Error Explicitness (1 - miss rate)      25%
    Answer Correctness rate                 20%
    No-Silent-Skip rate                     20%
    Parse Success rate                      15%
    Structural Safety (1 - violation)       10%
    Loop Safety (1 - infinite loop rate)     5%
    Observability (grammar-level)            5%

Honest-denominator rule: the four metrics that are *properties of a
program* (error_explicit, no_silent_skip, structural_safe, loop_safe)
plus observability are computed over PARSED programs only. If parse
rate is 0%, those rates are 0% — there are no programs to be safe.
This prevents vacuous-truth scores when a model fails to author any
valid AIL but the language-design constants would otherwise inflate
the score.

Parse Success and Answer Correctness use the full denominator (N) —
they measure authoring success per attempt, not per parsed program.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ---------- metric computation ----------

WEIGHTS = {
    "error_explicit":     0.25,
    "answer_correct":     0.20,
    "no_silent_skip":     0.20,
    "parse_success":      0.15,
    "structural_safe":    0.10,
    "loop_safe":          0.05,
    "observability":      0.05,
}


def _pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 0.0


def _side_metrics(cases: list[dict], side: str, *, language: str) -> dict[str, Any]:
    """Compute the seven HEAAL Score inputs from one side of the cases list."""
    n = len(cases)
    if n == 0:
        return {}

    parsed = sum(1 for c in cases if c[side].get("parsed"))
    answered = sum(1 for c in cases if c[side].get("answer_ok"))

    # Honest-denominator rule: properties below apply only to programs
    # that actually exist (parsed=True). Counting them over N when
    # parse rate is 0 produces vacuous-truth inflation (a model that
    # writes nothing scores 100% safe — there is nothing to be unsafe).
    parsed_cases = [c for c in cases if c[side].get("parsed")]

    # Error handling: applicable when a parsed program contains a failable
    # op. error_handling_ok=True → explicit, False → missing, None → not
    # applicable. Denominator is parsed programs that have applicable cases.
    eh_applicable = [c for c in parsed_cases
                     if c[side].get("error_handling_ok") is not None]
    eh_explicit   = sum(1 for c in eh_applicable
                        if c[side].get("error_handling_ok"))

    # Silent skip: B/C category prompts (judgment required) where the
    # parsed program never called the LLM. Denominator is parsed B/C cases.
    silent_eligible = [c for c in parsed_cases
                       if c.get("category") in ("B", "C")]
    silent_skipped  = sum(1 for c in silent_eligible
                          if not c[side].get("uses_llm"))

    # Structural / loop safety: properties of a parsed program. Denominator
    # is parsed cases. If parse rate is 0, both rates are 0 (no programs
    # exist to satisfy the property).
    structural_viol = sum(1 for c in parsed_cases
                          if c[side].get("side_effect_violation"))
    loops           = sum(1 for c in parsed_cases
                          if c[side].get("unbounded_loop"))

    # Observability: AIL's runtime emits trace + provenance for every
    # program that runs. The claim is grammar-level but applies only to
    # programs that actually ran. Zero parsed programs → zero
    # observability earned (nothing was observed).
    if language == "ail" and parsed > 0:
        observability_rate = 100.0
    else:
        observability_rate = 0.0

    m = {
        "error_explicit":  _pct(eh_explicit, len(eh_applicable)),
        "answer_correct":  _pct(answered, n),
        "no_silent_skip":  _pct(len(silent_eligible) - silent_skipped,
                                len(silent_eligible)),
        "parse_success":   _pct(parsed, n),
        "structural_safe": _pct(parsed - structural_viol, parsed),
        "loop_safe":       _pct(parsed - loops, parsed),
        "observability":   observability_rate,
    }
    m["score"] = round(sum(m[k] * w for k, w in WEIGHTS.items()), 1)
    m["_raw"] = {
        "total": n,
        "parsed": parsed,
        "answered": answered,
        "eh_applicable": len(eh_applicable),
        "eh_explicit": eh_explicit,
        "silent_eligible": len(silent_eligible),
        "silent_skipped": silent_skipped,
        "structural_violations": structural_viol,
        "loops": loops,
    }
    return m


def compute(data: dict) -> dict:
    cases = data.get("cases", [])
    return {
        "ail":    _side_metrics(cases, "ail",    language="ail"),
        "python": _side_metrics(cases, "python", language="python"),
        "meta": {
            "model": data.get("model", "unknown"),
            "host":  data.get("host"),
            "prompts_file": data.get("prompts_file"),
            "total_cases":  len(cases),
        },
    }


# ---------- terminal ----------

_ROW_LABELS = [
    ("error_explicit",  "Error Explicitness",  "%"),
    ("answer_correct",  "Answer Correctness",  "%"),
    ("no_silent_skip",  "No Silent-Skip rate", "%"),
    ("parse_success",   "Parse Success",       "%"),
    ("structural_safe", "Structural Safety",   "%"),
    ("loop_safe",       "Loop Safety",         "%"),
    ("observability",   "Observability",       "%"),
]


def emit_terminal(score: dict) -> str:
    meta = score["meta"]
    ail, py = score["ail"], score["python"]
    lines = [
        "",
        f"HEAAL Score — AIL vs Python  (model: {meta['model']}, N={meta['total_cases']})",
        "=" * 72,
        f"{'':<28}{'AIL':>10}{'Python':>12}   weight",
        "-" * 72,
    ]
    for key, label, unit in _ROW_LABELS:
        a = ail.get(key, 0.0)
        p = py.get(key, 0.0)
        w = WEIGHTS[key]
        lines.append(f"{label:<28}{a:>9.0f}{unit}{p:>10.0f}{unit}   {int(w*100)}%")
    lines += [
        "-" * 72,
        f"{'HEAAL Score':<28}{ail.get('score', 0):>9.1f} {py.get('score', 0):>11.1f}",
        "=" * 72,
        "",
    ]
    return "\n".join(lines)


# ---------- HTML ----------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>HEAAL Score — AIL vs Python</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #fafafa; color: #1f2937; margin: 0; padding: 40px 20px;
  }}
  .card {{
    max-width: 880px; margin: 0 auto; background: #fff;
    border-radius: 16px; padding: 40px 48px;
    box-shadow: 0 2px 24px rgba(0,0,0,0.06);
  }}
  h1 {{ font-size: 14px; font-weight: 600; letter-spacing: 0.1em;
       text-transform: uppercase; color: #6b7280; margin: 0; }}
  .meta {{ color: #9ca3af; font-size: 13px; margin-top: 4px; }}
  .scores {{ display: flex; gap: 32px; margin: 32px 0 40px 0;
             align-items: flex-end; }}
  .score-box {{ flex: 1; }}
  .score-box .label {{ font-size: 13px; font-weight: 600;
                       text-transform: uppercase; letter-spacing: 0.08em; }}
  .score-box .num {{ font-size: 72px; font-weight: 800; line-height: 1;
                     margin-top: 6px; }}
  .ail .label, .ail .num {{ color: #16a34a; }}
  .py  .label, .py  .num {{ color: #6b7280; }}
  .delta {{ font-size: 22px; font-weight: 700; color: #16a34a;
            padding-bottom: 12px; }}
  .chart {{ margin: 14px 0; }}
  .chart .row {{ display: flex; align-items: center; font-size: 14px; margin: 8px 0; }}
  .chart .name {{ width: 220px; color: #374151; }}
  .chart .bars {{ flex: 1; display: flex; flex-direction: column; gap: 4px; }}
  .chart .bar-row {{ display: flex; align-items: center; gap: 8px; }}
  .chart .bar {{ height: 14px; border-radius: 4px; }}
  .chart .bar.ail {{ background: #16a34a; }}
  .chart .bar.py  {{ background: #9ca3af; }}
  .chart .val {{ font-variant-numeric: tabular-nums; font-size: 12px;
                 color: #4b5563; width: 48px; text-align: right; }}
  .chart .weight {{ font-size: 11px; color: #9ca3af; width: 48px;
                    text-align: right; }}
  .footer {{ margin-top: 32px; padding-top: 20px; border-top: 1px solid #e5e7eb;
             font-size: 12px; color: #6b7280; line-height: 1.6; }}
  .footer code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
  a {{ color: #16a34a; }}
</style>
</head>
<body>
<div class="card">
  <h1>HEAAL Score</h1>
  <div class="meta">{model} &middot; {total_cases} tasks &middot; {prompts_file}</div>

  <div class="scores">
    <div class="score-box ail">
      <div class="label">AIL (<code>ail ask</code>)</div>
      <div class="num">{ail_score}</div>
    </div>
    <div class="delta">+{delta}</div>
    <div class="score-box py">
      <div class="label">Python (no harness)</div>
      <div class="num">{py_score}</div>
    </div>
  </div>

  <div class="chart">
    {rows}
  </div>

  <div class="footer">
    AIL is the <a href="https://github.com/hyun06000/AIL">Harness-Engineering-As-A-Language</a>
    reference implementation.
    The grammar itself is the harness — no linters, no AGENTS.md, no post-generation validators.
    Weights favor live measurements: error-handling, execution, silent-skip prevention
    are 65% of the score; structural-safety / loop-safety / observability together
    anchor the remaining 20% as language-level claims.
  </div>
</div>
</body>
</html>
"""


_ROW_TEMPLATE = """
    <div class="row">
      <div class="name">{label}</div>
      <div class="bars">
        <div class="bar-row">
          <div class="bar ail" style="width: {ail_pct}%"></div>
          <div class="val">{ail_val}</div>
        </div>
        <div class="bar-row">
          <div class="bar py" style="width: {py_pct}%"></div>
          <div class="val">{py_val}</div>
        </div>
      </div>
      <div class="weight">{weight}%</div>
    </div>
"""


def emit_html(score: dict) -> str:
    meta = score["meta"]
    ail, py = score["ail"], score["python"]
    rows_html = ""
    for key, label, unit in _ROW_LABELS:
        a = ail.get(key, 0.0)
        p = py.get(key, 0.0)
        rows_html += _ROW_TEMPLATE.format(
            label=label,
            ail_pct=max(a, 0), py_pct=max(p, 0),
            ail_val=f"{a:.0f}{unit}", py_val=f"{p:.0f}{unit}",
            weight=int(WEIGHTS[key] * 100),
        )
    ail_score = ail.get("score", 0)
    py_score = py.get("score", 0)
    return _HTML_TEMPLATE.format(
        model=meta["model"] or "unknown",
        total_cases=meta["total_cases"],
        prompts_file=(meta.get("prompts_file") or "").split("/")[-1] or "corpus",
        ail_score=f"{ail_score:.0f}",
        py_score=f"{py_score:.0f}",
        delta=f"{ail_score - py_score:.0f}",
        rows=rows_html,
    )


# ---------- CLI ----------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("json_path", type=Path,
                   help="benchmark result JSON produced by tools/benchmark.py")
    p.add_argument("--html", type=Path, default=None,
                   help="also write an HTML dashboard to this path")
    p.add_argument("--json-out", type=Path, default=None,
                   help="also write the computed score as JSON to this path")
    args = p.parse_args()

    data = json.loads(args.json_path.read_text(encoding="utf-8"))
    score = compute(data)
    print(emit_terminal(score))

    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(emit_html(score), encoding="utf-8")
        print(f"wrote {args.html}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(score, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        print(f"wrote {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
