# AIL Specification — 05: Effects

**Version:** 0.1 draft

A pure intent reads inputs and produces outputs. An effectful intent changes something in the world: it sends an email, writes to a database, spends money, moves a file, calls a human's phone. AIL treats effects as first-class, declared, and authorized — because an AI-authored program whose effect profile is implicit is an AI-authored program that can, and eventually will, do something the human did not intend.

This document specifies how effects are declared, invoked, and authorized.

---

## 1. The fundamental rule

> An AIL intent cannot change the world without declaring that it will and receiving authorization.

This is not merely a runtime check. It is enforced by the language: an intent's body cannot contain an operation that produces an effect unless that operation is declared as an `effect` and invoked through `perform`.

A runtime that permits effects outside this discipline is non-conforming.

## 2. Effect declarations

An effect is declared at the top level:

```ail
effect send_email {
    signature: (to: Address, subject: Text, body: Text) -> Receipt
    authorization: required
    idempotency: provide_key
    reversibility: none
    budget: from context.email_budget
    rate_limit: 10 per minute
    observable_by: [user, admin_log]
}
```

The fields are:

- **`signature`** — the effect's type, as if it were an intent.
- **`authorization`** — whether authorization is required before performing. See §4.
- **`idempotency`** — how retries are handled. See §5.
- **`reversibility`** — what the runtime can do to undo the effect. See §6.
- **`budget`** — consumption accounting. See §7.
- **`rate_limit`** — optional, applied by the runtime.
- **`observable_by`** — who receives a record of this effect. See §8.

All fields except `signature` have sensible defaults; `signature` is mandatory.

## 3. Invocation

Inside an intent body, an effect is performed with `perform`:

```ail
intent notify_customer(order: Order) {
    goal: customer aware of order.status
    body = compose_notification(order)
    receipt = perform send_email(
        to: order.customer.email,
        subject: body.subject,
        body: body.text
    )
    return receipt
}
```

`perform` is a statement-level construct that:

1. Resolves the effect declaration.
2. Assembles the authorization request (if required).
3. Checks budget consumption.
4. Attempts the effect, handling retries per idempotency policy.
5. Records an observability entry.
6. Returns the effect's return value (here `Receipt`).

If authorization is denied or budget is exhausted, `perform` raises an `EffectRefused` signal, which propagates like an exception but carries the refusal reason and remediation options.

## 4. Authorization

An effect with `authorization: required` cannot execute without a matching authorization. The host OS ([NOOS](../os/00-noos.md)) defines authorization in full; AIL only specifies what an effect says it needs.

`authorization` field values:

- **`none`** — no authorization needed. Suitable for read-only effects or low-stakes operations.
- **`required`** — authorization must be present at invocation time.
- **`capability: NAME`** — requires the caller to hold a named capability token.
- **`budget_only`** — authorization is implicit as long as the budget envelope permits.
- **`human_confirmation`** — a human must confirm at invocation time.
- **`declared_policy: POLICY`** — the effect is permitted when a declared policy evaluates to true. Policies are external documents resolvable by the host.

Authorization fields combine: `authorization: required and human_confirmation` means both a capability and a fresh human confirmation are needed.

The `authorization` field cannot be weakened by a caller or by evolution. An effect declared `human_confirmation` always requires human confirmation until its declaration is replaced by a human-approved program change.

## 5. Idempotency

A retry-safe effect needs a way to recognize a duplicate invocation. AIL effects declare how:

- **`natural`** — the effect is inherently idempotent (e.g., PUT of the same content to the same URL).
- **`provide_key`** — the caller must provide a key that uniquely identifies the intended effect instance. The runtime enforces that the same key produces one effect, not two.
- **`exactly_once`** — the runtime takes responsibility for exactly-once semantics via distributed coordination. Expensive; use only when necessary.
- **`at_most_once`** — the runtime will not retry. The caller handles failure.

If a caller does not provide a required key, the effect is refused with `MissingIdempotencyKey`.

## 6. Reversibility

Reversibility declares what, if anything, the runtime can do to undo the effect:

