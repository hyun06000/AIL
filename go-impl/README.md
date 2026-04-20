# ail-go — Go reference implementation

A second implementation of AIL, written in Go with the standard library
only. This exists to prove the language is **defined by its
specification**, not by the Python runtime that happened to write it
first. Both interpreters target
[`spec/08-reference-card.ai.md`](../spec/08-reference-card.ai.md); the
canonical source of truth is the spec, not either binary.

## What this demonstrates

AIL is a language, not "a Python library with a .ail file extension." A
programmer (or another AI) can write an `.ail` file once and run it
through:

- the Python interpreter at `reference-impl/` (full feature set), or
- the Go interpreter here (Phase-0 subset, static binary).

Both produce the same output for the supported subset. The Go binary is
8.3 MB, contains no external dependencies, and runs with no Python
installed.

```bash
# Python runtime:
cd reference-impl && python -m ail.cli run examples/fizzbuzz.ail --input 15
#  -> 1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz

# Go runtime (same .ail file):
cd go-impl && go build -o ail-go .
./ail-go run ../reference-impl/examples/fizzbuzz.ail --input 15
#  -> 1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz
```

Byte-for-byte identical.

## Coverage

Implemented:

- `fn` (pure keyword accepted for compat, check not enforced)
- `intent` (dispatched via HTTP to Ollama at `localhost:11434`)
- `entry`
- `if / else if / else`, `for VAR in COLLECTION`, `return`
- `attempt { try EXPR try EXPR ... }` — Result-error skipping cascade
  (no confidence threshold syntax yet)
- Arithmetic: `+ - * / %`
- Comparison: `== != < <= > >=`
- Boolean: `and or not` (short-circuit)
- Membership: `in`, `not in`
- List literals and the builtins: `length split join append range
  to_text to_number trim upper lower get is_ok is_error ok error
  unwrap unwrap_or unwrap_error`
- Tolerant `(value, confidence)` response parsing — identical tolerance
  matrix as the Python shared parser (pure JSON, code-fenced JSON,
  JSON-in-prose, confidence clamping)

Not yet (owned by the Python runtime for now):

- Provenance tracking (`origin_of`, `lineage_of`, `has_intent_origin`)
- Purity contract enforcement (parse accepts `pure fn`, no checker)
- Confidence threshold gating on `attempt` (block body works; threshold
  syntax is reserved in the spec but unimplemented in both runtimes)
- Implicit parallelism
- `evolve` / `context` / `with` / `branch` / `perform`
- Full stdlib imports (Python runtime bundles `stdlib/*.ail`; the Go
  runtime skips imports so programs using stdlib utilities must inline
  what they need)

## Usage

```bash
go build -o ail-go .

# Pure fn program:
./ail-go run PROGRAM.ail --input "INPUT"

# With ollama intent dispatch:
./ail-go run PROGRAM.ail --input "INPUT" --model llama3.1:latest
# or via env:
AIL_OLLAMA_MODEL=gemma2:latest ./ail-go run PROGRAM.ail --input "INPUT"

# Parse only:
./ail-go parse PROGRAM.ail

# Run the test suite:
go test ./...
```

## Cross-runtime consistency test

Two layers of consistency checks now exist:

**1. Single-embedded fizzbuzz, in-Go.**
`eval_test.go::TestFizzBuzzMatchesPython` embeds the fizzbuzz source and
asserts the output matches the Python runtime's output character for
character.

**2. Full conformance suite, in-Python.** A directory of `.ail` cases
each with its own `.input` and `.expected` files lives at
`reference-impl/tests/conformance/cases/`. The pytest driver at
`reference-impl/tests/conformance/test_conformance.py` runs each case
through BOTH runtimes and asserts byte-identical stdout. CI gates
every PR on this.

Current conformance coverage (as of v1.8.2):

| Case | Topic | Python | Go |
|---|---|---|---|
| 001_fizzbuzz | `if/else`, modulo, `for in range`, `join` | ✅ | ✅ |
| 002_vowels | string `split`/`lower`, `in` membership | ✅ | ✅ |
| 003_factorial | pure fn recursion, Number formatting | ✅ | ✅ |
| 004_insertion_sort | list manipulation, append, `to_text` | ✅ | ✅ |
| 005_korean_concat | Unicode strings, `trim` | ✅ | ✅ |
| 006_result_handling | `ok`/`error`/`is_ok`/`unwrap` | ✅ | ✅ |
| 007_nested_lists | nested `for` over `[[…]]` | ✅ | ✅ |
| 008_empty_list | empty-list edge in length/for | ✅ | ✅ |
| 009_arithmetic_precedence | operator precedence table (`*`/`/`/`%` vs `+`/`-`, cmp) | ✅ | ✅ |
| 010_boolean_ops | `and`/`or`/`not` precedence, `in`/`not in` | ✅ | ✅ |
| 011_string_pipeline | `trim`+`upper`+`lower`+`split`+`join`+`length` composed | ✅ | ✅ |
| 012_fibonacci | two-call recursion (stack/return handling) | ✅ | ✅ |
| 013_list_ops | list-of-lists build, nested `for`, positional `get` | ✅ | ✅ |
| 014_attempt_cascade | `attempt { try ... }` confidence-priority fallback | ✅ | ✅ |
| 015_unwrap_or | `Result.unwrap_or` default-value semantics | ✅ | ✅ |

Adding a case is zero-code: drop `NNN_name.ail`, `NNN_name.input`,
`NNN_name.expected` into `cases/`. Mark known Go gaps with a
`NNN_name.skip-go` file containing the skip reason.

## Why this matters

Before this runtime existed, "AIL is a programming language" was a
claim with only one piece of evidence. Now there are two independently
written interpreters that agree on what an `.ail` file means. That is
what makes a language a language.

## Roadmap for the Go runtime

In priority order:

1. Per-symbol stdlib import (so `import classify from "stdlib/language"`
   works without inlining)
2. `pure fn` static checker (mirror `parser/purity.py`)
3. Provenance tree attached to every `Value` (mirror
   `runtime/provenance.py`)
4. Implicit parallelism via goroutines (a natural fit)
5. Full effect system

None of these are in scope for v0.1. The point of v0.1 is to prove the
language is implementation-independent.
