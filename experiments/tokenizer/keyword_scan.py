#!/usr/bin/env python3
"""키워드 후보 전수 실측 + AIL 뼈대 vs Python 비교 — 사이클 grammar-draft s2 plan."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
import tiktoken
from tokenizers import Tokenizer

TOKS = {}
TOKS["o200k"] = lambda s, e=tiktoken.get_encoding("o200k_base"): len(e.encode(s))
TOKS["cl100k"] = lambda s, e=tiktoken.get_encoding("cl100k_base"): len(e.encode(s))
for name, fn in [("qwen2.5", "qwen25coder.json"), ("deepseek", "deepseekv3.json"), ("phi3", "phi3.json")]:
    t = Tokenizer.from_file(os.path.join(HERE, "tokenizers", fn))
    TOKS[name] = lambda s, t=t: len(t.encode(s).ids)

# 의미 슬롯 12 × 후보 — 키워드는 행 선두/공백 뒤에 온다 → " word" 형태로도 재서 병합 확인
SLOTS = {
    "계약 선언": ["intent", "contract", "task", "aim", "act"],
    "목적": ["goal", "purpose", "target", "want", "for"],
    "성공 조건": ["done", "success", "check", "expect", "until"],
    "금지": ["forbid", "never", "deny", "ban", "without"],
    "효과": ["effect", "perform", "does", "uses", "with"],
    "예산": ["budget", "limit", "cost", "cap", "spend"],
    "실패 처리": ["fail", "rescue", "catch", "else", "or"],
    "재시도": ["retry", "again", "repeat", "attempt", "backoff"],
    "반환": ["return", "give", "yield", "out", "emit"],
    "바인딩": ["let", "set", "bind", "val", "def"],
    "조건": ["if", "when", "unless", "cond", "case"],
    "분기 매칭": ["match", "on", "pick", "route", "switch"],
}

def counts(word):
    bare = {n: f(word) for n, f in TOKS.items()}
    sp = {n: f(" " + word) for n, f in TOKS.items()}
    return bare, sp

def main():
    total = 0
    print("| 슬롯 | 후보 | bare(5계열) | ' '+w(5계열) | 전계열 1토큰? |")
    print("|---|---|---|---|---|")
    winners = {}
    for slot, cands in SLOTS.items():
        for w in cands:
            total += 1
            bare, sp = counts(w)
            ok = all(v == 1 for v in bare.values()) and all(v == 1 for v in sp.values())
            print(f"| {slot} | `{w}` | {'/'.join(str(v) for v in bare.values())} | {'/'.join(str(v) for v in sp.values())} | {'✓' if ok else '✗'} |")
            if ok and slot not in winners:
                winners[slot] = w
    print(f"\n총 후보 {total}개. 슬롯별 첫 통과 후보: {winners}")

    # ── AIL 뼈대 표기 vs Python (사이클 ① A군 동일 로직) ──
    AIL = '''intent fetchUser(url) {
  goal profile
  done profile.name != none
  forbid [fs, shell]
  budget 2000 tokens, 5 s
  retry 3 backoff 2
  let data = http.get(url).json
  return { ok, name data.name, email data.email }
  fail return { ok false, error }
}'''
    PY = open(os.path.join(HERE, "sample_python.py")).read() if os.path.exists(os.path.join(HERE, "sample_python.py")) else None
    from measure import A
    py = A["python"]
    print("\n## AIL 뼈대 vs Python (동일 로직)\n")
    print("| | 문자 | " + " | ".join(TOKS) + " |")
    print("|---|---|" + "---|" * len(TOKS))
    for label, txt in [("AIL(초안)", AIL), ("Python", py)]:
        print(f"| {label} | {len(txt)} | " + " | ".join(str(f(txt)) for f in TOKS.values()) + " |")

if __name__ == "__main__":
    main()