- **`none`** — the effect is permanent once performed (e.g., sent email).
- **`compensate: INTENT`** — a named intent can compensate the effect (e.g., `send_correction_email` compensates `send_email`). Compensation is best-effort.
- **`reversible: INTENT`** — a named intent reliably reverses the effect (e.g., delete compensates create).
- **`time_window: DURATION, then IRREVERSIBLE`** — reversible within a window; permanent after.

Reversibility interacts with evolution and with rollback. An evolve rollback that would have canceled an irreversible effect logs a `RollbackLossOfEffect` event and proceeds; the effect stands. Reversible effects are compensated automatically during rollback if the `on_rollback` clause of the evolve block includes them.

## 7. Budget

Every effect consumes something. Most obviously money (LLM tokens, API calls), but also: time (deadline budgets), headcount (human review queue capacity), trust (rate-limited interactions with a user).

A budget is declared in a context or passed explicitly:

```ail
context customer_support_session extends default {
    email_budget: { per_session: 3, per_day: 10 }
    human_review_budget: { per_session: 1 }
    cost_budget: { per_session: 0.50 USD }
}
```

When an effect performs, the runtime decrements the corresponding budget. If the budget would go negative, the effect is refused with `BudgetExhausted`.

A budget refusal is not a failure of the program; it is a declared outcome the program should handle:

```ail
intent resolve(issue: Issue) {
    try:
        perform send_email(...)
    on BudgetExhausted as e:
        return defer_to_human(issue, reason: e.budget_name)
}
```

## 8. Observability

Every effect produces an observability entry. The entry includes:

- Effect name, timestamp, caller intent, active context chain
- Arguments (subject to redaction — see §10)
- Authorization that was used
- Outcome (success, refusal, failure)
- Budget consumed
- Idempotency key if any

The `observable_by` field declares who receives the entry:

- **`user`** — the requesting user sees this effect in their own activity log.
- **`admin_log`** — the operator's audit log.
- **`subject`** — a person the effect acts upon, not necessarily the user (e.g., the recipient of an email).
- **`public`** — the entry is part of a public ledger.

Omitting observability is not permitted. An effect declared with `observable_by: []` is rejected at compile time.

## 9. Effect composition

An intent MAY perform multiple effects. Default semantics:

- Effects execute in program order.
- Each effect's authorization is checked at its point of use, against the context active at that point.
- A failed effect does not automatically roll back prior effects. The program must declare compensation:

```ail
intent publish_post(draft: Post) {
    saved = perform db.save(draft)
    try:
        perform social.announce(draft)
        perform email.notify_subscribers(draft)
    on failure:
        perform compensate(saved)
}
```

For programs that need transactional semantics across effects, the stdlib provides `transaction { ... }`, which requires every enclosed effect to have `reversibility: reversible` or `compensate`:

```ail
transaction {
    perform db.save(draft)
    perform social.announce(draft)
    perform email.notify_subscribers(draft)
}
```

If any effect in a transaction fails, prior effects are compensated in reverse order. The transaction primitive is expensive and discouraged when not needed; most programs should handle partial failure explicitly.

## 10. Redaction

Arguments passed to effects often contain sensitive data. An effect declaration MAY specify redaction rules for observability:

```ail
effect send_email {
    signature: (to: Address, subject: Text, body: Text) -> Receipt
    observable_by: [user, admin_log]
    redact_in_log: {
        body: first_200_chars
        to: domain_only
    }
}
```

The argument is passed to the effect in full; only the recorded log entry is redacted. A runtime MUST apply declared redaction before writing to the named log channels.

## 11. The effect ledger

The host OS maintains an effect ledger: an append-only record of every effect performed by every intent under every user. The ledger is the source of truth for billing, auditing, rate limiting, and user-facing activity logs.

Programs MAY read their own past ledger entries through the `runtime.ledger` interface, subject to authorization. Programs MAY NOT write to the ledger directly; only `perform` writes, and only through the runtime.

## 12. What effects are not

- **Not private.** Observability is non-optional.
- **Not unbounded.** Every effect has a budget, even if the budget is "unlimited on this host" — that is itself a declaration.
- **Not reversible by default.** Reversibility is a declaration, not an assumption.
- **Not authorizable in-program.** A program cannot issue itself an authorization. Authorization comes from outside.

Next: [06-stdlib.md](06-stdlib.md).
