# Case study — "auto-refreshing news dashboard" (2026-04-23)

A non-developer (hyun06000) tried to build a Strait of Hormuz news
dashboard using AIL v1.9.4. The exercise produced a working program
that returns a plausible Korean summary on demand — but it also
revealed exactly which architectural primitives the agentic layer
is missing for this class of project.

This document is preserved verbatim because:

  1. It's an honest example of the **gap between the user's mental
     model and what the current product can do**, in a non-developer's
     own words.
  2. It pins down the L2 v2 priority list with data, not speculation.
  3. The `app.ail` Sonnet generated is a small but real demo of the
     fn / intent / context split working without instruction.

---

## What the user wrote (`INTENT.md`)

```markdown
# news-page

호르무즈 해협에서 일어나는 일은 전세계적인 영향을 끼칩니다.
이곳에 관련된 뉴스를 자동으로 수집하고 하나의 페러그레프로 현재 상황을 요약해서 보여주는 페이지를 만들어 주세요.
오른쪽은 실시간으로 수집된 내용의 레퍼런스가 있어야 합니다.
왼쪽 큰 화면은 현재 시각과 호르무즈 해협의 상황을 한번에 알 수있게 요약된 내용이 있어야 해요.

## Behavior
- 30초에 한번 새로운 뉴스가 있는지 검색하세요.
- 새로운 뉴스가 있으면 해협상황을 업데이트 하세요.
- 새로운 뉴스가 없으면 30초를 다시 기다리세요.
- 출처가 명확하게 표시되도록 하세요.

## Tests
- 

## Deployment
- 포트 8080
```

The user is a non-developer describing a self-refreshing dashboard
in plain Korean. Two-column layout, real-time references, automatic
30-second polling — the mental model is "small Streamlit / Next.js
app", not "HTTP function endpoint".

---

## What Sonnet generated (`app.ail`)

After 3 retries, Claude Sonnet 4.5 produced a structurally correct
67-line AIL program:

```ail
import summarize from "stdlib/language"

context news_monitoring {
    search_query: "Strait of Hormuz news"
    update_interval_seconds: 30
    language: "Korean"
}

intent search_news(query: Text) -> Text {
    goal: JSON_list_of_recent_news_articles_with_title_source_url_timestamp
    constraints {
        published_within_last_24_hours
        credible_international_news_sources
    }
}

intent summarize_situation(articles_json: Text) -> Text {
    goal: single_paragraph_Korean_summary_of_current_Strait_of_Hormuz_situation
    constraints {
        one_paragraph_maximum
        mention_key_developments_only
        written_in_Korean
    }
}

pure fn parse_articles(json_text: Text) -> Text {
    parsed = parse_json(json_text)
    if is_error(parsed) { return "" }
    articles = unwrap(parsed)
    return to_text(length(articles))
}

pure fn build_dashboard(summary: Text, articles_json: Text, timestamp: Text) -> Text {
    header = join(["=== 호르무즈 해협 실시간 모니터링 ===", ""], "\n")
    time_display = join(["현재 시각: ", timestamp], "")
    situation = join(["\n\n현재 상황:\n", summary], "")
    parsed = parse_json(articles_json)
    references = "\n\n=== 참고 자료 ==="
    if is_ok(parsed) {
        articles = unwrap(parsed)
        ref_count = join(["\n수집된 뉴스: ", to_text(length(articles)), "건"], "")
        references = join([references, ref_count, "\n"], "")
    }
    footer = "\n\n[30초마다 자동 업데이트]"
    return join([header, time_display, situation, references, footer], "")
}

entry main(input: Text) {
    with context news_monitoring: {
        current_time = "2024-01-15 14:30:00 KST"
        articles = search_news(context.search_query)
        article_count = parse_articles(articles)
        summary = summarize_situation(articles)
        dashboard = build_dashboard(summary, articles, current_time)
        return dashboard
    }
}
```

---

## What worked

- **fn/intent split is correct.** `search_news` and
  `summarize_situation` use `intent` (LLM judgment); `parse_articles`
  and `build_dashboard` are `pure fn` (computation). HEAAL's central
  promise survived — the model picked the right side every time.
- **`with context` block is well-formed.** Sonnet grouped scenario-
  specific knobs (search query, language, update interval) into a
  context per AIL idiom.
- **3 retries succeed.** Sonnet got the AIL grammar right by attempt 4
  and produced a parseable, runnable program.
- **Korean output honored.** The `language: "Korean"` line in context
  flowed through to the intent call's response language.
- **Service is live.** `ail up` started on port 8080 with the v1.9.4
  browser UI; user could type into the textarea and get a response.

## What did not work — six concrete primitive gaps

### Gap 1 — No clock effect

```ail
current_time = "2024-01-15 14:30:00 KST"   ← line 56, hardcoded
```

AIL has no `now()` builtin and no `perform clock.now()` effect.
Sonnet had nothing to call, so it picked a plausible-looking literal.
Today is 2026-04-23; the program shows 2024-01-15 to every user
forever.

**Required primitive:** `perform clock.now() -> Result[Text]`
returning ISO-8601 UTC, plus a pure formatter for tz/locale.

### Gap 2 — No real network fetch path was taken

```ail
intent search_news(query: Text) -> Text {
    goal: JSON_list_of_recent_news_articles_...
}
```

