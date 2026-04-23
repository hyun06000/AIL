# news-ticker

A small dashboard that refreshes every 10 seconds. Each tick bumps
a counter in persistent state; the dashboard reads the latest value.

Demonstrates three primitives composing:

- `perform schedule.every(10)` — recurring background invocation.
- `perform state.write(...)` — per-tick persistence.
- **`view.html`** — the dashboard page is a separate HTML file in the
  project. AIL code stays focused on computation; markup lives as a
  normal file editable without touching `.ail` sources. The client
  JS fetches `POST /` to get data from `entry main`.

## Behavior
- First request arms a 10-second schedule and returns the current count.
- Each background tick increments the stored count.
- Every refresh of the dashboard shows the newest count.

## Deployment
- Port 8080
