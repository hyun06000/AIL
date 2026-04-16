# NOOS — Neural-Oriented Operating System

**Version:** 0.1 design document · **Status:** Conceptual. No implementation yet.

An operating system decides what the fundamental units of computation are. Unix decided those units are files and processes. Plan 9 decided everything is a file. Mach decided everything is a message. Each decision shaped decades of software.

NOOS is a thought experiment taken seriously: **what if the fundamental units were intent, context, capacity, and attention?** This document is that design.

---

## 1. The inversion

A modern OS presents these abstractions to programs:

| Unix abstraction | What it is |
|---|---|
| File | A named byte stream |
| Process | A running address space |
| Thread | A schedulable execution |
| Syscall | A privileged request |
| Memory | Paged virtual address space |
| Device | A specialized file |

These abstractions made sense when programs were written by humans and did one deterministic thing at a time. They are a poor fit for programs that:

- Compose language-model calls with deterministic logic
- Need context, not argument lists, to behave correctly
- Consume model capacity as a first-class resource
- Evolve in place
- Must justify every effect to a human

NOOS offers a different primary vocabulary:

| NOOS abstraction | What it is |
|---|---|
| Intent | A live goal with constraints |
| Context | A typed, scoped situation |
| Capacity | Model tokens, latency envelopes, reasoning budget |
| Attention | Focus allocation across concurrent intents |
| Authority | Capability and authorization |
| Ledger | Append-only record of effects and evolution |

Files, processes, and threads still exist on NOOS, but they are built on these primitives, not the reverse.

---

## 2. Design premises

Four premises shape everything else:

### 2.1 AI is a first-class tenant

On Unix, a program runs because a human (or a scheduler on behalf of a human) launches it. On NOOS, a program runs because an intent was placed. An intent can be placed by a human, by a scheduler, or by another AI. All are first-class tenants with identities, authorizations, and budgets.

### 2.2 Context is shared infrastructure

Context, in the AIL sense, is OS-level. A user's preferences, a session's prior exchanges, a task's declared constraints — all of these are addressable, typed, subject to authorization. Programs do not carry their own context through argument passing; they read it from OS-level context services under authorization.

### 2.3 Capacity is a resource kind

A modern OS schedules CPU, memory, I/O, and sometimes GPU. On NOOS, the resource schedule includes model capacity: tokens per second on a given model, latency envelopes, reasoning depth budgets. Capacity is allocated, reserved, throttled, and billed just like other resources.

### 2.4 Effects are transactional and authorized

On Unix, a program `write()`s to a file and it happens. On NOOS, a program performs an effect through an authority kernel. Every effect passes through authorization, budget accounting, and ledger write before reaching the physical world.

---

## 3. Kernel surface

The NOOS kernel exposes syscalls organized in six families:

### 3.1 Intent family

- **`intent_place(spec)`** — submits an intent for execution. Returns an intent handle.
- **`intent_status(handle)`** — queries status: queued, running, completed, refused, failed.
- **`intent_result(handle)`** — retrieves the result, blocking or non-blocking.
- **`intent_cancel(handle)`** — requests cancellation. Subject to reversibility rules of its effects.
- **`intent_trace(handle)`** — returns the trace ledger segment for this intent.

### 3.2 Context family

- **`context_open(name)`** — obtains a handle on a named context. Authorization-gated.
- **`context_read(handle, field)`** — reads a field from a context.
- **`context_derive(parent, overrides)`** — creates a child context via `extends`.
- **`context_scope(handle)`** — activates a context for the current intent.

### 3.3 Capacity family

- **`capacity_request(kind, amount, deadline)`** — requests capacity. Kinds include: model tokens, reasoning budget, human attention, wall-clock time, monetary cost.
- **`capacity_reserve(kind, amount, window)`** — reserves capacity for a window.
- **`capacity_consume(reservation, actual)`** — accounts actual consumption.
- **`capacity_query(kind)`** — returns available, used, and projected capacity.

### 3.4 Authority family

- **`authority_request(effect, args)`** — requests authorization for a specific effect invocation.
- **`authority_grant(subject, capability, constraints)`** — issues a capability token (requires appropriate authority).
- **`authority_check(token, effect)`** — checks whether a token permits an effect.
- **`authority_revoke(token)`** — revokes a previously-granted capability.

### 3.5 Ledger family

- **`ledger_append(entry)`** — append a record to the ledger. Only authorized subjects may append.
- **`ledger_read(query)`** — read ledger entries matching a query. Authorization-gated per entry.
- **`ledger_attest(entry)`** — obtain a cryptographic attestation of an entry's presence.

### 3.6 Attention family

- **`attention_focus(intents)`** — tells the scheduler which intents are currently important.
- **`attention_yield()`** — declares that the current intent is low-priority for a period.
- **`attention_interrupt(handle, signal)`** — sends a structured signal to a running intent.

Each family has authorization requirements specified in [02-security.md](02-security.md).

---

## 4. Persistent stores

NOOS persists four things:

### 4.1 The Program Store

Versioned, content-addressed storage for AIL programs and their evolution chains. A program is identified by its root hash; a version is identified by the hash of its predecessor plus the modification. Immutable once written.

### 4.2 The Context Store

Named, typed, versioned contexts. User contexts, organizational contexts, session contexts, runtime contexts. Authorization on read and write. Contexts are referenced, not copied.

