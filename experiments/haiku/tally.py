#!/usr/bin/env python3
"""Haiku 실험 집계 — 생성물 15개 × 5계열 토큰 + AIL 준수 판정."""
import os, re, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, os.path.join(HERE, ".."))
import tiktoken
from tokenizers import Tokenizer

TOKS = {}
TOKS["o200k"] = lambda s, e=tiktoken.get_encoding("o200k_base"): len(e.encode(s))
TOKS["cl100k"] = lambda s, e=tiktoken.get_encoding("cl100k_base"): len(e.encode(s))
for name, fn in [("qwen2.5", "qwen25coder.json"), ("deepseek", "deepseekv3.json"), ("phi3", "phi3.json")]:
    t = Tokenizer.from_file(os.path.join(HERE, "..", "tokenizer", "tokenizers", fn))
    TOKS[name] = lambda s, t=t: len(t.encode(s).ids)

CARD = open(os.path.join(HERE, "prompts.md")).read().split("## AIL 전용 접두")[1].split("## 문제")[0]

LANGS = ["python", "go", "c", "js", "ail"]
print("| 문제 | 언어 | 문자 | " + " | ".join(TOKS) + " | 5계열 평균 |")
print("|---|---|---|" + "---|" * (len(TOKS) + 1))
means = {l: [] for l in LANGS}
for p in ["P1", "P2", "P3"]:
    for l in LANGS:
        s = open(os.path.join(HERE, f"{p}-{l}.txt")).read()
        cs = [f(s) for f in TOKS.values()]
        m = statistics.mean(cs)
        means[l].append(m)
        print(f"| {p} | {l} | {len(s)} | " + " | ".join(map(str, cs)) + f" | {m:.0f} |")
print()
print("| 언어 | 3문제 평균 토큰 | Python 대비 |")
print("|---|---|---|")
py = statistics.mean(means["python"])
for l in LANGS:
    m = statistics.mean(means[l])
    print(f"| {l} | {m:.0f} | {100*(m-py)/py:+.0f}% |")
card_t = {n: f(CARD) for n, f in TOKS.items()}
print(f"\nAIL 스펙 카드 입력 오버헤드: {card_t} (평균 {statistics.mean(card_t.values()):.0f})")
# AIL 준수: task 블록마다 goal·done·never 존재?
print("\nAIL 3슬롯 준수:")
for p in ["P1", "P2", "P3"]:
    s = open(os.path.join(HERE, f"{p}-ail.txt")).read()
    tasks = re.findall(r'task \w+\([^)]*\) \{', s)
    g, d, n = s.count("\n  goal") + s.count("goal "), len(re.findall(r'\bdone ', s)), len(re.findall(r'\bnever', s))
    goals = len(re.findall(r'^\s*goal ', s, re.M)); dones = len(re.findall(r'^\s*done ', s, re.M)); nevers = len(re.findall(r'^\s*never', s, re.M))
    print(f"  {p}: task {len(tasks)}개, goal {goals}, done {dones}, never {nevers} → {'전 태스크 준수' if len(tasks)==goals==dones==nevers and tasks else '불일치'}")
