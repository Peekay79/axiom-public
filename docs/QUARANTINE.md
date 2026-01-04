Quarantine (Poison/Injection Defense)
=====================================

Overview
--------
Incoming texts are heuristically scored for trust and scanned for injection patterns. Flagged items are quarantined and excluded from recall by default.

Env Flags
---------
- QUARANTINE_ENABLED: true
- QUARANTINE_TRUST_MIN: 0.4
- QUARANTINE_INJECTION_FILTER: true
- QUARANTINE_NAMESPACE: mem_quarantine (optional for separate collection)

Write Path
----------
- On `POST /memory/add`, flagged items are marked `{quarantined:true, reason, trust_score}`; Cockpit emits `quarantine.flagged` and the response includes `{mode:"quarantined"}` when applicable.

Retrieval Path
--------------
- Default filter excludes `quarantined:true` (unless `INCLUDE_QUARANTINE=true`).
- Counters: `quarantine.flagged`, `quarantine.released` (when items are moved back by operator).

Cockpit
-------
- Aggregator: `quarantine: {flagged_5m, released_5m}` (optional last IDs)
- Exporters: `cockpit.quarantine.flagged_5m`, `cockpit.quarantine.released_5m`

Tests
-----
See `tests/test_quarantine.py`.

