# Optional Strand Memory (Neo4j) — Developer Guide

Mission
- Additive, optional, non-breaking strand graph that mirrors memory nodes and links contextual continuity across time.
- Complements Qdrant vector search with graph-native traversal and queries.

Setup
- Install driver: `pip install -r requirements-neo4j.txt`
- Enable via env: `ENABLE_STRAND_GRAPH=true`
- Configure:
  - `NEO4J_URI` (default `bolt://localhost:7687`)
  - `NEO4J_USER` (default `neo4j`)
  - `NEO4J_PASSWORD` (empty allowed for local dev)
- Activation requires BOTH the env flag and the driver. Otherwise, sync is a no-op (dry-run logging).

Schema alignment
- Mirrors fields compatible with `schemas/memory.schema.json` and `qdrant_payload_schema.py` payloads.
- Node label: `Memory` with properties: `id`, `content`, `speaker`, `memory_type`, `tags`, `created_at`, `updated_at`, `schema_version`.
- Constraints/Indexes applied lazily by `ensure_schema()` using `memory/strand/schema.cypher`.

Integration points
- Qdrant store hooks (env-gated):
  - `qdrant_backend.py` → `sync_strand(memory_id, payload, ...)`
  - `qdrant_ingest.py` (batch sync)
- Isolation: imports are inside the gated blocks; base system runs if Neo4j is missing.

> Cerberus – Backup & Guardian (Optional)
> - Enable via `ENABLE_CERBERUS=true` to protect memory/vector data with versioned snapshots.
> - Auto snapshots before risky actions (e.g., `--create-collections`, `qdrant_ingest.py`), plus a CLI `cerberus-cli` and HTTP API for manual `snapshot/list/restore`.
> - Retention defaults to 3 snapshots (`CERBERUS_RETENTION=3`); archives under `/backups/` or fallback.
> - All hooks are NO-OP when disabled; `--force` can override pre-snapshot prompts when allowed.

Minimal examples
- Health snapshot
```python
from memory.strand.strand_graph import strand_health_snapshot
print(strand_health_snapshot())
```
- Demo (dry-run or live depending on env/driver)
```bash
python -m memory.strand.demo
```
- Query a strand from a known memory id
```python
from memory.strand.strand_client import get_driver
from memory.strand.strand_graph import query_strand

driver = get_driver()  # None if disabled; then dry_run applies
for row in query_strand(driver, start_id="<MEMORY_ID>", depth=3, log=None, dry_run=(driver is None)):
    print(row)
```

Observability
- Logs prefixed `[strand_sync]`, with upsert/link steps and latency.
- In-memory counters: attempts, successes/failures, p95 latency (last hour) via `strand_health_snapshot()`.

Troubleshooting
- Symptom: no ops executed
  - Check `ENABLE_STRAND_GRAPH=true`; ensure `neo4j` is installed; verify logs report enabled state.
- Symptom: auth errors
  - Set `NEO4J_USER/NEO4J_PASSWORD`; verify URI.
- Symptom: performance issues
  - Confirm indexes/constraints applied; reduce sync volume or batch.

Safety & non-breaking
- If disabled or driver missing, sync functions return early (no exceptions leaked).
- Qdrant ingestion paths unaffected; strand sync runs best-effort after successful vector upserts.