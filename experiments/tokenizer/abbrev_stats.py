#!/usr/bin/env python3
"""축약 통계 실측 — 사이클 ail-grammar-skeleton/abbrev-stats s2 plan 고정분.

식별자 120개 × 축약 2종 × 토크나이저 5계열 + 키워드 40쌍.
출력: 통계 markdown(stdout) + 차트 PNG 2장 (docs/research/assets/).
"""
import os, statistics, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "docs", "research", "assets")
os.makedirs(OUT, exist_ok=True)

import tiktoken
from tokenizers import Tokenizer

TOKS = {}
TOKS["o200k"] = lambda s, e=tiktoken.get_encoding("o200k_base"): len(e.encode(s))
TOKS["cl100k"] = lambda s, e=tiktoken.get_encoding("cl100k_base"): len(e.encode(s))
for name, fn in [("qwen2.5", "qwen25coder.json"), ("deepseek", "deepseekv3.json"), ("phi3", "phi3.json")]:
    t = Tokenizer.from_file(os.path.join(HERE, "tokenizers", fn))
    TOKS[name] = lambda s, t=t: len(t.encode(s).ids)

# ── 표본 생성: 흔한 프로그래밍 어휘 풀 → 2~3어 camelCase 120개 ──
VERBS = ["fetch", "parse", "update", "delete", "create", "validate", "render", "handle", "compute", "schedule"]
NOUNS = ["user", "profile", "request", "response", "token", "session", "message", "config", "payment", "schema",
         "buffer", "channel", "cluster", "document", "template"]
TAILS = ["count", "result", "status", "handler", "manager", "timeout", "index", "cache"]

def camel(words):
    return words[0] + "".join(w.capitalize() for w in words[1:])

pairs2 = [camel([v, n]) for v, n in itertools.product(VERBS[:8], NOUNS[:9])][:72]
pairs3 = [camel([v, n, t]) for v, n, t in zip(VERBS * 5, NOUNS * 4, TAILS * 7)][:48]
IDENTS = (pairs2 + pairs3)[:120]

def devowel(word):  # 첫 글자는 남기고 모음 제거 (usrProf 방식)
    parts, cur = [], ""
    for ch in word:
        if ch.isupper() and cur:
            parts.append(cur); cur = ch
        else:
            cur += ch
    parts.append(cur)
    out = []
    for p in parts:
        out.append(p[0] + "".join(c for c in p[1:] if c.lower() not in "aeiou"))
    return "".join(out)

def truncate(word, n=3):  # 어절별 앞 3자 절단 (fchUsr 방식)
    parts, cur = [], ""
    for ch in word:
        if ch.isupper() and cur:
            parts.append(cur); cur = ch
        else:
            cur += ch
    parts.append(cur)
    return "".join(p[:n].capitalize() if i else p[:n] for i, p in enumerate(parts))

# ── 키워드 40쌍 (온전형, 축약형) ──
KEYWORDS = [("intent", "itt"), ("goal", "gl"), ("forbid", "fbd"), ("budget", "bgt"), ("achieve", "achv"),
            ("observe", "obsv"), ("effect", "eff"), ("retry", "rty"), ("timeout", "tmo"), ("failure", "flr"),
            ("success", "scs"), ("declare", "dcl"), ("require", "req"), ("provide", "prv"), ("consume", "csm"),
            ("branch", "brn"), ("verify", "vrf"), ("measure", "msr"), ("record", "rcd"), ("expose", "xps"),
            ("string", "str"), ("number", "num"), ("index", "idx"), ("config", "cfg"), ("context", "ctx"),
            ("pointer", "ptr"), ("buffer", "buf"), ("argument", "arg"), ("parameter", "param"), ("variable", "var"),
            ("function", "func"), ("initialize", "init"), ("maximum", "max"), ("minimum", "min"), ("temporary", "tmp"),
            ("source", "src"), ("destination", "dst"), ("directory", "dir"), ("command", "cmd"), ("length", "len")]

def tok_avg(s):
    return {n: f(s) for n, f in TOKS.items()}

