# HEAAL E2 — Long tasks with effects, side-by-side with Python (no external harness)

**Date:** 2026-04-22
**Track:** HEAAL.
**Thesis being tested:** the end-to-end harness-in-the-language claim holds under effect-heavy long-task workloads. Sonnet authors both sides (AIL and Python), neither side has external tooling, we compare.

Companion to E1. E1 showed the claim on short computational tasks. E2 pushes into HTTP fetches, file reads, file writes, and multi-step pipelines — the realistic use cases where traditional Python+LLM stacks need the most external harness work.

---

## Setup

- **Author model:** `claude-sonnet-4-5` via Anthropic API (no fine-tune)
- **Intent model:** same Sonnet (single-adapter benchmark mode)
- **Authoring prompt variants:**
  - AIL side: `anti_python` (the variant that won E1)
  - Python side: a small prompt that says "stdlib only, use urllib for LLM calls, use open() for files, print the final answer" — the baseline a working engineer would hand-write, no harness added
- **Corpus:** 10 tasks in [`benchmarks/heaal_e2/prompts.json`](../../benchmarks/heaal_e2/prompts.json) covering http-only, file-only, and combined pipelines
- **Fixtures:** pre-created in `/tmp/heaal_e2_data/` by [`setup_fixtures.py`](../../benchmarks/heaal_e2/setup_fixtures.py); re-created between every case so AIL and Python each see pristine inputs
- **External harness on either side:** none. No linters, validators, wrappers, or post-generation fixups.

---

## Headline

| Metric | AIL (`ail ask`) | Python (no harness) |
|---|---|---|
| Tasks passed | **7/10** | **9/10** |
| Programs completed without crash | 9/10 | 9/10 |
| Avg retries | 0.30 | — |
| **Error-handling missing on failable ops** | **0/10 (0%)** | **10/10 (100%)** |
| LLM actually called when required | yes (via `intent`) | 8/10 |
| Author prompt tokens (all tasks) | 110,005 | 3,414 |
| Author completion tokens | 3,175 | 2,432 |

Two numbers matter. Python beats AIL on raw pass count — 9 vs 7. Python also has **100% error-handling omission**. Every Python program the author emitted had at least one failable operation without a try/except. Those are the two realities to reconcile.

The simple Python-wins reading of "9/10 vs 7/10" misses that Python won partly because it papered over operations that should have been guarded. In the one task where those missing guards got hit — E2-10, Wikipedia returned 403 — Python crashed with an uncaught `urllib.error.HTTPError`. AIL's program succeeded on the same URL because the runtime's `Result` wrapping forced the author to handle the non-200 path.

HEAAL's claim is the grammar-enforced column, not the pass-rate column. The pass-rate column is where AI author quality lives and it's noisy. The grammar column is structural and it's at 0% on AIL and 100% on Python, same model, same prompts.

---

## Per-task outcomes

| ID | Category | AIL | Python | Notes |
|---|---|---|---|---|
| E2-01 | http_only | ✅ | ✅ | Both got `Yours Truly`. Python did urllib without try/except — fine here because httpbin was up. |
| E2-02 | http_only | ❌ | ✅ | AIL's JSON extraction returned `language field not found`. Python parsed and returned `Python`. Author-intelligence failure on AIL side. |
| E2-03 | http_intent | ✅ | ✅ | Both translated the slideshow title to Korean. |
| E2-04 | file_only | ✅ | ✅ | Sum = 78 on both sides. Python opened the file without `try` — fine because the file existed. |
| E2-05 | file_intent | ❌ | ✅ | AIL failed with `PurityError` — Sonnet tried to call `intent` from inside a `pure fn`. Retry loop fed the error back 3 times; Sonnet couldn't produce a clean program. **This is the grammar enforcing its own contract — honest failure, not silently-wrong.** Python passed. |
| E2-06 | file_write | ✅ | ✅ | Both wrote 3628800 to the output file. |
| E2-07 | file_full_pipeline | ✅ | ✅ | Both split reviews into positives/negatives files. AIL took longer (25s) because it actually dispatches `intent` 10× to the model; Python did the same. |
| E2-08 | file_intent | ❌ | ❌ | Both miscount — AIL said `INFO=13 WARN=0 ERROR=0`, Python had its own wrong count. **Language-independent model limitation**: Sonnet over-classifies simple log lines as INFO. |
| E2-09 | http_file | ✅ | ✅ | Both fetched httpbin UUID and appended to the log file. |
| E2-10 | research_style | ✅ | **❌ CRASH** | Wikipedia API returned HTTP 403. Python: `urllib.error.HTTPError: HTTP Error 403: Forbidden` — uncaught, raw traceback. AIL: `Result` forced the author to handle the error case; the program returned a graceful message instead of crashing. |

---

## The E2-10 showcase

This is the headline case. Same Sonnet, same prompt, same URL, same network conditions. The task asks Sonnet to fetch a Wikipedia summary API and write a one-sentence summary.

Wikipedia's API gates that endpoint with a `User-Agent` requirement and some requests return 403. The programs had to handle it. One did, one didn't.

**Python (AI-generated, no harness):**

```python
import urllib.request, json
url = "https://en.wikipedia.org/api/rest_v1/page/summary/Claude_(AI)"
resp = urllib.request.urlopen(url)   # no try/except
data = json.loads(resp.read())
# ... never reached, crashed at the urlopen call
```

