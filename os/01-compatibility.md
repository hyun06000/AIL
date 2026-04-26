# HEAAOS — 01: Compatibility with Conventional Operating Systems

**Version:** 0.1 design document

A clean-slate OS is a decade-long project. An AIL runtime that does not run today is a spec nobody validates. This document specifies how HEAAOS abstractions are realized on conventional operating systems (Linux, macOS, Windows) in **compatibility mode** — a userspace AIRT daemon plus a host integration layer.

---

## 1. Scope

Compatibility mode provides every HEAAOS kernel surface as a userspace facility. It is sufficient for:

- Developing AIL programs.
- Running production AIL workloads in a single-tenant setting.
- Integrating AIL with conventional software stacks.

It is not sufficient for:

- Multi-tenant hard isolation.
- Hardware-rooted trusted computing.
- Formal security guarantees beyond what the host OS provides.

Treat compatibility mode as "HEAAOS in a process", the way WSL is "Linux in a Windows process."

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│              User's AIL program (.ailg)              │
└──────────────────────┬──────────────────────────────┘
                       │ kernel calls
                       ▼
┌─────────────────────────────────────────────────────┐
│                  airtd (daemon)                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  Intent    │  │  Context   │  │  Ledger      │  │
│  │  Manager   │  │  Store     │  │  (SQLite)    │  │
│  └────────────┘  └────────────┘  └──────────────┘  │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  Authority │  │  Evolution │  │  Calibration │  │
│  │  Engine    │  │  Supervisor│  │  Store       │  │
│  └────────────┘  └────────────┘  └──────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐  ┌─────────┐  ┌──────────┐
    │  Model   │  │  Host   │  │  User    │
    │  Adapter │  │  OS     │  │  Surface │
    │ (LLM API)│  │ bridges │  │ (local   │
    │          │  │         │  │  server) │
    └──────────┘  └─────────┘  └──────────┘
```

Three outbound integration points:

- **Model Adapter**: speaks to one or more LLM providers via their APIs. Pluggable.
- **Host OS bridges**: translates declared effects (file, network, process) to host syscalls.
- **User Surface**: a local web UI on `https://heaaos.local:PORT` (TLS with a self-signed local CA or user-provided certificate) where humans place intents, approve effects, and read the ledger.

---

## 3. The daemon: `airtd`

`airtd` is a long-running process. On Linux it installs as a systemd user service; on macOS as a launchd agent; on Windows as a user-scope service.

### 3.1 Endpoints

`airtd` exposes:

- **Unix domain socket** at `$XDG_RUNTIME_DIR/airtd.sock` for local programs.
- **Local HTTPS** on `127.0.0.1:<port>` for the User Surface and for CLI tooling.
- **Optional gRPC** for programmatic integration.

All endpoints require authentication. Local socket connections are authenticated by uid. HTTP requires a session token obtained via local browser flow.

### 3.2 State

`airtd` persists state under `~/.heaaos/`:

```
~/.heaaos/
├── config.toml              # user config: models, adapters, policies
├── programs/                # content-addressed program store
│   └── <hash>/
│       ├── source.ailg
│       └── evolution.log
├── contexts/                # named contexts
├── ledger.db                # SQLite append-only ledger
├── calibration.db           # per-intent calibrators
├── capabilities/            # issued capability tokens
└── trust/                   # signing keys, trusted model IDs
```

### 3.3 Upgrade and data migration

Upgrades of `airtd` migrate state by versioned migrations. A migration that cannot be applied automatically blocks startup and surfaces a migration prompt in the User Surface.

---

## 4. Running an AIL program

### 4.1 From the command line

```bash
ail run program.ail --context ./job-context.ail --input "document text"
```

The CLI:

1. Connects to `airtd` via the local socket.
2. Submits the program for compilation (if not cached by content hash).
3. Places an intent using the specified context and input.
4. Streams the trace and final result back to stdout.

### 4.2 From another program

A host program can embed AIL via a language-specific client library. The reference library is [../reference-impl/python/](../reference-impl/python/), but other language bindings can be written against the daemon's protocol.

### 4.3 As a service

`airtd` can expose an intent as an HTTP endpoint. A program's `entry` declaration becomes a URL:

```toml
# ~/.heaaos/config.toml
[expose.translate]
program = "sha256:abc123..."
entry = "main"
authorization = "token"
rate_limit = "10/min"
```

Requests to `/intent/translate` with appropriate authorization invoke the program.

---

## 5. Host effect bridges

Conventional effects (file I/O, network, process execution) are not native to HEAAOS. They are bridged:

### 5.1 Bridge declarations

