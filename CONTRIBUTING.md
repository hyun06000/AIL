# Contributing to AIL

🇰🇷 Korean: [`CONTRIBUTING.ko.md`](CONTRIBUTING.ko.md)

AIL is an early-stage language project. At this point, design critique is as valuable as code — if not more. You don't need to write a pull request to contribute meaningfully.

---

## Ways to contribute

### Argue with the design

The specification documents in `spec/`, `runtime/`, and `os/` are normative but not final. If a design decision looks wrong to you, open an issue with the `design-critique` label and explain why. Don't hold back — the project gets stronger when its core decisions get stress-tested.

Particularly valuable: critique of the confidence model in [spec/03-confidence.md](spec/03-confidence.md), the evolution bounds in [spec/04-evolution.md](spec/04-evolution.md), and the purity rules in [spec/01-language.md](spec/01-language.md).

### Answer an open question

[docs/open-questions.md](docs/open-questions.md) lists problems the project knows about but hasn't solved. Picking one and writing a proposed answer — even just as a GitHub issue — moves things forward.

### Write example programs

More examples make the language easier to reason about. If you write a program that exposes a missing feature, a confusing syntax choice, or a parser bug, send it in. Examples live in `reference-impl/examples/`.

### Fix the reference implementation

The parser's error messages are terse. The executor doesn't check all constraints. Confidence propagation is nominal. PRs that close these gaps are welcome.

### Port the runtime

The main interpreter is Python. A Rust or Go implementation of AIRT, even a partial one, would be a significant contribution — both as a performance baseline and as independent validation that the spec is implementable.

---

## Development setup

```bash
git clone https://github.com/hyun06000/AIL.git
cd AIL/reference-impl
pip install -e ".[dev]"
pytest
```

Running a program:

```bash
ail run examples/hello.ail --input "World" --mock --trace
```

---

## Repository layout

```
ail-project/
├── spec/              # Language specification
├── runtime/           # AIRT runtime design documents
├── os/                # NOOS operating system design documents
├── reference-impl/    # Python interpreter
│   ├── ail/           # Source
│   ├── examples/      # .ail example programs
│   └── tests/         # pytest tests
└── docs/              # Tutorials, FAQ, open questions
```

---

## Style

**Spec documents:** Short sentences. Normative statements use MUST/SHOULD/MAY. Prefer numbered sections for cross-references. Aim for "RFC" rather than "blog post" — terse, precise, no apologies for the subject matter.

**Python code:** PEP 8, type hints encouraged. The interpreter values clarity over cleverness.

**Commit messages:** Summary line in imperative mood, under 72 chars. Body explains *why*, not *what* (the diff shows what).

---

## Issue labels

- `[design]` — question or critique of a specification choice
- `[bug]` — behavior in the reference implementation that doesn't match the spec
- `[feature]` — a new language feature or runtime capability
- `[docs]` — clarification or correction in specification or documentation

---

## Code of conduct

Be direct, be kind, be specific. Critique ideas, not people. Assume good faith. If you disagree with someone's reasoning, say what you think they're missing rather than dismissing it.

---

## License

By contributing, you agree that your contributions will be licensed under Apache License 2.0.
