# AIL Specification — 02: Context

**Version:** 0.1 draft

Context is the most structurally important feature of AIL and the one with the least analog in other languages. It is not a global variable. It is not a dependency injection container. It is not a prompt template. This document explains what it is.

---

## 1. The problem context solves

A natural-language instruction like "translate this document" is underspecified in an unbounded number of ways:

- What target language?
- What register — formal, casual, academic, legal?
- What happens when a proper noun has no good translation?
- What is "good" — fidelity to source, fluency in target, or both?
- What is the cost budget?
- Who is allowed to see the output?

Humans resolve underspecification by drawing on the surrounding situation. An AI executing an intent has no surrounding situation unless the program gives it one. Context is that mechanism.

In traditional languages, the answers to those questions are threaded through function arguments, configuration objects, global state, or — most commonly — implicit assumptions baked into the implementation. Each of these strategies fails for AI-authored code:

- **Arguments bloat** until every function takes twenty of them.
- **Config objects** are opaque to the AI about what fields matter where.
- **Global state** produces spooky action at a distance.
- **Implicit assumptions** are the main source of "the AI did something weird" bug reports.

Context makes situational assumptions a declared, typed, traceable program artifact.

## 2. What a context is

A context is a named, typed, immutable record declared at the top level of a program. Once declared, it may be activated inside a scope with `with context NAME:`. All intent calls within that scope see the context as `context`.

Contexts form a tree via `extends`. A child context inherits every field of its parent and may add new fields or explicitly `override` parent fields.

```ail
context default {
    register: "neutral"
    cost_budget: 0.10            // USD per call
    latency_budget: 5000ms
    weight: accuracy == speed
    audience: "general"
    language: "auto_detect"
    trace: partial
}

context translation_job extends default {
    weight: fidelity >> brevity
    preserve: [formatting, proper_nouns, numbers, citations]
    target_language: required     // no default; caller must supply
}

context formal_korean_translation extends translation_job {
    override register: "formal"
    override target_language: "Korean"
    honorific_level: "합니다체"
}
```

## 3. Context activation

### 3.1 `with` statement

Inside an intent or entry, `with context NAME:` activates the context for the remainder of the block, or for the nested block if the statement ends with a colon and indented body.

```ail
entry main(doc: Text) {
    with context formal_korean_translation:
        translated = translate_document(doc)
    return translated
}
```

Outside a `with` block, the context is `default`. An intent is never without a context; there is always at least `default`.

### 3.2 Context composition

Multiple contexts can be stacked:

```ail
with context formal_korean_translation:
    with context high_stakes_legal:
        result = translate_document(doc)
```

The inner context must be compatible with the outer: its declared parent chain must include the outer, or both must share a common ancestor and their non-overlapping fields must not conflict. Compatibility is checked at compile time where possible and at runtime otherwise.

When stacked, field resolution walks inner-to-outer. An inner `override` takes precedence.

### 3.3 Implicit propagation

Every intent call inside an activated `with` block receives the active context. There is no need to pass it explicitly. Intent bodies access it as `context.FIELD`.

This includes calls across module boundaries. An imported intent sees the caller's context. If the imported intent was designed against a different context, the runtime attempts to project: fields declared in the intent's expected context are taken from the caller's context where names match and types are compatible; missing fields fall back to the intent's declared defaults; extra fields are dropped.

## 4. Field types

A context field may be:

- **A concrete value**: `register: "formal"`
- **A type requirement**: `audience: Text`
- **A predicate-typed value**: `cost_budget: Number where value > 0`
- **A required field**: `target_language: required`
- **A weight expression**: `weight: fidelity >> brevity`
- **A list**: `preserve: [formatting, proper_nouns]`
- **A reference to another context field**: `backup_language: language`

A field marked `required` has no default. An attempt to activate a context that leaves it unset is a compile-time error if statically detectable and a runtime error otherwise.

### 4.1 Weight expressions

A weight expression declares the relative importance of competing objectives. The operators are:

- `A == B` — equal importance
- `A > B` — A is somewhat more important
- `A >> B` — A is much more important
- `A >>> B` — A is dominant; B considered only for ties

