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

v1.8 with 211 tests, 14 examples, two runtimes, PyPI distribution — and 0 stars. This means nobody outside hyun06000 has tried it. More features will not fix this. The project needs ONE person to run `pip install ailang && ail ask "hello"` and find it useful.

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
