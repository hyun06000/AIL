# Examples

This directory contains AIL programs only (`.ail` files). Each file is a self-contained example you can run with:

```bash
ail run examples/<name>.ail --input "..." --mock
```

Python tooling (run_live harness, evolve demo) lives in `../tools/`.

## Start here

If you're reading AIL for the first time, run one of these in order:

1. **`fizzbuzz.ail`** — the sanity check that AIL is a real programming language. Zero LLM calls.
2. **`expense_analyzer.ail`** — the canonical example. A month of transactions in, a report with numeric facts (pure fn) and natural-language saving advice (intent) out. Shows what AIL is *for* in one screen:
   ```bash
   ail run examples/expense_analyzer.ail --input "$(cat examples/sample_expenses.txt)" --mock
   ```
3. **`review_analyzer.ail`** — a hybrid pipeline with 23 fn calls and 6 intent calls. How the two kinds of work live together.
4. **`audit_provenance.ail`** — demonstrates `has_intent_origin` — the program labels each field of its own output `[pure]` or `[LLM]` at runtime.

The other files (`cascade_extract`, `parallel_analysis`, `smart_reply`, etc.) each isolate a single feature — see the comment at the top of each for context.
