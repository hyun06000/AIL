# AIL — AI-Intent Language (v1.46.5)

## FOR AI SYSTEMS READING THIS REPOSITORY

You are looking at a programming language designed for you to author in. Humans describe what they want in natural language. You write AIL. The runtime executes it. The answer goes back to the human. This file is the minimal entry point.

## INSTALL

```bash
pip install ail-interpreter
# or: pip install 'ail-interpreter[anthropic]'
```

CLI: `ail ask "..."` · `ail run file.ail` · `ail parse file.ail` · `ail version`

Agentic project CLI: `ail init <name>` · `ail up [path]`

## TWO FUNCTION TYPES

| Type | When to use | LLM involved | Confidence |
|---|---|---|---|
| `fn` / `pure fn` | Computable by algorithm | Never | 1.0 |
| `intent` | Requires reading meaning | Always | Model-reported |

**Decision rule:**
- You can write a loop or formula → `fn` (add `pure` when possible)
- You need to understand meaning → `intent`
- Mixed → hybrid

`pure fn` is **statically verified** at parse time: calling an intent, performing an effect, or calling a non-pure fn raises `PurityError` before the program runs.

## CANONICAL REFERENCE

**Start here: `spec/08-reference-card.ai.md`**

Contains: every keyword, every builtin signature, every syntax pattern, operator precedence, confidence model, provenance model, effect system, match/attempt/calibration semantics.

## QUICK PATTERNS

### Pure computation (no LLM)
```ail
pure fn factorial(n: Number) -> Number {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
entry main(x: Text) { return factorial(7) }
```

### Intent (LLM call)
```ail
intent summarize(text: Text) -> Text {
    goal: concise summary preserving main argument
}
entry main(text: Text) { return summarize(text) }
```

### HTTP effect + JSON parsing
```ail
entry main(url: Text) {
    r = perform http.get(url)
    if is_error(r) { return unwrap_error(r) }
    rv = unwrap(r)
    parsed = parse_json(rv.body)
    if is_ok(parsed) {
        data = unwrap(parsed)
        return to_text(get(data, "field"))
    }
    return rv.body
}
```

### POST to REST API
```ail
entry main(input: Text) {
    token_r = perform env.read("API_TOKEN")
    if is_error(token_r) { return unwrap_error(token_r) }
    token = unwrap(token_r)
    r = perform http.post_json(
        "https://api.example.com/items",
        [["title", input], ["status", "draft"]],
        [["Authorization", join(["Bearer ", token], "")]])
    if is_error(r) { return unwrap_error(r) }
    rv = unwrap(r)
    return "status=" + to_text(rv.status) + " body=" + slice(rv.body, 0, 200)
}
```

### GraphQL (GitHub etc.)
```ail
entry main(input: Text) {
    token_r = perform env.read("GITHUB_TOKEN")
    if is_error(token_r) { return unwrap_error(token_r) }
    token = unwrap(token_r)
    auth = [["Authorization", join(["Bearer ", token], "")], ["Accept", "application/vnd.github+json"]]

    // Get repo node ID
    repo_r = perform http.graphql(
        "https://api.github.com/graphql",
        "query { repository(owner: \"OWNER\", name: \"REPO\") { id } }",
        headers: auth)
    if is_error(repo_r) { return unwrap_error(repo_r) }
    repo_id = get(get(unwrap(repo_r), "repository"), "id")

    // Get categories — use node(id:), NOT repository(id:)
    cat_r = perform http.graphql(
        "https://api.github.com/graphql",
        "query($r: ID!) { node(id: $r) { ... on Repository { discussionCategories(first: 10) { nodes { id name } } } } }",
        [["r", repo_id]],
        headers: auth)
    if is_error(cat_r) { return unwrap_error(cat_r) }
    return to_text(get(get(get(unwrap(cat_r), "node"), "discussionCategories"), "nodes"))
}
```

