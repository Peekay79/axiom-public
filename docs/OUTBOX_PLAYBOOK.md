# Outbox Playbook (Stability Core)

This guide explains how to operate the Outbox + Saga system for multi‑pod writes.

## Overview
- Exactly‑once side‑effects using an idempotent outbox (SQLite by default)
- Claim with visibility timeout to avoid duplicate processing
- Retries with exponential backoff; DLQ after max retries
- Governor saga signals emitted for cockpit observability

## Configuration
- OUTBOX_ENABLED: true|false (default: false)
- OUTBOX_BACKEND: sqlite (default)
- OUTBOX_DB: path to sqlite db (default: /var/run/outbox.sqlite)
- OUTBOX_VISIBILITY_SEC: claim visibility timeout (default: 60)
- OUTBOX_MAX_RETRIES: max retry attempts before DLQ (default: 8)

## Operations

### Inspect
- List all items or by status:
  - statuses: PENDING, CLAIMED, DONE, DLQ
  - Python REPL: `from outbox.admin import list as list_items; list_items("DLQ")`

### Replay DLQ
- After downstream recovery, replay DLQ items via admin tool or `outbox.admin.replay(id)`.
- Items must be idempotent (same idem_key); handlers should be safe to re‑run.

### Purge
- Purge DONE or DLQ after validation:
  - `from outbox.admin import purge_status; purge_status("DONE")`
  - `purge_status("DLQ")`

### Saga Signals
- Emitted per item:
  - saga_begin.WriteMemorySaga
  - saga_step.WriteMemorySaga.<type>
  - saga_end.WriteMemorySaga
- Cockpit aggregates these under `/status/cockpit` to visualize the pipeline.

## Idempotency
- The store enforces a unique `idem_key`; duplicates return the first id.
- Side‑effect handlers must be idempotent using stable ids in payload.

## Enabling Strict Idem Enforcement
- Ensure Governor middleware populates `X-Correlation-ID` and `Idempotency-Key` at pod edges.
- With `GOVERNOR_STRICT_MODE=true`, missing headers return 400.

## Worker Deployment
- Run `outbox.worker.OutboxWorker(build_default_handlers()).run_forever()` inside Vector/Belief pods.
- Configure handlers per pod role if needed.

## Smoke
- Enable OUTBOX_ENABLED=true
- Write to memory → 202 Accepted with `{cid, idem_key, outbox_ids}`
- Kill vector pod → items retry then DLQ; after recovery, replay succeeds
- Cockpit shows saga steps