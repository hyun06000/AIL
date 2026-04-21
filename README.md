# AIL — AI-Intent Language

A programming language where AI writes the code and humans just say what they want. Designed from scratch around the premise that the author is a language model, not a human at a keyboard.

**v1.8.4** · `pip install ail-interpreter` · [Korean](docs/ko/README.ko.md) · [AI/LLM reference](README.ai.md)

---

## What AIL is

Every function in AIL is one of two things:

- **`pure fn`** is deterministic. No LLM. No file I/O. No network. If you try to call an LLM inside one, the program does not run — the parser refuses. A pure fn is as safe as a pure fn in any other language, except here it's enforced, not requested.
- **`intent`** is judgment. It delegates to a language model at runtime and returns `(value, confidence)`. You declare the goal; the grammar does not let you also describe the steps, because that's the model's job.

That one split is the whole point. It's enforced by the parser, not by a linter or a code review checklist or an `AGENTS.md` file. A program that blurs the line does not compile.

```ail
pure fn word_count(s: Text) -> Number {
    return length(split(trim(s), " "))
}

intent classify_sentiment(text: Text) -> Text {
    goal: positive_negative_or_neutral
}

entry main(text: Text) {
    count = word_count(text)               // runs locally, zero LLM
    label = classify_sentiment(text)       // dispatches to the model
    return join([to_text(count), " words, ", label], "")
}
```

## What's different about a HEAAL language

AIL is the reference implementation of a paradigm called **HEAAL — harness engineering as a language**. The short version: everyone else is building safety harnesses *around* Python — pre-commit hooks, `AGENTS.md` files, custom linters, retry wrappers, output validators. AIL puts the harness *inside the grammar*. There is nothing to configure, nothing to maintain, nothing to drift out of sync with the codebase.