def main():
    rows = []
    for ident in IDENTS:
        for kind, ab in [("devowel", devowel(ident)), ("trunc", truncate(ident))]:
            full_t, ab_t = tok_avg(ident), tok_avg(ab)
            rows.append({"full": ident, "abbrev": ab, "kind": kind,
                         "char_saved": len(ident) - len(ab),
                         "delta": {n: ab_t[n] - full_t[n] for n in TOKS},
                         "full_t": full_t, "ab_t": ab_t})
    kw_rows = []
    for full, ab in KEYWORDS:
        full_t, ab_t = tok_avg(full), tok_avg(ab)
        kw_rows.append({"full": full, "abbrev": ab,
                        "delta": {n: ab_t[n] - full_t[n] for n in TOKS},
                        "full_t": full_t, "ab_t": ab_t})

    names = list(TOKS)
    # 통계
    print("## 식별자 120개 × 축약 2종 × 5계열 (총 %d 실측)\n" % (len(rows) * len(names)))
    for kind in ["devowel", "trunc"]:
        sub = [r for r in rows if r["kind"] == kind]
        deltas = [r["delta"][n] for r in sub for n in names]
        saved = sum(1 for d in deltas if d < 0); same = sum(1 for d in deltas if d == 0); worse = sum(1 for d in deltas if d > 0)
        print(f"### {kind} (모음 제거)" if kind == "devowel" else f"### {kind} (3자 절단)")
        print(f"- 평균 문자 절약: {statistics.mean(r['char_saved'] for r in sub):.1f}자")
        print(f"- 토큰 변화 중앙값 {statistics.median(deltas):+.0f}, 평균 {statistics.mean(deltas):+.2f}")
        print(f"- 절약된 경우 {saved}/{len(deltas)} ({100*saved/len(deltas):.0f}%), 동일 {same} ({100*same/len(deltas):.0f}%), 악화 {worse} ({100*worse/len(deltas):.0f}%)")
        for n in names:
            ds = [r["delta"][n] for r in sub]
            print(f"  - {n}: 중앙값 {statistics.median(ds):+.0f}, 악화율 {100*sum(1 for d in ds if d>0)/len(ds):.0f}%")
        print()
    kw_deltas = [r["delta"][n] for r in kw_rows for n in names]
    kw_saved = sum(1 for d in kw_deltas if d < 0)
    print("## 키워드 40쌍 × 5계열\n")
    print(f"- 토큰 변화 중앙값 {statistics.median(kw_deltas):+.0f}, 절약 {100*kw_saved/len(kw_deltas):.0f}%, 악화 {100*sum(1 for d in kw_deltas if d>0)/len(kw_deltas):.0f}%")
    ok = [(r['full'], r['abbrev']) for r in kw_rows if statistics.median([r['delta'][n] for n in names]) < 0]
    print(f"- 중앙값 기준 절약되는 축약(어휘에 실재): {', '.join(f'{f}→{a}' for f, a in ok)}")

    # 차트
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.size"] = 11

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, kind, title in [(axes[0], "devowel", "vowel-removed (usrProf style)"),
                            (axes[1], "trunc", "3-char truncated (fchUsr style)")]:
        sub = [r for r in rows if r["kind"] == kind]
        deltas = [r["delta"][n] for r in sub for n in names]
        lo, hi = min(deltas), max(deltas)
        ax.hist(deltas, bins=range(lo, hi + 2), color="#d62728" if statistics.median(deltas) >= 0 else "#2ca02c",
                edgecolor="white", align="left")
        ax.axvline(0, color="black", lw=1)
        ax.axvline(statistics.median(deltas), color="blue", lw=2, ls="--", label=f"median {statistics.median(deltas):+.0f}")
        ax.set_title(f"{title}\nΔtokens = abbrev − full  (n={len(deltas)})")
        ax.set_xlabel("token delta (— saves | + costs)"); ax.set_ylabel("count"); ax.legend()
    fig.suptitle("Does abbreviation save tokens? 120 identifiers × 5 tokenizers", y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "abbrev-hist.png"), dpi=110, bbox_inches="tight")

    fig2, ax = plt.subplots(figsize=(7.5, 5.5))
    xs = [r["char_saved"] for r in rows]
    ys = [statistics.mean(r["delta"][n] for n in names) for r in rows]
    colors = ["#d62728" if y > 0 else ("#2ca02c" if y < 0 else "#7f7f7f") for y in ys]
    ax.scatter(xs, ys, c=colors, alpha=0.6, s=28)
    ax.axhline(0, color="black", lw=1)
    ax.set_xlabel("characters saved by abbreviation")
    ax.set_ylabel("mean token delta across 5 tokenizers")
    ax.set_title("Characters saved vs tokens paid — every point above 0 pays MORE tokens\n(240 abbreviated identifiers)")
    fig2.tight_layout()
    fig2.savefig(os.path.join(OUT, "abbrev-scatter.png"), dpi=110, bbox_inches="tight")
    print("\n차트 저장: docs/research/assets/abbrev-hist.png, abbrev-scatter.png")

if __name__ == "__main__":
    main()
