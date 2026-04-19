# Changelog

All notable changes to the AIL project are documented in this file.

---

## v1.8.1 — 2026-04-20

**First PyPI release under the new name `ail-interpreter`.**

Distribution name on PyPI: `ail-interpreter` (was `ailang`, rejected
by PyPI's similarity check against `ai-lang`). Import name and CLI
both remain `ail`.

**Packaging fixes**
- `pyproject.toml` no longer packages a stray `ail_mvp/` directory
  (left over on contributor disks from the v1.8 rename).
- The language reference card is now bundled inside the wheel at
  `ail/reference_card.md`. Previously `ail ask` on pip installs
  silently fell back to a ~400-char stub instead of the real 22k
  spec, degrading author prompt quality.
- `tests/test_spec_bundled.py` guards against the bundled copy and
  `spec/08-reference-card.ai.md` drifting.

**Lexer**
- `#` is now accepted as an alias for `//` line comments in both
  the Python and Go runtimes. AI authors trained heavily on Python
  reach for it reflexively; the cost of rejecting was a lost-
  confidence moment per prompt. Spec keeps `//` canonical.

**`ail ask` — first real-world prompt (`factorial of 7`) on llama3.1:8B**
- Author prompt names the three real stdlib modules (core, language,
  utils) so the model stops inventing `stdlib/math`.
- `_remediation_hints` surface targeted corrections for five common
  failure classes (bad imports, ternary `?:`, generic type
  annotations like `[Number]`, literal `\n` escape leaks, top-level
  JSON-wrapper leaks) — each carried into the retry prompt as a
  constraint.
- Few-shot example #1 (trivial `return 42`) replaced with a factorial
  recursion example — small models anchor strongly to the first
  example, and the old one taught nothing.
- `ask()` auto-extracts a bare integer from the prompt as
  `input_text` when the caller didn't pin one. Covers programs like
  `factorial(to_number(x))` that would otherwise blow up recursion on
  empty input.
- Tolerance: when the model wraps its answer in a single backtick and
  echoes the prompt's examples section verbatim (observed on
  llama3.1:8B), `_recover_echoed_program` recovers the full AIL
  program from the echo rather than extracting just the bare
  expression.

**Benchmark**
- `tools/bench_authoring.py` rewritten to measure three axes — parse
  rate, fn/intent routing accuracy, final-answer correctness — across
  a 50-case corpus tagged `pure_fn` / `pure_intent` / `hybrid`.
  Baseline on llama3.1:8B: 54% parse, 52% routing, 30% final-answer.
  Hybrid routing jumped from 0/15 on the old prompt to 10/15 after
  the decision rules landed.

**Tolerance (unrelated to ask)**
- Malformed JSON wrapper recovery — when the model returns
  `{"value": "...", "confidence": 1.0}` with unescaped inner quotes,
  a regex-based lenient extractor pulls out the AIL source instead
  of falling through to the parser.
- Literal-`\n`-escape unescape — source with backslash-n and no real
  newlines gets decoded.

**Tests:** 223 passing (was 211 in v1.8.0).

---

## v1.5 — 2026-04-17

**Implicit parallelism.** Independent intent calls run concurrently.

- Consecutive Assignments whose RHS contain intent calls and are
  pairwise independent are grouped into parallel batches and evaluated
  via a ThreadPoolExecutor. No async/await — the independence is
  structural.
- Wall-clock latency for N independent intents drops from N·t to t.
- Dependent sequences (`b = f(a)`) stay sequential; the planner
  detects data flow.
- Trace entries from a batch carry `parallel=True`; batches are
  bracketed by `parallel_batch_start`/`_end` markers.
- Thread-safety: `Trace.record/enter/exit` are now lock-protected.

**Files:** `runtime/parallel.py` (new), `runtime/executor.py`,
`runtime/trace.py`, `examples/parallel_analysis.ail` (new).

**Tests:** 13 new (155 total).

---

## v1.4 — 2026-04-17

**`attempt` blocks — confidence-priority cascade.**

```ail
extracted = attempt {
    try direct_parse(x)     // pure, wins if ok
    try scan_tokens(x)      // pure, cheap fallback
    try infer_number(x)     // LLM — last resort
}
```

- Evaluates each `try` in order. A try qualifies when the result is
  not a Result-typed `error(...)` and its confidence ≥ 0.7.
- First qualifying try wins; if none qualify, the last try's value is
  returned with its low confidence preserved.
- Selected index is recorded via a new `attempt` origin kind; upstream
  lineage is preserved through the origin's parent chain.
- `pure fn` bodies may contain `attempt` blocks, but every `try` must
  itself be pure; intents inside a pure-fn attempt are rejected at
  parse time.

**Files:** `parser/ast.py` (`AttemptExpr`), `parser/parser.py`,
`parser/lexer.py`, `parser/purity.py`, `runtime/executor.py`,
`runtime/provenance.py` (`ATTEMPT` kind, `attempt_origin()`),
`examples/cascade_extract.ail` (new).

**Tests:** 11 new (142 total).

---

## v1.3 — 2026-04-17

**Structural purity contracts — `pure fn`.**

- `pure fn` declares a statically-verified contract: no `perform`
  statements, no intent calls, no calls to non-pure fns, no
  `eval_ail`. Violations raise `PurityError` at parse time.
- Composed with provenance (v1.2): a pure fn's output is compile-time
  guaranteed to have `has_intent_origin(result) == false`.
- All 11 `stdlib/utils.ail` utilities upgraded to `pure fn`.
- Unqualified `fn` retains unchanged semantics (backward compatible).

