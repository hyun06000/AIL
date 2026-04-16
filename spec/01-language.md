# AIL Specification — 01: The Language

**Version:** 0.1 draft

This document defines the core syntactic and semantic units of AIL. Every program in AIL is built from these. Other specification documents refine specific subsystems; this one is the baseline.

---

## 1. Top-level declarations

An AIL source file (`.ail`) is a sequence of top-level declarations. The permitted declarations are:

| Declaration | Purpose |
|---|---|
| `context` | Defines a named context type |
| `intent` | Defines an intent (the AIL equivalent of a function) |
| `evolve` | Attaches evolution rules to an intent |
| `effect` | Declares a side effect and its authorization contract |
| `entry` | Marks the program's entry point |
| `import` | Brings external intents, contexts, or effects into scope |

Order of declarations does not affect semantics. Forward references are permitted.

## 2. Intents

An **intent** is the fundamental unit of computation in AIL. It replaces what other languages call a function.

### 2.1 Syntax

```ail
intent NAME(PARAMS) -> RETURN_TYPE {
    goal: GOAL_EXPRESSION
    constraints { CONSTRAINTS }
    examples { EXAMPLES }          // optional
    on_low_confidence(...) { ... } // optional
    trace: TRACE_LEVEL             // optional; default partial
}
```

### 2.2 Semantics

When an intent is invoked, the runtime does the following:

1. Resolves the active context (see [02-context.md](02-context.md)).
2. Evaluates the `goal` expression into a structured objective.
3. Enumerates candidate strategies. A strategy may be: invoking a language model, calling a deterministic sub-intent, calling an external effect, or a composition of these.
4. Executes the selected strategy under the declared constraints.
5. Evaluates constraint satisfaction and the result's confidence.
6. If confidence falls below the `on_low_confidence` threshold, invokes the declared handler.
7. Emits a trace at the declared trace level.

Critically, step 3 is not specified by the program. The program says **what** must be true; the runtime decides **how**.

### 2.3 Goal expressions

A `goal` expression describes the desired state of the return value. It may be:

- A type assertion: `goal: Text matching pattern P`
- A predicate: `goal: output such that semantically_equivalent(output, input, in: target_language)`
- A reference to another intent: `goal: summarize(source, max_tokens: 200)`
- A multi-clause conjunction: `goal: Text and faithful_to(source) and tone(context.register)`

The goal is not a prompt. The runtime may use it to construct a prompt, but it may equally use it to select a deterministic strategy, dispatch to a specialized model, or decline the call.

### 2.4 Constraints

A `constraints` block contains zero or more named constraints. Each constraint is:

- **Hard** (must hold for the result to be accepted), or
- **Soft** (preferred but not required), indicated by the `prefer` keyword.

```ail
constraints {
    fidelity > 0.9                      // hard
    prefer brevity < 500 tokens         // soft
    no_personal_data in output          // hard
    latency < 2000ms                    // hard, measured
}
```

Constraints may reference:

- The output value
- The input parameters
- The active context
- Runtime metrics (`latency`, `tokens`, `cost`, `confidence`)
- Built-in predicates (see [06-stdlib.md](06-stdlib.md))

A hard constraint violation causes the intent to fail with a `ConstraintViolation` signal, which propagates like an exception but carries the violated constraint and the attempted output.

### 2.5 Examples as executable specification

An intent MAY include an `examples` block. Examples serve three purposes:

1. They are checked by the compiler for internal consistency.
2. They are passed to the runtime to guide strategy selection (e.g., few-shot prompting, distillation).
3. They are used by the `evolve` subsystem to detect regressions.

```ail
examples {
    ("Hello, world") => ("안녕하세요, 세계")
    ("The quarterly report is attached.", register: "casual")
        => ("분기 보고서 첨부했어요.")
}
```

Examples are not tests in the unit-test sense. Matching is semantic, not literal: the runtime considers an example satisfied if the output is within a configurable semantic distance of the expected value.

## 3. Contexts

Contexts are AIL's solution to the single largest source of bugs in natural-language-driven systems: the unstated assumption.

A context is a typed, named, hierarchical bag of assumptions. It is documented in full in [02-context.md](02-context.md); this section gives the surface syntax.

```ail
context NAME extends PARENT {
    FIELD: VALUE_OR_TYPE
    ...
}
```

Contexts are activated with `with`:

```ail
with context translation_job:
    result = translate_document(input)
```

Within the activated scope, any intent call implicitly receives the context. The context is also available inside intent bodies as `context.FIELD`.

Contexts compose by extension and narrowing, not by overriding. A child context cannot silently change a parent's field; it must declare `override FIELD: NEW_VALUE` to do so, and the override is visible in traces.

## 4. Confidence and branching

Every AIL value is a **confident value**: a pair of `(value, confidence)` where confidence is a number in `[0, 1]`. The literal `"hello"` has implicit confidence `1.0`. A value produced by a model call has the model's reported confidence, calibrated per [03-confidence.md](03-confidence.md).

### 4.1 The `branch` construct

AIL does not have `if`. It has `branch`, which dispatches by confidence-weighted distribution:

```ail
branch classify_sentiment(text) {
    [positive > 0.7]  => respond_warmly()
    [negative > 0.7]  => respond_carefully()
    [mixed or low_confidence] => ask_clarification()
} calibrate_on user_feedback
```

