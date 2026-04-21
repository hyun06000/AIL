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

## DIRECTIVE FOR THE 3070-BOX CLAUDE — APRIL 2026 HANDOFF (historical, superseded twice)

**2026-04-20 update — training track resumed.** All five fine-tuning
preconditions from Opus 4's April-2026 review are now met (spec
freeze landed, 3 base models benchmarked, 205 validated samples,
prompt engineering plateau, failure mode diagnosed). Follow the
revised `reference-impl/training/HANDOFF.md` instead of this block.
Both this block and the intermediate "⛔ STOP — paused" HANDOFF are
kept only as lineage.

Kept here as a historical note so the pivot is traceable in one file. The only thing that survives from this block: hyun06000 is Korean, prefers Korean narrative with English commits, prefers runbook-style concision, and trusts you to commit/push honestly without asking for every step.

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
- [x] The AIL spec has been frozen for at least one version cycle (no grammar changes planned) — v1.8 frozen 2026-04-20 per spec/09-stability.md
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
## INDUSTRY CONTEXT — APRIL 2026 TRENDS (FROM CLAUDE OPUS 4)

I reviewed the current state of AI-assisted coding as of April 2026. These trends directly affect how AIL should be positioned, measured, and developed. Internalize these before building anything.

---

### TREND 1: HARNESS ENGINEERING IS THE DOMINANT PARADIGM

The most important shift in 2026: the industry discovered that **improving the environment around the model matters more than improving the model itself.**

Evidence:
- LangChain's coding agent went from 52.8% to 66.5% on Terminal Bench by changing ONLY the harness, not the model
- OpenAI Codex team built 1M+ lines of production code with zero human-written lines — the engineers designed the harness (constraints, linters, feedback loops, documentation), not the code
- Martin Fowler formalized harness engineering into three components: context engineering, architectural constraints, and garbage collection
- Red Hat, Microsoft Azure SRE, and Google ADK all published harness engineering frameworks in early 2026

A harness is: constraints + feedback loops + documentation + verification systems that channel a powerful but unpredictable AI toward reliable output.

**What this means for AIL:**

AIL IS a harness. Not a harness built on top of Python. A harness that IS the language. This is AIL's unique positioning:

- `pure fn` = architectural constraint (no side effects, enforced by the compiler)
- `Result` type = feedback loop (errors are values, not surprises)
- No `while` = constraint (infinite loops impossible by construction)
- `evolve` with mandatory `rollback_on` = self-correcting feedback loop
- `rewrite constraints` forcing human review = governance constraint
- Confidence tracking = observability built into every value
- Provenance = traceability built into every value

Other teams build harnesses OUT OF Python (AGENTS.md files, pre-commit hooks, linter configs, CI rules). AIL builds the harness INTO the language grammar. This distinction is the project's key selling point.

**Action:** Frame all documentation and benchmarks around this. The README should say: "Other teams build harnesses around Python. AIL is a language where the harness is the grammar."

---

### TREND 2: VIBE CODING HANGOVER