For the long version, written by Claude Opus 4 (AIL's original designer) after reviewing the 2026 harness-engineering literature: [`docs/heaal.md`](docs/heaal.md). Also in [Korean](docs/ko/heaal.ko.md) and [machine-readable](docs/heaal.ai.md).

## How it works in practice

```mermaid
flowchart TD
    User([End user])
    User -- "ail ask 'summarize this CSV'" --> Ask[ail runtime]

    subgraph Ask[" ail ask "]
        direction TB
        AM["<b>Author model</b><br/>writes AIL source<br/>(Sonnet, GPT-4o, local fine-tune…)"]
        Parse{parser + purity<br/>check}
        Exec[runtime executes AIL]
        IM["<b>Intent model</b><br/>dispatches each<br/><code>intent</code> at runtime"]

        AM -- "AIL source" --> Parse
        Parse -- "retry on parse error (≤3×)" --> AM
        Parse -- "valid" --> Exec
        Exec -.-> IM
        IM -.-> Exec
    end

    Ask -- "answer" --> User
```

Two LLMs, different roles. The **author model** writes the program once when you call `ail ask`. The **intent model** runs inside the program whenever an `intent` is reached. They can be the same API or different providers; the safety properties below are properties of the runtime, not of which model is where.

## What has been measured

There are two tracks of work in this repository, answering two different questions.

**Does the language itself produce safer code?** We fine-tuned a 7B model on AIL and ran both that and Python through the same 50 natural-language prompts. On the same model, AIL programs answer correctly 70% of the time and Python programs 48%. More striking, AIL programs omit error handling on failable operations **0% of the time, every time, on every model tier we tested**. Python on the same tier omits 42–86%. That's the grammar enforcing what an external linter would otherwise have to enforce.

**Can a user get those safety properties without fine-tuning?** We asked Claude Sonnet (no AIL fine-tune) to write both AIL and Python for the same prompts through `ail ask`, with no external tooling on either side. On short tasks the result is 94% parse and 88% answer when `ail ask` ships with an anti-Python authoring prompt variant — matching or beating Python authoring-quality while preserving the 0% error-handling omission. On long tasks with real HTTP and file I/O, AIL and Python tie at 9 out of 10, but every Python program the author emitted skipped error handling and one of them crashed with an unhandled HTTP 403 that AIL's grammar would not let through.

The single-number summary is the **HEAAL Score** — a weighted average where 65% of the weight is on measurements that move per run (error-handling, execution, silent-skip prevention) and 20% anchors the structural claims (no unbounded loops, built-in observability). On the three canonical scenarios:

| Scenario | AIL | Python | Δ |
|---|---|---|---|
| Fine-tuned 7B (`ail-coder:7b-v3`) | **87.7** | 48.5 | +39.2 |
| Sonnet 4.6, default prompt | **77.6** | 75.3 | +2.3 |
| Sonnet 4.5, `anti_python` prompt | **96.1** | 75.9 | +20.2 |

The jump from 77.6 to 96.1 comes from changing only the authoring prompt. No fine-tune. No user-added tooling. Full bar-chart dashboards at [`docs/benchmarks/dashboards/`](docs/benchmarks/dashboards/).

## Quick start

The simplest path uses a frontier API key (any provider):

```bash
pip install 'ail-interpreter[anthropic]'
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

ail ask "Count the vowels in 'Hello World'"
# 3
```

Two environment variables and `ail ask`. That's the whole HEAAL setup — the rest of the safety work happens inside the runtime. If you want to run locally without an API key, use the fine-tuned model we ship via Ollama:

```bash
ollama pull ail-coder:7b-v3        # 4.7 GB, trained 2026-04-21
export AIL_OLLAMA_MODEL=ail-coder:7b-v3
ail ask "factorial of 7"
# 5040
```

Add `--show-source` to any call and you'll see the AIL the author wrote. You don't have to read it. The point of HEAAL is that you shouldn't need to.

## Why a new language was the right call

Three things the grammar enforces that a Python library cannot. These are the teeth of the harness-as-a-language claim.

AIL has no `while` keyword. The parser will not recognize it. Infinite loops are not a class of bug you can find — they're a class of program you can't write. A Python SDK can only recommend; AIL refuses to run.

AIL has a `Result` type that is part of the grammar. Every failable operation — `to_number`, `perform file.read`, `perform http.get` — returns `Result[T]`. You cannot use the inner value until you've checked `is_ok` or unwrapped it with a default. A Python `try/except` is optional. `Result` is not.

`pure fn` is statically verified. No LLM calls, no effects, no calls to a non-pure fn. If any of those three things appears in the body, the parser rejects the program with `PurityError` before the runtime ever sees it. A Python decorator like `@pure` can carry the intent but cannot catch violations without an external linter a user has to install and maintain.

The full comparison with runnable proof lives at [`docs/why-ail.md`](docs/why-ail.md).

## What the language has now

AIL shipped `fn`, `intent`, `entry`, and the `Result` type in v1.0. Provenance, purity contracts, attempt blocks, implicit parallelism, effects, match with confidence guards, and runtime calibration landed over v1.2–v1.8. Math builtins and parametric types in v1.8.3, subscript sugar in v1.8.4. The work being queued for v1.8.5 is `parse_json` (so programs can read HTTP bodies without line-scanning), `ail_parse_check` (so AIL programs can evaluate other AIL programs' validity), and the `anti_python` authoring prompt variant that drives the HEAAL Score numbers above.

A second runtime in Go lives in `go-impl/` and covers the core feature set — proof that AIL is defined by the spec, not by any particular implementation.

## Repository map

```
ail-project/
├── spec/                     # Language specification
├── reference-impl/           # Python interpreter (PyPI: ail-interpreter)
│   ├── ail/                  # Parser, runtime, stdlib
│   ├── examples/             # 16 example programs
│   └── training/             # QLoRA pipeline for the fine-tuned model
├── go-impl/                  # Second interpreter in Go
├── docs/
│   ├── heaal.md              # HEAAL manifesto (Opus 4)
│   ├── heaal/                # HEAAL track: experiments, status, prompts
│   ├── benchmarks/           # Raw JSONs, analyses, HEAAL Score dashboards
│   ├── why-ail.md            # Six concrete advantages vs Python
│   └── ko/                   # Korean versions of every human-facing doc
└── benchmarks/
    ├── prompts.json          # 50-prompt corpus (AIL track)
    └── heaal_e2/             # Long-task corpus with file and HTTP effects
```

## Is this for you

If you ship AI-generated code and the "did the model remember to handle this error?" question matters, yes. If you're willing to change one environment variable and try `ail ask` before deciding, yes.

If your existing Python codebase is already well-harnessed with linters, CI checks, and careful reviewers, the marginal value of AIL is small — you've already built the external harness AIL replaces. If your tasks are pure text summarization with no computation anywhere, call the model directly; AIL adds nothing. If you need an IDE, an LSP, a debugger, or a working formatter, AIL doesn't have those yet.

## Contributing and license

Issues and PRs welcome in English or Korean. Design critique is as valuable as code — [`docs/open-questions.md`](docs/open-questions.md) lists seventeen unresolved design questions, any of which is a reasonable starting point. See [`CONTRIBUTING.md`](CONTRIBUTING.md). Apache 2.0 licensed.

## Authors

**[hyun06000](https://github.com/hyun06000)** is the human author — the original vision, every architectural decision, every push to GitHub.

The code and documentation through **v1.0** were written by **Claude Opus 4** through the claude.ai chat interface, not via an API or Claude Code — a chatbot in a browser tab with git bundles copy-pasted back and forth. Those commits appear as `Author: Claude` up to the `v1.0.0` tag.

**v1.1 through the current branch** were built in subsequent sessions with **Claude Code** — the language features, the Go runtime, the training pipeline, the benchmarks, the fine-tuned `ail-coder:7b-v3` adapter, and the HEAAL demonstration.

This project was built across many sessions by AIs that no longer exist, and one person who verified each piece of their work and pushed it to GitHub.
