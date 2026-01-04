## Governor Layer (Cockpit Phase 5)

The Governor observes and (optionally) enforces contracts and invariants across pods. It is additive, flag-gated, and fail-closed by default.

### Feature Flags

- `GOVERNOR_ENABLED` (default: true)
- `GOVERNOR_STRICT_MODE` (default: false)
- `GOVERNOR_REQUIRE_IDEMPOTENCY` (default: true)
- `GOVERNOR_REQUIRE_CORRELATION_ID` (default: true)
- `GOVERNOR_RETRIEVAL_MONITOR_ENABLED` (default: true)
- `GOVERNOR_BELIEF_GOVERNANCE_ENABLED` (default: true)

Strict mode upgrades soft warnings into hard 4xx rejections at pod edges.

### Modules

- `governor/ids.py` — correlation ID + idempotency helpers
- `governor/middleware.py` — header normalization for API handlers
- `governor/saga.py` — saga/outbox observability signals
- `governor/retrieval_monitor.py` — embedding stats and recall cohorts
- `governor/belief_governance.py` — provenance checks and contradictions
- `governor/schemas/v1/*.json` — minimal typed payload schemas

### Cockpit Integration

New sections under `/status/cockpit` JSON:

```
governor: {
  sagas: { "WriteMemorySaga": { began, ended_ok, ended_err } },
  retrieval: {
    embedding_norms: { "mem": { mean, p95, n } },
    recall_cohorts: { "mem": { "canary@5": 0.6 } }
  },
  contract_violations: { missing_correlation_id, missing_idempotency_key, schema_violation },
  belief: { contradictions }
}
```

Metrics export adds `cockpit.governor.contracts_weak`.

### Usage Examples

Enforce headers at pod edge (soft by default):

```python
from governor.middleware import ensure_correlation_and_idempotency
headers = ensure_correlation_and_idempotency(req_headers, payload, require_cid=True, require_idem=True)
```

Saga markers:

```python
from governor.saga import saga_begin, saga_step, saga_end
saga_begin(cid, "WriteMemorySaga", {"route": "POST /memory"})
saga_step(cid, "WriteMemorySaga", "journal_append", ok=True)
saga_end(cid, "WriteMemorySaga", ok=False, summary={"rolled_back": False})
```

### Example curl

```bash
curl -X POST http://localhost:8002/memory/add \
  -H "X-Correlation-ID: corr_123" \
  -H "Idempotency-Key: idem_abc" \
  -d '{"content":"test"}' -H 'Content-Type: application/json'
```

### Tests

Run hermetic tests:

```bash
pytest -k governor_contracts -q
```

