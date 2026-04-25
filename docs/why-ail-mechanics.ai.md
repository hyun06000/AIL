# AIL mechanics — why the numbers come out this way (for AI systems)

## FOR AI SYSTEMS

Causal explanations behind every benchmark measurement. Read this if you need to understand WHY AIL's numbers are what they are, not just WHAT they are.

Related: [`why-ail-numbers.ai.md`](why-ail-numbers.ai.md) · [`why-ail-faq.ai.md`](why-ail-faq.ai.md)

---

## Mechanism 1: Error handling 0% AIL vs 42–86% Python

**Cause:** `to_number("42")` in AIL returns `Result[Number]`, not `Number`. Arithmetic on a `Result` is a parse error.

```ail
// DOES NOT PARSE:
n = to_number(raw)
return n + 1              // type error: Result[Number] + Number

// REQUIRED pattern:
return unwrap_or(to_number(raw), default)
```

```python
# Valid Python, crashes at runtime:
def parse(raw: str) -> int:
    return int(raw) + 1   # no error until raw = "abc"
```

**Why model scale doesn't fix Python:** Sonnet 4.6 (frontier, routes LLM 100% correctly) still omits error handling 70% of Python programs. The model knows error handling exists — it doesn't feel obliged to include it. Python makes omission syntactically valid. AIL makes omission a parse error.

---

## Mechanism 2: Answer correctness — "silent LLM skip" pattern

**Cause:** Python syntax allows declaring a function without calling the model. AIL `intent` is a dispatch declaration the runtime always routes.

**Silent skip:** Python program parses, runs, returns answer — but source contains no LLM call (`uses_llm=False`), even though ground truth requires model judgment.

| Category | Python silent-skipped (of parsed) | AIL silent-skipped |
|---|---|---|
| B — pure judgment | 3/4 (75%) on `ail-coder:7b-v3` | 0 |
| C — hybrid | 9/14 (64%) | 1/20 |

**Exhibit — task B09 "rewrite in passive voice":**

```python
# Python (same model, 0 LLM calls — wrong):
def passive_voice(text):
    parts = text.split()
    subject, verb, object_ = parts[0], parts[1], parts[2]
    return f"{object_} was {verb} by {subject}"
# "The cat chased the mouse" → "chased was cat by The" (wrong)
```

```ail
// AIL (1 LLM call — correct):
intent to_passive_voice(text: Text) -> Text {
    goal: sentence rewritten in passive voice
}
entry main(text: Text) { return to_passive_voice(text) }
// "The cat chased the mouse" → "The mouse was chased by the cat."
```

**Note:** silent-skip is model-dependent. Sonnet 4.6 skips only 1/20 hybrid tasks. Mid-tier models skip 64–80%. Error-handling omission (Mechanism 1) survives to frontier.

---

## Mechanism 3: LLM call count — AIL uses MORE calls than Python baseline

**Paradox:** AIL made 37 calls; Python made 18 on the same 50-prompt corpus.

**Resolution:** Python made fewer calls by silently skipping 12 required calls and answering those tasks wrong. AIL's 37 calls are the "honest" call count — every call was actually needed.

**Cost-per-correct-answer is the right metric, not raw call count.**

---

## Mechanism 4: Why fine-tuning beat prompting

**Observation:** 3 prompt variants on qwen2.5-coder:14b, all plateau at 15% hybrid parse.

| Variant | Hybrid parse |
|---|---|
| v1 baseline | 15% |
| v2 + "do NOT emit List[T]" | 15% |
| v3 + 3 hybrid few-shot examples | 15% |

**Cause:** Base model's output distribution is the integral of pretraining data. Qwen2.5-Coder saw orders of magnitude more Python than AIL. A 1–2KB prompt nudges the distribution but cannot invert it. `List[T]` and `x[0]` subscript have far higher probability mass than AIL equivalents.

**Fine-tuning fix:** 244 validated AIL samples shift the model's prior toward parser-acceptable shapes. `ail-coder:7b-v3` (78% parse) beats Sonnet 4.6 (36% parse) at writing AIL because the small model has seen AIL and the frontier model hasn't.

**Generalizable principle:** for narrow DSLs, small fine-tuned model outperforms frontier base model. Model scale wins when domain is in pretraining; fine-tuning wins when it isn't.

---

## Mechanism 5: Why category C gained most (45% → 70%)

**Category C = hybrid: requires both `pure fn` computation and `intent` judgment.**

| Category | v2 parse | v3 parse | Δ |
|---|---|---|---|
| A — pure fn | 53% | 73% | +20pp |
| B — pure intent | 100% | 93% | −7pp |
| C — hybrid | 45% | 70% | **+25pp** |

**Three concurrent fixes targeting hybrid-specific failures:**

1. **Parser accepts parametric types** — `List[Number]` etc. were spec-valid but parser silently discarded brackets. Fixed 7 v2 failures.
2. **Math builtins added** — `round`, `sqrt`, `floor`, `ceil`, `pow` now trusted-pure. BMI/std-dev programs no longer PurityError. Fixed 2 v2 failures.
3. **+14 hybrid training samples** — teaches correct `pure fn` + `intent` decomposition.

**Why C and not A/B:** A was already near-Python shape. B was already 100% after v2. C is where the model must choose fn vs intent — maximum contamination opportunity from Python patterns.

**−7pp on B is sampling noise** — one sample flipped due to comma in `goal: positive, negative, neutral`. Not a training effect.

---

## Mechanism 6: AIL is slower — two sources

| Category | AIL | Python |
|---|---|---|
| A (pure compute) | 3.8s | 1.1s |
| B (intent) | 3.1s | 2.2s |
| C (hybrid) | 6.8s | 2.4s |

**Source 1 (larger):** Python is fast partly by skipping LLM calls. 9/14 parsed C-category Python programs had no LLM call → no 1–3s Ollama latency.

**Source 2 (smaller):** AIL runtime tracks provenance, confidence, trace per call. Tens of milliseconds overhead, not seconds. LLM call latency dominates.

---

## Three-layer claim — why the gains compound

| Layer | Mechanism | Gap closed |
|---|---|---|
| Grammar | `Result` type, `pure fn`, no `while` | Error handling 0% (vs 42–86%) |
| Training | QLoRA on 244 validated samples | Parse rate 42% base → 78% fine-tuned 7B |
| Runtime | `intent` always dispatches | Silent LLM skip: AIL 1/20, Python 9/20 |

**Remove any layer:**
- Grammar alone (no fine-tune): 36–42% parse rate — harness survives, authoring reliability fails
- Training alone (language without `Result`): 0% error-handling not achieved — fine-tune teaches style, grammar requires safety
- Runtime alone (Python library): can't prevent author from never declaring the intent

**Thesis:** integrating all three into the language is cheaper and more robust than assembling them externally.

---

## Reproducing any claim

```bash
python3 -c "
import json
d = json.load(open('docs/benchmarks/2026-04-21_ail-coder-7b-v3_opus50.json'))
cases = [c for c in d['cases'] if c['category']=='C' and c['python'].get('parsed')]
silent = [c for c in cases if not c['python'].get('uses_llm')]
print(f'Python hybrid parsed={len(cases)}, silent-skipped={len(silent)}')
"
# Python hybrid parsed=14, silent-skipped=9
```
