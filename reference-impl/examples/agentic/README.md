# Agentic project examples

Each subfolder is a complete AIL project: an `INTENT.md` written in
plain language plus a pre-authored `app.ail`. Run `ail up <folder>`
to start the service; the AI agent reads INTENT.md, executes the
declared tests against the saved app.ail, then serves on the port
declared in `## Deployment`.

| Example | Backend needed | What it shows |
|---|---|---|
| [`word-counter/`](word-counter/) | None | Smallest possible agentic project — `Result` threading, HTTP 500 on validation error. README's headline demo. |
| [`csv-stats/`](csv-stats/) | None | Pure-fn pipeline: parse a CSV body, skip the header, error on malformed rows. No LLM calls per request. |
| [`visit-counter/`](visit-counter/) | None | Cross-request state — `perform state.read` / `state.write`. Each request increments a counter; the value survives process restart. L2 v2 primitive demo. |
| [`sentiment/`](sentiment/) | Author + intent (Anthropic / OpenAI / Ollama) | The fn/intent split in one program — pure word count + LLM sentiment label. One model call per request. |
| [`news-ticker/`](news-ticker/) | None | Recurring work via `perform schedule.every(10)` + persistent `state.write` + HTML output mode. Three L2 v2 primitives composing in one dashboard. |

## Running

From the repo root:

```bash
ail up reference-impl/examples/agentic/csv-stats
# in another shell:
curl -X POST localhost:8081/ -d $'Alice,85\nBob,92\nCarol,78'
# count=3
# total=255
# average=85
```

For `sentiment/` you'll need an authoring backend configured:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
ail up reference-impl/examples/agentic/sentiment
curl -X POST localhost:8082/ -d "I love this product"
# 4 words, sentiment: positive
```

## Re-authoring from scratch

The committed `app.ail` files let the examples run without paying for
an LLM call. To see the agent author from INTENT.md (the actual non-
developer flow), delete `app.ail` first:

```bash
rm reference-impl/examples/agentic/word-counter/app.ail
ail up reference-impl/examples/agentic/word-counter
# [word-counter] app.ail empty — authoring via `ail ask`...
# [word-counter] wrote ...
```

The agent re-runs the declared tests against whatever the model
produced. If the tests pass it serves; if they fail, it aborts and
prints the failures so you can edit INTENT.md and try again.

## State directory

Each project gains a `.ail/` directory on first `ail up`:

```
project/
├── INTENT.md
├── app.ail
└── .ail/
    ├── tests.json    # test cases extracted from INTENT.md
    ├── ledger.jsonl  # every authoring decision, test run, request
    └── state/        # cross-session evolve state (placeholder)
```

`.ail/` is local — gitignored by each example's `.gitignore`.
