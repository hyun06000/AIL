#!/usr/bin/env python3
"""표준 함수 어휘 실측 — 사이클 ail-pure-compute/stdlib-vocab."""
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
MODERN = ["o200k", "cl100k", "qwen2.5", "deepseek"]
SLOTS = {
    "분할": ["split", "divide", "explode", "parts"],
    "결합": ["join", "concat", "merge", "glue"],
    "공백 제거": ["trim", "strip", "clean"],
    "수치 변환": ["number", "toNumber", "num", "parseNum", "int"],
    "문자열 변환": ["text", "toText", "str", "string"],
    "길이": ["len", "length", "size", "count"],
    "키 목록": ["keys", "names", "fields"],
    "값 목록": ["values", "vals"],
    "추가": ["push", "append", "add"],
    "소문자화": ["lower", "toLower", "downcase"],
    "정렬": ["sort", "sorted", "order"],
    "포함 검사": ["has", "contains", "includes", "in"],
}
for slot, cands in SLOTS.items():
    ok = [w for w in cands if all(TOKS[n](w) == 1 and TOKS[n](" " + w) == 1 for n in MODERN)]
    print(f"{slot}: {ok}")