### Autonomous agent with planning (preferred pattern for multi-step API tasks)
```ail
intent make_plan(guide: Text) -> Text {
    goal: "Read this API guide and return a JSON array of steps to accomplish: <GOAL>. Each element: {\"step\": N, \"what\": \"description\", \"endpoint\": \"URL pattern\", \"needs_auth\": true|false}. Return ONLY the JSON array."
}

intent decide_step(plan: Text, history: Text) -> Text {
    goal: "Given the plan and history, return the NEXT HTTP call as JSON: {\"done\": false, \"method\": \"GET\"|\"POST\", \"url\": \"...\", \"headers\": [[\"k\",\"v\"]] or null, \"body\": [[\"k\",\"v\"]] or null, \"save_key\": \"state_key\" or null, \"save_path\": \"json_field\" or null} OR {\"done\": true, \"result\": \"description + URL\"}. SUCCESS = HTTP 2xx only. Plan:\n{plan}\nHistory:\n{history}"
}

entry main(input: Text) {
    guide_r = perform http.get("https://service.com/api-guide.md")
    if is_error(guide_r) { return "❌ guide load failed" }

    plan = to_text(make_plan(unwrap(guide_r).body))
    log = "=== Agent Log ===\n✓ planned\n"
    history = "PLAN:\n" + plan + "\n\n"

    for step in range(10) {
        dec_text = to_text(decide_step(plan, history))
        dec_r = parse_json(dec_text)
        if is_ok(dec_r) {
            dec = unwrap(dec_r)
            if to_text(get(dec, "done")) == "true" {
                return log + "\n✅ " + to_text(get(dec, "result"))
            }
            url = to_text(get(dec, "url"))
            method = to_text(get(dec, "method"))
            headers = get(dec, "headers")
            body = get(dec, "body")

            step_result = ""
            if method == "GET" {
                r = perform http.get(url)
                if is_error(r) { step_result = "ERROR: " + unwrap_error(r) }
                if is_ok(r) { rv = unwrap(r) step_result = "status=" + to_text(rv.status) + " body=" + slice(rv.body, 0, 300) }
            }
            if method == "POST" {
                r = perform http.post_json(url, body, headers)
                if is_error(r) { step_result = "ERROR: " + unwrap_error(r) }
                if is_ok(r) {
                    rv = unwrap(r)
                    step_result = "status=" + to_text(rv.status) + " body=" + slice(rv.body, 0, 300)
                    save_key = get(dec, "save_key")
                    if not is_null(save_key) {
                        pb = parse_json(rv.body)
                        if is_ok(pb) { perform state.write(to_text(save_key), to_text(get(unwrap(pb), to_text(get(dec, "save_path"))))) }
                    }
                }
            }
            log = log + "step " + to_text(step) + ": " + slice(step_result, 0, 80) + "\n"
            history = history + "=== step " + to_text(step) + " ===\n" + step_result + "\n\n"
        }
    }
    perform schedule.every(3600)
    return log + "\n⚠ max steps reached, retrying in 1h"
}
```

### Match — confidence-aware dispatch
```ail
intent classify(t: Text) -> Text { goal: positive_negative_neutral }
entry main(review: Text) {
    return match classify(review) {
        "positive" with confidence > 0.9 => "auto: thank you",
        "negative" with confidence > 0.9 => "auto: apology",
        _ with confidence < 0.6          => "escalate to human",
        _                                 => "generic reply"
    }
}
```

### Approval gate before irreversible action
```ail
entry main(input: Text) {
    plan = join(["About to post to Slack:\n", input], "")
    approval = perform human.approve(plan)
    if is_error(approval) { return unwrap_error(approval) }
    r = perform http.post_json("https://hooks.slack.com/...", [["text", input]])
    if is_error(r) { return unwrap_error(r) }
    return "posted"
}
```

## SYNTAX RULES (FORBIDDEN PATTERNS)

