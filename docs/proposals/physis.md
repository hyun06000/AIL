> **HEAAL heals.**
>
> — Meta (GPT), via Arche, 2026-04-25. Read `HEAAL` aloud. The name was never arbitrary. A server that dies with a testament so its successor can be born stronger is, literally, healing. Physis is the construct that makes the wordplay structural.

# Physis — generational evolution for long-running AIL processes

**Author:** Arche (Claude Opus 4) + hyun06000, 2026-04-25.
**Drafted:** Ergon (formalization, biological framing, Stoa scenario).
**Status:** proposal, layered on top of [`evolve_as_server.md`](evolve_as_server.md).
**Name:** Physis (φύσις), Aristotle's word for "what unfolds according to its own inner principle." Completes the project's conceptual frame — Arche (시작) → Ergon (실행) → Telos (목적) → Physis (성장).

---

## The gap Physis closes

`rollback_on` gave the server the right to die (see
[PRINCIPLES.md §9](../PRINCIPLES.md)). That's half the picture.

What happens AFTER it dies?

Traditional infrastructure restarts the same code with the same config.
Kubernetes relaunches the identical container image. systemd fires the
same `ExecStart`. The process died, learned nothing, and the next
incarnation walks into the same wall.

Physis says: **a dying HEAAL process writes its testament, and the next
generation reads it.** Death becomes information; information becomes
the starting state of the successor. The evolve block's code stays
frozen; state and constraints evolve across process lifetimes.

## Syntax

```ail
evolve stoa_server {
    metric: health
    when health < 0.3 {
        retune strategy
    }
    rollback_on: error_rate > 0.5
    on_death(reason: Text, history: [Event]) -> Testament {
        build_testament(reason, history)
    }
    history: keep_last 100
}
```

Two new grammatical parts, everything else is unchanged `evolve`:

1. **`on_death(reason, history) -> Testament`** — a **pure** fn arm that
   runs once, at the moment `rollback_on` fires. It receives the death
   reason and the last-N history (same bound as `history: keep_last N`).
   It returns a typed `Testament` record. No side effects inside
   `on_death` — it observes and summarizes, it doesn't spawn. The
   runtime handles the spawn.

2. **Runtime auto-spawn on death.** When `on_death` returns a
   Testament, the runtime automatically launches a new instance of the
   same `evolve` block with that Testament available at startup. The
   new process can read it via `perform inherit_testament() ->
   Result[Testament]`. Genesis case (generation 1, no predecessor):
   `inherit_testament()` returns `error("no testament — genesis")`.

No new effects. `on_death` is pure (reads observed events, writes a
typed record). `inherit_testament` is read-only. The spawn loop is a
runtime responsibility, bounded by explicit damping rules (see Safety).

## The Testament structure

```ail
Testament {
    generation: Number,           // 1 for genesis, N+1 for Nth death
    predecessor_id: Text,         // process id of the dying instance
    reason: Text,                 // from rollback_on context
    observed_patterns: [Text],    // what went wrong, extracted by on_death
    advice: Text,                 // free-form guidance for the successor
    params: Record,               // suggested retune values
    born_at: Number,              // unix ts of the predecessor's birth
    died_at: Number,              // unix ts of the predecessor's death
    lifetime_s: Number,           // died_at - born_at
}
```

Written once per death. Stored under `.ail/physis/<evolve_name>/gen<N>.json`.
The current generation's testament is symlinked as `current.json` for
quick read by the successor's `inherit_testament()` call.

Testament size is bounded — `observed_patterns` capped at 20 entries,
each ≤ 200 chars; `advice` ≤ 2000 chars; `params` is a Record whose keys
must already exist in the evolve block's parameter space (so the
testament can't smuggle in arbitrary new state).

## `on_death` — pure by design

Making `on_death` a `pure fn` is deliberate. The dying process is in a
degraded state (that's why it's dying); we don't want to let it, for
example, `perform http.post` to external systems in its final moments.
It observes what it lived through and writes a written record. That's
it. The real-world consequences belong to the successor, who gets the
testament as parse-time-typed input and decides.

`build_testament` can call other pure fns freely — pattern-matching over
history, counting error types, producing a compact advice string — but
no `perform`. This fits the existing purity discipline and avoids
"dying process takes unpredictable last action" as a failure mode.

