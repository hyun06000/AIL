# AIL — AI-Intent Language

> A language, runtime, and operating system designed from first principles for AI as the primary author of computation.

**Status:** Draft specification v0.1 · Reference implementation in progress

🇰🇷 **한국어 독자:** [`docs/ko/README.ko.md`](docs/ko/README.ko.md) 에서 한국어 개요를 읽으실 수 있습니다.

---

## Why this exists

Every programming language in widespread use today was designed for humans writing code. Syntax exists to reduce human cognitive load. Type systems exist to prevent human errors. IDEs exist to scaffold human memory.

But the authorship of code is shifting. In 2026, a significant portion of production code is written by AI systems and reviewed (or not reviewed) by humans. The language those AI systems use is still Python, still JavaScript, still C++ — languages whose every design decision assumes a human at the keyboard.

This project asks a different question:

> If AI is the author, what should the language look like?

AIL (AI-Intent Language) is the answer, built across three layers:

| Layer | Name | What it is |
|---|---|---|
| Language | **AIL** | A declarative, probabilistic, context-first language whose programs describe *intent* rather than procedure |
| Runtime | **AIRT** | A runtime that treats AI model calls as first-class primitives and executes programs as adaptive probabilistic graphs |
| OS | **NOOS** | An operating system whose kernel exposes intent, context, and model capacity as syscalls instead of files, processes, and memory |

Humans interact with this stack the same way they always do: in natural language. The AI writes AIL, AIRT runs it, NOOS hosts it. The human describes what they want.

---

## The core inversion

Traditional computing assumes:

- **Determinism is normal, uncertainty is the exception.**
- **Code describes steps.**
- **Context is implicit and lost at function boundaries.**
- **Programs are static artifacts that humans write and then freeze.**

AIL inverts all four:

- **Uncertainty is normal, certainty is the exception.** Every value carries a confidence.
- **Code describes intent.** The runtime decides steps.
- **Context is first-class.** It is passed, inherited, and narrowed like a type.
- **Programs are live.** They observe their own behavior and rewrite themselves under declared constraints.

---

## Repository layout

```
ail-project/
├── spec/              # Language specification (normative)
├── runtime/           # AIRT runtime design documents
├── os/                # NOOS operating system design documents
├── reference-impl/    # Python reference interpreter for AIL
├── examples/          # Example AIL programs
├── docs/              # Tutorials, design rationale, FAQ
└── .github/           # CI, issue templates
```

Start here:

- [**spec/00-overview.md**](spec/00-overview.md) — Read this first
- [**spec/01-language.md**](spec/01-language.md) — The language
- [**runtime/00-airt.md**](runtime/00-airt.md) — The runtime
- [**os/00-noos.md**](os/00-noos.md) — The OS
- [**reference-impl/README.md**](reference-impl/README.md) — Run an AIL program today

---

## Design tenets

These govern every decision in this project. When a choice is unclear, return to these.

1. **AI is the author, human is the stakeholder.** Syntax optimizes for AI generation and AI reading, not human typing.
2. **Intent over procedure.** If the runtime can figure it out, the program should not specify it.
3. **Probabilistic by default.** Booleans and exact equality are escape hatches, not primitives.
4. **Context is a type.** What a program *means* depends on the situation it runs in, and that situation is declared.
5. **Live programs.** Source code is the seed; the executing program is the organism.
6. **Observability is not optional.** Every intent has a decision trace. The runtime cannot hide why it did what it did.
7. **Humans remain in the loop for consequences.** Actions with real-world effects require declared authorization, not just absence of prohibition.

Tenet 7 matters. This project is designed assuming AI will execute it, but is not designed to remove humans. The OS layer explicitly makes authorization a first-class syscall.

---

## Project status

This repository currently contains **design documents and a reference interpreter** for a subset of AIL. AIRT and NOOS are described as specifications; they are not yet implemented. The goal of v0.1 is to make the ideas concrete enough that:

- You can read an AIL program and understand it.
- You can run a simple AIL program against a language model today.
- You can argue with the design and open an issue.

See [ROADMAP.md](ROADMAP.md) for what comes next.

---

## License

Apache 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Early-stage projects benefit most from design critique — issues challenging the core assumptions are as valuable as code.
