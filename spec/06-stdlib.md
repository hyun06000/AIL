# AIL Specification — 06: Standard Library

**Version:** 0.1 draft

The standard library is a curated set of intents, contexts, and effects that any conforming runtime MUST make available. It is deliberately small. The goal is to ship a minimum that lets programs do useful work without every program needing to redefine basic building blocks.

Items are grouped by module. Each module has a path; a program imports:

```ail
import summarize from "stdlib/language"
import context default from "stdlib/core"
```

---

## 1. `stdlib/core`

Foundational types and contexts.

### Contexts

- **`default`** — the context active when no other is. Fields: `register`, `cost_budget`, `latency_budget`, `weight`, `audience`, `language`, `trace`. See [02-context.md §2](02-context.md) for full schema.
- **`strict`** — extends `default` with tighter budgets and hard constraints on determinism. Suitable for high-stakes flows.
- **`exploratory`** — extends `default` with relaxed budgets and soft constraints. Suitable for drafts and prototypes.

### Types

- **`Confidence`** — number in `[0, 1]`.
- **`Distribution[T]`** — PMF over `T`.
- **`Interval[T]`** — `(low, high)` pair over an ordered `T`.
- **`Set[T]`** — multiple candidates with per-item confidence.

### Intents

- **`identity(x: T) -> T`** — returns `x`. Useful as a default target in `branch`.
- **`refuse(reason: Text) -> Never`** — aborts the current intent with a declared refusal reason. Recorded in trace; distinct from a failure.

---

## 2. `stdlib/language`

Operations on natural-language text.

- **`summarize(source: Text, max: Number) -> Text`** — produces a summary within the token limit. Context-aware (register, audience, weight).
- **`translate(source: Text, to: Language, from: Language?) -> Text`** — translates text. Infers source language from context or detection if unspecified.
- **`classify(text: Text, labels: [Label]) -> Distribution[Label]`** — returns a distribution over the provided labels.
- **`extract(source: Text, schema: Schema) -> Record`** — structured extraction. Schema violations raise `ExtractionFailed`.
- **`rewrite(source: Text, instruction: Text) -> Text`** — applies a rewrite instruction.
- **`embed(source: Text) -> Vector`** — returns an embedding. The embedding space is identified in the return type; incompatible embeddings cannot be compared.

All of these intents have associated `calibrate_on` signals and support `evolve` rules.

---

## 3. `stdlib/reason`

Operations for structured reasoning.

- **`decompose(goal: Text, context: Context) -> [Subgoal]`** — breaks a goal into subgoals. Used by planner intents.
- **`verify(claim: Text, evidence: [Text]) -> Confidence`** — assesses whether the evidence supports the claim. Returns a calibrated confidence.
- **`compare(a: T, b: T, criteria: [Criterion]) -> Comparison`** — structured comparison under named criteria.
- **`critique(artifact: T, rubric: Rubric) -> Critique`** — returns strengths, weaknesses, and suggestions.
- **`consensus(answers: [T]) -> (value: T, agreement: Confidence)`** — finds the consensus of multiple candidate answers.

---

## 4. `stdlib/effects`

Pre-declared effects commonly needed. Importing these provides declarations only; the host decides whether to supply an implementation.

- **`http.get(url: URL) -> Response`** — read-only. `authorization: declared_policy`, `observable_by: [admin_log]`.
- **`http.post(url: URL, body: Bytes) -> Response`** — write. `authorization: required`, `observable_by: [user, admin_log]`.
- **`db.read(query: Query) -> Rows`** — read from a database. Host-provided.
- **`db.write(statement: Statement) -> Outcome`** — write to a database. `authorization: required`.
- **`file.read(path: Path) -> Bytes`** — read-only.
- **`file.write(path: Path, content: Bytes) -> Outcome`** — `authorization: required`, `reversibility: compensate: file.restore`.
- **`message.send(to: Address, content: Message) -> Receipt`** — `authorization: required and human_confirmation` for first-time recipients; `required` for repeat.
- **`human.ask(question: Text, expect: Schema) -> Answer`** — delegate a decision to a human. The canonical way to pull a human into the loop. `budget: from context.human_interaction_budget`.

---

## 5. `stdlib/time`

- **`now() -> Time`** — current time. Does not advance within a single intent call.
- **`deadline(in: Duration) -> Time`** — returns a deadline relative to `now()`.
- **`within(deadline: Time, do: Intent) -> Result | Timeout`** — runs an intent with a deadline.
- **`schedule(at: Time, do: Intent) -> Handle`** — schedules an intent for later execution. Requires `authorization: required`.

---

## 6. `stdlib/trace`

- **`trace.current() -> Trace`** — the trace of the currently-executing intent.
- **`trace.attach(key: Text, value: Any)`** — attach a key-value pair to the current trace entry.
- **`trace.span(name: Text, do: Intent) -> T`** — run an intent inside a named trace span.
- **`trace.get(id: TraceId) -> Trace`** — retrieve a past trace. Authorization required for traces not owned by the caller.

---

## 7. `stdlib/confidence`

Pure functions on confidence values. See [03-confidence.md §8](03-confidence.md).

- **`and(c1, c2, ...) -> Confidence`**
- **`or(c1, c2, ...) -> Confidence`**
- **`not(c) -> Confidence`**
- **`calibrate(raw: Number, model: ModelId, context: Context) -> Confidence`**
- **`ece(samples: [(prediction, outcome)]) -> Number`** — Expected Calibration Error

---

## 8. `stdlib/planner`

Higher-level composition.

- **`plan(goal: Text) -> Plan`** — decomposes a goal into a plan of intent calls. The plan is reviewable before execution.
- **`execute(plan: Plan) -> Result`** — runs a plan. Respects all effects and authorizations inside.
- **`revise(plan: Plan, feedback: Feedback) -> Plan`** — produces an updated plan given feedback.

Plans are a structured data type, not free text. This is important: a plan is inspectable, diffable, and revisable without re-running the planner.

---

## 9. What is not in the standard library

Deliberately omitted:

- **General-purpose I/O beyond the listed effects.** Ad-hoc I/O invites untraced side effects.
- **Concurrency primitives.** The runtime manages concurrency; programs do not fork threads.
- **Cryptographic primitives.** Effects that need crypto call out to host-provided effects with their own authorization.
- **Machine-learning training.** AIL is for authoring intent. Training is an external activity whose artifacts become models that AIL may invoke via effects.
- **UI primitives.** Rendering belongs in the host.

A program needing any of these uses a host-provided effect or refuses to run on hosts that do not provide it.

---

The specification ends here. The next document is [../runtime/00-airt.md](../runtime/00-airt.md) — the runtime.
