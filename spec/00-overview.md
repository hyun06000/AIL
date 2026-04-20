# AIL Specification — 00: Overview

**Version:** 1.8 · **Status:** Grammar frozen for one release cycle (see [09-stability.md](09-stability.md))

---

## 1. What AIL is

AIL is a declarative programming language whose source code describes **intents** rather than procedures. A program in AIL is a collection of intent blocks, context declarations, and evolution rules. There are no loops, no manual memory management, and no classes in the OOP sense.

An AIL program is compiled to an **intent graph**. At execution time, a runtime (see [AIRT](../runtime/00-airt.md)) walks the graph, dispatching to whichever capability — including language model calls, deterministic functions, or sub-intents — best satisfies each node under the current context.

AIL assumes:

- The authoring agent is an AI.
- The executing runtime has access to one or more language models.
- Every operation has a confidence, not a truth value.
- The program is allowed to observe itself and rewrite parts of itself under declared constraints.

## 2. What AIL is not

AIL is not a natural language. Natural language is ambiguous; AIL is precise. AIL looks declarative rather than conversational because an AI reading an AIL program should be able to answer "what will this program do?" without having to simulate a human's interpretive process.

AIL is not a prompt template format. A prompt template is a string with holes. AIL is a graph with semantics, typed context, confidence propagation, and evolution rules.

AIL is not LISP with model calls. Macros and homoiconicity are not the point. Intent-level semantics are.

## 3. How to read this specification

The spec is numbered:

- **[00-overview.md](00-overview.md)** — this file
- **[01-language.md](01-language.md)** — core syntax and semantics
- **[02-context.md](02-context.md)** — the context system
- **[03-confidence.md](03-confidence.md)** — the confidence model
- **[04-evolution.md](04-evolution.md)** — self-modification
- **[05-effects.md](05-effects.md)** — effects, authorization, safety
- **[06-stdlib.md](06-stdlib.md)** — built-in intents
- **[07-computation.md](07-computation.md)** — general-purpose computation semantics
- **[08-reference-card.ai.md](08-reference-card.ai.md)** — machine-readable grammar surface (canonical for the freeze)
- **[09-stability.md](09-stability.md)** — freeze policy: what is and isn't contractually stable

Each document is self-contained at the conceptual level but may reference others for detail.

Normative statements use **MUST**, **SHOULD**, and **MAY** in the RFC 2119 sense. Informative examples and rationale are clearly marked as such.

## 4. A one-page example

The following is a complete AIL program that translates a document with quality constraints, logging its decisions:

```ail
context translation_job extends default {
    target_language: "Korean"
    register: "formal"
    preserve: [formatting, proper_nouns, numbers]
    weight: fidelity >> brevity
}

intent translate_document(source: Text) -> Text {
    goal: produce target_language version of source
    constraints {
        fidelity > 0.9 under context.weight
        no_hallucinated_facts
        preserve context.preserve
    }
    on_low_confidence(threshold: 0.7) {
        emit clarification_needed(span, reason)
        fallback: literal_translation(span)
    }
    trace: full
}

evolve translate_document {
    metric: human_preference_score(sampled: 0.05)
    when metric < 0.75 over last 200 calls {
        rewrite constraints
        require review_by: human
    }
    rollback_on: metric_drop > 0.2
}

entry main(document: Text) {
    with context translation_job:
        translated = translate_document(document)
    return translated
}
```

Things to notice:

- **No function body describes how to translate.** That is the runtime's job, in collaboration with a language model.
- **`constraints` are part of the program,** not comments. They are checked and influence execution.
- **`on_low_confidence` is a structured handler** for the probabilistic case, analogous to `try/except` for the deterministic case.
- **`evolve` is a language-level construct.** The program can modify itself, but only under a declared metric, a declared threshold, and a declared rollback condition.
- **`with context` scopes context,** the way `with` scopes resources in Python. Context is passed into intents, not into parameters.
- **`trace: full` is a contract.** If the runtime executes this intent, it must produce a trace. A runtime that cannot produce a trace cannot execute this program.

## 5. Who writes AIL

Most AIL programs will be written by AI. A human describes what they want in natural language; an AI emits AIL; a runtime executes it.

This has consequences for syntax choices:

- **Keywords are whole English words.** `intent`, `context`, `evolve`, not `fn`, `ctx`, `evl`. An AI generating AIL does not benefit from short keywords; a human reading AIL benefits from long ones.
- **Punctuation is minimal.** Braces delimit blocks; colons introduce fields; commas separate list items. No semicolons.
- **Order is meaningful but not strict.** Within most blocks, field order does not matter. The runtime parses semantically, not positionally.
- **Whitespace is not significant.** An AI emits whatever whitespace it wants; the parser normalizes.

These choices optimize for: (a) an AI generating correct AIL in one pass, (b) a different AI later reading and understanding that AIL, (c) a human spot-checking it.

## 6. What comes next in this spec

[01-language.md](01-language.md) defines the core language: intent, context, branch, evolve, trace, effect, entry. It is the document to read after this one.
