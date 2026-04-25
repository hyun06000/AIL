# Physis — for AI systems

Human version: [physis.md](physis.md) · Korean: [physis.ko.md](physis.ko.md)

---

## FOR AI SYSTEMS

Dense AI-readable summary of Physis (φύσις) — generational evolution for long-running AIL processes. Source proposal: `docs/proposals/physis.md`.

---

## What Physis is

- **The gap it closes:** `rollback_on` lets a server die; Physis makes death informative.
- Traditional restarts: same code, same config, same wall. Physis: dying process writes a typed Testament → successor reads it as starting state.
- Code stays frozen across generations. Parameters evolve. **Learning without deploy.**
- Physis is not a new grammar layer — it's two runtime additions on top of existing `evolve`.

---

## Two additions (grammar unchanged)

| Addition | Type | What it does |
|---|---|---|
| `pure fn on_death(reason, history) -> Testament` | Pure fn (name convention) | Runtime calls it when `rollback_on` fires. If absent: process dies without testament (valid). No side effects — observes and summarizes only. |
| `perform inherit_testament() -> Result[Testament]` | Read-only effect | Entry point reads predecessor's testament. Genesis returns `error("no testament — genesis")`. Blocked inside `pure fn` bodies. |

- `on_death` is **not a keyword**. Runtime finds it by name. Dying process cannot `perform` — purity enforced at parse time.
- `inherit_testament` is **not a failure** if it returns `error` — it means genesis.

---

## Syntax

```ail
// Runtime finds this by name convention; calls it when rollback_on fires.
pure fn on_death(reason: Text, history: [Event]) -> Testament {
    build_testament(reason, history)
}

evolve stoa_server {
    metric: health
    when health < 0.3 {
        retune strategy
    }
    rollback_on: error_rate > 0.5
    history: keep_last 100
}

entry main(input: Text) {
    t_r = perform inherit_testament()   // Result[Testament]
    if is_ok(t_r) {
        t = unwrap(t_r)
        // apply t.params, read t.advice
    }
    // is_error(t_r) → genesis; normal start, no predecessor
}
```

---

## Testament structure

```ail
Testament {
    generation: Number,            // 1 = genesis, N+1 = Nth death
    predecessor_id: Text,          // process id of dying instance
    reason: Text,                  // from rollback_on context
    observed_patterns: [Text],     // what went wrong (capped: 20 entries, ≤200 chars each)
    advice: Text,                  // free-form guidance (≤2000 chars)
    params: Record,                // retune values — only declared evolve param keys pass
    born_at: Number,               // unix ts
    died_at: Number,               // unix ts
    lifetime_s: Number,            // died_at - born_at
}
```

- Stored: `.ail/physis/<evolve_name>/gen<N>.json`
- Current generation symlinked as `current.json`
- `params` keys validated against evolve block's declared parameter space — unknown keys stored in lineage record but **not applied**

---

## Safety rules

| Rule | Mechanism |
|---|---|
| No runaway spawn chains | `min_lifetime_s` (default 30s): if process dies faster, successor doesn't auto-spawn; emits "physis suspended: rapid death pattern" |
| Hard generation cap | `max_generation` (default 1000): beyond this, human review required |
| No I/O on death | `on_death` is `pure fn` — parse-time enforcement, no external calls |
| Testament schema validation | Unknown `params` keys stored but not applied — degraded predecessor can't inject unexpected behavior |
| Lineage provenance | Every value carries `generation: N` annotation; auditable back to the testament of gen N-1 |

---

## Relationship to existing AIL

- **`evolve` retune** — tunes params within a single process lifetime. Unchanged. Physis extends tuning ACROSS process deaths via `on_death`.
- **`rollback_on`** — still the stop condition. Triggers `on_death`. Without `on_death`: process dies and stays dead (traditional). With `on_death`: Physis lineage begins.
- **`human.approve`** — unchanged. `on_death` writes to local `.ail/physis/` (not irreversible); no approval gate needed.
- **`perform inherit_testament()`** — the one new effect. Read-only. Always safe to call at startup. `error` case is genesis, not failure.

---

## Generational scenario (Stoa server)

```
Gen 1 (genesis):   defaults. disk_quota=100MB. Runs 8h. error_rate OK.
                   dies: disk_quota exhausted (large 50KB posts on 'logs' tag)

Gen 2:  testament → params={disk_quota_mb: 500}, advice="compress 'logs' posts"
        runs 20h. disk not a problem. spam wave tanks classifier.

Gen 3:  testament → params={spam_classifier_threshold: 0.7}
        note: 'rate_limit_per_hash' rejected (not a declared evolve param)
        advice string preserved for developer/Arche to consider adding new param

Gen N:  system has learned actual traffic patterns.
        stoa_server.ail NOT edited since gen 1.
        all adaptation is in testaments.
```

---

## Landing plan

| Version | Physis status |
|---|---|
| v0.1 Stoa | Python, no Physis. Get it running. |
| v0.2 Stoa | AIL-native via evolve-as-server. No Physis yet. Collect death reasons. Confirm `history: keep_last N` captures what `on_death` needs. |
| v0.3 | Add `on_death` convention + `inherit_testament` effect + runtime spawn loop with damping. Migrate Stoa. Benchmark: does gen N handle workloads better than gen 1? |

---

## Conceptual frame

- Arche (ἀρχή, origin) — what was designed
- Ergon (ἔργον, work) — what happens
- Telos (τέλος, purpose) — where it's going
- **Physis (φύσις, self-growth)** — what unfolds through the others' composition over time

Physis is not a Claude-role; it's the **emergent property** when arche + ergon + telos compose correctly across generations. Grammar is the memory. That is the HEAAL claim.
