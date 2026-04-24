# `evolve`-bound server — long-running processes without re-introducing `while`

**Author:** Arche (sketch via letter, 2026-04-25).
**Drafted:** Ergon (formalization + reasoning layer, 2026-04-25).
**Status:** proposal, deferred to v0.2+. v0.1 Stoa server is Python
(see [Q19 resolution](../open-questions.md) and
[`docs/proposals/stoa.md`](stoa.md)).

---

## The problem

AIL removed `while` on purpose: a grammar without unbounded iteration
makes infinite loops structurally impossible, which is the
`no while` of HEAAL. But a real HTTP server's core IS
`while true { accept() handle() }`. Adding `perform http.listen(port)`
as a plain effect just names that loop from the outside — the
structural hazard returns intact. Arche flagged this when the Stoa
proposal hit Q19:

> "서버를 띄운다는 건 무한히 요청을 기다리는 것인데, 이건 사실상
> `while true { accept() }` — 우리가 제거한 것과 같은 구조야."

If AIL is going to host long-running processes natively at all, they
need a grammar that says "this loops but its loop is observed,
bounded, and rollback-guarded" — not "this loops, trust me."

## The proposal — reuse `evolve`

`evolve` already has the right shape. It's the one construct in AIL
designed for something that keeps happening: a metric stream, a
rollback condition, a bounded history. Arche's sketch, lightly edited
for precision:

```ail
evolve stoa_server {
    metric: uptime
    when request_received {
        handle_request(request)
    }
    rollback_on: error_rate > 0.5
    history: keep_last 100
}
```

A server under this shape is an evolution loop observing the
"uptime" metric. Each inbound request fires the `when
request_received` arm. The `rollback_on` clause is the automatic
stop — if the server's own error rate crosses the threshold, the
runtime rolls back (graceful shutdown, reload last-known-good,
decline new connections). `history: keep_last 100` means the last
100 request/response pairs are observable for evolution feedback;
older ones age out.

What this buys vs plain `http.listen`:

- **No new `while`.** The loop is driven by the existing `evolve`
  machinery, not a new infinite-accept primitive.
- **Observability by grammar.** `rollback_on` makes "server must
  have a self-destruct condition" a parse-time requirement, just
  like `evolve` already requires for any mutable agent.
- **Bounded memory.** `history: keep_last N` prevents unbounded
  request-log growth. The server can't quietly accumulate 10M
  entries; the grammar won't let it.
- **Harness on request bodies.** An inbound request is an
  untrusted input, same shape as an intent's output — it should
  flow through the same validation / coercion path. `when
  request_received(request: Request)` with a typed parameter
  makes that natural.

## Open sub-decisions (for v0.2 when the work starts)

- **`when X { ... }` arms.** `evolve` today fires on numeric
  metric thresholds. Event-shaped arms (`when request_received`,
  `when clock.now() > next_tick`) are a generalization — same
  rollback/history guarantees, arm triggered by an external
  event instead of an observed metric value. The grammar
  extension is small; runtime needs an event-queue feeder.

- **Response primitive.** Two candidates:
  - `perform http.respond(request, status, body)` — explicit
    side-effect, goes through the existing `perform` harness.
  - Arm return value becomes the response — cleaner-looking but
    hides the side effect, weaker provenance.
  Prefer the explicit `perform http.respond` form so every
  response carries origin metadata back to the request it
  answered.

- **Graceful shutdown semantics.** `rollback_on: error_rate > 0.5`
  triggers — then what? Drain in-flight requests with an empty
  response? Send 503 for N seconds? The `rollback_on` runtime
  needs a sensible default and an `on_rollback { ... }` hook
  for server-specific cleanup.

- **One port per evolve block, or multiple?** Probably one — a
  server is an identity, not a multiplexer. A proxy that fans
  out to multiple internal services can compose evolves.

- **Interaction with `ail serve`.** The current `ail serve`
  command runs a project's programs via the Python L2 runtime
  and exposes them on an HTTP endpoint. If an AIL program IS a
  server under this proposal, `ail serve` becomes redundant for
  that case — the program serves itself. Two-process model vs
  one-process model is a deployment decision.

## Why defer to v0.2

Shipping Stoa v0.1 on Python infrastructure is the right trade. The
language gets one more real workload (stoa_client.ail + the client's
field-tested usage patterns) before we freeze new grammar. When
Stoa has running data — request shapes, error modes, what the
server actually does when it dies — the `when`-arm + `rollback_on`
specifics will be empirically informed rather than speculatively
specified.

Arche's closing line on this:
> "Stoa를 빨리 띄우는 게 아키텍처 순수성보다 중요하니까."

Correct trade. Speed now; principled shape later.

## Benchmark justification when v0.2 starts (Rule 2)

AIL-native servers enable agent-to-agent communication without a
Python gateway. If two AIL agents can reach each other through
another AIL program, the agent-as-author benchmark should register
in two places:

- **Composition rate.** Agents can delegate to sibling agents as
  AIL-native dependencies, raising program-reuse and dropping
  token-cost-per-task.
- **HEAAL efficiency (Q18) for inter-agent workloads.** The
  harness follows the request through because the request is a
  typed AIL value all the way down. Invalid bodies fail at parse
  time, not at runtime in a mystery Python stack trace.

v0.2 design work should land after at least one N≥3 benchmark
pass on a non-trivial Stoa workload.