The arm with the highest posterior probability wins. Ties are broken by declaration order. The `calibrate_on` clause tells the runtime which signal to use to correct miscalibration over time.

### 4.2 Why not `if`

`if` forces a binary collapse of a fundamentally graded signal. An AI processing "is this message hostile?" almost never produces a bit; it produces a distribution. The program should operate on that distribution, not throw information away at the first branch.

Programs that want determinism can write:

```ail
branch x {
    [x.confidence == 1.0 and x.value == true] => a()
    [otherwise] => b()
}
```

— but in practice, if you find yourself writing that, you are using the wrong tool.

## 5. Effects and authorization

Any operation with effects outside the program — network calls, file writes, sending messages, spending money, invoking other agents — must be declared as an `effect` and authorized before execution.

```ail
effect send_email {
    signature: (to: Address, subject: Text, body: Text) -> Receipt
    authorization: required
    idempotency: provide_key
    reversibility: none
    budget: from context.email_budget
}
```

Within an intent, effects are invoked with `perform`:

```ail
intent notify_customer(order: Order) {
    goal: customer aware of order.status change
    body = compose_notification(order)
    perform send_email(
        to: order.customer.email,
        subject: body.subject,
        body: body.text
    )
}
```

The `authorization: required` declaration means the runtime MUST obtain authorization before executing the effect. The authorization model is defined by the host OS (see [NOOS](../os/00-noos.md)); common forms are: a human approval prompt, a cryptographic capability token, or a pre-declared budget envelope.

Effects are covered in full in [05-effects.md](05-effects.md).

## 6. Evolution

An `evolve` block attaches self-modification rules to an intent. The full model is described in [04-evolution.md](04-evolution.md); the surface is:

```ail
evolve INTENT_NAME {
    metric: METRIC_EXPRESSION
    when CONDITION {
        ACTION
    }
    rollback_on: ROLLBACK_CONDITION
    history: keep_last N
    require review_by: WHO   // optional
}
```

Evolution is deliberately constrained: it requires a metric, a condition, an explicit action, and a rollback condition. An `evolve` block that is missing any of these is a compile error. The language refuses to let an intent mutate itself "because it felt like it."

## 7. Types

AIL has a structural, gradually-typed type system.

Primitive types: `Text`, `Number`, `Boolean`, `Confidence`, `Time`, `Address`, `Token`, `Bytes`.

Composite types: records `{ field: Type, ... }`, lists `[Type]`, unions `Type | Type`, refinements `Type where PREDICATE`.

Every type may be annotated with a confidence bound: `Text @ confidence >= 0.8` is the type of text values carrying at least 0.8 confidence.

Types are checked at compile time where possible and at runtime otherwise. A type mismatch is a `TypeViolation` signal.

## 8. Imports

```ail
import translate_document from "stdlib/language"
import context formal_korean from "./contexts.ail"
import effect send_email from "org://email-service@v2"
```

Three import namespaces are recognized:

- `stdlib/...` — built-ins (see [06-stdlib.md](06-stdlib.md))
- relative paths — files in the same project
- `org://NAME@VERSION` — organizational registry entries, resolved by the host

## 9. Entry points

A program that is executed directly (not imported) MUST declare exactly one `entry`:

```ail
entry main(input: Text) {
    // body
}
```

An entry may take any number of parameters; the runtime is responsible for binding them from its invocation context (command line, API call, OS message, etc.).

## 10. Reserved keywords

The following are reserved and cannot be used as identifiers:

```
intent  context  evolve  effect  entry  import  from  as
goal  constraints  examples  on_low_confidence  trace
with  override  extends  perform  branch  otherwise
prefer  require  when  calibrate_on  rollback_on
metric  history  keep_last  under  matching
and  or  not  in  such  that
```

This list is conservative; keywords MAY be added in later versions but MUST NOT be removed.

## 11. Grammar summary

An informal EBNF of the surface grammar follows. It is not the normative grammar (that lives in [grammar.ebnf](grammar.ebnf) when the reference implementation lands), but it is tight enough to read programs with.

```
program      = { declaration } ;
declaration  = intent_decl | context_decl | evolve_decl
             | effect_decl | entry_decl | import_decl ;

intent_decl  = "intent" ident "(" params ")" [ "->" type ] block ;
context_decl = "context" ident [ "extends" ident ] block ;
evolve_decl  = "evolve" ident block ;
effect_decl  = "effect" ident block ;
entry_decl   = "entry" ident "(" params ")" block ;

block        = "{" { field | statement } "}" ;
field        = ident ":" expression ;
statement    = assignment | branch_stmt | perform_stmt
             | with_stmt | expression ;

branch_stmt  = "branch" expression "{"
                  { "[" expression "]" "=>" expression }
               "}" [ "calibrate_on" expression ] ;

with_stmt    = "with" "context" ident ":" statement ;
perform_stmt = "perform" ident "(" args ")" ;
```

## 12. What this document does not cover

This document gives the surface. The following are developed elsewhere:

- Context inheritance, narrowing, and override — [02-context.md](02-context.md)
- Confidence arithmetic and calibration — [03-confidence.md](03-confidence.md)
- Evolution safety, sandboxing, and human review — [04-evolution.md](04-evolution.md)
- Effect authorization, capabilities, budgets — [05-effects.md](05-effects.md)
- Standard library — [06-stdlib.md](06-stdlib.md)

The next document to read is [02-context.md](02-context.md).
