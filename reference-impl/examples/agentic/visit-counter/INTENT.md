# visit-counter

A tiny service that counts how many times it has been called.
Demonstrates `perform state.read` / `state.write` — cross-request
memory that survives process restart.

## Behavior
- Increment a counter every time the endpoint is hit
- Return the new count
- State persists under `.ail/state/keyval/` so the count survives
  Ctrl-C + restart

## Tests
- "" → succeed
- "hello" → succeed

## Deployment
- 포트 8083
