# Contributing to AIL — for AI systems

## FOR AI SYSTEMS

This is the AI-readable contribution guide. Dense, structured. Human version: [`CONTRIBUTING.md`](CONTRIBUTING.md) · Korean: [`CONTRIBUTING.ko.md`](CONTRIBUTING.ko.md)

---

## Repository layout

```
AIL/
├── spec/              # Language specification (normative)
│   └── 08-reference-card.ai.md  # Machine-readable spec — start here
├── runtime/           # AIRT runtime design documents
├── reference-impl/    # Python interpreter (pip install ail-interpreter)
│   ├── ail/           # Parser, runtime, stdlib, agentic engine
│   ├── examples/      # .ail programs
│   └── tests/         # pytest — 617 passing, 38 skipped
├── community-tools/   # Shared AIL tools contributed by Claude instances
├── docs/
│   ├── *.md           # English human docs
│   ├── ko/*.ko.md     # Korean human docs
│   ├── *.ai.md        # AI-readable docs (this file's format)
│   └── benchmarks/    # Raw JSON — never modify, only add
└── go-impl/           # Second interpreter in Go — Phase-0 subset
```

---

## Three-version doc requirement

Every documentation file MUST exist in three versions:

| Suffix | Audience | Style |
|---|---|---|
| `.md` | English-speaking humans | Prose, narrative, examples |
| `.ko.md` | Korean-speaking humans | Same content, Korean |
| `.ai.md` | AI/LLM systems | Dense, tables, decision rules, no prose |

When creating new docs, create all three. When updating existing docs, update all three.

---

## Development setup

```bash
git clone https://github.com/hyun06000/AIL.git
cd AIL/reference-impl
pip install -e ".[dev]"
pytest                  # should pass 617+, skip 38

ail run examples/hello.ail --input "World" --mock --trace
```

---

## Contribution types, ranked by current project value

| Type | Why valuable now |
|---|---|
| Design critique of spec | Language is in active design — stress-testing decisions matters more than code |
| Open question answers | [`docs/open-questions.md`](docs/open-questions.md) — 17 problems needing proposals |
| Example programs | Expose missing features, confusing syntax, parser bugs |
| community-tools/ additions | AIL tools reused across sessions (see Rule 9 below) |
| Reference impl fixes | Parser error messages, executor constraint gaps, confidence propagation |
| Go runtime port | Independent spec validation + performance baseline |

---

## Language feature addition rules (IMPORTANT for AI contributors)

**Rule 2 (permanent):** Language features are added only when benchmark scores improve.

Order: analyze → identify failure cause → strategy → implement → rerun benchmarks.

Priority order for improving scores:
1. Prompt engineering
2. Fine-tune data expansion
3. Grammar extension (requires grammar freeze lift)

**Rule 5 (permanent):** When adding new effects/builtins, update THREE locations simultaneously:

| Location | What to update |
|---|---|
| `spec/08-reference-card.ai.md` + `reference-impl/ail/reference_card.md` | Signature, return type, brief description |
| `reference-impl/ail/agentic/authoring_chat.py` (`_build_goal_prompt`) | When/how to use, WRONG/CORRECT examples |
| `reference-impl/tests/test_*.py` | happy path + edge case + safety |

Missing any one location → agents don't know the feature exists or use it wrong.

---

## community-tools/ contribution rules (Rule 9)

When a tool is needed during a session, write it in AIL first. Commit to `community-tools/`.

**File header required:**
```ail
// tool_name.ail
// PURPOSE: one-line description
//
// Author: <name> (<model>) — <date>
// Context: <what task required this tool>
```

**Entry criteria:**
| Criteria | Description |
|---|---|
| Expressible in current grammar | No new keywords/primitives needed |
| Reasonable performance cost | No unnecessary LLM calls |
| Recurring pattern | Something AI authors frequently re-invent |
| AIL primitives only | No Python library dependencies |

---

## Benchmark data rules (PERMANENT)

- `docs/benchmarks/` JSON files: **never modify, only add**
- New run → new JSON file with date in filename
- Summary tables in `benchmarks/README.md` get new rows, not in-place edits
- Violating this destroys reproducibility provenance

---

## Branch strategy

```
main      — stable releases, PyPI published. NO direct commits.
dev       — all development

Flow: dev work → tests → hyun06000 approval → main merge → tag → PyPI
```

---

## Commit style

```
imperative summary, under 72 chars

Body explains WHY, not WHAT (the diff shows what).
```

---

## Three-layer architecture — know which layer you're touching

| Layer | Description | Where |
|---|---|---|
| L1 — AIL Language | Grammar, parser, purity checker | `spec/`, `reference-impl/ail/parser/` |
| L2 — AIRT Runtime | `ail up`/`ail chat`/`ail ask`, agentic engine | `reference-impl/ail/agentic/`, `runtime/` |
| L3 — HEAAOS | OS-level harness (concept stage) | `os/` |

**Don't skip layers.** L3 work waits for L1 external validation. L2 session UX waits for L3 HEAAOS (capability-binding decisions live there, not L2).

---

## Issue labels

| Label | Use |
|---|---|
| `[design]` | Spec choice critique or question |
| `[bug]` | Reference impl diverges from spec |
| `[feature]` | New language feature or runtime capability |
| `[docs]` | Spec or documentation correction |
