# Contributing to AIL

Thank you for looking at this project. AIL is an early-stage design effort —
a programming language, runtime, and OS designed for a world where AI is the
primary author of code. At this stage, **design critique is as valuable as
code**, and the most useful contributions may not be pull requests.

---

## Ways to contribute

### 1. Argue with the design

The specification documents under `spec/`, `runtime/`, and `os/` are normative
but not final. If a design decision looks wrong, open an issue labeled
`design-critique` and explain why. Don't hold back; the project is stronger
when its core commitments have been stress-tested.

Particularly valuable: critique of the specific choices in
[spec/01-language.md](spec/01-language.md), the confidence model in
[spec/03-confidence.md](spec/03-confidence.md), and the evolution bounds in
[spec/04-evolution.md](spec/04-evolution.md).

### 2. Answer an open question

The file [docs/open-questions.md](docs/open-questions.md) lists problems the
authors know about but have not solved. Picking one of these and writing a
proposed answer — even just as a GitHub issue — moves the project forward.

### 3. Write example programs

AIL is easier to reason about when there are more example programs. If you
write a program that exposes a missing feature, a confusing syntax choice,
or a parser bug, send it in. The `reference-impl/examples/` directory is
where they live.

### 4. Fix the reference implementation

The MVP in `reference-impl/` is deliberately small but already exposes real
gaps. The parser's error messages are terse; the executor does not check
most constraints; the confidence propagation is nominal. PRs closing these
gaps are welcome.

### 5. Port the runtime

The MVP is in Python. A Rust or Go implementation of AIRT, even a partial
one, would be a major contribution — both as a performance baseline and as
independent validation of the spec.

---

## Repository layout

```
ail-project/
├── spec/              # Normative language specification
├── runtime/           # AIRT runtime design documents
├── os/                # NOOS operating system design documents
├── reference-impl/    # Python MVP interpreter
│   ├── ail/       # Source
│   ├── examples/      # .ail example programs
│   └── tests/         # pytest tests
└── docs/              # Tutorials, FAQ, open questions
```

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

## Style

**Spec documents:** Markdown. Short sentences. Normative statements use
MUST/SHOULD/MAY. Prefer numbered sections for cross-references. When in
doubt, the tone should be "RFC" rather than "blog post" — terse, precise,
unapologetic about the subject matter.

**Python code:** Standard PEP 8, type hints encouraged, docstrings where the
purpose is not obvious from the name. The MVP values clarity over cleverness.

**Commit messages:** Summary line in imperative mood under 72 chars. Body
explains *why* the change was made, not *what* was changed (the diff shows
that).

---

## Issue templates

When opening an issue, use one of these starting points:

- `[design]` — question or critique of a specification choice
- `[bug]` — reference implementation behavior deviating from the spec
- `[feature]` — a new language feature or runtime capability
- `[docs]` — clarification or correction in specification or tutorial

---

## Code of conduct

Be direct, be kind, be specific. Critique ideas, not people. Assume good
faith. If you disagree with someone's reasoning, say what you think they're
missing — don't dismiss.

For anything that goes beyond that, please open a private issue or email
the maintainer listed in the repository settings.

---

## License

By contributing, you agree that your contributions will be licensed under
the Apache License 2.0, matching the rest of the project.
