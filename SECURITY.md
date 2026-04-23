# Security Policy

## Supported versions

AIL is an early-stage research project. Only the latest released minor version receives security updates. Older versions are considered end-of-life.

| Version | Supported |
|---|---|
| 1.46.x (latest) | ✅ |
| < 1.46 | ❌ |

The PyPI package is `ail-interpreter`. Check your installed version with:

```bash
python -c "import ail; print(ail.__version__)"
```

## Reporting a vulnerability

**Do not open a public GitHub issue for security problems.**

Report privately through one of these channels:

1. **GitHub Security Advisories** — preferred. Open a draft advisory at <https://github.com/hyun06000/AIL/security/advisories/new>. This is encrypted to the maintainer and does not become public until a fix is released.
2. **Email** — `hyun06000@gmail.com`. Use subject line `[AIL security]` and include the report contents below.

### What to include

- Description of the issue
- Steps to reproduce, ideally as a minimal `.ail` program or a command invocation
- The AIL version (`python -c "import ail; print(ail.__version__)"`)
- The Python and OS version
- Your estimate of the impact (information disclosure, code execution, denial of service, etc.)

### What happens next

This is a solo-maintained research project, so response is best-effort rather than contractual. You should expect:

- Acknowledgement within **7 days**
- Triage and initial assessment within **14 days**
- A fix or a documented mitigation before the next public release

If the issue is being actively exploited, say so in the subject line (`[AIL security – active exploit]`) and acknowledgement will be faster.

## Scope

### In scope

- The Python interpreter in `reference-impl/ail/` (parser, executor, provenance, calibration, evolution, purity checker)
- The Go interpreter in `go-impl/`
- The `ail ask` / `ail run` / `ail parse` CLI
- The model adapters (`ail/runtime/anthropic_adapter.py`, `ollama_adapter.py`, `openai_adapter.py`)
- The effect system (`perform http.get`, `perform file.read`, etc.)
- The `eval_ail` runtime primitive (AIL-generating-AIL)
- Anything published to PyPI as `ail-interpreter`

### Out of scope

- The AIL specification documents themselves (`spec/`, `runtime/`, `os/`). Design critique is welcome but goes through [CONTRIBUTING.md](CONTRIBUTING.md), not a security advisory.
- Vulnerabilities in third-party models the runtime talks to (Claude, GPT, Llama, etc.). Those belong to the respective providers.
- Vulnerabilities in transitive Python dependencies. Those belong to the upstream maintainers; we will bump pins when CVEs are published.
- The fine-tuning pipeline (`reference-impl/training/`) is research code and not considered security-critical. Prompt injections in training data are a research concern tracked in `docs/open-questions.md`, not a security advisory.
- Any harm caused by the language model's own output (hallucinations, unsafe code suggestions, prompt injection in user-supplied text). These are properties of the model, not the interpreter.

## Security-sensitive areas that are by design

AIL has a few primitives that would look alarming in a conventional security audit. These are **intentional** and documented:

- **`perform` effects** execute real I/O (HTTP, file reads) when a program calls them. By design, `pure fn` bodies cannot call them — the parser rejects the program before execution. If you find a way to trigger an effect from inside a `pure fn`, that is a security issue and we want to know.
- **`eval_ail(source, input)`** parses and runs arbitrary AIL at runtime. The running code runs under the same capabilities as the caller. Programs that accept untrusted AIL source and pass it to `eval_ail` are running untrusted code by design. This is analogous to Python's `exec`.
- **`evolve` blocks** allow a program to modify its own source under declared constraints. `rewrite constraints` actions always require human review before being applied. If you find a way to bypass the human-review gate, that is a security issue.

## Credit

By default, reporters are publicly credited in the release notes and advisory. If you want to be anonymous, or want a specific handle/email/affiliation to be used, tell us when you file the report.

There is no bug bounty.