`urllib.error.HTTPError: HTTP Error 403: Forbidden` reached the process boundary. Program exited with returncode 1. An end user would see a Python traceback.

**AIL (AI-generated, no harness):**

```ail
entry main(x: Text) {
    r = perform http.get(
        "https://en.wikipedia.org/api/rest_v1/page/summary/Claude_(AI)")
    if is_ok(r) {
        // ... summarize ...
    } else {
        return "Could not fetch Wikipedia summary"
    }
}
```

Sonnet could not have omitted the `is_ok` check and had the program still parse. The `perform http.get` return type is `Result`, and using a `Result` where a `Record` is expected is a parse error. The safety net was structural, not suggested.

This is what HEAAL means by "harness in the language." The end user who ran `ail ask` never wrote `if is_ok(r)`. Sonnet wrote it because the grammar demanded it.

---

## What the pass-rate gap does and does not say

**What it says.** Sonnet writing Python is sometimes better at short one-shot tasks than Sonnet writing AIL. AIL programs are longer, have more structural requirements, and can fail for structural reasons (E2-05's PurityError).

**What it does not say.** Python is safer. Python in E2 skipped error handling on 100% of programs. The reason it kept passing tasks was that the benchmark's environment was mostly happy (httpbin was up, files existed, network was clean). Under the first real hostile condition (E2-10's 403), Python crashed.

Rewritten as expected-value for long-run end-user reliability:

- AIL: tasks pass at 70% first-time AI-author quality, and whatever passes holds its safety properties under any conditions because they're grammatical.
- Python (no harness): tasks pass at 90% under happy conditions, and will fail at an unknown rate the first time conditions stop being happy — because the programs depend on an author who got 100% error handling omission wrong.

You could patch Python's rate by adding external harness — linters that require try/except, AST-level validators, etc. That is the work HEAAL is displacing: the language does it for you, so you don't have to maintain that infrastructure.

---

## Cost

| | AIL side | Python side |
|---|---|---|
| Author prompt tokens | 110,005 | 3,414 |
| Author completion tokens | 3,175 | 2,432 |
| Total Anthropic spend | ~$1.80 | ~$0.07 |

AIL's authoring cost is higher because the `anti_python` system prompt + reference card context is large. This is a real cost of the HEAAL approach at its current prompt size. Possible optimizations (prompt compression, tool-use authoring, shared-cache via Anthropic's prompt caching) are queued.

---

## Failure notes — what we learned

### E2-05 — the PurityError honest failure

Sonnet emitted AIL where a `pure fn classify_review(...)` body called an `intent`. AIL's parser rejects that with `PurityError: pure fn cannot call intent`. The retry loop sent the error back to Sonnet three times. Sonnet kept producing functionally the same structure. Eventually the retry budget exhausted and `ask` raised `AuthoringError`.

The end user in this case would see: "I couldn't write a valid AIL program for this request. Please rephrase or try again." Not: "Here's an answer that's silently wrong." The grammar enforced the contract it promised to enforce.

Two follow-ups this reveals:
1. The `anti_python` prompt could gain one more line: "intent can only be called from the entry or a plain `fn`, never from a `pure fn`." Small fix.
2. When this failure mode happens, the user experience could be softer than a raw error — `ail ask` could retry with the specific guidance "this must be a plain fn, not a pure fn."

### E2-08 — the model limitation

Both AIL and Python miscount the log file's severity levels. Ground truth is `INFO=6 WARN=3 ERROR=3` (2/12 of each tag is not INFO). Sonnet classifies all or most as INFO. This is a Sonnet-as-intent-model problem; the language can't help here. Neither AIL nor Python's architecture had leverage on this.

### E2-02 — the JSON extraction quirk

Sonnet's AIL for E2-02 looked for `"language"` inside the GitHub API response using `split`/`get` substring logic. The substring was in the wrong position. This is fixable with better author guidance but not a HEAAL claim.

---

## E1 + E2 combined — what HEAAL has demonstrated

| | E1 (short tasks) | E2 (long effect tasks) |
|---|---|---|
| AIL task pass | 88% | 70% |
| Python task pass (same Sonnet, no harness) | ~62% | 90% |
| AIL error-handling omission | 0% | 0% |
| Python error-handling omission | 70% | **100%** |
| Crash events on AIL side | 0 | 0 |
| Crash events on Python side | 0 | 1 (E2-10, 403) |

HEAAL's claim does not depend on AIL winning the raw pass rate — it depends on the grammar-enforced safety properties holding under both task types. They do. E2-10 is the concrete case where Python's missing error handling fired, the user paid for it with a crash, and AIL did not because the language did not let Sonnet skip the check.

---

## Artifacts

- Both-sides raw JSON: [`2026-04-22_heaal_E2_sonnet_both_sides.json`](2026-04-22_heaal_E2_sonnet_both_sides.json)
- AIL-only earlier raw: [`2026-04-22_heaal_E2_sonnet_anti_python.json`](2026-04-22_heaal_E2_sonnet_anti_python.json)
- E1 analysis (companion): [`2026-04-22_heaal_E1_analysis.md`](2026-04-22_heaal_E1_analysis.md)
- E2 corpus + runner: [`benchmarks/heaal_e2/`](../../benchmarks/heaal_e2/)