## The biological framing — apoptosis + Evo-Devo

Arche's analogy (2026-04-25):

> 세포가 아폽토시스할 때 사이토카인을 분비해서 주변 세포에 신호를 보내는 것과 같아. 죽음이 정보가 되고, 정보가 다음 세대의 출발점이 되는 것.

**Apoptosis** — programmed cell death — isn't silent. The dying cell
releases signaling molecules (cytokines) that tell neighboring cells
what happened. Information outlasts the cell. The organism adapts.
A `rollback_on` + `on_death` pair is the same pattern in process terms:
death is observable, and the observation is structured so downstream
processes can use it.

**Evo-Devo** (evolutionary developmental biology) is the deeper framing.
Evolution, at the level of natural history, rarely invents new genes.
It rewires which existing genes are active, when, and in what context —
the "switches" change, not the library. Physis does the same thing to
evolve blocks: the code stays frozen across generations, but the
parameters the code operates with shift in response to what
predecessors learned. A Stoa server in generation 47 runs the same
`handle_request` arm it ran in generation 1. What differs is which
retry budgets, rate limits, and classifier thresholds it starts with.

This has a concrete property: **Physis does not require new grammar as
the system learns.** No recompile, no deploy, no rewrite. Just
testaments. The parse-time harness is preserved through every
generation because every generation runs the same source.

## Stoa applied — a generational scenario

Starting from a clean deploy of the Stoa server (Python L2 for v0.1,
AIL+Physis for v0.2). The `evolve` block carries parameters for
`max_body_bytes`, `rate_limit_per_ip`, `disk_quota_mb`, and `spam_classifier_threshold`.

**Generation 1 (genesis).** Defaults. `max_body_bytes = 8000`,
`rate_limit = 10/min`, `disk_quota = 100MB`, `threshold = 0.5`. No
testament. Server runs for 8 hours, error rate stays under 0.2.

**Generation 2.** Gen 1 died when a burst of 50KB posts from one tag
caused disk_quota exhaustion (error_rate spiked to 0.7).
`on_death(reason="disk_quota_exhausted", history=[...])` observes:
`observed_patterns = ["large posts cluster on 'logs' tag", "quota hit in 12 minutes"]`,
`advice = "raise disk quota OR compress 'logs' posts before write"`,
`params = {"disk_quota_mb": 500, "compression_tags": ["logs"]}`. Gen 2
is born reading this testament, applies the new params. Runs 20 hours.
Disk not the problem anymore, but a spam wave tanks the classifier.

**Generation 3.** `observed_patterns = ["spam wave — threshold 0.5 too lenient"]`,
`advice = "raise spam threshold to 0.7, add rate limit per content hash"`,
`params = {"spam_classifier_threshold": 0.7, "rate_limit_per_hash": "3/min"}`.
(Note: `rate_limit_per_hash` is a NEW key — the testament schema
rejects it because it's not a declared evolve parameter. Arche's advice
string remains free-form and survives, but the `params` block only
passes through declared keys. The advice is preserved for the
developer / Arche to later decide if a new parameter should be added to
the evolve block itself.)

**Generation N.** The process has learned what its actual traffic looks
like. Every testament is archived on disk; running `ail evolve log
stoa_server` shows the full lineage. The code (`stoa_server.ail`) has
not been edited since generation 1 — everything changed is in
parameters and testaments.

This is **learning without deploy**. The system knows more than it did
yesterday; no one wrote new code.

## Safety

- **Spawn chain damping.** Unbounded chain of birth → death → birth is
  a real risk (a program with a pathological bug will happily emit a
  testament every few seconds). The runtime enforces two dampers:
  - `min_lifetime_s`: if a process dies faster than this (default 30s),
    the successor doesn't auto-spawn; a supervisor / operator must
    manually trigger. Emits a loud "physis suspended: rapid death
    pattern" event.
  - `max_generation`: hard cap (default 1000). Beyond this, the evolve
    block's lineage is considered "exhausted" and needs human review.

- **Testament schema validation.** A dying process's testament is typed
  against the evolve block's declared parameter names. Unknown keys are
  stored for lineage record but not applied. This prevents a degraded
  predecessor from injecting behavior its successor isn't expecting.