### 4.3 The Ledger

Append-only effect and evolution record. Partitioned by tenant; queryable by intent, user, subject, time. Retention is policy-driven.

### 4.4 The Calibration Store

Per-intent, per-context calibrators. Updated continuously by AIRT. Versioned with the program.

Notably absent: a general-purpose filesystem in the Unix sense. NOOS hosts one (it has to), but it is a compatibility surface, not a primary abstraction. The primary abstractions are the four above.

---

## 5. Scheduling

The NOOS scheduler allocates three resources concurrently:

- **Compute** — CPU and GPU time for deterministic work
- **Capacity** — model tokens and reasoning budget
- **Attention** — which pending intents get resources now

The scheduler is driven by:

- **Deadlines** — declared in intent spec via `context.latency_budget`
- **Weights** — derived from context `weight` expressions
- **Budgets** — capacity remaining per tenant
- **Dependencies** — intent call graphs

An intent that is latency-critical and has sufficient budget runs immediately. An intent that is low-priority queues until capacity is available. An intent that exceeds its budget is refused, not silently enqueued.

The scheduler is introspectable: any authorized intent can query the current schedule and its projected slot.

---

## 6. Identity and authorization

Every actor — human, intent, service — has an identity. Identities hold capabilities. An intent operating on behalf of a user inherits a subset of the user's capabilities, narrowed by the intent's declared scope.

### 6.1 Capability tokens

A capability is a signed grant specifying:

- **Subject** — the holder
- **Effect pattern** — which effects the token permits
- **Constraints** — budget caps, time windows, targeting restrictions
- **Delegation** — whether the holder can pass the capability onward
- **Revocation** — the token's expiration and revocation record

Tokens are not opaque to the runtime; AIRT reads the constraints and enforces them before invoking an effect.

### 6.2 Authorization flow

An effect with `authorization: required` triggers this flow:

1. AIRT prepares the effect request.
2. The Authority identifies the currently-active capabilities of the intent.
3. If a capability covers the requested effect within its constraints, authorization succeeds.
4. If no capability covers, the Authority surfaces the request to the user's authorization UI.
5. The user approves, denies, or defers.
6. On approval, a capability is issued (scope-limited, often single-use) and the effect proceeds.

### 6.3 Delegation chains

An intent may spawn sub-intents. A sub-intent inherits a subset of the parent's capabilities. The delegation is recorded; the sub-intent cannot escalate beyond its parent's scope.

---

## 7. User interface

NOOS is unusual in that it has opinionated expectations about how humans interact with it. Two UI surfaces are first-class:

### 7.1 The Intent Surface

A user-facing interface where humans state goals and see intent progress. It is not a terminal; it is not a desktop. It is a place where:

- You describe what you want in natural language.
- The system proposes an intent (reviewable before placement).
- You can inspect any intent's trace at any time.
- Effects that need authorization arrive here as contextual approvals.
- Evolution proposals arrive here as review requests.

### 7.2 The Ledger Surface

A user-facing interface where humans inspect what the system has done on their behalf. Every effect is listed. Every authorization used is listed. Every evolution accepted is listed. The user can filter, search, attest, and — where reversibility permits — undo.

Both surfaces are optional at the kernel level; they are required at the distribution level. A NOOS distribution without these is not a NOOS distribution.

---

## 8. Compatibility with conventional OSes

An ordinary machine runs Linux, macOS, or Windows. NOOS as a clean-slate OS is a research object. More practically, AIL programs should be runnable today on existing systems. [01-compatibility.md](01-compatibility.md) specifies a **NOOS-on-host** mode: AIRT runs as a userspace daemon on Linux, simulating the kernel surfaces described here and delegating where necessary to the underlying OS.

In compatibility mode:

- Intents are NOOS primitives, implemented by the AIRT daemon.
- Context storage is an authenticated local database.
- The ledger is a local append-only log.
- Capabilities are signed by a user-key and checked by the daemon.
- Effects bridge to conventional system calls via vetted adapters.

Compatibility mode does not provide kernel-level security guarantees; it is a software envelope, not a trusted computing base. It is sufficient for development and for many production use cases.

---

## 9. Hardware assumptions

NOOS assumes access to:

- **At least one language model**, local or remote, addressable via a network endpoint.
- **Persistent storage** supporting append-only semantics.
- **A trusted clock** for deadlines and expirations.
- **Cryptographic primitives** for capability signing.

NOOS does not assume:

- A specific model provider.
- A specific hardware architecture.
- A specific storage backend.
- The presence of accelerators; if present, capacity_request can target them.

---

## 10. What NOOS does not do

- **Not a replacement for Linux.** Conventional applications run on compatibility mode or on the host OS beside NOOS.
- **Not a sandbox.** NOOS is an execution environment; it does not claim to contain arbitrary user code.
- **Not autonomous.** Humans remain in the loop for effects, evolution above thresholds, and authorization grants.
- **Not a chat interface.** The Intent Surface is not a chatbot wrapping a filesystem; it is a structured intent placement and monitoring tool.

---

## 11. Related documents

- [01-compatibility.md](01-compatibility.md) — running NOOS abstractions on a conventional OS
- [02-security.md](02-security.md) — threat model and security properties
- [03-governance.md](03-governance.md) — multi-tenant policies, quotas, fairness

The compatibility document is the most important next read for anyone implementing NOOS-hosted AIRT.
