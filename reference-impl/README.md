# AIL Reference Implementation (MVP)

**Status:** Minimum viable interpreter · Python 3.10+

This directory contains a working subset of AIL. It is not the full specification — it covers enough to make the language tangible:

- Parsing `.ail` source to an AST
- A simplified intent graph representation
- Context declaration, activation, inheritance, override
- Intent execution via a pluggable language model backend
- Confidence-gated branching
- Basic constraint checking
- A simple trace log per invocation

What the MVP does **not** include (explicit scope limits):

- Evolution (`evolve` blocks are parsed but not executed)
- Full effect system (a single `human_ask` effect is supported via stdin)
- Calibration (confidence is pass-through from model)
- Type checking beyond structural matching
- The Authority / ledger / User Surface (these are NOOS-level)

The MVP's purpose is to let someone clone this repo, set one environment variable, and run an AIL program against a language model today. Everything else in this project is spec; this directory is proof-of-concept.

---

## Quick start

```bash
# From the repository root:
cd reference-impl
pip install -e .

# Set your Anthropic API key:
export ANTHROPIC_API_KEY=sk-ant-...

# Run an example:
ail run examples/hello.ail --input "Hello, world"

# Or, programmatically:
python -c "from ail_mvp import run; print(run('examples/hello.ail', input='Hello, world'))"
```

---

## Architecture

```
ail_mvp/
├── __init__.py          # Public API: run(), compile(), load_context()
├── parser/
│   ├── lexer.py         # Tokenizer
│   ├── parser.py        # Recursive descent → AST
│   └── ast.py           # AST node types
├── runtime/
│   ├── graph.py         # Intent graph construction from AST
│   ├── context.py       # Context type, resolution, stacking
│   ├── dispatcher.py    # Strategy selection (MVP: single strategy per intent)
│   ├── model.py         # Model adapter interface
│   ├── anthropic.py     # Anthropic adapter
│   ├── trace.py         # Trace recording
│   └── executor.py      # The main execution loop
├── stdlib/
│   └── core.py          # Built-in intents: summarize, translate, etc.
└── cli.py               # Command-line entry point
```

---

## Running the examples

```bash
# A complete translation program
ail run examples/translate.ail --input "$(cat document.txt)" --context examples/contexts.ail

# Sentiment classification with branching
ail run examples/classify.ail --input "I really enjoyed the film, but the ending dragged."

# A program that asks a human for help when uncertain
ail run examples/ask_human.ail --input "What should I have for dinner?"
```

---

## Extending

The model adapter is pluggable. To add support for another provider, implement the `ModelAdapter` protocol in `runtime/model.py` and register it in `runtime/executor.py`.

To add a new built-in intent, add it to `stdlib/core.py` and register it in `ail_mvp/__init__.py`.

---

## Limitations honestly listed

- Parser errors are terse. Improving them is a good first PR.
- Performance is not a priority; the MVP sequences everything.
- No persistence: each `run` is a fresh state.
- The single bundled adapter requires an Anthropic API key. A local-model adapter is future work.

See [open-questions.md](../docs/open-questions.md) for larger unresolved design questions.
