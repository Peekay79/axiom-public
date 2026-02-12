# Axiom Subsystem Status

This document describes what is active, degraded, or stubbed in different operating modes of the public Axiom repo.

## Operating Modes

| Mode | How to start | What you get |
|------|-------------|--------------|
| **Core (fallback)** | `pip install -e .` + run Memory API | JSON-backed memory, beliefs, journaling, contradiction detection, CHAMP agent layer. No semantic recall. |
| **Vector (Qdrant)** | `docker compose -f docker-compose.qdrant.yml up --build` | Everything in Core + Qdrant-backed semantic recall, vector queries, embedding support. |

## Subsystem Matrix

| Subsystem | Core mode | Vector mode | Notes |
|-----------|-----------|-------------|-------|
| Memory API (`/memory/add`, `/list_ids`, etc.) | ✅ Active | ✅ Active | JSON persistence in Core; Qdrant-backed in Vector |
| Health probes (`/ping`, `/readyz`, `/health`) | ✅ Active | ✅ Active | Always available |
| World map endpoints | ✅ Active | ✅ Active | Requires `world_map.json` to be present |
| Belief engine | ✅ Active | ✅ Active | Contradiction detection, confidence decay, reflection |
| Journaling | ✅ Active | ✅ Active | Event logging to `data/logs/` |
| CHAMP decision engine | ✅ Active | ✅ Active | Agent layer; import from `axiom_agent.champ` |
| Cockpit signals | ✅ Active | ✅ Active | File-based boot/readiness reporting |
| Semantic recall (`/vector/query`) | ⚠️ Stubbed | ✅ Active | Returns empty/error in Core mode |
| Embedding service | ❌ Not available | ⚠️ Optional | Requires `requirements-vector.txt` deps |
| Vector adapter (legacy `/v1/*`) | ❌ Not available | ⚠️ Optional | Compatibility layer; most users don't need this |
| Theory of Mind engine | ✅ Library only | ✅ Library only | Importable from `src/axiom/theory_of_mind/`; no HTTP surface |
| Belief graph (Neo4j/SQLite) | ⚠️ SQLite only | ⚠️ SQLite only | Neo4j backend requires separate setup not covered here |
| LLM integration | ❌ Not included | ❌ Not included | Orchestration + LLM calls are external to this repo |
| Discord bot | ❌ Not included | ❌ Not included | Lives in private repo |

## How to check at runtime

```bash
# Health endpoint shows subsystem status
curl -s http://localhost:8002/health | python -m json.tool

# Cockpit signals (if cockpit is running)
ls -la axiom_boot/

# Check which mode the Memory API started in
grep "mode" data/logs/memory.log | tail -5
```

## Key environment variables that affect status

| Variable | Default | Effect |
|----------|---------|--------|
| `USE_QDRANT_BACKEND` | `false` | Enables Qdrant vector backend |
| `AXIOM_AUTH_ENABLED` | `false` | Enables bearer token auth on endpoints |
| `AXIOM_CANARIES` | `true` | Runs vector self-checks on startup |
| `AXIOM_COMPOSITE_SCORING` | `false` | Enables composite retrieval scoring |
| `JOURNAL_VECTOR_ENABLED` | `false` | Upserts journal entries to vector store |
