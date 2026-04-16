# AIL MVP Examples

Four programs that demonstrate progressively more of the language. All four
pass parsing; the first three are exercised by the test suite. You can run
any of them against either the mock adapter (no network) or a real language
model (requires `ANTHROPIC_API_KEY`).

---

## `hello.ail` — the simplest program

```bash
ail run examples/hello.ail --input "World" --mock --trace
```

Demonstrates: `intent`, `goal`, `constraints`, a single model-backed call,
the `default` context being implicitly active.

## `translate.ail` — context inheritance

```bash
ail run examples/translate.ail --input "Hello, world" --mock --trace
```

Demonstrates: `context ... extends`, `override`, `with context` activating
a context for the duration of a block, `on_low_confidence` as a fallback
handler. The trace shows the full chain `default → translation_job →
formal_korean` and which context supplied each field.

## `classify.ail` — branch dispatch

```bash
ail run examples/classify.ail --input "I loved it!" --mock --trace
```

Demonstrates: `branch` with multiple arms, equality comparison against the
branched value, `otherwise` fallback. The arm that matches the classified
value wins; the others never execute.

## `ask_human.ail` — human-in-the-loop

```bash
ail run examples/ask_human.ail --input "I am tired" --mock
```

Demonstrates: the `on_low_confidence` handler firing when the model's
confidence falls below the declared threshold, and `perform human_ask` as
the escape hatch to a human. The MVP's default `ask_human` reads from stdin;
the Python API lets you inject a callback for tests or other UIs.

---

## Running against a real model

Set `ANTHROPIC_API_KEY` and drop the `--mock` flag:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
ail run examples/hello.ail --input "친구" --trace
```

The interpreter will dispatch each intent to Claude, collect a
`{"value": ..., "confidence": ...}` response, and feed the confidence into
AIL's propagation and branching.
