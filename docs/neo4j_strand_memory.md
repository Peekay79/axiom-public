### Neo4j Strand Memory (Optional)

This module adds an optional "strand memory" graph to complement Axiom's existing Qdrant vector memory. It mirrors memory entries as nodes in Neo4j and links them with relationships (strands) to represent contextual continuity and relatedness across time.

- Purpose: Provide graph-native traversal and path queries across memories.
- Differs from Qdrant: Qdrant provides dense vector similarity search; Neo4j provides explicit graph topology for reasoning over connections.
- Non-breaking: Fully additive. When disabled, Axiom functions exactly as before.

### Optional Install
- Via extras (if project packaging is present): `pip install .[neo4j]`
- Or via requirements file: `pip install -r requirements-neo4j.txt`
- Activation requires BOTH: `ENABLE_STRAND_GRAPH=true` and the Neo4j driver installed. If either is missing, strand sync is a no-op.

### Enable/Disable
- Toggle with environment variable: `ENABLE_STRAND_GRAPH=true`
- If disabled or the Neo4j driver is not installed, the system gracefully performs no external operations; the demo runs in dry‑run and logs the Cypher it would execute.

### Configuration
Set via environment variables (defaults in parentheses):
- `NEO4J_URI` (`bolt://localhost:7687`)
- `NEO4J_USER` (`neo4j`)
- `NEO4J_PASSWORD` (empty → unauthenticated local dev). If missing, a clear log will note unauthenticated connection.

### Schema
Cypher definitions live in `memory/strand/schema.cypher` and are applied on first use.
- Memory nodes: label `Memory` with properties `id`, `content`, `speaker`, `memory_type`, `tags`, `created_at`, `updated_at`, `schema_version`
- Relationships: `(:Memory)-[:RELATED]->(:Memory)` with optional `reason`, `score`, timestamps

This extends the JSON memory schema (`schemas/memory.schema.json`) by mirroring compatible fields; no overrides or breaking changes are introduced.

### Integration Hook
The hook is called after successful vector insertion in Qdrant:
- Function: `memory.strand.strand_graph.sync_strand(memory_id, payload)`
- Behavior: Upserts the `Memory` node; future versions may link based on heuristics.
- Errors: All Cypher failures are logged with memory UUID and a concise error line; full traceback is logged at debug level.

### Observability & Troubleshooting
- Logs are prefixed with `[strand_sync]` and include memory UUIDs and latency (ms).
- Minimal metrics are tracked in-memory over a rolling window and last hour:
  - Attempts, successes, failures
  - p95 latency over the last hour
  - Last success and error timestamps
- Programmatic health snapshot:
```python
from memory.strand.strand_graph import strand_health_snapshot
print(strand_health_snapshot())
```
- If `neo4j` is not installed, you will see: `Strand graph disabled—neo4j driver not installed.`
- If credentials are absent, you will see a log noting an unauthenticated connection attempt.

### Demo
Run a dry‑run or live demo that inserts two nodes, links them, and queries a strand path:
```bash
python -m memory.strand.demo
```
The demo echoes both the Cypher queries and the results.

### Example Cypher Queries
- Upsert a memory node:
```cypher
MERGE (m:Memory {id: $id})
ON CREATE SET m.content = $content, m.speaker = $speaker, m.memory_type = $memory_type, m.tags = $tags, m.created_at = datetime()
```
- Link two memories:
```cypher
MATCH (a:Memory {id: $from_id}), (b:Memory {id: $to_id})
MERGE (a)-[r:RELATED]->(b)
SET r.reason = $reason, r.score = $score, r.updated_at = datetime()
```
- Query a strand from a starting memory:
```cypher
MATCH p = (m:Memory {id: $start_id})-[:RELATED*1..3]->(n:Memory)
RETURN p LIMIT 100
```

### Notes
- Production deployments should secure Neo4j with authentication and TLS.
- Strand graph is early scaffolding; additional linking heuristics and analytics can be layered without changing Qdrant workflows.