A bridge is a trusted adapter that realizes an AIL effect as host syscalls:

```toml
[bridge."file.write"]
implementation = "host:fs"
allowed_paths = ["~/Documents/noos/", "/tmp/noos/"]
require_authorization = true
max_size_mb = 100
```

Bridges run in the `airtd` process by default. High-risk bridges (process execution, arbitrary network) can be delegated to sandboxed helper processes.

### 5.2 Default bridge set

A reference HEAAOS compatibility installation ships with:

- **`file.read`, `file.write`** — scoped to configured directories.
- **`http.get`, `http.post`** — scoped to allowed domains, with TLS verification.
- **`message.send` (email)** — via user-configured SMTP or provider API.
- **`db.read`, `db.write`** — via user-registered database connections.
- **`shell.exec`** — disabled by default; requires explicit opt-in per bridge.
- **`human.ask`** — surfaces via the User Surface as a question card.

Any bridge not in the installed set is unavailable. A program requiring an unavailable bridge fails to place with `BridgeMissing`.

### 5.3 Custom bridges

Users and organizations can register additional bridges. A bridge registration must:

- Declare its effect signature.
- Provide a signed implementation binary or an endpoint URL.
- Declare its reversibility, budget, and observability.
- Pass a local sanity check (signature valid, endpoint reachable).

Bridge registrations are audited. Every effect flowing through a bridge records the bridge ID in the ledger.

---

## 6. Model adapters

The Model Adapter presents language models as a uniform interface to AIRT. Per-adapter configuration specifies:

- Provider (Anthropic, OpenAI, local runtime, etc.)
- Model identifiers and their capability profiles
- Authentication
- Rate limits
- Fallback chains

The adapter:

- Translates AIRT's prompt + constraint packages into provider-specific formats.
- Extracts confidence signals where available.
- Reports latency and cost to the capacity accounting system.
- Signs model responses for ledger attestation.

Local models are supported via a `file:` or `pipe:` adapter that speaks to an inference server on the host.

---

## 7. The User Surface

A local web application, served by `airtd`, that humans use for:

- **Intent placement** — describe goal in natural language; see the AIL program the system intends to run; approve, revise, or cancel before placement.
- **Authorization approvals** — inbound requests appear as cards with the effect, the arguments (redacted per declaration), the budget impact, and Approve / Deny / Defer buttons.
- **Ledger browsing** — filter, search, attest, and undo (where reversibility permits).
- **Evolution review** — pending modifications appear with diffs, metrics, sample calls.
- **Capability management** — issue, inspect, revoke.

The surface is accessible at `https://heaaos.local:<port>`. First-time access walks the user through generating a local CA and installing it in the user's OS trust store.

A CLI equivalent exists for users who dislike browsers: `ail approve`, `ail ledger`, `ail evolve`.

---

## 8. Installation

The reference installation:

```bash
# Linux / macOS
curl -sSf https://install.heaaos.local/sh | sh

# or from source
git clone https://github.com/<org>/ail-project
cd ail-project
make install-daemon
```

After install, a one-time configuration wizard runs in the User Surface. It asks:

- Which model providers to configure
- Which local directories to permit as `file.*` bridge targets
- Whether to expose intents as HTTP endpoints
- Whether to enable evolution

Sensible defaults exist for every question; the wizard is a review, not a quiz.

---

## 9. Resource governance in compatibility mode

Compatibility mode does not control hardware. It governs what it can:

- **Capacity** — tokens, latency, cost: accounted against user-configured budgets. Exceeding refuses new intents.
- **Compute** — best-effort; `airtd` runs at the user's process priority.
- **Concurrency** — capped by configurable limits per tenant (single-user: per-program).

Multi-tenant deployments of compatibility mode (one `airtd` serving many users) require external tenant isolation; `airtd` provides authorization and accounting per tenant but not kernel-enforced isolation.

---

## 10. Telemetry and privacy

`airtd` sends no telemetry by default. A user may opt in to:

- Crash reports (local daemon crashes only; no program data).
- Anonymous usage statistics (counts of intents placed, no content).
- Calibration sharing (contributing calibration data to a community pool; heavily sanitized).

Each is individually opt-in. Default is strict silence.

---

## 11. What compatibility mode cannot do

- Enforce isolation against a root-level compromise of the host.
- Prevent a user with system access from editing the ledger outside the daemon's API. (The ledger is cryptographically attested; tampering is detectable, not preventable, in this mode.)
- Meter hardware-level resources accurately on shared systems.

Users requiring these guarantees need a HEAAOS-native deployment or a hardware attestation chain beneath the daemon.

---

Next: [02-security.md](02-security.md).
