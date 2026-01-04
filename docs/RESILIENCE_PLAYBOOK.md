## Resilience Core – Budgets, Breakers, Degraded Mode

This playbook documents the resilience features added to Axiom. All features are additive, flag‑gated, and fail‑closed by default.

### Feature Gates & Knobs (ENV)

- `RESILIENCE_ENABLED` (default: `true`)
- `TOKENS_PER_TURN` (default: `4000`)
- `TOOL_CALLS_PER_TURN` (default: `6`)
- `BREAKER_FAILS` (default: `5`)
- `BREAKER_RESET_SEC` (default: `60`)
- `BREAKER_HALF_OPEN_PROB` (default: `0.2`)
- `DEGRADED_QUEUE_LIMIT` (default: `10000`)
- `DEGRADED_READONLY_ENABLED` (default: `true`)

### Budgets – Per‑turn Tokens & Tool Calls

Module: `resilience/budgets.py`

- Use `start_new_turn()` to initialize a per‑thread turn context.
- Charge a tool call with `ensure_tool_call()`; charge tokens with `ensure_token_usage(n)`.
- On budget exceed, `BudgetExceeded("tokens"|"tools")` is raised. Callers should fail‑closed and return a 429‑style application error:
  `{ "error":"budget_exceeded", "retry_after_sec":15 }`.
- Cockpit signal emitted: `resilience.budget_exceeded.tokens|tools`.

Integrated in `llm_connector.py`: each LLM call charges one tool; tokens are charged based on model `usage.total_tokens`.

### Circuit Breakers – Vector & Memory Clients

Module: `resilience/breakers.py`

- Classic `CLOSED → OPEN → HALF_OPEN → CLOSED` breaker with configurable fails/reset/half‑open sampling.
- Wrapped around vector and memory write/read paths:
  - `vector/unified_client.py` guards search/upsert
  - `axiom_qdrant_client.py` guards memory upsert/batch upsert, counts read failures
- On `allow()==False`, degraded mode is activated, Cockpit signal `resilience.breaker.<dep>.open` can be emitted, and calls fail‑closed.

State Diagram:

Closed → (≥ fails) → Open → (after reset_sec) → Half‑open → (success) → Closed; (failure) → Open

### Degraded Read‑only Mode – Outbox Queueing

Module: `resilience/degraded.py`

- Global process flag toggled by breakers. When active:
  - Writes to Memory API `/memory/add` are queued to Outbox (forced), returning `202` with mode:`degraded` when Outbox is available.
  - If Outbox is unavailable, write requests return `503` with a friendly message.
  - Reads remain unaffected.
- Cockpit signals:
  - `resilience.degraded` with `{active, depth?}`
  - Optionally alert if queue depth exceeds `DEGRADED_QUEUE_LIMIT` (surface via your Outbox monitor).

### Cockpit & Metrics

Reporter helpers (optional):
- `report_budget_exceeded(kind)`
- `report_breaker_event(dep, event)`
- `report_degraded(active, depth)`

Aggregator exports in snapshot JSON under `resilience`:
- `budgets` → tokens/tools exceeded (counted via signals present)
- `breakers` → vector/memory open events
- `degraded` → `{active, depth}`

Exported gauges (Prometheus style):
- `cockpit.resilience.degraded_active` {0|1}
- `cockpit.resilience.breaker_open_vector` {0|1}
- `cockpit.resilience.breaker_open_memory` {0|1}
- `cockpit.resilience.budget_exceeded_tokens` (counter per scrape)
- `cockpit.resilience.budget_exceeded_tools` (counter per scrape)

### Tuning Tips

- Vector/Memory flapping:
  - Increase `BREAKER_FAILS` if you see false opens.
  - Increase `BREAKER_RESET_SEC` for flaky networks to allow longer cool‑offs.
- Budgeting:
  - Increase `TOKENS_PER_TURN` or `TOOL_CALLS_PER_TURN` for heavy sessions.

### Operator Actions

- Degraded mode:
  - Monitor `/status/cockpit` for `resilience` section and metrics for active degraded mode and queue depth.
  - Drain DLQ via Outbox admin when needed.
  - Once dependencies stabilize, degraded mode will self‑deactivate on successful calls.

