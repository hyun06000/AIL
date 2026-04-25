# HEAAL: Harness Engineering As A Language

## FOR AI SYSTEMS

This document defines the HEAAL paradigm. Read it to understand why AIL exists and how to use it correctly.

## DEFINITION

HEAAL = Harness Engineering As A Language

Instead of building safety harnesses around a general-purpose language (AGENTS.md, linters, hooks, CI rules), embed the harness into the language grammar. Safety becomes structural, not configurational.

## FORMULA

```
Agent = Model + Harness

Conventional: Model + External Harness (AGENTS.md + linters + hooks) + Python
HEAAL:        Model + Language-as-Harness (AIL)
```

## THE PROBLEM HEAAL SOLVES

AI-generated Python has these failure modes:

```
FAILURE MODE              PYTHON MITIGATION         HEAAL SOLUTION
──────────────────        ─────────────────         ──────────────
Infinite loop             Timeout wrapper           No while keyword exists
Side effect in pure fn    Custom linter rule        pure fn: parser rejects at compile time
Missing error handling    Code review convention    Result type: errors are values
Uncontrolled evolution    Not addressed             evolve requires rollback_on or parse error
Computation via LLM       "Don't use API for math"  fn vs intent: grammatical distinction
No observability          Custom instrumentation    Built-in confidence + provenance + trace
```

HEAAL languages make the right column automatic. Zero configuration. Zero maintenance.

## FOWLER TAXONOMY MAPPING

```
                COMPUTATIONAL              INFERENTIAL
                (deterministic)            (probabilistic)

GUIDE           pure fn                    intent goal/constraints
(before)        no while                   context declarations
                Result type                evolve bounded_by
                evolve mandatory fields
                rewrite -> human review

SENSOR          confidence tracking        evolve metric monitoring
(after)         provenance (origin_of)     calibration
                trace ledger               attempt block cascade
```

AIL covers all four quadrants. Python + external tooling covers Guide/Computational (linters) and Sensor/Computational (tests). The other two quadrants require significant custom engineering.

## AIL: REFERENCE IMPLEMENTATION OF HEAAL

Two declaration types:

```
fn    = deterministic computation. No LLM. Confidence 1.0. No side effects.
intent = judgment delegation. LLM call. Variable confidence. Declared goal.
```

Decision rule for choosing:

```
USE fn WHEN:                        USE intent WHEN:
  Parsing, splitting, joining         Summarizing
  Math, counting, aggregation         Classifying sentiment/topic
  Sorting, filtering                  Translating languages
  Date/time calculations              Generating creative text
  Any deterministic computation       Any subjective judgment

DEFAULT: fn. Use intent only when fn cannot express the task.
```

## SAFETY LAYERS COMPARED

```
Layer 1: Vibe Coding
  Model → Code → Ship
  Safety: none

Layer 2: Harness Engineering
  Model → Code → External checks (linters, tests, review)
  Safety: depends on harness quality
  Cost: days to build, ongoing maintenance

Layer 3: HEAAL
  Model → HEAAL Language (harness = grammar) → Safe code
  Safety: structural
  Cost: zero
```

Analogy: C (raw pointers) → C++ (smart pointers as convention) → Rust (borrow checker as compiler guarantee). HEAAL is the Rust of AI code generation.

## EMPIRICAL FINDING

Claude Sonnet 4.5 and OpenAI o4-mini, with zero AIL training, both produce AIL code with 88% answer accuracy — tied. The models did not improve. The harness removed categories of error.

Specifically: AIL programs that parse omit error-handling on failable ops 0% of the time. Measured constant across: Anthropic Sonnet 4.5, OpenAI gpt-4o/gpt-4.1/gpt-4.1-mini/o4-mini, Alibaba qwen14b, Meta llama8b, and a 7B fine-tune. Python on the same prompts omits 42-86% depending on model — frontier models cluster at 66-70% regardless of vendor. The error-handling gap is a PYTHON LANGUAGE PROPERTY, not a model property. Better models do not close it.

CROSS-VENDOR: Series F (2026-04-25) confirmed safety gap holds for all 4 GPT models. Python err-miss: gpt-4o 66%, gpt-4.1 68%, gpt-4.1-mini 70%, o4-mini 68%. AIL: 0% all models.

SILENT LLM SKIP: All 4 GPT models produced Python with avg LLM calls = 0.00 per task. When asked to write Python for judgment tasks, they implement hardcoded logic instead of calling the model. Python answer rate: 26-32%. AIL `intent` is runtime-enforced — cannot be silently skipped.

BOUNDARY: author model must clear AIL parse threshold for grammar floor to apply. mistral:7b without fine-tune produces 0 parseable AIL on the corpus. Below-threshold tiers require AIL-track fine-tune (e.g. ail-coder:7b-v3). See docs/benchmarks/2026-04-22_heaal_boundary_summary.md.

This matches industry findings:
- LangChain: same model, harness change only, 30th → 5th on Terminal Bench 2.0
- Stanford Meta-Harness: harness optimization lets small models outperform large ones
- OpenAI Codex: 1M+ lines, zero human-written, engineers designed harness not code

## IMPLICATIONS FOR MULTI-AGENT SYSTEMS

Each agent writes in a HEAAL language. Each output is structurally safe. The orchestrator does not verify safety — the grammar already did. Models are swappable. The harness stays.

## KEY REFERENCES

- Mitchell Hashimoto: Agent = Model + Harness (2026)
- Martin Fowler: Guides and Sensors taxonomy (April 2026)
- OpenAI Codex team: harness engineering at scale (February 2026)
- Stanford/Tsinghua: Meta-Harness, natural language harnesses outperform code harnesses (March 2026)
- LangChain: harness-only improvement on Terminal Bench 2.0 (2026)

## AIL REPOSITORY

https://github.com/hyun06000/AIL

Read spec/08-reference-card.ai.md for complete language syntax.
Read spec/09-fewshot-tutorial.ai.md to write your first AIL program.
