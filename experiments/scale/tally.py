#!/usr/bin/env python3
"""확대 실험 집계 — 50 생성물 × 5계열 토큰 + AIL 통과율(ail-check)."""
import os, statistics, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
import tiktoken
from tokenizers import Tokenizer
TOKS = {}
TOKS["o200k"] = lambda s, e=tiktoken.get_encoding("o200k_base"): len(e.encode(s))
TOKS["cl100k"] = lambda s, e=tiktoken.get_encoding("cl100k_base"): len(e.encode(s))
for name, fn in [("qwen2.5", "qwen25coder.json"), ("deepseek", "deepseekv3.json"), ("phi3", "phi3.json")]:
    t = Tokenizer.from_file(os.path.join(HERE, "..", "tokenizer", "tokenizers", fn))
    TOKS[name] = lambda s, t=t: len(t.encode(s).ids)

LANGS = ["python", "go", "c", "js", "ail"]
PROBS = [f"P{i}" for i in range(1, 11)]
CHECK = os.path.join(HERE, "..", "..", "parser", "target", "debug", "ail-check")

means = {l: [] for l in LANGS}
rows = []
for p in PROBS:
    for l in LANGS:
        path = os.path.join(HERE, f"{p}-{l}.txt")
        s = open(path).read()
        m = statistics.mean(f(s) for f in TOKS.values())
        means[l].append(m)
        rows.append((p, l, len(s), m))
print("| 언어 | 10문제 평균 토큰(5계열) | vs Python |")
print("|---|---|---|")
py = statistics.mean(means["python"])
for l in sorted(LANGS, key=lambda x: statistics.mean(means[x])):
    m = statistics.mean(means[l])
    print(f"| {l} | {m:.0f} | {100*(m-py)/py:+.0f}% |")
print("\n문제별 AIL vs 최저 기존 언어:")
for i, p in enumerate(PROBS):
    best = min((means[l][i], l) for l in LANGS if l != "ail")
    a = means["ail"][i]
    print(f"  {p}: ail {a:.0f} vs 최저 {best[1]} {best[0]:.0f} → {'승' if a < best[0] else '패'}")
print("\nAIL ail-check 판정:")
ok = 0
for p in PROBS:
    r = subprocess.run([CHECK, os.path.join(HERE, f"{p}-ail.txt")], capture_output=True, text=True)
    line = r.stdout.strip().splitlines()[0] if r.stdout else "?"
    ok += line.startswith("OK")
    print(f"  {p}: {line}")
print(f"통과율: {ok}/10")