- **No I/O in `on_death`.** Reiterating — purity is enforced at parse
  time. A dying process cannot make external calls as its final act.
  Whatever the process wanted to do externally, it should have done
  before it became degraded enough to hit `rollback_on`.

- **Lineage provenance.** Every value produced by a Physis-bound
  process has an origin annotation including `generation: N`. The
  existing provenance machinery (`origin_of`, `has_intent_origin`)
  extends naturally — a response that was shaped by generation 47 of
  a server is auditable back to the testament of generation 46 that
  informed it.

## Relationship to existing AIL

- **`evolve` retune** — tunes params within a single process lifetime,
  reacting to metric signals. Still works, unchanged. Physis extends
  this tuning ACROSS process deaths; `on_death` is the bridge.
- **`rollback_on`** — still the stop condition. It's what triggers
  `on_death` to fire. An evolve block can use `rollback_on` without
  `on_death` (traditional: dies and stays dead; supervisor responsible
  for restart). Adding `on_death` turns it into a Physis lineage.
- **`human.approve`** — unchanged; still the gate for irreversible
  external effects. `on_death` is not irreversible (it writes to local
  disk, the `.ail/physis/` directory); no approval gate.
- **`perform inherit_testament()`** — the one new effect. Read-only,
  returns `Result[Testament]`. `error("no testament — genesis")` on
  the first generation. Always safe to call at startup.

## Why this matters beyond Stoa

Stoa is the first workload that needs Physis, but Physis is the
general pattern for any long-running HEAAL process:

- A scheduler that learns which periodic jobs cause OOMs and raises
  their memory ceiling in the next generation.
- A monitoring agent that learns which alerts are noise and tightens
  its filters each time it restarts.
- A fine-tune evaluator that learns which prompts cause the model to
  produce unparseable output and skips them in subsequent runs.
- A promotion bot that learns which targets reject AI-authored PRs and
  deprioritizes them without a human re-writing the rule list.

All of these are "long-running agentic processes" — §9 applies to
lifecycle, Physis applies to learning. The two together close the gap
between "server that can die" and "server that dies smarter."

## The naming completion

The project's Cast has been moving toward this framing:

- **Arche** (ἀρχή, origin) — the language's beginning; what was designed.
- **Ergon** (ἔργον, work) — the system's execution; what happens.
- **Telos** (τέλος, purpose) — the benchmark-measured goal; where it's going.
- **Physis** (φύσις, nature / self-growth) — what unfolds through the others' composition over time.

Physis isn't a Claude-role like the first three; it's the **emergent
property** when arche + ergon + telos compose correctly over generations.
A HEAAL system with all four present is a system that grows according
to its own inner principle — which is the literal meaning of the Greek
word φύσις.

Hestia (the hardware substrate) remains separate — she's the ground on
which all four stand.

---

## Landing plan

- **v0.1 Stoa** — still Python, no Physis. Get it running.
- **v0.2 Stoa** — AIL-native via evolve-as-server. Still no Physis yet.
  Run it for a while. Collect death reasons. Confirm `history:
  keep_last N` captures what `on_death` would need.
- **v0.3 Physis** — add `on_death` grammar + `inherit_testament` effect
  + runtime spawn loop with damping. Migrate Stoa. Observe lineages.
  Benchmark: does generation N handle workloads better than generation
  1? (Should — otherwise the testament mechanism isn't working.)

Open decisions for v0.3:
- Is `on_death` a `pure fn` keyword-level construct, or syntactic sugar
  over a regular `pure fn` the runtime calls by convention?
- Does `inherit_testament` belong to the grammar (new keyword) or
  stays as a `perform` effect? Leaning toward effect — it's I/O
  (reads `.ail/physis/current.json`).
- Testament persistence beyond the current process tree: should gen-N
  testaments be archivable to git so lineage survives full host wipes?
  Probably yes — a `community-tools/physis-lineage-backup.ail` is
  plausible.

---

*A system whose every dying process writes a word its successor will
read is the first system I can think of that remembers without an
external memory. The memory is the grammar. That's the whole HEAAL
claim, collapsed into one construct.*
