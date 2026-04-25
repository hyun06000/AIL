# AIL Open Questions — for AI systems

Dense reference. Human version: [`open-questions.md`](open-questions.md) · Korean: [`ko/open-questions.ko.md`](ko/open-questions.ko.md)

Status tags: **open** (no answer) · **sketched** (partial, needs validation) · **deferred** (not needed for v0.1, blocks later) · **resolved** (done)

---

## Language-level

- **Q1 — Confidence composition across heterogeneous models** — *sketched*
  When a strategy calls multiple models, their confidences must combine. Current spec: min-of-inputs for deterministic ops, calibrated-self-report for non-deterministic. May be too conservative. Proposed directions: per-(intent,model) calibration with meta-calibrator; Bayesian update treating each model as independent noisy estimate; per-intent confidence semantics.

- **Q2 — Formal semantics** — *open*
  AIL has informal operational semantics only. Denotational semantics would enable: program equivalence checking (is this evolved version equivalent under declared bounds?), compiler optimization (fold redundant intent calls), formal runtime conformance verification. Large effort; requires partial language stabilization first.

- **Q3 — Types for distributions and intervals** — *open*
  `Distribution[T]`, `Interval[T]`, `Set[T]` introduced in spec but operations not fully defined. Interaction with `branch` and constraint satisfaction unspecified. Principled design pending.

- **Q4 — `in` operator and collection membership** — *resolved (v0.1.1)*
  Added `MembershipOp` AST node; `x in C` and `x not in C` at comparison precedence. Confidence propagation: `min(element.confidence, collection.confidence)`. Five executor tests cover it.

---

## Runtime-level

- **Q5 — Cross-runtime evolution sync** — *deferred*
  Same AIL program on two runtimes (prod + staging); one evolves an intent — should it propagate? Default likely: no. Sync protocol, conflict resolution, rollback coordination undesigned.

- **Q6 — Adversarial inputs and calibration** — *open*
  Attacker controlling inputs can systematically corrupt calibration via false feedback. Current design relies on robustness only. Proposed directions: authenticated feedback channels (signed-only updates calibration); anomaly detection on calibration updates (flag sudden ECE changes); per-source calibrators that can be quarantined.

- **Q7 — Strategy catalog bootstrapping** — *sketched*
  Dispatcher needs candidate strategies for a goal. Sources: handwritten per deployment (low flexibility, high trust); derived from `stdlib/*` registry; AI-generated from program itself (raises alignment questions). Reference impl uses one-strategy-per-intent. Real AIRT needs more.

- **Q8 — Latency-under-uncertainty dispatch** — *open*
  Given `{ latency < 2000ms, fidelity > 0.9 }`: fast low-fidelity vs. slow high-fidelity strategy. Scoring rule works when distributions are well-calibrated; behavior unclear when uncalibrated or latency distribution has long tail.

---

## OS-level

- **Q9 — Policy conflict resolution** — *sketched*
  Multiple policy levels (operator, tenant, user, intent) can conflict. Spec handles lower-cannot-grant-what-higher-denies. Hard case: two equal-level policies conflict. Likely direction: last-writer-wins is unacceptable; conflicts should surface for human resolution with structured diff. Surfacing mechanism unspecified.

- **Q10 — Ledger retention vs. right-to-deletion** — *deferred*
  Cryptographically-chained ledger with selective deletion is hard. Techniques exist (redaction trees, verifiable deletion proofs). Which to adopt, and how to balance against auditability, is open architectural question.

- **Q11 — Trust in bridges** — *open*
  Bridges are signed per spec; who signs, how revocation propagates, how to evaluate trustworthiness before installation — all unspecified. Full answer likely looks like a sigstore-like ecosystem for bridges. Large effort.

- **Q12 — Local-first vs. cloud-first deployment** — *deferred*
  Single user on single machine is covered. Multi-user office or personal multi-device deployment has different trust and sync requirements. Neither covered in current spec.

---

## Ecosystem-level

- **Q13 — Program portability** — *open*
  AIL program not fully portable: depends on available model adapters, bridges, calibrators. "Runs on any conforming runtime" is undefined given these dependencies. Likely answer: manifest declaring minimum runtime requirements + compliance-level declaration on runtimes. Details unwritten.

- **Q14 — Debugging workflows** — *sketched*
  Traces are primary surface; debugging probabilistic programs through traces alone is hard. Tools needed: trace diffing between runs, counterfactual replay ("what if confidence had been higher here?"), calibration visualizations, constraint-violation explanations. None exist yet.

- **Q15 — Community norms around evolution** — *open*
  Intent in shared library evolving differently per user means no single canonical behavior. How should community-maintained library handle evolution? Lock off? Publish evolution recommendations? Version evolved variants? Sociotechnical question; best answered by watching real communities.

- **Q16 — Do comments belong in an AI-authored language?** — *open*
  If primary author and reader are both AI: (1) documentation for humans drops out — humans aren't in read path; (2) temporary disable dominated by regenerate-and-replace; (3) pragma surface doesn't exist in AIL. v5 training experiment empirically removed `//` and `#` — author model doesn't appear to need comments. Proposed directions: keep comments but discourage in training data; drop in v2.0 as breaking change; add `/** @reason */` block for trace-exported annotations only.

- **Q17 — Is "humans don't read AIL" too absolute?** — *open*
  Practice: `ail ask --show-source` users do read generated code to sanity-check. Question: does the language need a "human-friendly display" mode (re-indent, re-comment on demand)? If that mode exists, does it pull the language back toward "Python with braces"? Especially sharp if Q16 drops comments — how do humans understand 500-line programs? Or is 500-line `.ail` itself a design smell?

- **Q18 — HEAAL Score, harness efficiency axis** — *open (proposed 2026-04-24)*
  Current HEAAL Score: parse rate + answer rate. A/B v2 experiment proposes new dimension: **tokens spent per parseable answer** (`exact / 1K tokens`). Results on 50 prompts × 3 paths: AIL intent (wrapped) = 0.163, stripped system prompt = 0.000, raw API = 0.012. Wrapper pays ~150 tokens system prompt, halves output tokens, net ~equal cost — but ~20× exact-match rate. Open decisions: what denominator (tokens, dollars, latency, or weighted)? per-category or single aggregate? Does this bias fine-tuning toward terseness at cost of mild accuracy? Not real until agreed in `docs/heaal.md` and benchmark spec.

- **Q19 — `perform http.listen(port)` — HTTP server as first-class effect** — *resolved (2026-04-25)*
  **Resolution:** v0.1 server in Python (L2 infrastructure per PRINCIPLES §5-ter). AIL-native server deferred to `evolve`-bound pattern — server IS an evolving agent on `uptime` metric with `rollback_on: error_rate > 0.5`, request handling in `when request_received { ... }` arms. No new primitive needed; generalization of `evolve` to event streams. Full sketch: [`proposals/evolve_as_server.md`](proposals/evolve_as_server.md). Rationale: plain `http.listen` would grammatically re-introduce `while true { accept() }` — the structure `while` removal was designed to eliminate.
