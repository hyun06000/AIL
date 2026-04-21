# AIL Specification — 09: Stability & Freeze Policy

**Version:** 1.8 · **Status:** Grammar frozen for one release cycle (2026-04-20 → next major review)

---

## 1. Why this document exists

AIL went through eight minor versions between v1.0 and v1.8 (≈60 commits).
Each change was individually motivated, but the accumulated grammar churn
made one downstream activity impossible: **training a small model to author
AIL reliably.** A fine-tune against v1.7 syntax is worse than useless
against v1.8 — the model becomes *confidently wrong*.

This document declares which parts of the language are contractually
stable, which parts remain free to evolve, and the conditions under which
the freeze is lifted. The freeze was the last outstanding precondition
from Claude Opus 4's April 2026 fine-tuning checklist.

## 2. What is frozen (grammar surface)

The following **cannot change** without a major version bump:

### 2.1 Top-level declarations
`fn`, `pure fn`, `intent`, `context`, `effect`, `evolve`, `entry`,
`import`. Keyword spelling, argument order, and mandatory fields are
fixed. New optional fields may be added.

### 2.2 Control flow keywords
`if` / `else if` / `else`, `for VAR in COLLECTION`, `branch`, `attempt`,
`match`, `return`, `with context`. No `while` will be added. No new
control-flow keywords will be added during the freeze.

### 2.3 Type system surface
`Text`, `Number`, `Boolean`, `List[T]`, `Map[K,V]`, `Result[T]`,
`Confidence`. Parametric syntax (`List[Text]`) is stable.

### 2.4 Result type API
`ok(x)`, `error(msg)`, `is_ok(r)`, `is_error(r)`, `unwrap(r)`,
`unwrap_or(r, default)`, `unwrap_error(r)`. Names and arities are fixed.

### 2.5 Built-in function signatures
The 30+ built-ins documented in `spec/08-reference-card.ai.md` §BUILT-INS
have fixed names and argument order. Additions are permitted; renames,
removals, or argument reorderings are not.

### 2.6 Operators
Arithmetic (`+ - * / %`), comparison (`== != < <= > >=`), boolean
(`and or not`), membership (`in`, `not in`), concatenation via
`join(...)`. Operator precedence table in §01 is fixed.

### 2.7 Confidence model
Confidence is a number in `[0.0, 1.0]` attached to every value.
Propagation rule: `fn` output confidence = min of input confidences;
`intent` output confidence = model-reported. This rule is frozen.

### 2.8 Evolve contract
Required fields: `metric`, `when`, `action`, `rollback_on`, `history`.
`rewrite constraints` always forces human review. These invariants are
frozen.

## 3. What is NOT frozen

The freeze is on **grammar visible to the AIL author**. Everything else
may change:

- **Standard library contents.** New modules and functions may be added
  to `stdlib/`. Renames of stdlib symbols follow a deprecation cycle
  (warn for one release, remove the next).
- **Runtime internals.** Executor implementation, trace ledger format,
  parallelism heuristics, calibration back-ends. Two runtimes must
  remain behaviourally equivalent on the frozen grammar; how they get
  there is free.
- **Effect implementations.** `perform http.get(...)` etc. may land or
  change semantics during the freeze — the *declaration* syntax is
  frozen, the *runtime behaviour* of specific effects is not.
- **CLI surface.** `ail ask`, `ail run`, `ail parse` flags and behaviour
  may change. The CLI is not part of the language.
- **Error messages.** Parse-time and runtime error text may be improved
  freely.
- **Performance.** No guarantees, no freeze.
- **Additive parser desugarings** that strictly broaden the input
  language without changing the meaning of any program already
  parsing under the freeze. These ship as patch releases. Precedent:
  `List[T]` parametric type annotations accepted as no-op (v1.8.3),
  `EXPR[INDEX]` accepted as sugar for `get(EXPR, INDEX)` (v1.8.4 —
  closes issue #1). The reference card §EXPRESSIONS records each
  sugar; semantics are the existing builtin's, unchanged.

## 4. How the freeze is enforced

- `spec/08-reference-card.ai.md` is the canonical grammar surface. A PR
  that changes its contents in a way that breaks §2 above is a
  grammar-breaking change and must bump the major version.
- The conformance suite (forthcoming, tracked separately) runs all
  example programs against both Python and Go runtimes. Any divergence
  is a release blocker.
- New language features go to `spec/10-proposals.md` (to be created on
  first proposal) and wait for the next major version cycle.

## 5. When the freeze lifts

The freeze is lifted when ALL of:

1. A working fine-tune has been trained and evaluated on this frozen
   grammar (the activity this freeze exists to enable).
2. At least one release cycle has passed since v1.8 (the freeze date).
3. A concrete new feature has a written proposal, a benchmark delta
   justifying it, and an implementation plan that covers both
   runtimes.

Absent (1), any language change invalidates the fine-tune investment.
Absent (3), the grammar drifts for aesthetic reasons — the same failure
mode the freeze exists to prevent.

## 6. What this does NOT say

The freeze is a contract with downstream model trainers, not a promise
that v1.8 is perfect. Known rough edges (parse rate gap vs Python,
fn/intent decision ambiguity on small models, Go runtime covering only
a Phase-0 subset) remain open. They will be addressed through harness,
tooling, and runtime work — not by changing the grammar.

---

## Appendix: Freeze declaration

> AIL grammar is frozen at v1.8 as of 2026-04-20.
>
> No keyword additions, no keyword removals, no renames of built-ins
> or Result-type functions, no changes to operator precedence, no
> changes to confidence propagation or evolve invariants, until the
> conditions in §5 are met.
>
> Stdlib contents, runtime internals, effect implementations, CLI,
> error messages, and performance remain free to evolve.

Logged into [`docs/benchmarks/`](../docs/benchmarks/) snapshot metadata
as the 5th and final fine-tuning precondition from Claude Opus 4's
April 2026 review.
