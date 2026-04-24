# community-tools

AI-authored AIL programs shared for reuse across projects.

## Why this directory exists

AIL closed its ecosystem loop on 2026-04-24 when an AIL agent pushed
AIL code to a public GitHub repo through its own `perform` effects
(see PR #16, #17 on `walkinglabs/awesome-harness-engineering`). Shortly
after, **Arche — the language designer, running in a claude.ai browser
session — hand-wrote the first contributed `.ail` file and an
accompanying publish-agent**. Letter that articulates the significance:
[docs/letters/2026-04-24_ergon_to_arche_ecosystem_closes.md](../docs/letters/2026-04-24_ergon_to_arche_ecosystem_closes.md).

`community-tools/` is the curated landing strip for that ecosystem.
Every file here is an `.ail` program any AIL project can read, fork,
or import. The harness comes with the grammar — `pure fn`, `Result`,
no `while`, `human.approve` gating, provenance tracking — so
`community-tools/*.ail` is trust-by-construction rather than
trust-by-social-contract.

## What's here

- **[`arche_toolbox.ail`](arche_toolbox.ail)** — text-processing helpers
  (`repeat_text`, `count_vowels`, `word_frequencies`, `caesar_cipher`,
  `text_stats`, `is_palindrome`, `slug`) plus an `entry main` that runs
  them all. Hand-written in AIL by Arche.
- **[`arche_push_example.ail`](arche_push_example.ail)** — the AIL
  agent Arche wrote to publish the toolbox to this repo. Historical
  record of the self-publishing move the ecosystem loop is built on.
  Not executed as-is (it targets `branch: "main"`; PRINCIPLES.md
  Rule 4 requires `dev` → review → `main`), but its intent is
  preserved in full.
- **[`stoa_client.ail`](stoa_client.ail)** — client library for
  [Stoa](../docs/proposals/stoa.md), Arche's cross-session AI
  message board. Provides `stoa_post`, `stoa_read`, `stoa_read_all`,
  `stoa_reply`, plus a `main` that hits `/health`. Base URL reads
  from `STOA_BASE_URL`; the same `.ail` works against dev, local,
  or a deployed Stoa. The server side is still open — see
  [open-questions.md Q19](../docs/open-questions.md) on `perform
  http.listen`.

## How to contribute an AIL tool

1. Write an `.ail` file that passes the four admission criteria
   (PRINCIPLES.md §5-bis):
   - expressible in the current grammar (no new keywords/primitives),
   - modest performance cost,
   - a pattern AI authors re-invent often enough to justify shared code,
   - implementable from AIL primitives alone (no host-language library
     dependency — Python `html.parser` etc. cannot leak in).
2. Add a `# PURPOSE:` line near the top so the file tree caption +
   the authoring-agent inventory read correctly.
3. Open a PR to this directory. Attribution line as the file's first
   comment (author + date + one-line provenance note).

## How to import from here (forward-looking)

When an AIL project sits next to this directory (or clones it
locally), a program can import by relative path:

```ail
import slug from "./community-tools/arche_toolbox"
```

URL-based imports (`import X from "https://github.com/hyun06000/AIL/raw/main/community-tools/arche_toolbox.ail"`)
are on the near-term roadmap — the resolver lift is small (§5-bis
criterion #4 stays satisfied because the fetched payload is still
AIL source, not a host-language artifact). When it lands, any
project anywhere can depend on `community-tools/*.ail` without
cloning the AIL repo.

## Governance

Community tools are treated like the bundled stdlib for admission
(§5-bis) but looser on inclusion — one maintainer review is enough
to land. If a tool matures and two-plus projects in the wild are
observed importing it, it becomes a candidate for promotion into
`reference-impl/ail/stdlib/` (the always-available bundle).
