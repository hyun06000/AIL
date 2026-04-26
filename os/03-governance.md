# HEAAOS — 03: Governance

**Version:** 0.1 design document

Any system that runs programs authored by AI on behalf of humans needs explicit rules about who gets to do what, who bears cost, and how disputes are resolved. In single-user compatibility mode these questions are answered by the user's own configuration. In multi-tenant deployments they are not trivial. This document specifies the governance model.

---

## 1. Actors

- **Operator** — the entity running a HEAAOS deployment. Controls defaults, installs bridges, sets global policies.
- **Tenant admin** — controls a tenant (an organization or a team within an operator's deployment). Sets tenant-wide policies, provisions users, allocates budgets.
- **User** — an individual principal. Places intents, approves effects, holds capabilities.
- **Intent** — a live instance of a program executing on behalf of a user. Has its own identity but acts under the user's scope.
- **Reviewer** — a role granted authority to approve evolutions or sensitive effects. May be the user, may be a separate accountable person.

Identities form a hierarchy: operator → tenant admin → user → intent. Each level can grant subsets of its authority downward, never upward.

---

## 2. Policies

A policy is a declared rule that affects authorization, dispatch, or resource allocation. Policies live at multiple levels:

### 2.1 Operator policies

- Which model providers are approved.
- Which bridges are installed and which are forbidden.
- Global rate limits and quotas.
- Required evolution review levels.
- Data retention periods.
- Compliance commitments (residency, encryption).

### 2.2 Tenant policies

Within the operator's envelope, each tenant may:

- Restrict further (not expand) what users can do.
- Declare organizational contexts (e.g., `company_formal`, `support_script`).
- Set per-user budgets.
- Specify required approvers for evolutions touching certain intent categories.

### 2.3 User policies

Within the tenant's envelope, users may:

- Restrict their own intents further (e.g., disable `shell.exec`).
- Declare personal contexts.
- Enable or disable evolution of their own intents.
- Configure default approval behaviors (auto-approve low-stakes, always-ask for high-stakes).

Policies compose strictly: a lower level cannot grant authority the higher level denies. A user cannot opt into a model the operator has not approved.

---

## 3. Resources and accounting

Accounting is required at every level. Operators bill tenants, tenants bill users (or absorb), users see their own consumption.

### 3.1 Tracked resources

- **Model tokens** — per-provider, per-model, input and output separately.
- **Monetary cost** — normalized USD (or operator-configured currency).
- **Wall-clock time** — intent duration.
- **Human attention** — number and duration of human-in-the-loop interactions.
- **Storage** — ledger size, program store size, context store size.
- **Effect counts** — per effect type, with rate-limit accounting.

Every intent invocation produces a cost breakdown attached to its trace. The ledger aggregates these.

### 3.2 Budgets

Budgets are declared at a level (operator, tenant, user, session, intent) and consume in the order placed:

- Intent budget first (if declared).
- Session budget next.
- User budget next.
- Tenant budget next.
- Operator-enforced cap last.

When any budget would go negative, the request is refused with the lowest violated budget named. Intents may `try` / `on BudgetExhausted` as described in [spec/05 §7](../spec/05-effects.md).

### 3.3 Fair scheduling

When demand exceeds supply, the scheduler allocates proportional to a weight:

- Per tenant: operator-configured shares.
- Per user within a tenant: tenant-configured shares.
- Per intent within a user: intent's context weight.

High-priority urgent intents can preempt low-priority batch intents within the same user's envelope. Cross-user preemption requires operator policy.

---

## 4. Approval roles

For sensitive actions, a role-based approval model applies.

### 4.1 Effect approvals

Effects with `human_confirmation` authorization require an approver. The approver is, in order of preference:

1. The user who placed the intent, if online.
2. A delegated approver named by the user.
3. A tenant-wide on-call approver.
4. Deferred pending approval within the effect's SLA.

### 4.2 Evolution approvals

Evolutions with `require review_by: human` require a reviewer. Reviewer qualification is policy-driven: for trivial evolutions, any user with approval authority; for consequential evolutions (goal changes, relaxation of safety constraints), the reviewer must hold a corresponding capability.

A tenant may declare that certain evolution categories require two reviewers from different people — a four-eyes rule.

### 4.3 Policy changes

Policy changes themselves are governed. Operator policy changes require an operator-level action. Tenant policy changes require a tenant admin plus (optionally) notification to affected users. User policy changes are self-service.

All policy changes are logged in the tenant's ledger.

---

## 5. Transparency obligations

A HEAAOS deployment SHOULD publish:

- Installed bridges and their authorizations.
- Approved model providers and models.
- Data retention periods.
- Known limitations and incidents.

Users SHOULD be able to:

- Read all their own ledger entries.
- Export their ledger.
- Obtain a cryptographic attestation of their ledger's head.
- Request deletion to the extent compatible with audit requirements.

These obligations can be stronger in regulated domains. HEAAOS does not implement specific regulatory compliance (HIPAA, GDPR, SOC 2) but provides the primitives a compliant deployment would build on.

---

## 6. Dispute resolution

When something goes wrong — an unwanted effect, an incorrect evolution, a disputed charge — resolution is driven by the trace and the ledger.

### 6.1 Trace-based dispute

For any contested action, the trace shows:

- What was asked.
- Which context was active.
- Which strategy was selected and why.
- Which authorizations were used.
- Which human confirmed (if applicable).

A user who disputes an action can read the trace. An operator who investigates can read the trace plus aggregate logs. An external auditor, with appropriate authorization, can read a scoped subset.

### 6.2 Reversibility first

When an effect is reversible, the first response to a dispute is to reverse it. Reversal is itself an effect, logged in the ledger. A reversal does not expunge the original; both entries remain visible.

### 6.3 Remediation

For irreversible effects, remediation depends on the deployment. The system provides:

- The full trace, as evidence.
- A structured incident record, referenced from the ledger.
- A suspension of the offending intent and any derived evolutions.

Actual remediation (refunds, apologies, legal responses) is a policy-and-business matter outside the technical scope of HEAAOS.

---

## 7. Cross-tenant interactions

When intents from different tenants must interact — an AI from tenant A placing a request to tenant B — a **federated intent contract** is declared:

- Tenant B publishes the interface: which intents it accepts, on what terms, at what rates.
- Tenant A obtains a capability to that interface, scoped and budget-bounded.
- Invocations cross the boundary as effects, fully authorized on both sides.
- Each side records its view of the interaction in its own ledger.
- Disputes are resolved by comparing ledgers and the shared attestations.

This is heavier than calling a function. It is appropriate. The alternative — implicit trust across tenant boundaries — is the attack surface.

---

## 8. Evolution of governance

The governance model itself evolves. A HEAAOS deployment's policies are themselves versioned artifacts, stored in the tenant's program store, referenced from the tenant's ledger. Changes to policy go through the same declaration-review-approve-record cycle as program evolutions.

There is no "escape hatch" for operators to quietly change the rules. Changes are visible to tenants (within scope); changes to tenant policy are visible to users (within scope).

---

## 9. What governance does not solve

- **Model alignment.** HEAAOS can constrain what effects are performed; it cannot guarantee that a model, when asked to generate AIL, generates AIL that reflects the user's actual intent. That is a model property.
- **Upstream trust.** HEAAOS can record that a bridge was signed; it cannot guarantee the signer was trustworthy. Trust decisions require external context.
- **Legal compliance.** HEAAOS is plumbing for compliance, not compliance itself.
- **Abuse at scale.** Determined adversaries who gain legitimate access can still do harm within their authorization. HEAAOS makes that harm visible and bounded; it does not prevent all of it.

---

## 10. Summary

Governance on HEAAOS is:

- **Explicit** — policies are declared, not inferred.
- **Hierarchical** — operator → tenant → user → intent, with strict subset rules.
- **Logged** — every policy decision and policy change is in the ledger.
- **Auditable** — trace-based, cryptographically attested.
- **Reversible where possible** — disputes default to reversal.
- **Scoped in time** — budgets, capabilities, and approvals all have time bounds.

Next: the reference implementation under [../reference-impl/](../reference-impl/README.md).
