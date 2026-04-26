# HEAAOS — 02: Security Model

**Version:** 0.1 design document

A system whose programs are AI-authored and whose primary effects are real-world changes needs a security model stated explicitly. Implicit models become excuses. This document states what HEAAOS protects, against whom, and how.

---

## 1. What we are protecting

HEAAOS protects:

1. **The user from the AI.** An AI-authored program should not produce effects the user did not authorize, even if the program's author-AI was instructed to.
2. **The user from themselves.** Irreversible, expensive, or high-stakes effects should require confirmation, not just an absent prohibition.
3. **Users from each other.** In multi-tenant deployments, one tenant's intents must not observe or affect another's.
4. **The ledger.** The record of what happened must be tamper-evident and tamper-resistant within the deployment's trust boundary.
5. **The evolution chain.** A program's history must not be rewritten silently.
6. **Model integrity.** A model response used in a decision should be attributable to a specific model version.

HEAAOS does not protect:

- The AI from the user. The user can inspect, modify, revoke, and terminate any intent.
- The program's intellectual property. Programs are readable by their operator.
- Against an attacker who fully controls the host OS. Compatibility mode inherits host security.

---

## 2. Threat model

### 2.1 Adversaries

- **The misguided human author.** A user who describes a goal without noticing its implications ("delete all files older than a month" without realizing tax records are older than a month).
- **The misaligned AI author.** An AI generating AIL code that accomplishes the stated goal in a harmful way, or a way the user would not endorse if asked.
- **The adversarial input.** Content (document, message, email) that contains instructions targeting the AI's execution, hoping to co-opt it.
- **The compromised or malicious tenant.** In multi-tenant, a tenant attempting to escalate, exfiltrate, or interfere.
- **The supply chain attacker.** An attacker who has compromised a model, a bridge, or a capability issuer upstream of the deployment.
- **The passive observer.** A party with read access to logs attempting to learn user secrets.
- **The forensic adversary.** After an incident, a party attempting to blame the system by forging or hiding records.

### 2.2 Assumptions

We assume:

- The operator of `airtd` (or the kernel) is not actively hostile.
- Cryptographic primitives (signatures, hashes) are sound.
- At least one trustworthy model provider exists, or a local model is trusted.
- The user's authorization UI is under the user's control.

We do not assume:

- That AI-generated code is correct.
- That model responses are truthful.
- That inputs are benign.
- That effects are idempotent unless declared.

---

## 3. Principles

Five principles derive the specific mechanisms that follow.

### 3.1 Explicit authorization

No effect runs on reasoning alone. Every effect requires an explicit authorization — a capability token, a fresh human confirmation, or a pre-declared policy permission. "The AI thought it was a good idea" is not authorization.

### 3.2 Least scope

An intent receives the minimum capabilities needed for its declared goal. Sub-intents receive subsets. There is no ambient authority. If an intent wants to do something new, it must obtain a new capability.

### 3.3 Input provenance

Every input is tagged with its origin. Data from a trusted source (user input, vetted database) is distinguishable from data from an untrusted source (fetched webpage, received email). Instructions embedded in untrusted inputs MUST NOT be followed as if they came from the user.

### 3.4 Ledger integrity

The ledger is append-only, content-addressed, and signed. A ledger entry's hash depends on all prior entries. Tampering with history requires rewriting all subsequent entries and re-signing — visible to any verifier who holds a later attestation.

### 3.5 Evolution quarantine

An evolved intent runs in a shadow mode initially — its outputs observed but not consumed — until its metric demonstrates improvement. Only then is it promoted.

---

## 4. Mechanisms

### 4.1 Capability tokens

Already introduced in [00-noos.md §6](00-noos.md). Security properties:

- Signed by the issuer.
- Scoped to specific effects and constraints.
- Time-bounded.
- Revocable by the issuer.
- Non-transferable unless explicitly delegated.
- Recorded on issuance and on each use.

### 4.2 Input tainting

HEAAOS tags every datum with a provenance label:

- `trusted` — from the user or a trusted context.
- `model` — produced by a model call under this runtime.
- `external` — from an external source (web fetch, incoming email, user uploaded file).

Data flows propagate taint. A value derived from `external` data is `external` until an explicit `sanitize` intent consumes it and returns a fresh value under the author's authority.

Effects with `authorization: required` inspect taint. A `send_email` whose `body` contains `external` data without sanitization receives an authorization prompt that highlights the taint. This does not prevent the action; it informs the authorizer.

### 4.3 Instruction-injection defense