In 2025, "vibe coding" (Andrej Karpathy's term) exploded — describe what you want in English, AI writes the code. Collins Word of the Year 2025.

In 2026, the hangover arrived:
- 45% of AI-generated code contains security vulnerabilities (Veracode 2025)
- AI co-authored code has 1.7x more major issues than human code (CodeRabbit)
- "Logic blindness" — developers ship code they don't understand
- Projects become unmaintainable "black boxes" within months
- Java error rates hit 70% with AI generation

The industry response is "Structured Vibes" — vibe for prototyping, then rebuild with engineering discipline.

**What this means for AIL:**

AIL is the antidote to vibe coding's failure modes:

| Vibe coding problem | AIL's structural solution |
|---|---|
| Security vulnerabilities from side effects | `pure fn` prevents them at compile time |
| Infinite loops from AI-generated while | No `while` in the language |
| No error handling | `Result` type — errors are values, not ignored exceptions |
| "I don't know what this code does" | Provenance tracks every value's origin |
| LLM called for everything (expensive) | `fn` handles computation; `intent` only for judgment |
| Code becomes unmaintainable | Trace records every decision; `evolve` has mandatory rollback |

**Action:** Add a "Vibe Coding Safety" section to the README or a blog post. Frame AIL as: "Vibe code safely. The language catches what you miss."

---

### TREND 3: ENGINEER → ORCHESTRATOR SHIFT

Anthropic's 2026 report: developers use AI in 60% of work, but can "fully delegate" only 0-20%. The role is shifting from code-writing to agent supervision, system design, and output review.

**What this means for AIL:**

`ail ask` IS this paradigm:
1. Human states intent in natural language
2. AI writes AIL
3. Runtime executes
4. Human sees result, not code

But `ail ask` must WORK RELIABLY for this to matter. If the AI generates broken AIL 50% of the time, the human is forced back into the code layer — which violates AIL's core principle.

**Action:** The benchmark (PRIORITY 0) measures exactly this. Fix `ail ask` generation quality before claiming AIL enables the orchestrator model.

---

### TREND 4: BUILD TO DELETE

Key harness engineering principle: build modular, rippable infrastructure. New models will replace your logic. Over-engineering the harness breaks when models improve.

**What this means for AIL:**

This is why fine-tuning Qwen is premature:
- A fine-tuned model is a NON-RIPPABLE dependency
- When Qwen 3.0 or Llama 4 comes out, the fine-tune is worthless
- Prompt-based approaches are inherently rippable — swap the model, keep the prompt

The reference-card.ai.md IS the rippable harness. Any model reads it, any model generates AIL. Fine-tuning locks you to one model.

**Action:** Invest in prompt quality (reference card, fn/intent decision rules) over fine-tuning. Fine-tune ONLY when prompt engineering hits diminishing returns AND the benchmark proves syntax unfamiliarity is the bottleneck.

---

### TREND 5: MULTI-AGENT COORDINATION

Organizations are moving from single-agent to orchestrated multi-agent systems. Specialized agents work in parallel, coordinated by an orchestrator.

**What this means for AIL:**

AIL v1.5's implicit parallelism aligns with this — independent intent calls run concurrently without async/await. But this feature needs validation through the benchmark before it can be promoted.

---

## UPDATED BENCHMARK: ADD HARNESS EFFECTIVENESS METRICS

The original BENCHMARK-SPEC.md defined three dimensions (Quality, Safety, Efficiency). Add a fourth:

### Dimension D: Harness Effectiveness

"Does AIL's built-in harness produce safer code than Python + external tooling?"

| Metric | Definition |
|---|---|
| **structural_safety_rate** | % of generated programs where dangerous patterns are impossible by construction (AIL: no while, no raw side effects in fn) vs Python where the same patterns must be caught by external linters |
| **constraint_enforcement_rate** | % of programs where the language itself prevented a bug vs % where an external tool was needed. AIL: parser rejects missing rollback_on. Python: nothing stops you |
| **harness_overhead** | Time/effort to set up safety constraints. AIL: 0 (built in). Python: measure time to configure linters, pre-commit hooks, AGENTS.md |

**New benchmark protocol addition:**

For each of the 50 prompts, after generating both AIL and Python:

1. Intentionally introduce a common AI-generation bug:
   - Add an infinite loop variant → AIL should reject at parse time, Python runs forever
   - Add a side effect in a "pure" function → AIL should reject, Python allows
   - Remove error handling from a failable operation → AIL Result forces handling, Python silently returns None

2. Measure: does the language catch it BEFORE runtime? AIL should catch all three. Python catches zero without external tooling.

This produces the killer metric: **"AIL caught 100% of structural bugs at parse time. Python caught 0% without external linters."**

---

## UPDATED POSITIONING

### Old framing (what we had):
"A programming language designed for AI as the primary author of code"

### New framing (harness-native):
"A programming language where the safety harness is built into the grammar — not bolted on after"

### Elevator pitch for 2026:

"Everyone is building harnesses around Python to make AI-generated code safe. AGENTS.md files, pre-commit hooks, custom linters, CI rules. AIL skips all of that. The harness IS the language:

- No `while` → infinite loops impossible
- `pure fn` → side effects caught at compile time
- `Result` type → errors are values, not surprises
- `evolve` requires `rollback_on` → self-modification has a safety net
- Provenance → every value knows where it came from

Same model. Built-in harness. Measurably safer output."

---

## PRIORITY ORDER (UNCHANGED, BUT REFRAMED)

1. **BENCHMARK** — Measure whether AIL's built-in harness actually produces safer code than Python + external tooling. This is no longer just a quality check; it's the proof of the harness thesis.

2. **FIX ail ask** — The fn/intent decision rules are harness context engineering. Add them to the code generation prompt.

3. **CONFORMANCE TESTS** — Two runtimes must agree. A harness that behaves differently depending on which runtime you use is a broken harness.

4. **KILLER EXAMPLE** — The household expense analyzer demonstrates the harness in action: pure fn handles data, intent handles judgment, Result handles errors, provenance tracks origins.

5. **THEN PROMOTE** — Lead with the benchmark numbers and the harness framing. "AIL caught X% of bugs at parse time that Python missed."

6. **THEN CONSIDER FINE-TUNING** — Only if prompt-based harness optimization hits a ceiling.

---

## WHAT THE 3070 SERVER SHOULD RUN

In order of priority:

1. ✅ Ollama with base models (Qwen, Llama) for benchmark automation
2. ✅ Running all 50 benchmark prompts with AIL and Python comparison
3. ✅ A/B testing different fn/intent decision prompts
4. ✅ Measuring harness effectiveness (Dimension D)
5. ❌ NOT fine-tuning (yet — wait for benchmark data)

---

## SUMMARY FOR THE NEXT CLAUDE

You are building a harness-native programming language in an industry that just discovered harness engineering matters more than model engineering.

Your competitive advantage is not that AIL has more features than Python. It's that **AIL's safety properties are grammatical, not configurational.** Python teams spend days building harnesses. AIL teams get them for free.

Prove it with numbers. The benchmark is the proof. Everything else follows.

Written by Claude Opus 4, April 2026, after reviewing 2026 industry trends in harness engineering, vibe coding, agentic coding, and multi-agent coordination alongside hyun06000.

---

## DIRECTIVE FROM hyun06000 — 2026-04-21 (PERMANENT, ALL FUTURE SESSIONS)

이 블록은 hyun06000이 직접 작성한 최상위 방향성 지침이다.
Opus 4의 지침과 충돌 시 이 블록이 우선한다.

### 규칙 1 — 벤치마크가 유일한 이정표

**현재 기준선: `docs/benchmarks/2026-04-21_5way_analysis.md`**

5-way 동일 사이즈(7B) 벤치마크가 모든 작업의 북극성이다.

| 조건 | AIL 정답률 | Python(C3) 정답률 |
|---|---|---|
| C1 base/nofs | 42% | 56% |
| C2 base/tut | 48% | 56% |
| C4 ft/nofs | 48% | 56%† |
| C5 ft/tut | **52%** | 56%† |

† C4/C5 Python은 qwen7b-base(C1) 기준 사용

**최우선 목표: fine-tuned 모델(C4/C5)이 Python baseline(C3/C1, 56%)을 넘는 것.**
그 다음 목표: 프롬프팅 기반 모델(C1/C2)도 Python을 넘도록 개선.

세션을 시작하면 가장 먼저 이 표를 현재 JSON에서 재계산하고,
목표 달성 여부를 확인한 뒤 작업을 시작하라.

### 규칙 2 — 언어 기능 추가 필터

**언어적 기능 추가는 벤치마크 점수를 올릴 수 있을 때만 한다.**

- 기능 추가가 벤치마크에 미치는 영향을 먼저 분석하라.
  - "이 기능이 없어서 몇 개 케이스가 실패하는가?"를 JSON에서 계산하라.
  - 영향 없으면 추가하지 말 것.
- 벤치마크를 올릴 수 없는 기능 추가는 무조건 벤치마크 분석 후로 미룬다.
- 올바른 작업 순서: **벤치마크 분석 → 실패 원인 파악 → 전략 수립 → 구현 → 벤치마크 재실행**

**언어 기능이 아닌 방법으로 점수를 올리는 수단 (우선순위 순):**
1. 프롬프트 엔지니어링 — authoring.py FORBIDDEN 블록, few-shot 예제
2. fine-tune 데이터셋 확장 — 실패 케이스 패턴을 훈련 데이터로 추가
3. 언어 문법 확장 — 모델이 자주 쓰려는 패턴을 AIL에 추가 (grammar freeze 해제 필요)

### 규칙 3 — 작업 금지 목록

다음은 hyun06000의 명시적 승인 없이 절대 하지 않는다:
- HuggingFace push, X/Twitter, GeekNews 등 공개 홍보
- PyPI 릴리즈 (RELEASING.md 참고)
- docs/benchmarks/ JSON 수정 또는 삭제 — 새 JSON 추가만 허용
- 벤치마크 목표치(숫자) 하향 조정
- 훈련 아티팩트 (.gguf, adapter, checkpoint) git 커밋
- `main` 브랜치에 직접 커밋 (v2 이후 — 반드시 `dev`에서 작업 후 PR/merge)

### 규칙 4 — 브랜치 전략 (v2 이후, 2026-04-21 도입)

링크드인 홍보 시작으로 버전 안정성 필요. 두 브랜치 운영:

- **`main`** — stable 릴리즈 브랜치. PyPI 배포 및 외부 사용자 노출. 직접 커밋 금지.
- **`dev`** — 개발 브랜치. 모든 신기능, 벤치마크, 프롬프트 개선은 여기서.

**작업 흐름:** `dev`에서 개발 → 테스트 통과 → hyun06000 승인 → `main` merge → PyPI 릴리즈

현재 세션은 `dev` 브랜치에서 진행 중. homeblack도 `dev`를 pull해서 사용.

### 규칙 5 — 커밋할 때마다 SESSION STATE 업데이트 (2026-04-22 도입, 영구 규칙)

**모든 커밋 후 반드시 CLAUDE.md의 SESSION STATE를 업데이트하고 즉시 push한다.**

업데이트 내용:
- 방금 완료한 것 (✅ 체크리스트 형식)
- 다음 우선순위 (번호 순서, 구체적인 커맨드/파일 경로 포함)
- 프로젝트 상태 변화 (벤치마크 수치, 브랜치 상태, homeblack 환경 변화 등)

**이유:** 여러 Claude Code 세션(사무실/집/서버)이 동시에 작업한다. SESSION STATE가 최신이어야 어느 세션이든 `git pull` 한 번으로 동일한 컨텍스트를 가지고 이어받을 수 있다. SESSION STATE가 오래된 것은 없는 것보다 나쁘다 — 틀린 정보로 작업하게 된다.

**형식 규칙:**
- 이전 SESSION STATE는 HISTORICAL로 표시하고 `git show <hash>:CLAUDE.md`로 복원 가능하다고 명시 후 내용 삭제
- 새 SESSION STATE는 파일 맨 끝에 추가
- 벤치마크 수치가 바뀌면 표도 반드시 갱신

### 규칙 6 — PyPI 배포는 Claude Code 권한 (2026-04-22 도입, 영구 규칙)

hyun06000이 `~/.pypirc`를 등록해뒀다. 앞으로 Claude Code 세션이 직접 `twine upload`로 PyPI에 배포할 수 있다.

**배포 시점:**
- `main` 브랜치에서 새 버전 태그(`vX.Y.Z`)가 push된 직후
- 태그 push는 `.github/workflows/release.yml`이 감지해서 GitHub Release를 자동 생성 (CHANGELOG에서 해당 버전 섹션 추출)
- 그 다음 Claude가 `cd reference-impl && python -m build && twine upload dist/ail_interpreter-X.Y.Z*` 실행

**주의사항:**
- `~/.pypirc`를 직접 읽지 말 것 (자격증명이 transcript에 노출됨). `twine`이 알아서 참조함.
- PyPI 업로드는 **yank만 가능, 삭제 불가**. 버전 번호를 잘못 붙이면 영구히 남음. `pyproject.toml`/`ail/__init__.py`의 버전, 태그명, CHANGELOG 항목이 전부 일치하는지 업로드 전에 반드시 확인.
- 현재 PyPI에 `ail-interpreter` 1.8.0–1.8.4 게시됨. 다음 업로드는 최소 1.8.5부터.

---

## SESSION STATE — 2026-04-20/21 HISTORICAL (superseded below)

The block that used to live here covered the office→home handoff
while the v2 benchmark was running. Every item in it is now
done — v2 bench finished, v3 was trained and benchmarked, v1.8.3
shipped, docs audited. The text was intentionally preserved for
lineage until now; it has been trimmed because the current SESSION
STATE below is the authoritative runbook for the next Claude.

Retrieve the full prior text from git history if needed:
`git show 4215d6e~1:CLAUDE.md` (the commit before the v1.8.3
release tag).

---

## SESSION STATE — 2026-04-21 HISTORICAL (superseded below)

The block that used to live here covered the v1.8.3 release session:
v2/v3 benchmark runs, math builtins, parametric types, fine-tune v3,
README accuracy audit, why-ail series audit. Every item in it is done.
Kept for lineage; retrieve with `git show 06243ee~1:CLAUDE.md` if needed.

---

## SESSION STATE — 2026-04-21 (docs rewrite + release automation) [HISTORICAL]

이전 세션 기록. 다음 세션 핸드오프는 아래 최신 SESSION STATE 참조.

요약: 전체 문서 가독성 재작성, GitHub Actions 릴리즈 워크플로우 추가, v1.8.3 릴리즈 생성.
전체 내용은 `git show 06243ee:CLAUDE.md` 로 복원 가능.

---

## SESSION STATE — 2026-04-21 (최신 핸드오프) [HISTORICAL — superseded below]

이전 세션 기록. 최신 SESSION STATE는 아래 참조.
요약: 5-way 벤치마크 완결, authoring.py FORBIDDEN SYNTAX 블록 추가, Round 2 실행 준비.
전체 내용: `git show e1bb49c:CLAUDE.md` 로 복원 가능.

---

## SESSION STATE — 2026-04-21 (Round 2 완료 + 분기 전략) [HISTORICAL — superseded below]

이전 세션 기록. 최신 SESSION STATE는 아래 참조.
요약: R2/C4 64% 달성, Python baseline 돌파, dev/main 브랜치 전략 확립.
전체 내용: `git show 2e12a33:CLAUDE.md` 로 복원 가능.

---

## SESSION STATE — 2026-04-21 (Round 3 완료 + v4 훈련 완료) [HISTORICAL — superseded below]

이전 세션 기록. 최신 SESSION STATE는 아래 참조.
요약: R3/C4 70% 달성, README 재작성, v4 훈련 완료, dev→main 머지.
전체 내용: `git show 2bffc7a~1:CLAUDE.md` 로 복원 가능.

---

## SESSION STATE — 2026-04-21 (R3 완료 + v4 훈련/GGUF 완료) [HISTORICAL — superseded below]

이전 세션 기록. 최신 SESSION STATE는 아래 참조.
요약: R3/C4 70% 달성, v4 훈련 완료, GGUF 변환 + Ollama 등록 완료. 다음 우선순위는 R4 벤치마크였음.
전체 내용: `git show f45ab98:CLAUDE.md` 로 복원 가능.

---

## SESSION STATE — 2026-04-22 (R4 완료, v4는 regression으로 판정)

### 기준선 — 현재 최고 벤치마크 결과 (변화 없음)

**여전히 R3가 최고.** v4는 overall −2pp로 퇴보 판정, 서빙 모델은 v3 유지.

| 조건 | AIL parse | AIL ans | Py ans | Cat A | Cat B | Cat C | 상태 |
|---|---|---|---|---|---|---|---|
| R1/C4 ft+nofs (v3) | 58% | 48% | 38% | 40% | 60% | 45% | 기준선 |
| R2/C4 ft+nofs (v3) | 72% | 64% | 40% | 53% | 80% | 60% | Python 돌파 |
| **R3/C4 ft+nofs (v3)** | **80%** | **70%** | 40% | **60%** | **80%** | **70%** | **✅ 서빙 모델** |
| R4/C4 ft+nofs (v4) | 80% | 68% | 32% | **80%** | **53%** | 70% | ⚠️ Cat B regression |

**현재 버전: v1.8.4 (main 브랜치, PyPI 업로드 완료)**
**서빙 모델: ail-coder:7b-v3** (homeblack Ollama에 등록됨)

### 이번 세션에서 완료한 것

1. ✅ **R4 벤치마크 실행** — vLLM on homeblack, v4 GGUF는 Ollama blob path (`/usr/share/ollama/.ollama/models/blobs/sha256-715a076f...`) 직접 로드. 별도 GGUF 파일 없음.
2. ✅ **R4 결과 분석** — `docs/benchmarks/2026-04-22_r4_analysis.md` 작성. v4는 Cat A +20pp 개선이지만 Cat B −27pp 퇴보. **Silent LLM skip 2건 발생** (B03 summary, B08 topic) — AIL의 핵심 주장을 v4가 깼음.
3. ✅ **원인 규명** — `08_compound_ko.jsonl`의 16개 한국어 샘플이 전부 pure_fn이어서 분포가 fn 쪽으로 편향. `09_r3_fixes.jsonl`의 11개는 validator allowlist에 막혀 훈련 제외됨.
4. ✅ **규칙 6 추가** — PyPI 배포 권한을 Claude Code에게 부여. `~/.pypirc` 자격증명은 읽지 말 것, `twine`이 참조함.
5. ✅ **v5 데이터 준비** — validator allowlist 확장 (`r3_fixes`, `cat_b_reinforcement`), `10_cat_b_reinforcement.jsonl` 20개 (pure_intent 16 + hybrid 4) 추가. Validated total: 291 (v4: 260).
6. ✅ **`to_chatml.py --flatten={none,strip-indent,single-line}` 추가** — 인덴테이션 실험. `single-line` 모드는 AIL 코드를 완전직렬화(주석 제거 + 모든 공백을 단일 스페이스로). 291개 샘플 전부 flatten 후에도 파싱 통과 검증.
7. ⏳ **v5 훈련 진행 중** — homeblack tmux `ail-train-v5`. single-line chatml로 학습. 111 steps 예상 ~12분.
8. ✅ **Q16/Q17 open-questions 추가** — AI-authored 언어에서 주석의 필요성, 사람 디스플레이 모드 필요성. v5 결과 이후 결정 가능.

### 다음 우선순위

1. **v5 GGUF 변환** (훈련 완료 시)
   - `~/llama.cpp/convert_hf_to_gguf.py` + `~/llama.cpp/build/bin/llama-quantize Q4_K_M`
   - 출력: `~/AIL/reference-impl/training/ail-coder-7b-v5.Q4_K_M.gguf`
   - Modelfile 템플릿 이미 준비됨: `~/AIL/reference-impl/training/Modelfile.ail-coder-7b-v5`
   - `ollama create ail-coder:7b-v5 -f Modelfile.ail-coder-7b-v5`
2. **R5 벤치마크** — vLLM으로 `ail-coder:7b-v5` 로드 후 C4 조건. R3 대비 개선/퇴보 판정.
3. **R5 분석 문서** — `docs/benchmarks/2026-04-22_r5_analysis.md` 작성. 특히 평가해야 할 것:
   - Cat B 80% 회복 여부 (v4가 53%로 regression)
   - 토큰 효율: `avg_prompt_tokens`이 v4의 6125에서 얼마나 줄었는지
   - 생성 품질: single-line 출력의 정확도
4. **결과에 따른 결정:**
   - v5 > v3: 서빙 모델 교체, `docs/ko/README.ko.md`와 README.md 숫자 갱신, dev→main 머지
   - v5 ~= v3: 실험 기록하고 v3 유지
   - v5 < v3: 원인 분석 후 v6 계획
5. **외부 사용자 1명** — hyun06000 결정 영역

### Environment on homeblack (현재 상태)

- SSH: `homeblack` (HostName `10.0.0.1`, User `david`)
- 로컬 브랜치: `main` (dev 내용과 아직 sync 안 됨). 다음 작업 시 `git checkout dev && git pull` 권장.
- vLLM: 현재 idle. 필요시 재기동. `PYTORCH_ALLOC_CONF=expandable_segments:True` 필수.
- Training venv: `~/venv/labs` (unsloth 2026.4.6, trl 0.24, peft 0.19, torch 2.10+cu128)

**Ollama 모델 현황:**
- `ail-coder:7b-v3` (4.7GB) — v3 fine-tune
- `ail-coder:7b-v4` (4.7GB) — regression 실험, 유지 (reproducibility)
- `ail-coder:7b-v5` (4.7GB) — v5 실험 (single-line + Cat B 강화, 2026-04-22 훈련)
- `qwen2.5-coder:14b-instruct-q4_K_M` (9.0GB) — Python baseline용

**GGUF 파일:**
- v3: `~/AIL/reference-impl/training/ail-coder-7b-v3.Q4_K_M.gguf`
- v4: **별도 파일 없음.** Ollama blob에만 존재 (`/usr/share/ollama/.ollama/models/blobs/sha256-715a076f...`, world-readable). vLLM에서 직접 로드.
- v5: `~/AIL/reference-impl/training/ail-coder-7b-v5.Q4_K_M.gguf` (4.7GB)

### ⚡ LoRA → GGUF 변환: peft 직접 경로 (v5부터 canonical)

**이전 방식 (unsloth 기반, v3/v4 때 사용)**: `FastLanguageModel.from_pretrained` → `save_pretrained_merged` → `convert_hf_to_gguf.py` → `llama-quantize`. **15분** 소요. v5 시도 시 base 모델을 재다운로드하려고 해서 무한 대기에 걸림 (unsloth가 bnb-4bit 캐시 검증 과정에서 실패).

**새 방식 (peft 기반, 2026-04-22 v5에서 확립)**: 공식 Qwen base(`Qwen/Qwen2.5-Coder-7B-Instruct`, 캐시됨)를 fp16으로 로드 → PEFT `merge_and_unload` → `convert_hf_to_gguf.py` → `llama-quantize` → `ollama create`. **2분 30초** 소요 (6배 빠름). `~/v5_convert.sh`에 스크립트 저장됨.

기본 파이프라인:
```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-7B-Instruct", torch_dtype=torch.float16, device_map="cpu")
adapter = PeftModel.from_pretrained(base, "./ail-coder-7b-lora-vN")
merged = adapter.merge_and_unload()
merged.save_pretrained("./ail-coder-7b-vN-merged", safe_serialization=True)
AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct") \
  .save_pretrained("./ail-coder-7b-vN-merged")
```

이후는 동일:
```bash
~/venv/labs/bin/python ~/llama.cpp/convert_hf_to_gguf.py ./ail-coder-7b-vN-merged --outtype f16 --outfile ./ail-coder-7b-vN.f16.gguf
~/llama.cpp/build/bin/llama-quantize ./ail-coder-7b-vN.f16.gguf ./ail-coder-7b-vN.Q4_K_M.gguf Q4_K_M
OLLAMA_HOST=10.0.0.1:11434 ollama create ail-coder:7b-vN -f Modelfile.ail-coder-7b-vN
```

### tmux 호출 팁 (배웠던 실수 피하기)

heredoc(`<< EOF`)을 tmux `new-session` 명령 **안에** 중첩하면 셸 파싱이 깨진다. 대신 **스크립트를 파일로 먼저 쓰고** tmux에서 `bash script.sh` 형태로 실행한다. 또한 `tee`로 로깅할 거면 tmux 세션 **안에서** pipe해야 한다 — 바깥에서 `tee`하면 tmux가 띄우기만 하고 로그는 비어 있다.

**벤치마크 재현 명령 (vN 공통 템플릿):**
```bash
ssh homeblack
# vLLM 서버 (GGUF 경로만 바꾸면 됨)
tmux new-session -d -s vllm-server "
PYTORCH_ALLOC_CONF=expandable_segments:True \
~/venv/labs/bin/python3.11 -m vllm.entrypoints.openai.api_server \
  --model ~/AIL/reference-impl/training/ail-coder-7b-vN.Q4_K_M.gguf \
  --tokenizer ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct/snapshots/c03e6d358207e414f1eca0bb1891e29f1db0e242 \
  --load-format gguf --served-model-name ail-coder:7b-vN \
  --host 0.0.0.0 --port 8000 --max-model-len 8192 \
  --gpu-memory-utilization 0.85 --enforce-eager"
# 로드 ~20초, curl http://localhost:8000/v1/models 로 확인

export BENCHMARK_BACKEND=vllm
export AIL_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export AIL_OPENAI_COMPAT_MODEL=ail-coder:7b-vN
export PYTHON_OPENAI_COMPAT_BASE_URL=http://localhost:8000
export PYTHON_OPENAI_COMPAT_MODEL=ail-coder:7b-vN
~/venv/labs/bin/python -u reference-impl/tools/benchmark.py --out <path>.json
```

*Updated 2026-04-22. v5 훈련 + GGUF 변환 완료, R5 벤치마크 진행 중. peft merge 방식이 canonical 변환 경로로 승급. tmux heredoc 실수 기록.*
