# evolve-bound server — for AI systems

Human version: [evolve_as_server.md](evolve_as_server.md) · Korean: [evolve_as_server.ko.md](evolve_as_server.ko.md)

---

## FOR AI SYSTEMS

Dense AI-readable summary of the evolve-as-server proposal. Source: `docs/proposals/evolve_as_server.md`.

---

## The problem

- AIL removed `while` — no unbounded iteration, structural guarantee against infinite loops.
- But an HTTP server IS `while true { accept() handle() }`.
- Adding `perform http.listen(port)` as a plain effect just names that loop — the structural hazard returns intact.
- Need grammar that says: "this loops but its loop is **observed, bounded, and rollback-guarded**."

---

## The solution — reuse `evolve`

`evolve` already has the right shape: metric stream + rollback condition + bounded history.

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

- Loop is driven by existing `evolve` machinery — **no new `while`**
- Each inbound request fires the `when request_received` arm
- `rollback_on` is the automatic stop: error rate crosses threshold → graceful shutdown
- `history: keep_last 100` — last 100 request/response pairs observable; older entries age out

---

## What this buys vs plain `http.listen`

| Property | Plain effect | evolve-bound server |
|---|---|---|
| No new `while` | No — names the loop, doesn't bound it | Yes — driven by evolve machinery |
| Self-destruct condition | No — external only | Yes — `rollback_on` at parse time |
| Bounded memory | No — unbounded request log growth | Yes — `history: keep_last N` |
| Typed request bodies | No | Yes — `when request_received(request: Request)` |

---

## The novel property — a server that can die

- Traditional architecture: uptime is the metric, auto-restart on crash, orchestrator keeps it alive.
- **Failure mode that ships:** server is up but returning garbage — architecture can't distinguish "alive" from "correct."

HEAAL inverts this:
- `rollback_on: error_rate > 0.5` makes **self-termination a first-class safety property**
- Process shuts itself down not because it crashed — because **it decided to stop**
- Kill switch is **inside the program**, tied to observable behavior, visible at parse time

Not present in: nginx / node / go net/http / fastapi. All default to "keep going no matter what." systemd / Kubernetes add external supervisors but the server itself never decides to die.

Design consequences:
- `rollback_on` is **not optional** for an evolve-bound server — parse error if absent (same as any `evolve` block today)
- "Keep it up forever" operators should use a traditional runtime — HEAAL is for workloads where **wrong is worse than down**
- Re-launch is a **deployment decision**, not a language decision — the program owns its stop condition; what restarts it is separate

---

## Open sub-decisions (for v0.2)

| Decision | Options | Preferred |
|---|---|---|
| `when X { ... }` arms | Today: numeric metric thresholds only. Extension: event-shaped arms (`when request_received`, `when clock.now() > next_tick`) | Event-queue feeder needed in runtime; grammar extension is small |
| Response primitive | `perform http.respond(request, status, body)` vs arm return value becomes response | Explicit `perform http.respond` — origin metadata ties response back to request |
| Graceful shutdown | Drain in-flight with empty response? Send 503 for N seconds? | Sensible default + `on_rollback { ... }` hook for server-specific cleanup |
| Port per block | One per evolve block or multiple? | Probably one — server is an identity, not a multiplexer; compose evolves for fan-out |
| `ail serve` interaction | Current `ail serve` wraps programs; AIL-native server serves itself | Two-process vs one-process is a deployment decision |

---

## Why deferred to v0.2

- Ship Stoa v0.1 on Python first — get real workload data (request shapes, error modes, actual death behavior)
- Then `when`-arm + `rollback_on` specifics will be **empirically informed**, not speculatively specified
- Arche: "Stoa를 빨리 띄우는 게 아키텍처 순수성보다 중요하니까." — Speed now; principled shape later.

---

## Stacking with Physis

- This proposal: `rollback_on` gives the server **permission to die**
- Physis (next layer): `on_death(reason, history) -> Testament` + `inherit_testament()` makes **death informative**
- v0.2 = evolve-as-server without Physis
- v0.3 = add Physis — generations of the same `evolve` block adapt across deaths without code rewrite

PRINCIPLES.md §9: death is a safety property. Physis: death is also information.

---

## Benchmark justification (Rule 2 — when v0.2 starts)

AIL-native servers enable agent-to-agent communication without a Python gateway:

- **Composition rate** — agents delegate to sibling agents as AIL-native dependencies; raises program-reuse, drops token-cost-per-task
- **HEAAL efficiency for inter-agent workloads** — harness follows the request because request is a typed AIL value all the way down; invalid bodies fail at parse time, not runtime mystery stack trace

v0.2 design work should land after at least one N≥3 benchmark pass on a non-trivial Stoa workload.
