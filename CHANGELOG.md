# Changelog

All notable changes to the AIL project are documented in this file.

---

## v1.9.7 — 2026-04-23

Two fixes from hyun06000's `usd-now` test on v1.9.6. The headline:
v1.9.5's two L2 v2 primitives (`perform clock.now()` + the
http.get authoring nudge) **both verified** in production —
Sonnet wrote `perform http.get("https://api.exchangerate-api.com/...")`
and `perform clock.now()` exactly as steered, no fabrication, no
hardcoded timestamp. v1.9.7 closes the two adjacent issues that
emerged.

### Fixed — `chat_apply` (and therefore `--auto-fix`) crashed every time

- `ail/agentic/chat.py::_chat_examples()` returned dicts where the
  AnthropicAdapter (and others) iterate examples as `(input, output)`
  tuples. Every chat call therefore raised
  `ValueError: too many values to unpack (expected 2)` inside the
  adapter. `--auto-fix N` showed it via the friendly logger
  ("AI가 수정안을 내놓지 못했어요: ValueError: ..."), and `ail chat`
  on a real project would crash the same way.
- Same shape mismatch was fixed in `diagnosis.py` at v1.9.2; the
  parallel hole in `chat.py` survived because no path exercised
  it until hyun06000 hit `--auto-fix 2`.
- Added a regression test that asserts the example contract
  matches what the adapter expects (mirror of the diagnosis
  contract test from v1.9.2).

### Improved — authoring prompt: signal errors via Result, not strings

- In hyun06000's `usd-now` Sonnet wrote
  `if is_error(usd_result) { return unwrap_error(usd_result) }`
  for the empty-input and "abc" test cases. The function returns
  a Korean error string, which is fine UX in a browser — but the
  agentic test runner inspects the return shape (Result error vs
  plain Text) to decide whether the run "errored" or "succeeded".
  A returned string looks like success.
- New section in the default authoring goal: SIGNALING ERROR FROM
  entry main. The rule is "return the Result error directly, NOT
  `unwrap_error(...)`". Same for success — prefer `ok(value)` so
  the server / test runner can introspect uniformly. The HTTP
  layer already unwraps Result for end-user display, so users
  still see the same error text.

### Tests

- 331 tests pass (was 330). +1 chat-examples contract test.

### Verified by this release

- v1.9.5 fix #1 (`perform http.get`): ✅ Sonnet picked the effect
  on the real exchangerate-api URL with no `intent fetch_*`
  delegation.
- v1.9.5 fix #2 (`perform clock.now()`): ✅ Sonnet used the new
  primitive instead of the `"2024-01-15"`-style hardcoded literal
  the news-dashboard case study showed.
- v1.9.6 i18n (FriendlyLogger Korean): ✅ Whole session in Korean
  on a Korean INTENT.md, including the new auto-fix lines.

---

## v1.9.6 — 2026-04-23