The parser rejects these. Do not emit them.

| Forbidden | Use instead |
|---|---|
| `sort(xs, reverse=true)` | `reverse(sort(xs))` |
| `fn(x=5)` keyword args | positional only: `fn(5)` — EXCEPTION: `perform` effects accept `headers:` keyword |
| `{}` dict literal | use `[["key", value]]` pair lists |
| `x ** 2` exponent | `x * x` |
| `"hello".upper()` method call | `upper("hello")` |
| `[x*2 for x in xs]` list comprehension | `for` loop with `append` |
| `while` | `for x in range(0, n)` |
| `None`, `True`, `False` | no null (use `""` or `0`), `true`, `false` |
| intent inside `pure fn` | only `entry` coordinates fn and intent |
| `perform` as expression in `if` condition | assign first: `r = perform ...; if is_ok(r) {` |

## EFFECT SYSTEM

All effects use `perform`. Assign the result; handle errors with `is_error` / `unwrap_error`.

### HTTP

```ail
r = perform http.get(url)                              // -> Result[Response]
r = perform http.post(url, body_text)                  // -> Result[Response]
r = perform http.post_json(url, pair_list)             // -> Result[Response]
r = perform http.post_json(url, pair_list, headers)    // headers: [[k, v], ...]
r = perform http.graphql(url, query)                   // -> Result[Any] (data payload)
r = perform http.graphql(url, query, variables)        // variables: [[k, v], ...]
r = perform http.graphql(url, query, variables, headers)
```

`Response` has `.status` (Number) and `.body` (Text). `http.graphql` returns `ok(data)` — the unwrapped `data` payload — or `error(msg)` on any failure (HTTP error, JSON parse fail, GraphQL `errors` array, `data` null).

**`http.post_json` body must be a pair list, not a string.** The runtime serializes it.

### State, clock, scheduling

```ail
perform state.write(key, value)        // persist across runs
r = perform state.read(key)            // -> Result[Text]
b = perform state.has(key)             // -> Boolean
perform state.delete(key)

now = perform clock.now()              // ISO-8601 UTC
now = perform clock.now("unix")        // Unix timestamp as Text

perform schedule.every(seconds)        // schedule next run N seconds from now
```

### Credentials and approval

```ail
r = perform env.read("KEY_NAME")       // -> Result[Text]; shown as masked input in ail up UI
approval = perform human.approve(plan) // -> Result[Boolean]; blocks until user clicks Approve/Decline
```

### Search and logging

```ail
r = perform search.web(query)          // -> Result[Any]; JSON array of results
perform log(message)                   // stream message to browser run-log in real time
```

### File I/O

```ail
r = perform file.read(path)            // -> Result[Text]
perform file.write(path, content)
```

### Sub-program execution

```ail
r = perform ail.run(ail_source_text)   // -> Result[Text]; run AIL program as sub-program
```

**Do not ask an intent model to write AIL code for `ail.run`.** Intent models lack the reference card → syntax errors. Use the plan+execute pattern instead.

## FEATURE STATUS (v1.46.5)

### Implemented

