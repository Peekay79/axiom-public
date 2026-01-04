Event-Sourced Writes (Exactly-Once)
===================================

Overview
--------
Journaling and memory writes are appended to an event log with idempotency keys. A background consumer applies side-effects (journal append, vector upsert, belief recompute) exactly once.

Env Flags
---------
- EVENTLOG_ENABLED: true
- EVENTLOG_BACKEND: sqlite (only backend currently)
- EVENTLOG_DB: eventlog/axiom_events.sqlite
- EVENTLOG_BATCH_SIZE: 256
- EVENTLOG_TICK_SEC: 2

Data Model
----------
events(seq_id INTEGER PK AUTOINCREMENT, idem_key TEXT UNIQUE, cid TEXT, kind TEXT, payload JSON, ts INT, status TEXT, last_error TEXT)

Consumer
--------
`eventlog.consumer.EventConsumer` drains pending events, invokes handlers per kind, and marks `done` or `error`. Cockpit signals:
- eventlog.processed
- eventlog.errors
- eventlog.lag

Wire-Up (Memory Pod)
--------------------
- `POST /memory/add` appends `journal.append` (JSON mode) or `memory.write` (file mode) and returns `202 {event_id, idem_key}` when enabled. Legacy path remains when disabled.

Runbook
-------
`python -m pods.memory.eventlog_runner`

Cockpit
-------
Aggregator exposes `eventlog: {lag, processed_5m, errors_5m}`; exporters emit gauges `cockpit.eventlog.*`.

Tests
-----
See `tests/test_eventlog_exactly_once.py`.