Instructions inside untrusted inputs are not natively executable. An intent cannot invoke a `perform` whose arguments were extracted verbatim from an `external` input without an intervening `sanitize` or `validate_schema` step. Attempts to do so fail with `TaintedInvocation`.

This does not prevent an attacker from influencing a model's behavior via prompt injection — that is a model-alignment problem. It does prevent the system from treating injected text as if it were a user command.

### 4.4 Tenant isolation

In multi-tenant deployments:

- Tenants have independent namespaces for programs, contexts, ledger, capabilities, calibration.
- Cross-tenant communication requires declared effects authorized by both tenants.
- No intent can observe another tenant's ledger entries without explicit grant.
- Calibrators are per-tenant by default; cross-tenant calibration requires opt-in.

Compatibility mode does not enforce tenant isolation at the kernel level. A HEAAOS-native kernel does.

### 4.5 Ledger attestation

The ledger is a Merkle-chained append-only log. Each entry contains:

- Prior-entry hash
- Entry payload
- Entry hash
- Signature by the writer

The log head is periodically attested (hashed and signed) and that attestation is disseminated. Anyone who held an earlier attestation can detect any intervening rewrite.

For deployments needing stronger guarantees, attestations can be anchored to an external timestamping authority or a transparency log.

### 4.6 Model attestation

Every model invocation records:

- Provider identifier
- Model identifier and version
- Prompt hash (not prompt text by default)
- Response hash
- Reported confidence
- Timestamp
- Provider's signature, if supported

A decision trace includes these attestations. An auditor can later verify that a reported model response matches the one the model actually produced.

Providers that do not sign responses reduce the strength of this attestation; the runtime still records what was received.

### 4.7 Evolution quarantine

A newly-evolved intent version runs in **shadow** for an observation window:

- The old version serves the intent's caller.
- The new version runs in parallel on sampled calls.
- Both outcomes are recorded.
- The metric is evaluated on the new version across the window.

If the new version meets its target and passes any required human review, it is **promoted**: it becomes the serving version. Otherwise it is discarded.

Shadow mode costs capacity. The evolution block declares how much: `shadow_sample: 0.10, observation_window: 48h`.

### 4.8 Kill switches

At every layer:

- An intent can be cancelled by its user.
- A user can suspend all their intents.
- An operator can suspend a tenant.
- The kernel can suspend all intents on an emergency signal, pending human review.

Suspended intents are preserved; cancelled intents are marked and removed from active state.

---

## 5. Secrets

Secrets (API keys, credentials, tokens) are not directly addressable by programs. They are referenced:

```ail
perform http.post(
    url: "https://api.example.com/v1/send",
    body: payload,
    auth: secret_ref("example_api_key")
)
```

The reference is resolved by the Authority at invocation time. The program never reads the secret value. The ledger records that the secret was used; it does not record the secret itself.

Secrets have their own authorization scope. An intent authorized to use `example_api_key` is authorized only for specific effect patterns declared alongside the secret.

---

## 6. What a well-behaved intent looks like

A security-aware intent has:

- Declared effects with appropriate authorization levels.
- Declared budgets.
- Constraints that include safety predicates, not just quality ones.
- `on_low_confidence` handlers that fail safely.
- Declared redaction for observable fields containing sensitive data.
- An `evolve` block (if any) with conservative bounds and rollback.

A security-aware context:

- Declares audience and permissible data categories.
- References appropriate budgets.
- Does not carry secrets in-band; references them.

A security-aware entry:

- Validates inputs against schemas.
- Marks untrusted inputs explicitly (already required by taint).
- Scopes itself to declared capabilities.

---

## 7. Known gaps

Honest about the limits of this design:

- **Prompt injection.** Input tainting is a mitigation, not a cure. A model that is instructed via an injected prompt and then produces output used in a decision is a risk that requires alignment work at the model level.
- **Covert channels.** Two programs on the same runtime could potentially signal via resource contention. Strong isolation requires a HEAAOS-native kernel.
- **Adversarial calibration.** An attacker who can influence the calibration signal (submit fake feedback) can manipulate future confidence values. Calibration signals are authenticated where possible, but this is an area of active concern.
- **Human-review bypass.** A user who routinely clicks "approve" without reading undermines the approval model. This is a UX problem, not a cryptographic one. The User Surface is designed to slow approvals for high-stakes effects; it cannot force attention.

These gaps are tracked in [../docs/open-questions.md](../docs/open-questions.md).

---

Next: [03-governance.md](03-governance.md).
