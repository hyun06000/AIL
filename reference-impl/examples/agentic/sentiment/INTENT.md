# sentiment

Counts words in incoming text and classifies the sentiment with an LLM.
Output: `{count} words, sentiment: {label}`.

This example demonstrates AIL's `pure fn` + `intent` split — the word
count is deterministic (no model call); the sentiment label requires
judgment (one model call). Mixing them in one program is the language's
point.

## Behavior
- Word count via pure fn (no LLM)
- Sentiment label via intent (one LLM call per request)
- Empty input → error

## Tests
- "I absolutely love this product" → succeed
- "Worst purchase ever" → succeed
- "" → 에러

## Deployment
- 포트 8082

> **Note:** running `ail up` on this project requires an authoring +
> intent backend (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or local
> Ollama with `AIL_OLLAMA_MODEL` set). The committed `app.ail` is
> pre-authored so first-time `ail up` skips authoring; the intent
> call still hits a model on every request.