Weights participate in constraint satisfaction. A soft constraint tied to a higher-weighted objective is prioritized over one tied to a lower-weighted objective. The exact semantics of "more" and "much more" are defined in [03-confidence.md](03-confidence.md) §6.

## 5. Override, not mutation

Contexts are immutable. A `with` block cannot mutate fields. The only way to change a field within a scope is to `extends` a new context that overrides it.

This is a deliberate trade. It makes context behavior fully predictable from the program text: you can read a program top to bottom and know which context is active at any point. It also makes traces useful.

## 6. Override visibility

Every `override` in a context declaration is recorded. Traces show which context provided each field, including overridden ones. A developer reading a trace can answer "why did the intent think the register was formal?" without running the program.

```ail
context legal_translation extends formal_korean_translation {
    override honorific_level: "하십시오체"
    override weight: precision >>> fluency
    cite_statutes: required
}
```

A trace from an intent executed under `legal_translation` will show:

```
context chain:
  default
    ↓ translation_job     (weight, preserve, target_language)
    ↓ formal_korean_translation  (register*, target_language*, honorific_level)
    ↓ legal_translation   (honorific_level*, weight*, cite_statutes)

effective fields:
  register: "formal"                from formal_korean_translation
  target_language: "Korean"         from formal_korean_translation
  honorific_level: "하십시오체"     from legal_translation  *override*
  weight: precision >>> fluency     from legal_translation  *override*
  preserve: [...]                   from translation_job
  cite_statutes: required           from legal_translation
```

(`*` marks overrides.)

## 7. Why this matters for AI authorship

When an AI writes an AIL program, it often does not know every assumption the human has in mind. Context gives the AI a structured place to put the assumptions it does extract, and gives the runtime a structured place to ask when it discovers an assumption is missing.

Compare two sketches of the same program, first in a procedural language, then in AIL:

```python
# Procedural sketch
def translate(doc, lang="Korean", register="formal",
              preserve_formatting=True, preserve_proper_nouns=True,
              cost_cap_usd=0.10, latency_cap_ms=5000,
              model="sonnet-4", honorific="formal", ...):
    # implementation involving all these parameters
    ...
```

```ail
// AIL sketch
context job extends default {
    override target_language: "Korean"
    override register: "formal"
    preserve: [formatting, proper_nouns]
}

intent translate(doc: Text) -> Text {
    goal: Text faithful_to(doc, in: context.target_language)
    constraints {
        preserve context.preserve
        cost < context.cost_budget
        latency < context.latency_budget
    }
}

entry main(doc: Text) {
    with context job:
        return translate(doc)
}
```

The AIL version separates *what is being asked for* (intent) from *the situation it is being asked in* (context). The AI that writes the intent does not need to know the cost budget or the honorific level. The AI that writes the context does not need to know how translation is implemented. A human reading the program sees the assumptions listed in one place.

## 8. Context introspection

Inside an intent body, context may be inspected:

```ail
intent classify(text: Text) -> Label {
    goal: Label
    if context.has("domain"):
        prefer strategies specialized_for(context.domain)
}
```

The functions `context.has(name)`, `context.get(name, default)`, and `context.chain()` are available inside intent bodies. They are pure and do not cause side effects.

## 9. Runtime-supplied contexts

Some contexts are supplied by the runtime, not the program. Examples:

- `runtime_context` — capacity, quotas, model availability, current latency envelope
- `user_context` — requesting user identity, authorization scopes, preferences
- `session_context` — the current conversation, if any

These are always active, always read-only, and accessible by name: `runtime_context.available_models`, `user_context.preferences.language`.

A program MAY declare a field dependent on a runtime-supplied context:

```ail
context default {
    language: user_context.preferences.language or "English"
}
```

## 10. What context is not

- **Not a prompt.** A context informs how a prompt is constructed, but is not itself injected as a prompt.
- **Not mutable state.** See §5.
- **Not a capability grant.** Authorizations are declared on effects, not contexts. A context may *reference* an authorization, but the grant is separate.
- **Not unbounded.** A context has a schema (the fields it declares). Arbitrary ad-hoc keys are not permitted.

Next: [03-confidence.md](03-confidence.md).
