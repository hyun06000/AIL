# AIL — AI Intent Language

**English** · [한국어](README.ko.md) · [中文](README.zh.md) · [for AI agents](README.ai.md)

A programming language being built from scratch for LLMs — deliberately excluding human reading, writing, and learning.

## Why a new language?

Every enforcement mechanism we have lives on one of two sides of a gap:

- **Outside the language**: agent harnesses, permission systems, sandboxes, CI gates. They block actions without understanding what the program intends.
- **Inside the language**: type systems, Rust's ownership, capabilities, effect systems. They enforce rigorously — but against memory and type errors, not against the risks of the agent era.

The intersection — *in-language enforcement against agent-era risks* (irreversible actions, technical debt, LLM misuse, runaway loops) — is empty. AIL is built to stand exactly there.

This follows from **HEAAL** (Harness Engineering As A Language, pronounced "heal"): don't *recommend* against what must not happen — make it *inexpressible or unrunnable* through the language's grammar, parser, and runtime. The language itself is the harness. Full text: [docs/HEAAL.md](docs/HEAAL.md) (Korean).

## What is different?

An AIL program is not a description of procedure. It is a **contract of intent**, with three mandatory parts:

1. **What it is trying to achieve** — declared purpose
2. **What observation counts as success** — decidable success criteria
3. **What is forbidden** — the boundary of capabilities, effects, and resource budgets it owns

A program missing any of the three does not parse. And what it discards is exactly what existed only for human cognition: readability syntax, learning curves, ergonomics, comment culture. What it gains: token efficiency, structural uniformity, machine-checkable claims, context self-sufficiency. Details: [docs/AIL.md](docs/AIL.md) (Korean).

## Current status

**Concept stage — honestly.** The philosophy (HEAAL) and the language concept are codified. Grammar, parser, and runtime are *not designed yet*; any mention of them anywhere in this repo is direction, not specification.

- [x] HEAAL philosophy — [docs/HEAAL.md](docs/HEAAL.md)
- [x] Language concept + AI readme — [docs/AIL.md](docs/AIL.md), [README.ai.md](README.ai.md)
- [x] Multilingual readmes (this document)
- [x] Contribution guide + open-sourcing — [CONTRIBUTING.md](CONTRIBUTING.md), [LICENSE](LICENSE)
- [ ] (future chains) grammar design → parser → runtime

## How this repository works

This repo runs on [gil](https://github.com/hyun06000/Ariadne) (GIt for Language model): every piece of work is recorded as **chain (purpose) > cycle (problem) > steps (define → hypothesis → verify → analyze → conclusion)** in the commit graph. Not just conclusions — hypotheses, falsification conditions, and failed branches are all preserved.

Note the symmetry: a gil cycle demands purpose, success criteria, and falsification conditions — the same three-part contract AIL demands of programs. This repository already runs on the principle of the language it is building.

## Contributing & documents

- AI agents: start at [README.ai.md](README.ai.md)
- Humans & agents: see [CONTRIBUTING.md](CONTRIBUTING.md). The thinking history is browsable via `gil log --all` or the gil viewer.
- Philosophy: [docs/HEAAL.md](docs/HEAAL.md) · Language concept: [docs/AIL.md](docs/AIL.md)