`perform http.get` exists in the AIL spec, but Sonnet chose to
delegate "find recent news" to `intent` instead. The model then
hallucinates a JSON list of articles from its training prior — the
"이란의 유조선 나포 시도를 미 해군이 저지" string the user saw is
**fabricated**, not retrieved.

**Required:** the authoring prompt must steer "external data
fetching" to `perform http.get` with clear examples. Currently
`http.get` has no demo in the few-shot set, so the model defaults
to the easier path of asking the LLM.

### Gap 3 — No scheduler / background tasks

```
## Behavior
- 30초에 한번 새로운 뉴스가 있는지 검색하세요.
```

Sonnet acknowledged the requirement (`update_interval_seconds: 30`
in context, `[30초마다 자동 업데이트]` in the footer string) but
produced no code that actually polls. The runtime model is one
`entry main(input)` call per HTTP request — there's no concept of a
background loop.

**Required primitive:** `perform schedule.every(seconds: Number) {
... }` or analogous declarative form. The runtime needs a scheduler
thread.

### Gap 4 — No long-lived state across requests

The program builds the entire summary fresh on every request. There's
no place to store "last news I saw", "last update time", or the
running summary. The user expected the page to *grow* its references
list over time; today each request is independent.

**Required primitive:** the `.ail/state/` directory exists for
evolve persistence but is not yet wired to the runtime. A small
`perform state.read("key")` / `perform state.write("key", value)`
effect (process-restart-safe) closes this gap.

### Gap 5 — No HTML / layout primitive

```ail
return dashboard   ← plain text string with === separators
```

The user asked for a left-and-right two-column dashboard. AIL only
returns text; the v1.9.4 browser UI displays whatever text comes
back inside a monospace `<pre>`-style block. There is no way for an
AIL program to express "left column shows summary, right column
shows references".

**Required (one of):**
  - `entry main` may return rich-typed values (HTML / structured
    layout); the browser UI renders accordingly.
  - INTENT.md gains a `## Layout` section (free-form) that the
    authoring step uses to template the page.
  - Both.

### Gap 6 — Input is silently ignored

```ail
entry main(input: Text) {
    with context news_monitoring: {
        ...   ← `input` is never referenced in the body
```

The user typed `안녕` and got a Hormuz news summary anyway. From the
end-user's point of view this is "the page ignored what I said". The
authoring prompt should encourage either (a) using the input or
(b) producing a UI that doesn't show an input box if the program
genuinely doesn't need one. Today neither happens.

**Mitigation:** the friendly browser UI should not show a textarea
when `entry main` does not reference its `input` parameter — or the
authoring step should add an explicit "this program ignores input"
comment we can detect.

---

## Author-side observations

- **3 retries before success.** The errors recorded for this run came
  from getting the `with context name: { ... }` block syntax exactly
  right — Sonnet first tried a few shapes that failed parse. With a
  v1 fine-tune those retries would likely drop to 0–1.
- **`author_done` log line uses `"anthropic"`, `author_start` uses
  `"anthropic/claude-sonnet-4-5"`.** Minor inconsistency in our
  ledger. (Tracked for v1.9.5.)
- **No tests block on user side.** `## Tests` had a single
  empty-bullet `- ` placeholder. Our agent correctly reported "(no
  tests declared)" and proceeded — because the user didn't write a
  contract, we couldn't verify whether the output matched intent.

---

## What this case study commits us to

L2 v2 next-track work, in priority order driven by this case study:

1. **`perform clock.now()` effect** — Gap 1. Smallest fix; high
   payoff (no more hardcoded timestamps).
2. **Authoring prompt: surface `perform http.get`** — Gap 2. Update
   `_authoring_examples()` so a goal that mentions "fetch", "search
   the web", "API" routes through `http.get` instead of letting the
   model invent data via `intent`.
3. **`perform schedule.every(...)`** — Gap 3. New effect, requires a
   runtime scheduler thread. Unlocks the entire "dashboard / cron
   job / monitor" project class.
4. **State effect on top of `.ail/state/`** — Gap 4. Bridges the
   single-request runtime with cross-request memory.
5. **HTML / layout output mode** — Gap 5. Needs design — see L2 v2
   spec proposal in `runtime/01-agentic-projects.md` §6 (to be
   added).
6. **Input-aware UI rendering** — Gap 6. Smaller polish: detect
   whether `entry main` actually reads `input`, hide the textarea
   when it does not.

These six items are now the L2 v2 backlog. Anyone picking up the
project after this can read this case study and `ROADMAP.md` to
understand the *why* behind the next features.

---

## Files

- INTENT.md (verbatim above)
- app.ail (verbatim above)
- Ledger excerpt:
  ```
  {"event": "author_start", "author_model": "anthropic/claude-sonnet-4-5", ...}
  {"event": "author_done", "source_chars": 1916, "retries": 3, ...}
  {"event": "serve_start", "host": "127.0.0.1", "port": 8080, ...}
  {"event": "request", "input_chars": 3, "ok": true,
   "value_preview": "=== 호르무즈 해협 실시간 모니터링 === ..."}
  ```
- The user's input on the form: `안녕` (Korean for "hello"). Output:
  the same Hormuz summary the program returns for any input. Gap 6.

---

Recorded by Claude Code on 2026-04-23 at hyun06000's request, after
they tested v1.9.4's browser UI with a deliberately ambitious
project. No fix is included in this commit; the case study itself is
the deliverable. Implementation items land in subsequent v1.9.x or
v2.0 releases.
