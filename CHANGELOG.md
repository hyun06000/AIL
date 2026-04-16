# Changelog

All notable changes to the AIL project are documented in this file.

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