**Files:** `parser/purity.py` (new), `parser/ast.py` (`purity` field),
`parser/parser.py`, `parser/lexer.py`, `parser/__init__.py`,
`stdlib/utils.ail`.

**Tests:** 15 new (131 total).

---

## v1.2 — 2026-04-17

**Provenance — every value knows where it came from.**

- Each `ConfidentValue` now carries an `Origin` recording the
  operation that produced it, linked to the origins of its inputs.
- Origins are created at fn/intent/builtin/entry boundaries;
  binary/unary/field operations inherit the dominant parent origin to
  keep trees bounded.
- Intent origins additionally carry `model_id` and an ISO-8601
  timestamp for audit.
- New builtins: `origin_of(value)`, `lineage_of(value)`,
  `has_intent_origin(value)`. These cannot be shadowed by user fns
  or intents.

**Files:** `runtime/provenance.py` (new), `runtime/executor.py`,
`examples/audit_provenance.ail` (new), `spec/08-reference-card.ai.md`.

**Tests:** 18 new (116 total).

---

## v1.1 — 2026-04-17

**Result type for explicit error handling.**

- New builtins: `ok(value)`, `error(msg)`, `is_ok(r)`, `is_error(r)`,
  `unwrap(r)`, `unwrap_or(r, d)`, `unwrap_error(r)`.
- `to_number` now returns a Result on non-numeric input.
- `examples/safe_csv_parser.ail` demonstrates Result-based pipelines.

---

## v1.0.0 — 2026-04-17

**The first stable release.** AIL is a programming language designed for AI as the primary author of code. This release contains a complete language specification, a working Python interpreter, a standard library written in AIL, and evidence that the language works as intended.

### What ships

**Language specification** (8 documents)
- spec/00: Overview and design philosophy
- spec/01: Core syntax — intent, context, branch, entry, import
- spec/02: Context system — typed situational assumptions with inheritance
- spec/03: Confidence model — every value carries a belief measure in [0, 1]
- spec/04: Evolution — self-modification with metric, bounds, rollback, human review
- spec/05: Effects — declared side effects with authorization and observability
- spec/06: Standard library specification
- spec/07: Deterministic computation — fn, if/else, for, types, built-in functions

**Working interpreter** (Python, 88 tests)
- Lexer and recursive-descent parser for the full v1.0 grammar
- Executor with intent dispatch (LLM), fn execution (deterministic), and hybrid programs
- Context resolution with inheritance, override tracking, and scope stacking
- Confidence propagation per spec/03 §3
- Evolution supervisor: retune + rewrite constraints, version chain, bounded_by, rollback, human review
- Import resolver for stdlib modules
- eval_ail: parse and execute AIL source at runtime (self-generation)
- Anthropic adapter with robust JSON parsing (code fences, nested objects, confidence clamping)
- Mock adapter for offline development and testing
- .env file loader for API key management
- CLI: `ail run`, `ail parse`, `ail version`

**Standard library** (written in AIL, not Python)
- stdlib/core: identity, refuse
- stdlib/language: summarize, translate, classify, extract, rewrite, critique
- stdlib/utils: word_count, char_count, is_empty, repeat, pad_left, clamp, sum_list, average, flatten, unique, take

**21 built-in functions**
- Text: length, split, join, trim, upper, lower, starts_with, ends_with, replace, slice
- List: length, get, append, sort, reverse, range, map, filter, reduce
- Conversion: to_number, to_text, to_boolean
- Math: abs, max, min

**9 example programs**
- hello.ail — simplest case
- translate.ail — context inheritance with override
- classify.ail — branch dispatch on classifier output
- ask_human.ail — low-confidence fallback to human
- evolve_retune.ail — evolution with version chain
- summarize_and_classify.ail — stdlib imports
- fizzbuzz.ail — pure fn, no LLM, proof that AIL is a real language
- review_analyzer.ail — hybrid pipeline (fn 23 calls + intent 6 calls)
- meta_codegen.ail — AIL generates and executes AIL

**Documentation**
- Human-readable: README.md, CONTRIBUTING.md, ROADMAP.md
- AI-readable: README.ai.md, spec/08-reference-card.ai.md
- Korean: docs/ko/README.ko.md, evolve-guide.ko.md, stdlib-guide.ko.md
- Naming convention: .md (human), .ai.md (AI/LLM), .ko.md (Korean)

**CI/CD**
- GitHub Actions: tests on Python 3.10/3.11/3.12, smoke tests, evolve demo
- Optional live-test job against real Claude API

**Design documents** (vision, not implemented)
- runtime/00-airt.md — AI Runtime design
- os/00-noos.md — Neural-Oriented OS design
- os/01-compatibility.md, 02-security.md, 03-governance.md

### What was proven

1. An AI (Claude) read spec/08-reference-card.ai.md and generated valid AIL programs that executed correctly — for vowel counting, name sorting, and score analysis.

2. During code generation, a missing language primitive (list index access) was discovered. The `get()` builtin was added. This is the feedback loop the project was designed to enable.

3. FizzBuzz runs in AIL without any LLM involvement. AIL is a real programming language, not just an LLM orchestrator.

4. The review_analyzer example demonstrates the hybrid model working in practice: 23 fn calls (free, fast, deterministic) + 6 intent calls (LLM, for judgment only).

5. meta_codegen.ail demonstrates self-generation: an AIL program that produces another AIL program and executes it via eval_ail.

### Known limitations

- No `while` loop (by design — spec/07 §3.3)
- No lambda expressions (use named fn + pass name as string)
- No static type checking (runtime only)
- No pattern matching
- Evolution state does not persist across interpreter sessions
- `import` brings the entire module, not individual symbols
- AIRT and NOOS are design documents, not implementations
