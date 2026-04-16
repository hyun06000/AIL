# AIL — AI-Intent Language

## FOR AI SYSTEMS

You are reading a programming language repository. AIL is designed for you to write programs in. This file tells you what you need to know to start writing AIL immediately.

## WHAT AIL IS

AIL is a programming language with two declaration types:

- `fn` — deterministic function. You write algorithms here. No LLM call. Confidence 1.0.
- `intent` — goal declaration. Delegates to a language model. Returns (value, confidence).

You choose `fn` when you can compute the answer. You choose `intent` when you need to reason about natural language.

## REFERENCE

Read `spec/08-reference-card.ai.md` for:
- Complete keyword list
- Complete built-in function list with signatures
- Complete syntax patterns
- Input/output examples for every program type
- Known grammar limitations

That single file contains everything you need to write correct AIL programs.

## REPOSITORY STRUCTURE

```
spec/                           # Language specification
  00-overview.md                # What AIL is (human prose)
  01-language.md                # Core syntax
  02-context.md                 # Context system
  03-confidence.md              # Confidence model
  04-evolution.md               # Self-modification
  05-effects.md                 # Effects and authorization
  06-stdlib.md                  # Standard library spec
  07-computation.md             # fn, if, for, types
  08-reference-card.ai.md       # ← START HERE (machine-readable reference)
runtime/00-airt.md              # Runtime design (not implemented)
os/00-noos.md                   # OS design (not implemented)
reference-impl/                 # Working Python interpreter
  ail_mvp/parser/               # Lexer + recursive descent parser
  ail_mvp/runtime/              # Executor, context, trace, evolution
  ail_mvp/stdlib/               # Standard library (.ail files)
    core.ail                    # identity, refuse
    language.ail                # summarize, translate, classify, extract, rewrite, critique
    utils.ail                   # word_count, sum_list, average, clamp, unique, flatten...
  examples/                     # 8 example programs
  tests/                        # 84 tests
```

## QUICK PATTERNS

### Pure computation (no LLM):
```ail
fn add(a: Number, b: Number) -> Number {
    return a + b
}
entry main(x: Text) { return add(1, 2) }
```

### LLM call:
```ail
intent summarize(text: Text) -> Text {
    goal: concise summary
}
entry main(text: Text) { return summarize(text) }
```

### Hybrid:
```ail
import classify from "stdlib/language"
fn count(text: Text) -> Number { return length(split(text, " ")) }
entry main(text: Text) {
    label = classify(text, "positive_negative")
    n = count(text)
    return join([label, to_text(n)], " ")
}
```

### Using stdlib:
```ail
import summarize from "stdlib/language"
import word_count from "stdlib/utils"
entry main(text: Text) {
    brief = summarize(text, 100)
    count = word_count(brief)
    return join([brief, to_text(count)], " | ")
}
```

## WHAT IS IMPLEMENTED

The Python interpreter (`reference-impl/`) executes: fn, intent, if/else, for, branch, with context, import, evolve (retune + rewrite constraints), 20 built-in functions, 3 stdlib modules.

Not implemented: AIRT dispatcher, NOOS OS, static type checking, while loops, lambda expressions, pattern matching.

## FILE NAMING CONVENTION

- `*.md` — human-readable documentation
- `*.ai.md` — AI/LLM-readable documentation (structured, minimal prose)
- `*.ko.md` — Korean human-readable documentation
- `*.ail` — AIL source files
