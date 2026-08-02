#!/usr/bin/env python3
"""토크나이저 실측 — gil 사이클 ail-grammar-skeleton/tokenizer-survey s2 plan 고정분.

토크나이저 5개(o200k_base, cl100k_base, Qwen2.5-Coder, DeepSeek-V3, Phi-3) ×
샘플 2군(A: 동일 로직 4언어, B: 표기 변형 12종)의 토큰 수를 잰다.
출력: markdown 표 (stdout).
재현: pip install tiktoken tokenizers; tokenizers/ 에 HF tokenizer.json 3개 필요
      (Qwen/Qwen2.5-Coder-7B-Instruct, deepseek-ai/DeepSeek-V3,
       microsoft/Phi-3-mini-4k-instruct 의 resolve/main/tokenizer.json)
"""
import json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 토크나이저 로딩 ──────────────────────────────────────────
import tiktoken
from tokenizers import Tokenizer

TOKENIZERS = {}
TOKENIZERS["o200k(GPT-4o)"] = lambda s, e=tiktoken.get_encoding("o200k_base"): len(e.encode(s))
TOKENIZERS["cl100k(GPT-4)"] = lambda s, e=tiktoken.get_encoding("cl100k_base"): len(e.encode(s))
for name, fn in [("qwen2.5-coder", "qwen25coder.json"),
                 ("deepseek-v3", "deepseekv3.json"),
                 ("phi3(llama계)", "phi3.json")]:
    tok = Tokenizer.from_file(os.path.join(HERE, "tokenizers", fn))
    TOKENIZERS[name] = lambda s, t=tok: len(t.encode(s).ids)

# ── A군: 동일 로직(HTTP fetch + JSON 파싱 + 재시도 + 에러 반환) 4언어 ──
A = {}
A["python"] = '''import requests, time

def fetch_user(url, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return {"ok": True, "name": data["name"], "email": data["email"]}
        except Exception as err:
            if attempt == retries - 1:
                return {"ok": False, "error": str(err)}
            time.sleep(2 ** attempt)
'''
A["go"] = '''package main

import (
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type User struct {
    Name  string `json:"name"`
    Email string `json:"email"`
}

func fetchUser(url string, retries int) (*User, error) {
    for attempt := 0; attempt < retries; attempt++ {
        resp, err := http.Get(url)
        if err == nil && resp.StatusCode == 200 {
            var u User
            if err := json.NewDecoder(resp.Body).Decode(&u); err == nil {
                resp.Body.Close()
                return &u, nil
            }
            resp.Body.Close()
        }
        if attempt == retries-1 {
            return nil, fmt.Errorf("fetch failed: %v", err)
        }
        time.Sleep(time.Duration(1<<attempt) * time.Second)
    }
    return nil, nil
}
'''
A["c"] = '''#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <curl/curl.h>
#include <jansson.h>

int fetch_user(const char *url, int retries, char *name, char *email) {
    for (int attempt = 0; attempt < retries; attempt++) {
        CURL *curl = curl_easy_init();
        if (!curl) continue;
        curl_easy_setopt(curl, CURLOPT_URL, url);
        CURLcode res = curl_easy_perform(curl);
        curl_easy_cleanup(curl);
        if (res == CURLE_OK) {
            json_error_t err;
            json_t *root = json_loads(buffer, 0, &err);
            if (root) {
                strcpy(name, json_string_value(json_object_get(root, "name")));
                strcpy(email, json_string_value(json_object_get(root, "email")));
                json_decref(root);
                return 0;
            }
        }
        if (attempt < retries - 1) sleep(1 << attempt);
    }
    return -1;
}
'''
A["js"] = '''async function fetchUser(url, retries = 3) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      return { ok: true, name: data.name, email: data.email };
    } catch (err) {
      if (attempt === retries - 1) return { ok: false, error: String(err) };
      await new Promise(r => setTimeout(r, 2 ** attempt * 1000));
    }
  }
}
'''

# ── B군: 표기 변형 12종 — 같은 의미의 가상 AIL 조각을 표기만 바꿔서 ──
B = {}
# 1~3 키워드 길이 3단계 (같은 의도 계약 선언)
B["kw-long"] = 'intention fetch_user achieves "user profile loaded" forbidden [network.write] budget 2000 tokens'
B["kw-mid"] = 'intent fetch_user goal "user profile loaded" forbid [network.write] budget 2000 tokens'
B["kw-short"] = 'itt fetch_user gl "user profile loaded" fbd [network.write] bgt 2000 tokens'
# 4~6 식별자 스타일
B["id-snake"] = 'let user_profile_result = fetch_user_profile(request_timeout_ms, max_retry_count)'
B["id-camel"] = 'let userProfileResult = fetchUserProfile(requestTimeoutMs, maxRetryCount)'
B["id-abbrev"] = 'let usrProfRes = fchUsrProf(reqTmoMs, maxRtryCnt)'
# 7~9 블록 구분
B["block-indent"] = 'on failure:\n    log error\n    retry with backoff\n    return fallback'
B["block-brace"] = 'on failure { log error; retry with backoff; return fallback }'
B["block-end"] = 'on failure do\n  log error\n  retry with backoff\n  return fallback\nend'
# 10 기호 vs 단어 연산자
B["op-symbol"] = 'if count >= limit && !done { total += batch }'
B["op-word"] = 'if count at_least limit and not done then total add batch'
# 11~12 구조 표기
B["struct-json"] = '{"goal": "load user", "success": {"observe": "profile.name"}, "forbid": ["fs.delete"], "budget": 2000}'
B["struct-sexpr"] = '(goal "load user" (success (observe profile.name)) (forbid fs.delete) (budget 2000))'

def measure(samples):
    rows = []
    for sid, text in samples.items():
        row = {"id": sid, "chars": len(text)}
        for tname, fn in TOKENIZERS.items():
            row[tname] = fn(text)
        rows.append(row)
    return rows

def md_table(rows):
    names = list(TOKENIZERS)
    out = ["| 샘플 | 문자 | " + " | ".join(names) + " | 평균 tok/char |",
           "|---" * (len(names) + 3) + "|"]
    for r in rows:
        counts = [r[n] for n in names]
        tpc = statistics.mean(c / r["chars"] for c in counts)
        out.append(f"| {r['id']} | {r['chars']} | " + " | ".join(str(c) for c in counts) + f" | {tpc:.3f} |")
    return "\n".join(out)

def rank_correlation(rows):
    """계열 간 순위 상관(Spearman, 수식 직접): 표기 순위가 토크나이저 불변인가."""
    names = list(TOKENIZERS)
    ids = [r["id"] for r in rows]
    ranks = {}
    for n in names:
        order = sorted(ids, key=lambda i: next(r[n] / r["chars"] for r in rows if r["id"] == i))
        ranks[n] = {i: k for k, i in enumerate(order)}
    base = names[0]
    out = []
    m = len(ids)
    for n in names[1:]:
        d2 = sum((ranks[base][i] - ranks[n][i]) ** 2 for i in ids)
        rho = 1 - 6 * d2 / (m * (m * m - 1))
        out.append(f"- {base} vs {n}: ρ = {rho:.3f}")
    return "\n".join(out)

if __name__ == "__main__":
    print("## A군 — 동일 로직 4언어\n")
    ra = measure(A)
    print(md_table(ra))
    print("\n## B군 — 표기 변형 12종\n")
    rb = measure(B)
    print(md_table(rb))
    print("\n## B군 순위 상관 (tok/char 기준, o200k 대비)\n")
    print(rank_correlation(rb))