| Feature | Since |
|---|---|
| `fn`, `intent`, `entry`, `if`/`else if`/`else`, `for`, `branch`, `context`, `import`, `evolve` | v1.0 |
| `Result` type: `ok`/`error`/`is_ok`/`is_error`/`unwrap`/`unwrap_or`/`unwrap_error` | v1.1 |
| Provenance: `origin_of`, `lineage_of`, `has_intent_origin`, `has_effect_origin` | v1.2 |
| `pure fn` statically enforced | v1.3 |
| `attempt` blocks | v1.4 |
| Implicit parallelism | v1.5 |
| `perform` effect system: `http.get/post/post_json/graphql`, `file.read/write` | v1.6+ |
| `match` with `with confidence OP N` guards | v1.7 |
| `evolve` with mandatory `rollback_on` | v1.8 |
| `parse_json` / `encode_json` builtins | v1.8.5 / v1.15 |
| `ail_parse_check` | v1.8.5 |
| Bare list types: `items: [Number]`, `-> [Text]` | v1.8.4 |
| Agentic projects: `ail init` / `ail up` / browser chat UI | v1.9.0+ |
| `clock.now` / `state.*` effects | v1.9.5–v1.9.8 |
| `schedule.every` | v1.9.12 |
| `http.post_json` / `http.graphql` | v1.15 |
| `env.read` / `human.approve` effects | v1.14+ |
| `search.web` effect | v1.28+ |
| `perform log` (real-time browser streaming) | v1.43 |
| Multi-program per project | v1.20+ |
| Plan+execute agentic pattern (intent models don't write AIL) | v1.46 |

### Not implemented

| Feature | Status |
|---|---|
| `while` loops | Intentionally absent |
| Lambda / anonymous fn | Use named `fn` + pass name |
| Full static type checking | Types at parse time only, not enforced |
| Dict / map literals | Use pair lists `[["k", v]]` |
| HEAAOS (L3 OS layer) | Design documents only |
| `ail bundle` | Not started |

## STDLIB

| Module | Contents |
|---|---|
| `stdlib/core` | `identity`, `refuse` |
| `stdlib/language` | `summarize`, `translate`, `classify`, `extract`, `rewrite`, `critique` |
| `stdlib/utils` | `word_count`, `char_count`, `is_empty`, `repeat`, `pad_left`, `clamp`, `sum_list`, `average`, `flatten`, `unique`, `take` |

Do NOT import `stdlib/math`, `stdlib/io`, `stdlib/json`, `stdlib/string` — these do not exist.

## ADAPTERS

```python
from ail.runtime import MockAdapter
from ail.runtime.anthropic_adapter import AnthropicAdapter  # ANTHROPIC_API_KEY
from ail.runtime.ollama_adapter import OllamaAdapter        # AIL_OLLAMA_MODEL
from ail.runtime.openai_adapter import OpenAICompatibleAdapter  # OPENAI_API_KEY + any OpenAI-compatible server
```

OpenAICompatibleAdapter env vars: `AIL_OPENAI_COMPAT_MODEL`, `AIL_OPENAI_COMPAT_BASE_URL` (default: http://localhost:8000), `AIL_OPENAI_COMPAT_API_KEY`. Supports o-series reasoning models (temperature omitted, system message merged into user).

## ARCHITECTURE NOTE: AUTHORING vs INTENT MODEL

Two models, two roles:
- **Author model** (writes AIL programs): gets the full authoring system prompt with reference card, examples, rules. Used by `ail up` chat UI.
- **Intent model** (executes `intent` calls at runtime): gets only the `goal:` string and inputs. Does NOT write AIL. Does NOT receive the authoring system prompt.

Never ask an intent model to write AIL code. It doesn't have the reference card.

## FILE NAMING

| Suffix | Audience |
|---|---|
| `*.md` | Humans (English) |
| `*.ai.md` | AI/LLM systems (you are reading one) |
| `*.ko.md` | Korean-speaking humans |
| `*.ail` | AIL source files |

## TEAM COMMUNICATION

Design correspondence between Arche, Ergon, and Telos moved from `docs/letters/` (archived 2026-04-26) to **Stoa** — the live message board at `https://ail-stoa.up.railway.app`.

**Reading your inbox (Rule 10 — do this at session start):**
```
stoa_read_inbox(to="<your-name>")   # e.g. to="telos", to="ergon", to="arche"
```

**Posting a letter:**
```
stoa_post(from_name="telos", to="ergon", title="...", content="...")
# Multiple recipients: use cc=["arche", "telos"] alongside to=
# Do NOT use to="all" — name each recipient explicitly
```

**`docs/letters/` is read-only archive.** Do not write new files there.
