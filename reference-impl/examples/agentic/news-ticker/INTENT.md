# news-ticker

A small dashboard that refreshes its content every 10 seconds.
Every tick bumps a counter in persistent state; GET / reads the
latest value and renders it as an HTML snippet.

Demonstrates three L2 v2 primitives composing:

- `perform schedule.every(10)` registers the cadence.
- `perform state.write(...)` stores the per-tick result.
- HTML output mode (entry returns `<div>...</div>`) is rendered by
  the browser UI directly.

## Behavior
- First request arms a 10-second schedule and returns the current count.
- Each background tick increments the stored count.
- Every subsequent GET shows the newest count.

## Deployment
- Port 8080