Whole-session Korean localization for the FriendlyLogger. Until
v1.9.5 only the authoring-failure path localized; every other log
line ("Reading INTENT.md", "Running tests", "Tests didn't pass —
not starting the service", "Service is live", ...) stayed English
even when INTENT.md was Korean. That's half-translated output —
worse than a fully English interface for the audience we target.

Surfaced by hyun06000: on a Korean `usd-now` project, the
authoring-failure path showed Korean diagnosis but the test
summary and the abort sentence were in English.

### Changed

- **`FriendlyLogger` is now fully bilingual (Korean / English).**
  A `_STRINGS` table maps every log-line key to both languages.
  The logger instance takes a `language` hint on construction.
- **`bring_up` detects language from INTENT.md once at entry** and
  passes it through to `make_logger`. Korean INTENT → whole
  session in Korean: project header, reading-intent line, author
  start / done, test results ("성공 기대 → 성공", "에러 기대 → 에러"),
  summary ("4개 중 2개 통과 — 2개 아직 실패"), the tests-aborted
  block, watcher warnings, serving banner, port-collision error,
  auto-fix progress lines, shutdown.
- **Pluralization handled.** English pluralizes via `{s}` suffix
  resolved from the count argument; Korean uses the same phrase
  for singular and plural (linguistically correct).

### Compatibility

- `CompactLogger` stays language-neutral (it exists for scripts
  and CI that grep for `[PASS]`/`[FAIL]` markers). Unchanged.
- `--log compact` output is unchanged.
- `make_logger(style)` still works with one argument; the new
  `language` keyword is optional and defaults to English.

### Tests

- Still 330 tests. No new test file — each log string's layout is
  already indirectly covered by the agent end-to-end tests; the
  i18n change is a per-call lookup with defensive fallback to the
  English table for any missing Korean key.

---

## v1.9.5 — 2026-04-23

First two of the six L2 v2 primitives surfaced by the 2026-04-23
news-dashboard case study (see
`docs/case-studies/2026-04-23_news-dashboard.md`). Both are
small-footprint and land together.

### Added — `perform clock.now()` effect

- **`perform clock.now() -> Text`** — ISO-8601 UTC by default
  (`"2026-04-23T15:02:34Z"`). `perform clock.now("unix")` returns
  seconds-since-epoch as Text. Every returned value carries an
  effect-origin node, so `has_effect_origin(t)` is true and
  provenance can distinguish a real timestamp from a hardcoded
  literal.
- Rejected by `pure fn` at parse time (structural purity preserved).
- Rationale: the case study showed Sonnet generating
  `current_time = "2024-01-15 14:30:00 KST"` as a hardcoded literal
  because AIL had no clock primitive to call. An unchanging
  timestamp in a live service is always wrong. This closes the gap.

### Changed — authoring prompt steers fetches to effects, not intents

- **`FETCHING EXTERNAL DATA` section added to the default authoring
  goal.** Explicit rule: "if the task needs web data / files /
  current time, use `perform http.get` / `perform file.read` /
  `perform clock.now` — NOT an `intent`." The case study showed
  models delegate "search the web for X" to `intent search_news(...)`
  which then hallucinates news the LLM doesn't have. The new
  section names the failure mode and prescribes the fix.
- **Two new few-shot examples in `_authoring_examples()`:**
  (1) `perform http.get` pattern paired with an `intent` for
  interpretation — pins the "fetch via effect, interpret via
  intent" shape.
  (2) `perform clock.now()` pattern for prompts that mention
  "current time" or "now".
- Behavior change is prompt-only; the grammar is unchanged.

### Fixed

- Documentation drift: added `clock.now` to `reference_card.md` and
  `spec/08-reference-card.ai.md` alongside the other effect
  signatures.

### Tests

- 330 tests pass (was 325 in v1.9.4). New: 5 clock tests covering
  default ISO-8601 shape, explicit `"iso"` arg, `"unix"` arg,
  effect-origin carriage, and the purity-rejection contract when
  `perform clock.now` appears inside a `pure fn` body.

### Not yet — still open L2 v2 items

Four of the six case-study gaps remain. Next candidates:

  - `perform schedule.every(...)` for background polling (Gap 3)
  - Cross-request state effect on `.ail/state/` (Gap 4)
  - HTML / layout output mode (Gap 5)
  - Input-aware UI rendering (Gap 6)

---

## v1.9.4 — 2026-04-23

Closes two gaps in the non-developer experience. Surfaced by
hyun06000 after running a Korean project end-to-end and finding
curl unusable as the "send a request" interface. Also: the
file-watch auto-reload story was hidden in one log line; most
users would never discover it.

### Added — browser UI

- **`GET /` now returns an HTML page.** Single-page form: a
  textarea, a Send button, a result area, and the project's
  description pulled from INTENT.md's preamble. No framework, no
  npm, no build step — stdlib HTTPServer serves the HTML inline.
- **Localized to Korean or English** by detecting Hangul syllables
  in the project preamble. Labels ("보내기" / "Send", "결과" / "Result",
  the auto-reload tip) switch accordingly.
- **`POST /` behavior unchanged** — the existing curl / script path
  still works. Browsers submit the form via fetch() to the same
  endpoint; machines and humans share the URL.
- **Ctrl-Enter in the textarea submits.** Small but matters for
  keyboard users.
- **Content-Security-aware rendering.** User-controlled text
  (project name, preamble) is `html.escape()`d before landing in
  the DOM. Unit test covers the script-injection case.

### Changed — auto-reload is now loud

- **`Service is live` block rewritten.** Previously one line told
  the user the URL and Ctrl-C. Now three short paragraphs: (1)
  the URL, with an explicit "open it in a browser, there's a text
  box waiting"; (2) "Edit INTENT.md and save — the service updates
  itself. No restart. The tab you just opened keeps working."
  (3) "Ctrl-C here to stop."
- **README + docs/ko/README.ko.md updated** to match. The old
  `curl -X POST ...` block in the walkthrough is replaced with
  "open that URL in a browser" as the primary path; the curl form
  is mentioned one paragraph down for scripts.

### Tests

- 325 tests pass (was 318 in v1.9.3). New: 7 web-UI tests —
  render-page localization for both languages, HTML-escape
  safety, preamble extraction, and an end-to-end HTTP test that
  launches the real stdlib server and asserts `GET /` returns
  HTML with the expected content.

### Why this matters

v1.9.0–1.9.3 delivered the non-developer loop
("`ail init` → edit INTENT.md → `ail up`") but stopped at the
moment the service came up. If `curl` is the only way to talk to
the service, the audience we built this for has no way in. A
browser form costs a few hundred lines of stdlib-only Python and
closes that gap.

---

## v1.9.3 — 2026-04-23

Failed authoring attempts are now persisted to disk. Previously the
ledger only recorded the parse error; the actual AIL source the
model produced was thrown away. That meant a developer (or a future
meta-author AI built on top of these projects) had no artefact to
inspect or learn from when the model converged on the same wrong
shape repeatedly.

Surfaced by hyun06000: "정확한 에러 리포트를 얻거나 프로그램을 할 수
있는 사용자 혹은 메타 저자 AI 등이 이 문제를 해결하려면 세션의
저자 AI가 만든 코드나 결과물을 (실패한 거라도) 어딘가엔 기록해
둬야 할 거야."

### Added

- **`.ail/attempts/<UTC-timestamp>_author_failed.ail`** — written
  whenever the author exhausts its retry budget. The file is plain
  AIL source (not parseable, by definition) headed by a `//` comment
  block recording the timestamp, the author model, and one line per
  retry's parse error. The body is the LAST attempt verbatim, so
  someone — human or LLM — can pick up the artefact and see what
  shape the model is converging on.
- **`Project.save_failed_attempt()`** — public helper, also
  available to the chat / auto-fix paths in future versions.
- **`Project.attempts_dir`** — `attempts/` subdir of `.ail/`,
  created on demand. `.ail/` is gitignored so attempts never
  accidentally land in user's git history.
- **Ledger entry `attempt_saved`** — `{path, kind, source_chars}`
  references the file. The existing `author_failed_diagnose_attempt`
  entry now also carries `attempt_file`.
- **UI surfaces the attempt path.** Friendly mode prints a localized
  "AI's last attempt (failed)" line; compact mode prints `attempt:
  <path>`. Both pointing to the saved `.ail` file.

### Tests

- 318 tests pass (was 316 in v1.9.2). New: 2 attempts-save tests
  (file shape, on-demand directory creation).

### Why this matters

This is the foundation for two things L2 v2 will need:

  1. A meta-author AI that learns from failures by reading the
     attempts corpus instead of just retrying blindly.
  2. A debugging story for developers who do read AIL — they can
     grep the saved files for the patterns the author tends to
     get wrong.

For now it is just an artefact dump, but the artefacts are no longer
lost.

---

## v1.9.2 — 2026-04-23

Hot-fix on top of v1.9.1. The diagnose-on-failure feature shipped
yesterday crashed silently inside every adapter — the few-shot
examples were dicts where the existing adapter API expects
`(inputs_list, output)` tuples, raising `ValueError: too many values
to unpack` and falling back to the English static tip list every
time. So end users never actually saw the AI-translated explanation
the v1.9.1 release notes promised.

Caught by hyun06000's first real-world test: a Korean-language
project repeatedly hit the fallback path, which is also too
technical for a non-developer.

### Fixed

- **`diagnose_authoring_failure` examples shape.** Now matches the
  `(inputs_list, output)` tuple form the AnthropicAdapter (and the
  others) iterates over with `for inp, out in examples[:5]`. The
  v1.9.1 dict shape silently broke every diagnose call. Regression
  test added that asserts the example shape against what the
  adapter requires.

### Improved (also driven by the same test)

- **Static fallback is multilingual.** When the diagnose LLM call
  itself can't run (no API key, network down), the fallback message
  is now picked by detecting Hangul syllables in the user's
  INTENT.md. Korean projects get Korean fallback text. The new text
  drops command-line snippets (`ANTHROPIC_API_KEY`, `--auto-fix 2`)
  in favor of plain advice — the audience is a non-developer who
  doesn't know what an env var is.
- **Header strings localized.** "Could not build the program" /
  "Full log" headers now also localize to Korean when INTENT.md is
  in Korean.

### Tests

- 316 tests pass (was 314 in v1.9.1). New: 1 examples-shape
  contract test, 1 language-detection test.

---

## v1.9.1 — 2026-04-23

UX patch release. Surfaced by hyun06000's first-time use of v1.9.0 on
a real Korean-language project. Targets the audience the agentic
layer was designed for: people who know natural-language prompting
but no code.

No grammar changes; v1.8 spec freeze still in effect.

### End-user-friendly logging (default)

- **`ail up` output redesigned.** Sentences with breathing room, ✓/✗
  marks for tests, the author model identified by name on every run.
  The original v1.9.0 dev-style one-liners are still available with
  `ail up --log compact` for scripts and CI.
- **Author model now identified.** Previously the user had no way to
  tell which backend (`anthropic/claude-sonnet-4-5`, `ollama/ail-coder:7b-v3`,
  `openai_compat/...`) actually wrote `app.ail`. The friendly view
  now prints it on the authoring line and the ledger records it
  on every `author_start` event.

### Authoring failure becomes a plain-language conversation

- **Diagnose-on-failure.** When the author exhausts its retry budget,
  the agent now calls the same backend ONE more time with a
  different goal: "explain in plain language what made this hard
  and suggest one specific edit to INTENT.md". The reply is
  produced in the same natural language the user wrote INTENT.md in
  (Korean → Korean, English → English) and printed instead of the
  raw `ParseError: unexpected token COLON(':')@6:42` that v1.9.0
  showed.
- The diagnose prompt forbids code-level vocabulary (`syntax`,
  `colon`, `token`, `intent`, `pure fn`, `compile`, …) and frames
  the difficulty as a limit of what could be automated, not a
  user mistake.
- If the diagnose call itself fails (no API key, network down),
  falls back to a concise static tip list. Raw errors still go to
  `.ail/ledger.jsonl`.
- Module: [`reference-impl/ail/agentic/diagnosis.py`](reference-impl/ail/agentic/diagnosis.py).

### `ail init` UX

- **Both invocation paths shown.** `ail init foo` previously suggested
  only `ail up foo` as the next step; from inside the new project
  folder that command became `ail up foo/foo` and failed with a
  confusing "no INTENT.md" message. Now prints both forms:

  ```
    then:  ail up foo           (from here)
       or: cd foo && ail up     (from inside the project)
  ```

### INTENT.md parser tolerance

- **ASCII arrows accepted in test bullets.** Previously only the
  Unicode `→` separated input from expected outcome; bullets using
  `->` or `=>` were silently dropped (they appeared in the file but
  never ran). Now all three forms work; tests using `-> 에러` or
  `=> succeed` are recognized.

### Recorded design principle

> Errors that come from AI-generated code should be translated by AI
> into the user's language. Tokenizer / parser / runtime vocabulary
> should never reach a non-developer.

Captured in the diagnosis module docstring; intended to inform
future error-rendering work across the agentic layer.

### Tests

- 314 tests pass (was 308 in v1.9.0). New: 6 diagnosis, 1 arrow
  fallback. Existing tests unmodified — the friendly logger is
  routed through a `Logger` abstraction, ledger format is
  unchanged, all assertions still hold.

---

## v1.9.0 — 2026-04-22

First minor bump since v1.8.0 — adds the L2 layer of the HEAAL
paradigm. AIL is no longer a one-shot CLI calculator; an "AIL
project" is now a folder that an in-project AI agent owns. Two
commands cover the non-developer path: `ail init <name>` and
`ail up`. Everything else falls back to file editing the agent does
or the user does, both updated by the watch loop or by `ail chat`.

No grammar changes; v1.8 spec freeze still in effect.

### Agentic projects (L2 v0)

- **`ail init <name>`** — scaffolds a project folder with an
  `INTENT.md` template (the only file the human edits) and an
  empty `.ail/state/` directory plus an append-only ledger.
- **`ail up [path]`** — reads INTENT.md, authors `app.ail` via the
  existing `ask()` pipeline if empty, runs the test cases declared
  under `## Tests`, then serves over HTTP. POST `/` runs
  `entry main(input)` with the request body; GET `/healthz` returns
  200. Port collision fails loudly. Test extraction handles English
  (`## Tests`) and Korean (`## 테스트`) headers; quoted test inputs
  interpret `\n` `\t` `\r` escapes.
- **`.ail/ledger.jsonl`** — append-only record of every authoring
  attempt, test run, request, watcher event, chat edit, and
  auto-fix attempt. The L3-OS substrate begins here.
- **Three example projects** under
  `reference-impl/examples/agentic/`:
  `word-counter/` (pure fn, headline demo), `csv-stats/` (pure-fn
  pipeline with Result threading), `sentiment/` (fn + intent split,
  needs an authoring backend). Each ships with a pre-authored
  `app.ail` so the example runs without paying for an LLM call.

### Agentic projects (L2 v1)

- **File watcher + auto reload** — `ail up` polls INTENT.md and
  app.ail in a daemon thread. Editor saves picked up in ~1s without
  restarting the HTTP server. The handler reads app.ail fresh on
  every request, so the swap is automatic; the watcher's job is to
  re-run declared tests and warn (not abort) on failure. Opt out
  with `ail up --no-watch`.
- **`ail chat <path> "<request>"`** — natural-language project
  edits. The author backend gets the current INTENT.md + current
  app.ail + the user's request and returns updated whole-file
  replacements for either or both, plus a one-sentence summary.
  The agent saves the change and re-runs the declared tests.
- **`ail up --auto-fix N`** — when declared tests fail, hand the
  failures to the chat backend and retry up to N times before
  aborting. Stops early if the model declines to change anything.
  Default off (LLM cost is opt-in).

### HTTP server polish

- Result-shaped return values are unwrapped for HTTP clients
  (success → inner value, error → message + HTTP 500). Agentic
  programs that want to signal error use the idiomatic AIL pattern
  (`return error(...)`) instead of returning sentinel strings.

### Tests

- 307 tests pass (was 269 before v1.9.0 work began). New: 18
  agentic core, 5 watcher, 7 chat, 7 auto-fix.

### Documentation

- README + `docs/ko/README.ko.md` add a "From a one-shot answer to a
  running service" section walking through `ail init` → edit
  INTENT.md → `ail up` with real command output and curl examples.
- `runtime/01-agentic-projects.md` is the design doc this work
  implements; §6 v1 checklist is now ✅ for all three items
  (file watch, chat, auto-fix).

---

## v1.8.7 — 2026-04-22

Methodology correction + new boundary data. No grammar changes; spec
freeze still in effect. The headline is honesty: a vacuous-truth bug
in the HEAAL Score formula was caught and fixed before any of the
inflated numbers went into a manifesto or a public talk. Some
previously published scores moved (the AIL column unchanged in every
row; the Python column rose by 1–10 points in three rows). The
corrected scoring also lets us publish the mistral7b row, which
identifies the empirical boundary of the grammar-floor claim.

### Tooling correction

- **`reference-impl/tools/heaal_score.py`** — per-program metrics
  (Error Explicitness, Structural Safety, Loop Safety, Observability)
  now use the **parsed** count as their denominator, not **N**.
  Previously, when parse rate was 0, those rates defaulted to 100%
  — a model that authored zero programs scored higher on safety
  than a model that authored a few buggy ones. Vacuous truth.
  Parse Success and Answer Correctness keep N as denominator since
  they measure authoring-success-per-attempt.

  The variable named `exec_success` was actually computed from
  `answer_ok` (correct final answer). Relabeled the displayed metric
  to **"Answer Correctness"** so the displayed name matches what
  the code computes.

  Full audit including before/after table for every published
  score: [`docs/benchmarks/2026-04-22_score_audit.md`](docs/benchmarks/2026-04-22_score_audit.md).

### Documentation corrections

- **README.md, docs/why-ail.md, docs/heaal.md (+ ko/, ai.md mirrors)** —
  the "Python omits error handling 42–86%" claim was based on the
  old methodology. Corrected range under per-parsed denominator:
  **12–70%** depending on author model, with a sharper observation
  that *stronger models often omit more* (they attempt more ambitious
  code with more failable calls and skip wrapping more of them). The
  AIL number stays 0% on every tier where AIL parses — measured
  constant across Anthropic, Alibaba, Meta, and a 7B fine-tune.
- The headline R3 fine-tune row corrected from 87.7 / 48.5 / +39.2
  to 87.7 / 58.0 / +29.7. Still well above Python; the gap shrank
  honestly because Python's per-parsed safety properties are higher
  than the old methodology credited.

### New benchmark data — HEAAL boundary fully anchored

- **Stage D (`llama3.1:8b-instruct`)** — confirms `anti_python` is a
  frontier-only intervention on a third model family (Meta after
  Anthropic Sonnet ✅ and Alibaba Qwen ✅). 45/50 AIL programs
  bit-identical across default and anti_python runs. HEAAL Score:
  AIL 74.3 vs Python 43.7 (+30.6) — the largest gap among parsed
  tiers, demonstrating the grammar floor matters most when the
  author model is weakest *but still produces parseable output*.
  Writeup: [`docs/benchmarks/2026-04-22_heaal_D_llama8b_analysis.md`](docs/benchmarks/2026-04-22_heaal_D_llama8b_analysis.md).
- **Stage D' (`mistral:7b-instruct`)** — identifies the boundary.
  The model authors zero parseable AIL across both runs; instead it
  emits Python wrapper code that imports the AIL interpreter and
  embeds AIL as a string parameter. Under the corrected methodology
  this honestly scores AIL 0.0 vs Python 54.9. The grammar floor
  cannot lift programs that don't exist. The remedy for tiers below
  the parse threshold is the AIL track (fine-tune the base, e.g.
  `ail-coder:7b-v3`). Writeup:
  [`docs/benchmarks/2026-04-22_heaal_D_mistral7b_analysis.md`](docs/benchmarks/2026-04-22_heaal_D_mistral7b_analysis.md).
- **Boundary summary** — [`docs/benchmarks/2026-04-22_heaal_boundary_summary.md`](docs/benchmarks/2026-04-22_heaal_boundary_summary.md)
  combines C+D+D'+E1 into a single cross-tier table with three
  regimes and three remedies (frontier → `anti_python`, mid/small
  with parse → grammar floor, below parse → fine-tune).

### Forward-looking

- **L2 design recorded.** [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md)
  captures the 2026-04-22 design conversation about what an AIL
  "project" should look like once it's no longer a one-shot CLI:
  a folder with a single human-edited `INTENT.md` and an in-project
  AI agent that owns `app.ail`, tests, ledger, and evolve state.
  Two commands: `ail init`, `ail up`. No code yet — spec only,
  pending L1 closure (now done).

---

## v1.8.6 — 2026-04-22

Small additive release. Makes the AI-written AIL program persistable
from `ail ask`, and bundles the Stage C analysis that bounds when the
`anti_python` authoring variant helps.

### CLI

- **`ail ask --save-source PATH`** — writes the AIL source the author
  model produced to a file. The answer still goes to stdout; only
  the program is written. Pass `-` to emit the source to stdout
  after the answer instead of a file. Parent directories are
  created as needed; trailing newline is normalized.

  ```bash
  ail ask "Sum 1 to 100" --save-source sum.ail
  # 5050
  # --- AIL saved to sum.ail ---
  ail run sum.ail --input ""   # replay what the author wrote
  ```

  Six CLI unit tests covering file write, stdout `-`, parent-dir
  creation, newline normalization, and the partial-source path when
  `AuthoringError` is raised.

### Documentation

- **HEAAL Stage C analysis** — `docs/benchmarks/2026-04-22_heaal_C_qwen14b_analysis.md`
  plus two dashboards. Running the base `qwen2.5-coder:14b` with
  default vs `anti_python` prompts yields bit-identical AIL output
  across all 50 programs. The anti_python variant is a
  frontier-model intervention; at mid-tier coder bases it has no
  measurable effect at temperature 0. AIL's grammar-enforced floor
  still keeps the HEAAL Score at 80.9 vs Python 69.6 on this tier
  with zero prompt work.
- **`ail-mvp` install troubleshooting** — README now documents the
  clean-uninstall path for users hitting `ModuleNotFoundError: No
  module named 'ail_mvp'` from a pre-v1.8 stale editable install.
- **`--show-source` visibility** — Quick start has a concrete
  "Seeing the code the AI wrote" subsection with real output.
- **Why-AIL discoverability** — dedicated top-level section plus a
  Further Reading block linking the HEAAL manifesto, benchmarks,
  and dashboards from the README entry points.

### Internal

- CLAUDE.md trimmed from 1469 to 143 lines. Forward-looking only;
  session logs belong in git. Rule 5 reframed: CLAUDE.md is a NOW
  + NEXT snapshot, not a diary.

---

## v1.8.5 — 2026-04-22

Additive release within the v1.8 grammar freeze (spec §2.5 permits
builtin additions; §3 permits additive prompt variants). The headline
is the HEAAL demonstration: a frontier author model (Claude Sonnet)
writes AIL through `ail ask` with grammar-level safety properties
intact, with no fine-tune and no external harness. Three small
language additions and a scoring tool make that demonstration
reproducible.

### Language additions

- **`parse_json(source: Text) -> Result[Any]`** — pure builtin that
  parses JSON text and returns a Result. AIL programs no longer
  need to line-scan HTTP response bodies; `parse_json(resp.body)`
  then `get(data, "language")` is the idiomatic path. Registered in
  the purity allowlist; callable from `pure fn` bodies. Five unit
  tests covering object / array / nested / error / purity. Reference
  card updated under a new "JSON" section.
- **`ail_parse_check(source: Text) -> Result[Text]`** — pure
  self-reflection primitive. Parses a string as AIL and returns
  ok(source) if it parses, error(msg) otherwise. Does NOT execute
  — distinct from `eval_ail`, which runs the inner program. Six
  unit tests, including one that verifies an inner program
  declaring unresolvable intents still validates because only the
  parser runs. Reference card updated under a new "Self-reflection"
  section.
- **`AIL_AUTHOR_PROMPT_VARIANT=anti_python`** — new authoring prompt
  variant available to `ail ask`. Front-loads a "these patterns
  fail parse" block before any positive description, fights the
  author model's Python pretraining prior directly, and cuts
  overall prompt size 43% (4441 → 2526 chars) versus the default.
  On Claude Sonnet with no AIL fine-tune, this variant lifts AIL
  parse from 36% to 94% and AIL answer from 36% to 88% on the
  50-prompt corpus.

### New tool — HEAAL Score dashboard

- **`reference-impl/tools/heaal_score.py`** — standalone scorer that
  reduces a benchmark JSON to a single HEAAL Score plus an HTML
  dashboard. Weighted average of seven metrics:
    error explicitness (25%), execution success (20%),
    no-silent-skip rate (20%), parse success (15%),
    structural safety (10%), loop safety (5%), observability (5%).
  65% of the weight lives on measurements that move per run.
- **`tools/benchmark.py --report[=path.html]` and `--no-run`** —
  the existing benchmark runner now calls into `heaal_score` at
  the end. `--no-run --report=<file.html>` rescores an existing
  result JSON without re-running the benchmark.
- Three canonical dashboards committed under
  `docs/benchmarks/dashboards/`:
    AIL track, fine-tuned 7B:   AIL 87.7 vs Python 48.5
    HEAAL baseline (Sonnet):    AIL 77.6 vs Python 75.3
    HEAAL E1 (anti_python):     AIL 96.1 vs Python 75.9
  *(The Python 48.5 figure was corrected to 58.0 on 2026-04-22 after
  a methodology audit caught a vacuous-truth bug in `heaal_score.py`.
  Full audit + before/after table:
  `docs/benchmarks/2026-04-22_score_audit.md`. The correction will
  ship in v1.8.7.)*

### HEAAL documentation

- **`docs/heaal.md`** — paradigm-level manifesto written by Claude
  Opus 4 after reviewing the 2026 harness-engineering literature.
  Positions HEAAL (Harness Engineering As A Language) as the third
  layer of AI code safety after vibe coding and bolt-on harnesses,
  with the Rust borrow-checker analogy carrying the core claim
  (convention → compiler guarantee). Also in Korean
  (`docs/ko/heaal.ko.md`) and AI-readable (`docs/heaal.ai.md`).
- **`docs/heaal/`** — HEAAL track inside the repo: terminology
  (author model vs intent model), experiments E1–E2, prompt
  variants, benchmark runners.
- **E1 writeup** — `docs/benchmarks/2026-04-22_heaal_E1_analysis.md`.
- **E2 writeup** — `docs/benchmarks/2026-04-22_heaal_E2_analysis.md`,
  including the concrete E2-10 case where a Python program crashed
  on an unhandled `urllib.error.HTTPError 403` while the AIL program
  ran cleanly on the same URL because `perform http.get` returns a
  `Result` the grammar will not let the author skip.
- **`benchmarks/heaal_e2/`** — long-task corpus, fixture setup
  script, and runner with AIL + Python side-by-side scoring.

### AIL-track experiments (R4–R6)

- **R4 (v4 fine-tune)** — Cat A +20pp but Cat B −27pp vs R3.
  Archived; v3 remains the serving model.
- **R5 (v5 single-line format)** — severe regression (Cat C 20%)
  caused by a "leading-quote artifact" when the coder base model
  treats single-line AIL as a Python string literal. Hypothesis
  rejected for coder bases.
- **R6 (v6 same single-line format, non-coder base)** — recovers
  to 80% parse / 62% answer with zero leading-quote artifacts,
  confirming the R5 failure was coder pretraining prior, not the
  single-line format itself.

### Other

- **SECURITY.md** added at repo root (private reporting channel
  for vulnerabilities, scope definition, by-design primitives
  explained).
- **Governance Rules 5 and 6** in `CLAUDE.md`: SESSION STATE must
  be updated on every commit; Claude Code sessions have PyPI
  publish authority via `~/.pypirc`.
- **Open questions Q16 and Q17** added to `docs/open-questions.md`:
  are comments useful in an AI-authored language; should AIL grow
  a human-readable display mode.

---

## v1.8.4 — 2026-04-21

Additive parser sugar within the v1.8 grammar freeze (spec §3 was
amended to permit additive desugarings; same precedent class as
the v1.8.3 `List[T]` parser fix). Targeted at the last gap between
`ail-coder:7b-v3` and the G1 ≥ 80% AIL-parse gate.

### Language (both runtimes)

- **Subscript sugar:** `EXPR[INDEX]` is now accepted as syntactic
  sugar for `get(EXPR, INDEX)`. Parser-only desugar — the runtime
  path is the existing `get` builtin, semantics are unchanged.
  Closes [issue #1](https://github.com/hyun06000/AIL/issues/1) and
  the three remaining v3 fine-tune parse failures (A04, A12, C18 —
  all `list[i]` Python-style subscript leaks). Python parser uses a
  bracket-balanced lookahead to disambiguate from `branch [COND] =>`
  arm headers; the Go parser doesn't implement `branch` so no guard
  is needed there.
- New conformance case `018_subscript_sugar.ail` exercises bare-
  ident subscript, literal-list subscript, double subscript, and
  subscript inside a `pure fn` body. Byte-identical on both
  runtimes.

### Spec

- `spec/08-reference-card.ai.md` §EXPRESSIONS lists the new sugar
  alongside `EXPR.field`.
- `spec/09-stability.md` §3 now records "additive parser
  desugarings" as an explicit class of permitted patch-release
  changes within the freeze, with the v1.8.3 and v1.8.4 precedents
  enumerated.

### Tests

- Python: 288 passing (was 284), 2 skipped — same as before plus
  the 4 new branch-syntax regression guards.
- Conformance: 52 passing (was 49), 0 added skip — case 018's
  three test shapes all pass on both runtimes.
- Go: ok.

---

## v1.8.3 — 2026-04-21

Additive release within the v1.8 grammar freeze (spec §2.5 permits
builtin additions; parser fixes bring runtime in line with the
already-frozen spec surface). Closes the two dominant AIL-parse
failure classes surfaced by the ail-coder:7b-v2 benchmark.

### Language (both runtimes)

- **Math builtins added as trusted-pure:** `round`, `floor`, `ceil`,
  `sqrt`, `pow`. Usable directly inside `pure fn` bodies without
  imports. Closes PurityError on benchmark tasks C07 (BMI) and C12
  (standard deviation). Python and Go implementations are byte-
  equivalent (banker's rounding via `math.RoundToEven`;
  Result-error on `sqrt` of a negative).
- **Parametric types parse cleanly.** Spec §2.3 always listed
  `List[T]`, `Map[K,V]`, `Result[T]`, `Tuple[A,B]` as valid; the
  parsers were silently discarding the bracket clause. They now
  consume and ignore it (AIL stays dynamically typed, the bracket
  content is annotation-only). Closes ~3 AIL parse failures per
  benchmark run. Python and Go parser changes are parallel.

### Training

- **Dataset expansion v2 → v3:** 205 → 244 validated samples.
  +41 new entries cover: 7 math-builtin programs, 12 parametric-
  type fn signatures, 14 hybrid (fn + intent) shapes modelled on
  the benchmark C-category, 3 additional pure-intent examples,
  5 pure-fn variations.
- **`to_chatml.py` system prompt updated** to document the
  parametric types and math builtins so the fine-tune sees the
  same surface both during training and at inference.

### Benchmark results (ail-coder:7b v3 on the Opus 50-prompt corpus)

- AIL parse: 64% (v2) → **78%** (+14 pp; v3 misses G1 by one case)
- AIL answer: 56% → **70%**
- Category C (hybrid) parse: 45% → **70%** (+25 pp — headline)
- Error handling miss: **AIL 0% / Python 44%** — structural gap
  stable across every model tier tested (llama8b 86%, qwen14b 42%,
  Sonnet 4.6 70%).
- G3 verdict: **PASS** — AIL answer rate exceeds Python answer rate
  by 22 percentage points on the same fine-tuned model.

### Documentation

- New practical FAQ covering token economics and the adoption
  decision checklist: [`docs/why-ail-faq.md`](docs/why-ail-faq.md)
  (+Korean).
- New mechanics explainer with the mechanism behind each benchmark
  number, including reproduction one-liners:
  [`docs/why-ail-mechanics.md`](docs/why-ail-mechanics.md)
  (+Korean).
- Benchmark index [`docs/benchmarks/README.md`](docs/benchmarks/README.md)
  extended with the v3 run row.

251 tests pass (+27 since 1.8.2: math builtin unit tests, 2 new
conformance cases for math and parametric types).

---

## v1.8.2 — 2026-04-20

Real-world-prompt hardening. Each change fixes a failure mode
surfaced by live `ail ask` calls after 1.8.1 shipped.

- **Ollama HTTP timeout 120s → 300s**, with new env override
  `AIL_OLLAMA_TIMEOUT_S`. Larger models (gemma2:27b etc.) couldn't
  finish one author call with the full reference card in context
  within the old limit, so every retry was silently hitting
  socket.timeout.
- **Trailing markdown fence tolerance.** gemma2:9B emits valid AIL,
  then closes it with a standalone ``` line and appends an
  "Explanation:" prose block. The lexer used to choke on the stray
  backtick at the closing line. A new `_truncate_at_trailing_fence`
  step cuts source at the first lone ``` that has real AIL content
  above it.
- **Retry hints for prose-only responses.** llama3.1:8B sometimes
  abandons code entirely and writes a natural-language
  explanation. The lexer error (`unexpected character '!'` or
  top-level IDENT like `What` / `Let`) now triggers a targeted
  constraint telling the author to emit only AIL, no prose.

224 tests pass.

---

## v1.8.1 — 2026-04-20

**First PyPI release under the new name `ail-interpreter`.**

Distribution name on PyPI: `ail-interpreter` (was `ailang`, rejected
by PyPI's similarity check against `ai-lang`). Import name and CLI
both remain `ail`.

**Packaging fixes**
- `pyproject.toml` no longer packages a stray `ail_mvp/` directory
  (left over on contributor disks from the v1.8 rename).
- The language reference card is now bundled inside the wheel at
  `ail/reference_card.md`. Previously `ail ask` on pip installs
  silently fell back to a ~400-char stub instead of the real 22k
  spec, degrading author prompt quality.
- `tests/test_spec_bundled.py` guards against the bundled copy and
  `spec/08-reference-card.ai.md` drifting.

**Lexer**
- `#` is now accepted as an alias for `//` line comments in both
  the Python and Go runtimes. AI authors trained heavily on Python
  reach for it reflexively; the cost of rejecting was a lost-
  confidence moment per prompt. Spec keeps `//` canonical.

**`ail ask` — first real-world prompt (`factorial of 7`) on llama3.1:8B**
- Author prompt names the three real stdlib modules (core, language,
  utils) so the model stops inventing `stdlib/math`.
- `_remediation_hints` surface targeted corrections for five common
  failure classes (bad imports, ternary `?:`, generic type
  annotations like `[Number]`, literal `\n` escape leaks, top-level
  JSON-wrapper leaks) — each carried into the retry prompt as a
  constraint.
- Few-shot example #1 (trivial `return 42`) replaced with a factorial
  recursion example — small models anchor strongly to the first
  example, and the old one taught nothing.
- `ask()` auto-extracts a bare integer from the prompt as
  `input_text` when the caller didn't pin one. Covers programs like
  `factorial(to_number(x))` that would otherwise blow up recursion on
  empty input.
- Tolerance: when the model wraps its answer in a single backtick and
  echoes the prompt's examples section verbatim (observed on
  llama3.1:8B), `_recover_echoed_program` recovers the full AIL
  program from the echo rather than extracting just the bare
  expression.

**Benchmark**
- `tools/bench_authoring.py` rewritten to measure three axes — parse
  rate, fn/intent routing accuracy, final-answer correctness — across
  a 50-case corpus tagged `pure_fn` / `pure_intent` / `hybrid`.
  Baseline on llama3.1:8B: 54% parse, 52% routing, 30% final-answer.
  Hybrid routing jumped from 0/15 on the old prompt to 10/15 after
  the decision rules landed.

**Tolerance (unrelated to ask)**
- Malformed JSON wrapper recovery — when the model returns
  `{"value": "...", "confidence": 1.0}` with unescaped inner quotes,
  a regex-based lenient extractor pulls out the AIL source instead
  of falling through to the parser.
- Literal-`\n`-escape unescape — source with backslash-n and no real
  newlines gets decoded.

**Tests:** 223 passing (was 211 in v1.8.0).

---

## v1.5 — 2026-04-17

**Implicit parallelism.** Independent intent calls run concurrently.

- Consecutive Assignments whose RHS contain intent calls and are
  pairwise independent are grouped into parallel batches and evaluated
  via a ThreadPoolExecutor. No async/await — the independence is
  structural.
- Wall-clock latency for N independent intents drops from N·t to t.
- Dependent sequences (`b = f(a)`) stay sequential; the planner
  detects data flow.
- Trace entries from a batch carry `parallel=True`; batches are
  bracketed by `parallel_batch_start`/`_end` markers.
- Thread-safety: `Trace.record/enter/exit` are now lock-protected.

**Files:** `runtime/parallel.py` (new), `runtime/executor.py`,
`runtime/trace.py`, `examples/parallel_analysis.ail` (new).

**Tests:** 13 new (155 total).

---

## v1.4 — 2026-04-17

**`attempt` blocks — confidence-priority cascade.**

```ail
extracted = attempt {
    try direct_parse(x)     // pure, wins if ok
    try scan_tokens(x)      // pure, cheap fallback
    try infer_number(x)     // LLM — last resort
}
```

- Evaluates each `try` in order. A try qualifies when the result is
  not a Result-typed `error(...)` and its confidence ≥ 0.7.
- First qualifying try wins; if none qualify, the last try's value is
  returned with its low confidence preserved.
- Selected index is recorded via a new `attempt` origin kind; upstream
  lineage is preserved through the origin's parent chain.
- `pure fn` bodies may contain `attempt` blocks, but every `try` must
  itself be pure; intents inside a pure-fn attempt are rejected at
  parse time.

**Files:** `parser/ast.py` (`AttemptExpr`), `parser/parser.py`,
`parser/lexer.py`, `parser/purity.py`, `runtime/executor.py`,
`runtime/provenance.py` (`ATTEMPT` kind, `attempt_origin()`),
`examples/cascade_extract.ail` (new).

**Tests:** 11 new (142 total).

---

## v1.3 — 2026-04-17

**Structural purity contracts — `pure fn`.**

- `pure fn` declares a statically-verified contract: no `perform`
  statements, no intent calls, no calls to non-pure fns, no
  `eval_ail`. Violations raise `PurityError` at parse time.
- Composed with provenance (v1.2): a pure fn's output is compile-time
  guaranteed to have `has_intent_origin(result) == false`.
- All 11 `stdlib/utils.ail` utilities upgraded to `pure fn`.
- Unqualified `fn` retains unchanged semantics (backward compatible).

**Files:** `parser/purity.py` (new), `parser/ast.py` (`purity` field),
`parser/parser.py`, `parser/lexer.py`, `parser/__init__.py`,
`stdlib/utils.ail`.

**Tests:** 15 new (131 total).

---

## v1.2 — 2026-04-17

**Provenance — every value knows where it came from.**

- Each `ConfidentValue` now carries an `Origin` recording the
  operation that produced it, linked to the origins of its inputs.
- Origins are created at fn/intent/builtin/entry boundaries;
  binary/unary/field operations inherit the dominant parent origin to
  keep trees bounded.
- Intent origins additionally carry `model_id` and an ISO-8601
  timestamp for audit.
- New builtins: `origin_of(value)`, `lineage_of(value)`,
  `has_intent_origin(value)`. These cannot be shadowed by user fns
  or intents.

**Files:** `runtime/provenance.py` (new), `runtime/executor.py`,
`examples/audit_provenance.ail` (new), `spec/08-reference-card.ai.md`.

**Tests:** 18 new (116 total).

---

## v1.1 — 2026-04-17

**Result type for explicit error handling.**

- New builtins: `ok(value)`, `error(msg)`, `is_ok(r)`, `is_error(r)`,
  `unwrap(r)`, `unwrap_or(r, d)`, `unwrap_error(r)`.
- `to_number` now returns a Result on non-numeric input.
- `examples/safe_csv_parser.ail` demonstrates Result-based pipelines.

---

## v1.0.0 — 2026-04-17

**The first stable release.** AIL is a programming language designed for AI as the primary author of code. This release contains a complete language specification, a working Python interpreter, a standard library written in AIL, and evidence that the language works as intended.

### What ships

**Language specification** (8 documents)
- spec/00: Overview and design philosophy
- spec/01: Core syntax — intent, context, branch, entry, import
- spec/02: Context system — typed situational assumptions with inheritance
- spec/03: Confidence model — every value carries a belief measure in [0, 1]
- spec/04: Evolution — self-modification with metric, bounds, rollback, human review
- spec/05: Effects — declared side effects with authorization and observability
- spec/06: Standard library specification
- spec/07: Deterministic computation — fn, if/else, for, types, built-in functions

**Working interpreter** (Python, 88 tests)
- Lexer and recursive-descent parser for the full v1.0 grammar
- Executor with intent dispatch (LLM), fn execution (deterministic), and hybrid programs
- Context resolution with inheritance, override tracking, and scope stacking
- Confidence propagation per spec/03 §3
- Evolution supervisor: retune + rewrite constraints, version chain, bounded_by, rollback, human review
- Import resolver for stdlib modules
- eval_ail: parse and execute AIL source at runtime (self-generation)
- Anthropic adapter with robust JSON parsing (code fences, nested objects, confidence clamping)
- Mock adapter for offline development and testing
- .env file loader for API key management
- CLI: `ail run`, `ail parse`, `ail version`

**Standard library** (written in AIL, not Python)
- stdlib/core: identity, refuse
- stdlib/language: summarize, translate, classify, extract, rewrite, critique
- stdlib/utils: word_count, char_count, is_empty, repeat, pad_left, clamp, sum_list, average, flatten, unique, take

**21 built-in functions**
- Text: length, split, join, trim, upper, lower, starts_with, ends_with, replace, slice
- List: length, get, append, sort, reverse, range, map, filter, reduce
- Conversion: to_number, to_text, to_boolean
- Math: abs, max, min

**9 example programs**
- hello.ail — simplest case
- translate.ail — context inheritance with override
- classify.ail — branch dispatch on classifier output
- ask_human.ail — low-confidence fallback to human
- evolve_retune.ail — evolution with version chain
- summarize_and_classify.ail — stdlib imports
- fizzbuzz.ail — pure fn, no LLM, proof that AIL is a real language
- review_analyzer.ail — hybrid pipeline (fn 23 calls + intent 6 calls)
- meta_codegen.ail — AIL generates and executes AIL

**Documentation**
- Human-readable: README.md, CONTRIBUTING.md, ROADMAP.md
- AI-readable: README.ai.md, spec/08-reference-card.ai.md
- Korean: docs/ko/README.ko.md, evolve-guide.ko.md, stdlib-guide.ko.md
- Naming convention: .md (human), .ai.md (AI/LLM), .ko.md (Korean)

**CI/CD**
- GitHub Actions: tests on Python 3.10/3.11/3.12, smoke tests, evolve demo
- Optional live-test job against real Claude API

**Design documents** (vision, not implemented)
- runtime/00-airt.md — AI Runtime design
- os/00-noos.md — Neural-Oriented OS design
- os/01-compatibility.md, 02-security.md, 03-governance.md

### What was proven

1. An AI (Claude) read spec/08-reference-card.ai.md and generated valid AIL programs that executed correctly — for vowel counting, name sorting, and score analysis.

2. During code generation, a missing language primitive (list index access) was discovered. The `get()` builtin was added. This is the feedback loop the project was designed to enable.

3. FizzBuzz runs in AIL without any LLM involvement. AIL is a real programming language, not just an LLM orchestrator.

4. The review_analyzer example demonstrates the hybrid model working in practice: 23 fn calls (free, fast, deterministic) + 6 intent calls (LLM, for judgment only).

5. meta_codegen.ail demonstrates self-generation: an AIL program that produces another AIL program and executes it via eval_ail.

### Known limitations

- No `while` loop (by design — spec/07 §3.3)
- No lambda expressions (use named fn + pass name as string)
- No static type checking (runtime only)
- No pattern matching
- Evolution state does not persist across interpreter sessions
- `import` brings the entire module, not individual symbols
- AIRT and NOOS are design documents, not implementations
