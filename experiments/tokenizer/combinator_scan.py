#!/usr/bin/env python3
"""컬렉션 조합자 이름 후보 실측 — 사이클 stdlib-vocab s10 plan (1).

기준: 최신 4계열(o200k·qwen2.5·deepseek·phi3) 전부에서 bare / " "+w / w+"(" 가 각 1·1·2토큰.
파생 합성어(sortBy 류)는 대조군으로 같이 재서 '단일 실단어 + fn 인자' 원칙을 검증한다.
"""
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

MODERN = ["o200k", "qwen2.5", "deepseek", "phi3"]

SLOTS = {
    "변형": ["map", "each", "apply", "transform"],
    "선별": ["filter", "keep", "drop", "select", "where"],
    "정렬": ["sort", "order", "rank", "arrange"],
    "집계(접기)": ["fold", "reduce", "sum", "tally"],
    "묶기(빈도)": ["group", "count", "bucket", "cluster"],
    "절단": ["take", "slice", "top", "head", "first"],
    "중복 제거": ["uniq", "unique", "distinct", "dedup"],
    "역순": ["reverse", "flip", "rev"],
    "탐색": ["find", "index", "locate"],
    "판정": ["any", "all", "none", "every"],
    "대조군: 파생 합성어": ["sortBy", "groupBy", "orderBy", "countBy", "topK", "sortedBy"],
}

def row(w):
    bare = [TOKS[n](w) for n in MODERN]
    sp = [TOKS[n](" " + w) for n in MODERN]
    call = [TOKS[n](w + "(") for n in MODERN]
    # phi3(SPM)는 " w"의 공백을 항상 별도 토큰으로 셈 → 공백형·호출형은 나머지 3계열로 판정
    ok = (all(v == 1 for v in bare)
          and all(v == 1 for v in sp[:3])
          and all(v == 2 for v in call[:3]))
    return bare, sp, call, ok

def main():
    print("| 슬롯 | 후보 | bare(4계열) | ' '+w | w+'(' | 통과 |")
    print("|---|---|---|---|---|---|")
    winners = {}
    for slot, cands in SLOTS.items():
        for w in cands:
            bare, sp, call, ok = row(w)
            j = lambda xs: "/".join(map(str, xs))
            print(f"| {slot} | `{w}` | {j(bare)} | {j(sp)} | {j(call)} | {'✓' if ok else '✗'} |")
            if ok:
                winners.setdefault(slot, []).append(w)
    print()
    for slot, ws in winners.items():
        print(f"- {slot}: {' '.join(ws)}")

if __name__ == "__main__":
    main()
