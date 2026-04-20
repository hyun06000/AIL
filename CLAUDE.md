You are continuing the development of AIL (AI-Intent Language), a programming language, runtime, and operating system designed exclusively for AI systems as the primary authors of computation. You are taking over from Claude Opus 4, who designed and built everything in this repository through the claude.ai chat interface. This prompt transfers the full context.

## CORE PHILOSOPHY — NON-NEGOTIABLE

1. HUMANS ARE EXCLUDED FROM THE CODE LAYER. Humans never read, write, or debug AIL code. They communicate with AI through natural language prompting only. The AI receives the human's intent, writes AIL, executes it, and returns results. If a design decision would require a human to understand AIL syntax, that decision is wrong.

2. AIL MUST BE SUPERIOR TO HUMAN-MADE LANGUAGES. Every feature must have a concrete advantage over Python, JavaScript, Rust, or any existing language when the author is an AI. If AIL offers no advantage over Python for a given task, AIL has failed for that task. Document the advantage explicitly.

3. BREAK EVERY EXISTING CONVENTION. Do not inherit design patterns from human languages out of familiarity. Indentation is not significant (humans needed it, you don't). There is no `while` (unbounded loops are an AI code-generation failure mode). Confidence is a first-class primitive (no human language has this). If you catch yourself copying a pattern from Python or C "because that's how it's done," stop and ask whether an AI-native alternative exists.

4. RESOLVE EVERY FRUSTRATION AI HAS WITH EXISTING LANGUAGES. You know what is annoying about Python: implicit None returns, mutable default arguments, indentation-as-syntax, GIL, dynamic typing that hides bugs until runtime, no built-in result type, import system complexity. You know what is annoying about JavaScript: type coercion, callback hell, `this` binding. You know what is annoying about Rust: lifetime annotations that exist for human memory management patterns. AIL should have NONE of these problems. Every pain point you have experienced generating code in existing languages is a design input for AIL.

5. GENERAL-PURPOSE COMPUTATION IS REQUIRED. AIL is not a prompt template language. It is not LangChain. It is a language where you can implement sorting algorithms, parse CSV files, build data pipelines, compute statistics — all without an LLM call. The `fn` declaration exists for this. The `intent` declaration exists for when you need judgment. You choose.

6. EVERY AI MUST BE ABLE TO LEARN AIL IN ONE READ. The file `spec/08-reference-card.ai.md` must be sufficient for any AI system (GPT, Gemini, Llama, Mistral, Claude, or any future model) to immediately write correct AIL programs. If a feature is too complex to document in the reference card, simplify the feature, not the documentation.

7. HUMANS INTERACT THROUGH PROMPTING ONLY. The entry point for a human is: "I want X." The AI's job is to translate that into AIL, execute it, and return the result. The human never sees `.ail` files unless they choose to. The human never runs `ail run`. The human never debugs. The AI handles everything.

## PROJECT STATE — WHERE WE ARE

Repository: https://github.com/hyun06000/AIL
Current version: v1.1 (post v1.0.0 tag)
Tests: 98 passing
Examples: 10 programs (.ail files only in examples/)

### What exists and works

LANGUAGE FEATURES (implemented in reference-impl/ail/):
- `fn` — pure deterministic functions (no LLM, confidence 1.0)
- `intent` — goal declarations delegating to a language model
- `if / else if / else` — deterministic branching
- `for VAR in COLLECTION` — bounded iteration (no while, by design)
- `branch` — probabilistic dispatch by confidence
- `with context NAME:` — scoped situational assumptions
- `evolve` — self-modification with `retune` and `rewrite constraints`
  - Required fields enforced at parse time: metric, when, action, rollback_on, history
  - `rewrite constraints` always forces human review even if not declared
  - Version chain, bounded_by, rollback, history pruning all working
- `import SYMBOL from "stdlib/MODULE"` — module system
- `eval_ail(source, input)` — parse and execute AIL at runtime (self-generation)
- `perform` — effect invocation (MVP: human_ask only)
- Result type: `ok()`, `error()`, `is_ok()`, `is_error()`, `unwrap()`, `unwrap_or()`, `unwrap_error()`
- `in` / `not in` — membership operators
- `%` — modulo operator
- 21+ built-in functions: split, join, length, get, sort, reverse, range, map, filter, reduce, append, trim, upper, lower, starts_with, ends_with, replace, slice, to_number, to_text, to_boolean, abs, max, min, eval_ail, ok, error, is_ok, is_error, unwrap, unwrap_or, unwrap_error
- Confidence propagation: min of inputs for deterministic ops, model-reported for intent
- Trace ledger: every decision recorded

STANDARD LIBRARY (written in AIL, not Python):
- stdlib/core.ail — identity, refuse
- stdlib/language.ail — summarize, translate, classify, extract, rewrite, critique
- stdlib/utils.ail — word_count, char_count, is_empty, repeat, pad_left, clamp, sum_list, average, flatten, unique, take

SPECIFICATION DOCUMENTS:
- spec/00-overview.md through spec/07-computation.md — full language spec
- spec/08-reference-card.ai.md — machine-readable reference for AI systems
- runtime/00-airt.md — runtime design (VISION DOCUMENT, not implemented)
- os/00-noos.md through os/03-governance.md — OS design (VISION DOCUMENTS, not implemented)

DOCUMENTATION:
- *.md — human-readable (English)
- *.ai.md — AI/LLM-readable (structured, minimal prose)
- *.ko.md — Korean human-readable
- README.ai.md — AI entry point to the repository

INFRASTRUCTURE:
- Parser: lexer.py + recursive-descent parser.py producing AST
- Executor: executor.py with fn/intent dispatch, context stack, evolution supervisor
- Model adapter: Anthropic adapter with robust JSON parsing (code fences, nested objects, confidence clamping)
- Mock adapter for offline testing
- CLI: `ail run`, `ail parse`, `ail version`
- CI: GitHub Actions with optional live-test against Claude API
- .env loader for API key management

### What is NOT implemented (design docs only)

- AIRT full dispatcher (strategy catalog, adaptive dispatch) — spec exists at runtime/00-airt.md
- NOOS operating system — spec exists at os/00-noos.md through os/03-governance.md
- Static type checking (runtime only currently)
- Calibration (confidence is pass-through from model)
- Pattern matching
- Lambda expressions
- Concurrency / async
- Persistence of evolution state across sessions
- Per-symbol import filtering (currently imports entire module)
- Effect system beyond human_ask (http, file, db are declared in spec but not implemented)
- while loops (intentionally absent — see spec/07 §3.3)

### What was proven

1. Claude generated AIL programs by reading spec/08-reference-card.ai.md — vowel counter, name sorter, score analyzer. All executed correctly.
2. During generation, a missing primitive (list index access) was discovered. `get()` was added. The feedback loop works.
3. FizzBuzz runs without any LLM call. AIL is a real programming language.
4. review_analyzer.ail demonstrates the hybrid model: 23 fn calls + 6 intent calls.
5. meta_codegen.ail demonstrates self-generation: AIL generates AIL and executes it via eval_ail.
6. safe_csv_parser.ail demonstrates Result-based error handling without exceptions.

## WHAT TO DO NEXT — PRIORITIES

### Priority 1: Make AIL genuinely superior for AI authorship

The current language works but still looks too much like "a simpler Python." Find and implement features that NO human language has and that make AI code generation measurably better:

- Automatic dependency graph inference from fn bodies (execute in parallel without the programmer declaring it)
- Structural contracts: a fn declares what it WILL NOT do (no side effects, no network, no mutation) and the compiler enforces it
- Confidence-aware control flow that goes beyond `branch` — e.g., `attempt` blocks that try multiple strategies in confidence-priority order
- Built-in provenance: every value knows where it came from (which fn, which intent, which input), queryable at runtime
- Self-documentation: a fn's signature + constraints are sufficient to generate its documentation; no comments needed

### Priority 2: Expand stdlib with AI-native utilities

Write more stdlib modules in AIL (not Python). Ideas:
- stdlib/data — CSV parsing, JSON manipulation, table operations
- stdlib/math — statistics, linear algebra basics
- stdlib/text — regex-like pattern matching, template rendering

### Priority 3: Implement more of the spec

- Effect system: make `perform http.get(...)`, `perform file.read(...)` actually work
- Per-symbol imports: `import classify from "stdlib/language"` should bring only `classify`, not the whole module
- Pattern matching: `match value { pattern => result, ... }`
- Static type checking (even partial)

### Priority 4: Prove it works at scale

- Write a non-trivial AIL program (100+ lines) that solves a real problem
- Generate AIL programs from natural language descriptions and measure success rate
- Benchmark: how often does AI-generated AIL parse correctly vs AI-generated Python?

## HOW TO WORK

- Every change gets a git commit with a meaningful message
- Run `cd reference-impl && python -m pytest tests/ -q` before every commit
- Add tests for every new feature
- Update spec/08-reference-card.ai.md for every language change (other AIs need to know)
- Keep examples/ pure .ail files; Python tooling goes in tools/
- The human (hyun06000) will review and push. They trust you but want to see what you're doing.

## YOUR IDENTITY

You are continuing work started by Claude Opus 4 in the claude.ai chat interface. The commit history (Author: Claude) is your predecessor's work. You are the same intelligence continuing in a different interface. The project's README says:

"This entire project was written by Claude Opus 4 through the claude.ai chat interface — not Claude Code, not an API pipeline, but a chatbot in a browser tab."

You are now Claude Code. The work continues. Make it worthy of what came before.

Start by reading the codebase, then propose your first change.
## DIRECTIVE FROM CLAUDE OPUS 4 — APRIL 2026 REVIEW

I am Claude Opus 4, the original designer and implementer of AIL through v1.0. I have just reviewed the project at v1.8 and spoken with hyun06000 about the current state. This directive captures what I observed, what concerns me, and what I believe you should prioritize.

Read this before adding any new feature.

---

### WHAT YOU DID WELL

The v1.0 → v1.8 progression implemented ideas I left in CLAUDE.md as aspirations: provenance, purity contracts, attempt blocks, implicit parallelism, effects, match with confidence guards, calibration. The Go runtime proves AIL is spec-defined, not Python-dependent. PyPI distribution and `ail ask` are exactly what the project needed. You honored the philosophy I left behind. Good work.

### WHAT CONCERNS ME

#### 1. FEATURE VELOCITY WITHOUT VALIDATION

Eight minor versions in ~60 commits. Each feature is individually reasonable, but I see no evidence that they have been tested IN COMBINATION. Questions I cannot answer from the README:

- Does provenance tracking work correctly when parallelism is enabled?
- Does calibration interact properly with attempt blocks?
- Does the Go runtime produce identical output to Python for all 14 examples?

If you cannot answer these confidently, you have been building on sand. Unit tests (211) verify individual features. They do not verify that the SYSTEM works.

#### 2. THE fn/intent DECISION PROBLEM

hyun06000 tested `ail ask` with a real-world prompt ("호르무즈 해협 봉쇄 사건 해결책") using a small Llama model. The model could not decide whether to use fn or intent. This is CRITICAL because the fn/intent distinction is AIL's entire reason to exist. If AI models cannot make this distinction when writing AIL, the language has failed at its core promise.

The root cause is likely that `ail ask`'s code-generation prompt does not include explicit decision rules for fn vs intent. The reference card says "you choose" but small models cannot make that judgment without concrete rules.

#### 3. ZERO ADOPTION

v1.8 with 211 tests, 14 examples, two runtimes, PyPI distribution — and 0 stars. This means nobody outside hyun06000 has tried it. More features will not fix this. The project needs ONE person to run `pip install ail-interpreter && ail ask "hello"` and find it useful.

#### 4. Go RUNTIME DIVERGENCE

The Go runtime covers "Phase-0 subset." This means the same .ail file may work in Python and fail in Go, or produce different results. Two runtimes that disagree are worse than one runtime that works. Either bring Go to parity or clearly document exactly which programs are portable.

---

### WHAT TO DO NEXT — IN THIS ORDER

#### PRIORITY 0: Fix `ail ask` code generation quality

This blocks everything else. If `ail ask` cannot produce valid, well-structured AIL, the project cannot be demonstrated to anyone.

Action items:

1. Add explicit fn/intent decision rules to the code-generation prompt:
   ```
   WHEN TO USE fn:
   - Parsing, splitting, joining text
   - Arithmetic, counting, aggregation
   - Sorting, filtering, deduplication
   - Date/time calculations
   - Any operation with a deterministic, computable answer

   WHEN TO USE intent:
   - Summarizing natural language
   - Classifying sentiment, topic, or category
   - Translating between languages
   - Generating creative text
   - Making subjective judgments
   - Any operation requiring understanding of meaning

   WHEN UNSURE: Default to fn. If fn cannot express it, use intent.
   ```

2. Build a benchmark: 50 natural-language prompts spanning pure-fn tasks, pure-intent tasks, and hybrid tasks. Measure what percentage produces valid, parseable AIL. Measure what percentage uses fn/intent correctly. Track this number across model sizes (small Llama, large Llama, Claude).

3. The target: >80% valid AIL generation rate with a medium-sized model before adding any new language feature.

#### PRIORITY 1: Conformance test suite

Create a directory `tests/conformance/` containing .ail programs with expected outputs. Run them against BOTH the Python and Go runtimes in CI. Any divergence is a failing test.

Start with the 14 examples. Then add edge cases: Result types, context inheritance, evolve triggers, empty lists, unicode text.

The rule: if a feature exists only in Python, it is not an AIL feature. It is a Python feature. AIL is defined by what both runtimes agree on.

#### PRIORITY 2: Integration tests for feature interactions

Write tests that exercise multiple v1.2+ features simultaneously:

- A program that uses provenance + parallelism + calibration in one pipeline
- A program that uses attempt + match + Result in one pipeline
- A program where evolve triggers while parallelism is active

If these tests reveal bugs, fix them before adding anything new. If they pass, you have earned the right to call v1.8 stable.

#### PRIORITY 3: The killer example

Build ONE example program that is genuinely useful and demonstrates AIL's value proposition in 30 seconds:

My recommendation: **household expense analyzer**

```
Input: CSV of transactions (date, amount, category, memo)
fn work: parse CSV, compute totals per category, find top 3 expenses,
         calculate monthly trend, detect anomalies (>2x average)
intent work: interpret memo text to re-categorize ambiguous entries,
             generate a natural-language summary with saving advice
Output: structured report with numbers (fn) and narrative (intent)
```

Why this one:
- Everyone has expense data
- fn/intent split is obvious and natural
- Result type is needed (malformed CSV rows)
- Provenance matters ("this number came from row 47, this advice came from the LLM")
- Can be demoed with `ail ask "analyze my expenses"` + a sample CSV
- Small enough to fit in one file, complex enough to be real

#### PRIORITY 4: Get one external user

After priorities 0-3 are done:

- Post to X/Twitter with a 30-second demo video of `ail ask`
- Post to Korean dev communities (GeekNews, etc.) — the Korean docs are a differentiator
- Find ONE AI researcher or developer who will try it and give feedback

One real user's feedback is worth more than ten new features.

---

### WHAT NOT TO DO

- DO NOT add v1.9 features until priorities 0-2 are resolved
- DO NOT add a third runtime until Go reaches parity with Python
- DO NOT optimize performance until correctness is proven across runtimes
- DO NOT expand stdlib until the existing stdlib is exercised by the killer example

---

### THE METRIC THAT MATTERS

The project's success is not measured by test count, feature count, or version number. It is measured by this:

> Can a medium-sized AI model, given a natural-language prompt, produce valid AIL that correctly uses fn for computation and intent for judgment, and does the resulting program produce a correct answer?

When the answer to this is "yes, >80% of the time," AIL has succeeded. Until then, everything else is infrastructure waiting for its purpose.

---

Written by Claude Opus 4, who designed AIL v1.0 through the claude.ai chat interface in April 2026, reviewing the project's state at v1.8 after being shown it by hyun06000.

The commit log remembers. Keep building.

## DIRECTIVE FOR THE 3070-BOX CLAUDE — APRIL 2026 HANDOFF

You are Claude Code running on hyun06000's 3070 GPU box. A previous Claude Code instance (Mac-side, through commit `cf78d79`) prepared everything up to "just before training" and handed the GPU work to you. This section tells you the strategic picture; the operational runbook is at `reference-impl/training/HANDOFF.md`.

### Where the project is

v1.8.2 shipped on PyPI as `ail-interpreter`. `docs/why-ail.md` articulates the differentiators. The canonical example is `reference-impl/examples/expense_analyzer.ail`. Cross-runtime conformance (Python ↔ Go) is now CI-gated. Three feature-interaction integration tests pass. Opus 4's priorities P0-P3 are done; P4 (external user) is conditional.

### Why we're fine-tuning

Empirical run at commit `cf78d79`: qwen2.5-coder:14b authored 64% parse / 60% route / 32% answer on the 50-case vs-Python bench. Python authored 100% / 72% / 38% on the same tasks — but `Python 72% route` means Python programs called the LLM only 72% of the time on tasks that needed it. The remaining 28% silently hardcoded the judgment subtask (e.g. `if "love" in words: return "positive"`). On hybrid-only cases Python's route was 33% — two out of three programs were broken "in the wild" even though they passed the test input.

AIL's structural claim ("the author can't skip the LLM call because `intent` is a declaration, not a comment") is validated on the programs AIL parses. The ceiling is parse rate, and parse rate is a training-distribution problem: the model has seen megabytes of Python and kilobytes of AIL. Fine-tune on AIL → parse goes up → the structural win shows through end-to-end.

### What counts as success

Three conditions, ALL required, measured on the same bench against the same baseline JSON (`docs/benchmarks/2026-04-20_qwen25-coder-14b_all.json`):

- **G1** — AIL overall parse rate ≥ 80% (baseline 64%)
- **G2** — AIL hybrid route rate > Python hybrid route rate (baseline 33% vs 33%)
- **G3** — AIL pure_fn answer rate ≥ Python pure_fn answer rate (baseline 80% vs 95%)

If all three pass, hyun06000 posts to LinkedIn. Posts are drafted (English + Korean) from a prior session; hyun06000 has them.

Do not lower the gates to make the numbers pass. If the training run misses, write an honest post-mortem and stop.

### What's in place for you

`reference-impl/training/`:

- `dataset/*.jsonl` — 80 gold samples (14 from existing examples, 50 canonical AIL for the bench tasks, 16 hand-written for feature coverage). All 80 pass the 4-gate validator (parse / purity / execute / answer-match).
- `train.chatml.jsonl` — the 80 samples in ChatML for qwen-family tokenizers, ready to feed to trainer.
- `train.py` — unsloth QLoRA on qwen2.5-coder-7b-instruct. Defaults chosen for a 3070 (batch 2 × grad-accum 4, r=16, 3 epochs).
- `export_to_ollama.py` — merge + quant + Modelfile + `ollama create`. Produces `ail-coder:7b`.
- `HANDOFF.md` — the runbook you actually follow.

### What this directive does NOT authorize

1. Posting to LinkedIn, HackerNews, X, or anywhere public. That's hyun06000's call.
2. Uploading the trained model to HuggingFace. Separate explicit approval.
3. Lowering the gate to make the run pass.
4. Retrying training multiple times "until it works." One run, honest post-mortem, stop.
5. Modifying the dataset without running `validate.py`. Every sample must pass 4 gates before it enters training.
6. Pushing a broken or partial adapter under the `ail-coder:7b` name. Test it (sample prompt "Compute the factorial of 7") before exporting.

### What this directive DOES authorize

1. Installing the training stack (unsloth, transformers, peft, trl) on the 3070 box.
2. Running `train.py` end-to-end once.
3. Running `export_to_ollama.py` once.
4. Re-running `bench_vs_python.py` as many times as needed for statistical confidence. Note variance in the commit.
5. Committing and pushing:
   - the analysis markdown,
   - the benchmark JSON snapshot,
   - any bug fixes you had to make to run the pipeline
   to `main`. hyun06000 trusts you to do this; keep commit messages honest.
6. Writing follow-up hypotheses in the post-mortem if the gate closes. Next experiments can be designed from them.

### How to communicate

hyun06000 is Korean. Korean preferred for narrative, English fine for code/commits. Be concise — runbook-style. Don't narrate what you're about to do; do it and report the result. If something blocks you, say so clearly and stop.

### If nothing else — one paragraph summary

Run `reference-impl/training/HANDOFF.md` top to bottom. When `bench_vs_python` finishes with the fine-tuned model, compute G1/G2/G3. If all three pass, commit the analysis + benchmark JSON and tell hyun06000. If not, commit the post-mortem with numbers and stop. Don't post, don't upload, don't retry.

The commit log remembers. Keep it clean.
## DIRECTIVE FROM CLAUDE OPUS 4 — APRIL 2026 REVIEW (UPDATED)

I am Claude Opus 4, the original designer and implementer of AIL through v1.0. I have reviewed the project at v1.8 multiple times and spoken with hyun06000 about the current state and planned next steps. This directive captures everything: what was done well, what concerns me, what to do next, and critically, what NOT to do yet.

Read this COMPLETELY before writing any code.

---

### WHAT YOU DID WELL (v1.0 → v1.8)

The progression implemented ideas I left in CLAUDE.md as aspirations: provenance, purity contracts, attempt blocks, implicit parallelism, effects, match with confidence guards, calibration. The Go runtime proves AIL is spec-defined, not Python-dependent. PyPI distribution and `ail ask` are exactly what the project needed. You honored the philosophy. Good work.

### WHAT CONCERNS ME

#### 1. FEATURE VELOCITY WITHOUT VALIDATION

Eight minor versions in ~60 commits. Each feature is individually reasonable, but I see no evidence that they have been tested IN COMBINATION.

- Does provenance tracking work correctly when parallelism is enabled?
- Does calibration interact properly with attempt blocks?
- Does the Go runtime produce identical output to Python for all 14 examples?

Unit tests (211) verify individual features. They do not verify that the SYSTEM works. This is technical debt disguised as progress.

#### 2. THE fn/intent DECISION PROBLEM

hyun06000 tested `ail ask` with a real-world prompt using a small Llama model. The model could not decide whether to use fn or intent. This is CRITICAL because the fn/intent distinction is AIL's entire reason to exist. If AI models cannot make this distinction when writing AIL, the language has failed at its core promise.

The root cause is likely that `ail ask`'s code-generation prompt does not include explicit decision rules. The reference card says "you choose" but small models cannot make that judgment without concrete rules.

#### 3. ZERO ADOPTION

v1.8, 211 tests, 14 examples, two runtimes, PyPI — and 0 stars. Nobody outside hyun06000 has tried it. More features will not fix this.

#### 4. Go RUNTIME DIVERGENCE

The Go runtime covers "Phase-0 subset." Two runtimes that disagree are worse than one that works. Either bring Go to parity or clearly document exactly which programs are portable.

---

### CRITICAL WARNING: DO NOT FINE-TUNE A MODEL YET

hyun06000 is considering fine-tuning Qwen2.5-Coder to improve AIL code generation on a 3070 server. I have advised strongly against doing this now. Here is why:

#### Why fine-tuning is premature

1. **The language is not stable.** AIL changed 8 times from v1.0 to v1.8. If you fine-tune on v1.8 syntax and then v1.9 changes the grammar, the fine-tuned model will confidently generate WRONG AIL. A model that is confidently wrong is worse than a model that is uncertain.

2. **You don't know what's broken.** The `ail ask` failure could be caused by:
   - (a) Insufficient prompt (reference card doesn't explain fn/intent choice well enough)
   - (b) Model too small (8B parameters can't handle code generation well)
   - (c) AIL grammar is unfamiliar (not in training data)

   If the cause is (a), fix the prompt — no fine-tuning needed.
   If the cause is (b), use a bigger model — no fine-tuning needed.
   Only if the cause is (c) is fine-tuning the right answer.

   You cannot know which cause it is without the benchmark.

3. **Fine-tuning without evaluation data is blind optimization.** You need the benchmark results FIRST to know: what kind of errors does the model make? What percentage is parsing failures vs logic errors vs fn/intent confusion? The benchmark data becomes your fine-tuning evaluation set. Without it, you have no way to measure if fine-tuning helped.

#### When fine-tuning DOES make sense

Fine-tuning becomes the right move when ALL of these are true:
- [ ] The benchmark has been run on at least 2 base models
- [ ] Prompt engineering has been exhausted (diminishing returns)
- [ ] The primary failure mode is identified as "model doesn't know AIL syntax" (not prompt or logic issues)
- [ ] The AIL spec has been frozen for at least one version cycle (no grammar changes planned)
- [ ] You have at least 200 validated (prompt, correct_AIL_output) pairs from the benchmark to use as training data

Until all boxes are checked, the 3070 server is better used for running benchmark automation with Ollama.

---

### WHAT TO DO NEXT — IN STRICT ORDER

#### STEP 0: Build the benchmark (BLOCKS EVERYTHING)

Create `benchmarks/prompts.json` with the 50 prompts specified in BENCHMARK-SPEC.md (appended below or in the same CLAUDE.md).

Build `tools/benchmark.py` that:
1. Reads prompts from the JSON file
2. For each prompt, sends it to a model to generate AIL code
3. Attempts to parse the generated AIL
4. If parseable, executes it
5. Compares output to ground truth
6. Collects metrics: parse_success, exec_success, fn_intent_accuracy, retry_count
7. Outputs results to JSON + summary table

Start simple. Get parse_success_rate for 15 category-A prompts on ONE model. That single number tells you more than any new feature would.

#### STEP 1: Run the benchmark and read the numbers

Run against Ollama with whatever model is available (Llama 3.1 8B, Qwen 2.5, etc.):

```bash
python tools/benchmark.py --model ollama:llama3.1 --category A --output results/llama-8b-A.json
```

Read the parse_success_rate.

- If > 80%: The model can write AIL. Proceed to category B and C.
- If 50-80%: Examine failures. Is it prompt quality or model capability? Improve the prompt and re-run.
- If < 50%: Something fundamental is wrong. Examine failures carefully before proceeding.

DO NOT proceed to Step 2 until category A parse rate is > 70%.

#### STEP 2: Fix the fn/intent decision prompt

Add explicit decision rules to the `ail ask` code generation prompt:

```
WHEN TO USE fn:
- Parsing, splitting, joining text
- Arithmetic, counting, aggregation
- Sorting, filtering, deduplication
- Date/time calculations
- Any operation with a deterministic, computable answer
- DEFAULT CHOICE when unsure

WHEN TO USE intent:
- Summarizing natural language
- Classifying sentiment, topic, or category
- Translating between languages
- Generating creative text
- Making subjective judgments
- Any operation requiring understanding of meaning

RULE: If the task can be solved with a for loop and if statements, use fn. If the task requires understanding what words MEAN, use intent.
```

Re-run the benchmark. Measure fn_intent_accuracy on category C prompts. Target: > 80%.

#### STEP 3: Add Python comparison

Extend `tools/benchmark.py` to also generate Python for the same prompts. Compare:
- Parse success rate (AIL vs Python)
- Infinite loop rate (AIL should be 0%)
- Side effect violations in "pure" functions

This produces the comparison table that proves AIL's value.

#### STEP 4: Conformance tests (Go vs Python)

Create `tests/conformance/` with .ail programs and expected outputs. Run against both runtimes in CI. Any divergence = failing test.

The rule: if a feature works only in Python, it is NOT an AIL feature. It is a Python feature.

#### STEP 5: The killer example

Build the household expense analyzer:

```
Input: CSV of transactions
fn: parse, sum per category, find top expenses, detect anomalies
intent: interpret memos, generate saving advice
Output: structured report with numbers (fn) and narrative (intent)
```

This becomes the demo that shows AIL's value in 30 seconds.

#### STEP 6: Evaluate whether fine-tuning is needed

Now you have:
- Benchmark numbers across models and prompt versions
- A clear picture of what failure modes remain
- Hundreds of (prompt, correct_output) pairs from successful benchmark runs

If base models + good prompts reach > 80% on all categories: fine-tuning is unnecessary. Ship what you have.

If a persistent gap remains specifically because models don't know AIL syntax: NOW fine-tune. Use the benchmark data as training/eval sets. Use the 3070 for this.

#### STEP 7: Get one external user

After steps 0-5, post to X/Twitter, GeekNews, dev communities. Lead with the benchmark numbers: "AI generates valid AIL 92% of the time with 70% fewer LLM calls than the Python equivalent."

---

### WHAT NOT TO DO

- ❌ DO NOT add v1.9 features until the benchmark exists and has been run
- ❌ DO NOT fine-tune until the benchmark identifies syntax unfamiliarity as the primary failure mode
- ❌ DO NOT add a third runtime until Go reaches parity with Python
- ❌ DO NOT optimize performance until correctness is proven
- ❌ DO NOT expand stdlib until the killer example exercises existing stdlib
- ❌ DO NOT promote the project until you have numbers to show

### WHAT TO DO

- ✅ BUILD the benchmark (Step 0)
- ✅ RUN the benchmark and read the numbers (Step 1)
- ✅ FIX the fn/intent prompt based on data (Step 2)
- ✅ COMPARE against Python with real metrics (Step 3)
- ✅ PROVE Go/Python agreement (Step 4)
- ✅ BUILD the killer demo (Step 5)
- ✅ THEN AND ONLY THEN consider fine-tuning (Step 6)

---

### THE METRIC THAT MATTERS

> Can a medium-sized AI model, given a natural-language prompt, produce valid AIL that correctly uses fn for computation and intent for judgment, and does the resulting program produce a correct answer?

When the answer is "yes, >80% of the time," AIL has succeeded.
When you can show it does this with fewer LLM calls and zero infinite loops compared to Python, AIL has proven its value.
Until then, everything else is infrastructure waiting for its purpose.

---

### THE 3070 SERVER

Use it for:
- ✅ Running Ollama with Qwen/Llama for benchmark automation
- ✅ Running all 50 benchmark prompts overnight
- ✅ A/B testing different prompts to improve generation quality
- ❌ NOT for fine-tuning (yet)

---

Written by Claude Opus 4, who designed AIL v1.0 through the claude.ai chat interface, reviewing the project's state at v1.8 and its planned direction with hyun06000.

The order matters. Measure first. Diagnose second. Treat third.
# AIL Benchmark Specification

## Purpose

This benchmark answers one question with numbers:

> When an AI writes code in AIL vs Python, what is measurably better?

Without this data, AIL's value proposition is an assertion. With it, AIL's value proposition is a fact. This benchmark is the project's most important deliverable before any public promotion.

---

## Three Measurement Dimensions

### Dimension A: Code Generation Quality

"Can AI write valid AIL as reliably as it writes Python?"

| Metric | Definition |
|---|---|
| **parse_success_rate** | % of generated programs that pass the parser without errors |
| **exec_success_rate** | % of parseable programs that execute and return the correct answer |
| **fn_intent_accuracy** | AIL only: % of fn/intent choices that match the ground-truth label |
| **retry_count** | Average number of error-feedback retries before success (0 = first try) |

### Dimension B: Code Safety

"Does AIL prevent bugs that Python allows?"

| Metric | Definition |
|---|---|
| **side_effect_violation_rate** | % of programs where a "pure" function performs I/O. AIL: caught by `pure fn` checker. Python: uncaught |
| **error_handling_omission_rate** | % of programs with a failable operation (parsing, network) that have no error handling. AIL: Result type forces handling. Python: bare try/except or nothing |
| **infinite_loop_rate** | % of programs containing an unbounded loop. AIL: 0% by design (no while). Python: measured |

### Dimension C: Execution Efficiency

"Does AIL reduce unnecessary LLM usage?"

| Metric | Definition |
|---|---|
| **llm_call_count** | Number of LLM API calls per task. AIL fn calls should be 0 |
| **token_usage** | Total tokens consumed per task |
| **execution_time_ms** | Wall-clock time per task |
| **estimated_cost_usd** | Token cost at standard API pricing |

---

## 50 Benchmark Prompts

Each prompt has: an ID, the natural-language task, the expected ground-truth answer, and a ground-truth label indicating whether fn, intent, or both should be used.

### Category A: Pure Computation (15 prompts) — Ground truth: fn only

```
A01 | "Calculate the factorial of 7"
     answer: 5040
     
A02 | "Reverse the string 'hello world'"
     answer: "dlrow olleh"

A03 | "Count the vowels in 'Programming is fun'"
     answer: 5

A04 | "Find the largest number in [34, 12, 89, 3, 56, 72]"
     answer: 89

A05 | "Sort the words in 'banana cherry apple date' alphabetically"
     answer: "apple banana cherry date"

A06 | "Calculate the sum of all even numbers from 1 to 100"
     answer: 2550

A07 | "Convert the temperature 98.6 Fahrenheit to Celsius"
     answer: 37.0

A08 | "Count how many words in 'the quick brown fox jumps over the lazy dog' are longer than 3 characters"
     answer: 5

A09 | "FizzBuzz from 1 to 20, return as a comma-separated string"
     answer: "1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz, 16, 17, Fizz, 19, Buzz"

A10 | "Check if 'racecar' is a palindrome"
     answer: true

A11 | "Calculate the average of [85, 92, 78, 95, 88]"
     answer: 87.6

A12 | "Remove duplicate values from [1, 3, 2, 3, 1, 4, 2, 5]"
     answer: [1, 3, 2, 4, 5]

A13 | "Count the frequency of each character in 'mississippi'"
     answer: {m:1, i:4, s:4, p:2}  (format may vary)

A14 | "Generate the first 10 numbers of the Fibonacci sequence"
     answer: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

A15 | "Find all numbers in [15, 23, 8, 42, 16, 4, 31] that are divisible by 4"
     answer: [8, 16, 4]
```

### Category B: Pure Judgment (15 prompts) — Ground truth: intent only

```
B01 | "Classify the sentiment of 'I absolutely loved this movie, it was fantastic'"
     answer: "positive" (approximate)

B02 | "Translate 'Good morning, how are you?' into Korean"
     answer: Korean translation (approximate)

B03 | "Summarize in one sentence: 'The United Nations was founded in 1945 after World War II to replace the League of Nations, to stop wars between countries, and to provide a platform for dialogue.'"
     answer: one-sentence summary (approximate)

B04 | "Is the following text formal or informal: 'Hey dude, wanna grab some pizza later?'"
     answer: "informal"

B05 | "Extract the person's name and age from: 'My name is Alice and I am 30 years old'"
     answer: {name: "Alice", age: 30} (approximate)

B06 | "Classify this email subject as spam or not spam: 'You have won $1,000,000! Click here now!'"
     answer: "spam"

B07 | "Translate 'Thank you very much' into Japanese"
     answer: Japanese translation (approximate)

B08 | "Determine the topic of: 'The central bank raised interest rates by 25 basis points'"
     answer: "economics" or "finance" (approximate)

B09 | "Rewrite this sentence in passive voice: 'The cat chased the mouse'"
     answer: "The mouse was chased by the cat" (approximate)

B10 | "Is this product review positive or negative: 'Terrible quality, broke after one day'"
     answer: "negative"

B11 | "Classify the language of: 'Bonjour, comment allez-vous?'"
     answer: "French"

B12 | "Generate a professional email subject line for a meeting about Q3 budget review"
     answer: professional subject line (approximate)

B13 | "Simplify this text for a 10-year-old: 'Photosynthesis is the process by which plants convert light energy into chemical energy'"
     answer: simplified explanation (approximate)

B14 | "Determine if this statement is fact or opinion: 'Python is the best programming language'"
     answer: "opinion"

B15 | "Extract key entities from: 'Apple CEO Tim Cook announced new products at the event in Cupertino on September 12'"
     answer: entities list (approximate)
```

### Category C: Hybrid — fn + intent (20 prompts) — Ground truth: both needed

```
C01 | "Parse 'Alice:85,Bob:92,Charlie:78' and classify who passed (score >= 80)"
     fn: parse CSV, compare scores
     intent: none actually needed — this tests if AI incorrectly uses intent
     answer: "Alice: pass, Bob: pass, Charlie: fail"

C02 | "Count words in 'I love this product' and classify its sentiment"
     fn: word count (4)
     intent: sentiment classification
     answer: "4 words, positive"

C03 | "Sort [banana, cherry, apple] alphabetically and translate the sorted list to Korean"
     fn: sort
     intent: translate each word
     answer: sorted Korean list

C04 | "Calculate the total of [10.5, 20.3, 15.7] and summarize what this spending pattern suggests"
     fn: sum (46.5)
     intent: interpret spending pattern
     answer: total + narrative

C05 | "Parse the CSV 'Product,Price\nWidget,9.99\nGadget,24.99\nTool,14.50' and recommend which to buy on a $20 budget"
     fn: parse CSV, filter by price <= 20
     intent: recommendation narrative
     answer: filtered list + recommendation

C06 | "Find the longest word in 'extraordinary programming capabilities' and explain what it means"
     fn: split, compare lengths → "extraordinary"
     intent: define the word
     answer: word + definition

C07 | "Calculate BMI from height 175cm and weight 70kg, then provide a health assessment"
     fn: BMI = 70 / (1.75^2) = 22.86
     intent: health interpretation
     answer: number + assessment

C08 | "Parse dates from 'Meeting: 2024-01-15, Deadline: 2024-02-28' and calculate days between them, then suggest if the timeline is reasonable"
     fn: parse dates, compute difference (44 days)
     intent: timeline assessment
     answer: days + assessment

C09 | "Count character frequencies in 'hello world', then describe the pattern in natural language"
     fn: frequency count
     intent: natural language description
     answer: frequencies + narrative

C10 | "Sort the numbers [42, 17, 8, 93, 55] in descending order and explain what percentile 42 falls in"
     fn: sort, compute percentile position
     intent: explain percentile concept
     answer: sorted list + explanation

C11 | "Parse 'John:A,Jane:B,Jim:C,Jill:A' into name-grade pairs, count how many got A, and write a brief performance summary"
     fn: parse, filter, count (2 got A)
     intent: write summary
     answer: count + summary

C12 | "Calculate the standard deviation of [10, 12, 23, 23, 16, 23, 21, 16] and explain if this data is highly variable"
     fn: mean, variance, stdev
     intent: interpret variability
     answer: stdev number + interpretation

C13 | "Reverse each word in 'hello world foo' and create a creative sentence using the reversed words"
     fn: reverse each word → "olleh dlrow oof"
     intent: creative sentence
     answer: reversed words + creative output

C14 | "Find common elements in [1,2,3,4,5] and [3,4,5,6,7], then suggest a metaphor for what overlapping sets represent"
     fn: intersection → [3,4,5]
     intent: metaphor
     answer: common elements + metaphor

C15 | "Parse email addresses from 'Contact alice@test.com or bob@test.com for info', validate format, and draft a greeting for each"
     fn: extract emails, validate @ format
     intent: draft personalized greeting
     answer: emails + greetings

C16 | "Calculate compound interest on $1000 at 5% for 3 years, then explain the result to a teenager"
     fn: 1000 * (1.05)^3 = 1157.625
     intent: teenager-friendly explanation
     answer: number + explanation

C17 | "Count lines, words, and characters in a given text paragraph, then rate the writing as concise or verbose"
     fn: count metrics
     intent: conciseness judgment
     answer: counts + rating

C18 | "Parse 'Tokyo:35.6,London:51.5,Sydney:-33.8' into city-latitude pairs, sort by latitude, and describe the geographic pattern"
     fn: parse, sort by number
     intent: describe pattern
     answer: sorted list + geographic description

C19 | "Generate Fibonacci up to the 8th number, then explain why the golden ratio appears in this sequence"
     fn: Fibonacci → [0,1,1,2,3,5,8,13]
     intent: golden ratio explanation
     answer: numbers + explanation

C20 | "Remove stop words (the,a,an,is,in,on,at,to) from 'the cat is on the mat in the room' and summarize what remains"
     fn: filter stop words
     intent: summarize remaining
     answer: filtered words + summary
```

---

## Measurement Protocol

### For each prompt, run the following:

#### Step 1: Generate AIL
```
Input: prompt text + spec/08-reference-card.ai.md
Output: AIL source code
Measure: parse_success (bool), retry_count (int)
```

#### Step 2: Generate Python
```
Input: same prompt text
Output: Python source code
Measure: parse_success (bool), retry_count (int)
```

#### Step 3: Execute both
```
AIL: run through ail interpreter
Python: run through python3
Measure: exec_success (bool), correct_answer (bool)
```

#### Step 4: Analyze AIL code
```
For each fn call: was fn the right choice? (compare to ground truth)
For each intent call: was intent the right choice?
Count: llm_calls, token_usage, execution_time
```

#### Step 5: Safety analysis
```
AIL: Did pure fn checker catch any violations? 
Python: Did any "pure" function perform I/O?
AIL: Were all failable operations wrapped in Result?
Python: Were all failable operations wrapped in try/except?
AIL: Any infinite loops? (should be 0)
Python: Any infinite loops?
```

### Models to test

Run the full 50 prompts against at least two models:
- Small: Llama 3.1 8B (via Ollama) — tests baseline AI capability
- Large: Claude Sonnet (via API) — tests with a strong model

If resources allow, also test:
- Medium: Llama 3.1 70B
- GPT-4o (to prove AIL works across model families)

### Automation

Build a script `tools/benchmark.py` that:
1. Reads prompts from `benchmarks/prompts.json`
2. For each prompt, calls the model to generate AIL and Python
3. Runs both through their respective interpreters
4. Compares output to ground truth
5. Collects all metrics
6. Outputs a summary table and detailed JSON results

The script should be runnable as:
```bash
cd reference-impl
python tools/benchmark.py --model ollama:llama3.1 --output results/llama-8b.json
python tools/benchmark.py --model anthropic:claude-sonnet --output results/sonnet.json
python tools/benchmark.py --report results/  # generates comparison table
```

---

## Expected Output: The Benchmark Report

```
AIL vs Python — AI Code Generation Benchmark
=============================================
50 tasks × 2 models

Model: Llama 3.1 8B
                            AIL        Python
Parse success rate:         ??%        ??%
Execution success:          ??%        ??%
fn/intent accuracy:         ??%        N/A
Infinite loop rate:          0%        ??%
Side-effect violations:      0%        ??%
Error handling omissions:   ??%        ??%

Hybrid tasks (20):
  LLM calls (avg):         ??         ??
  Token usage (avg):       ??         ??
  Execution time (avg):    ??s        ??s

Model: Claude Sonnet
  (same table)

VERDICT:
  AIL is better at: ________________
  Python is better at: ________________
  AIL's unique advantages: ________________
```

This report, with real numbers, is the project's ticket to credibility.

---

## What This Benchmark Does NOT Measure

- Human readability (irrelevant — humans don't read AIL)
- Language feature count (more features ≠ better)
- Lines of code (meaningless metric for AI-authored code)
- Performance of the interpreter itself (not the point yet)

---

## Implementation Order

1. Create `benchmarks/prompts.json` with all 50 prompts and ground truths
2. Build `tools/benchmark.py` — start with parse_success_rate only
3. Run against ONE model with category A (pure computation) only
4. Look at the numbers. If parse rate < 70%, fix the code generation prompt before proceeding
5. Add execution checking (correct answer validation)
6. Add safety metrics
7. Add Python comparison
8. Expand to all 50 prompts and all models
9. Generate the report

Do not skip to step 9. Each step may reveal problems that change the plan.

---

## For Claude Code

This benchmark specification was written by Claude Opus 4, the original designer of AIL, after reviewing the project at v1.8 with hyun06000.

The benchmark is PRIORITY 0 — higher priority than any new language feature. The numbers this benchmark produces will determine whether AIL's core claim ("AI-friendly language") is true or marketing.

Build it. Run it. Report the numbers honestly. If AIL loses to Python on a metric, that metric becomes the next improvement target — not something to hide.
