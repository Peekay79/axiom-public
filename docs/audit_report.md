# Axiom Cognitive Architecture Audit Report

Executive summary
- Core cognitive stack is implemented and test-covered across memory, beliefs, contradictions, temporal/causal reasoning, journaling, CHAMP, and optional exploration engines.
- Vector memory (Qdrant) is primary and mature; strand graph (Neo4j) is optional, gated, and non-breaking.
- Schemas and payload normalization are actively enforced at ingestion and via scripts; canonical JSON schema is minimal and permissive.
- Observability exists via logs and some metrics hooks; recommend minimal metrics additions called out below.

Components found (status)
  - Vector memory (Qdrant): LIVE
    - `qdrant_backend.py` (class `QdrantMemoryBackend`), `axiom_qdrant_client.py` (class `QdrantClient`), `memory/utils/qdrant_compat.py` (version-agnostic helpers);
    collection mappings in `qdrant_payload_schema.py` and names in `memory/memory_collections.py`.
- Strand memory (Neo4j): LIVE (optional, gated)
  - `memory/strand/strand_client.py`, `memory/strand/strand_graph.py`, `memory/strand/schema.cypher`; gated imports in `qdrant_backend.py` and `qdrant_ingest.py` by `ENABLE_STRAND_GRAPH`.
- Persistent memory & fallback: LIVE
  - `pods/memory/memory_manager.py` (JSON `MEMORY_FILE`, `FallbackMemoryStore` via SQLite; transactional helpers).
- Journaling: LIVE
  - `journal_engine.py` (async generator, ToM/temporal/causal/contradiction integration), `journaling_enhancer.py` (structured journals/trends).
- Beliefs & contradictions: LIVE
  - `belief_registry.py`, `memory/belief_engine.py`, `nli_conflict_checker.py`, `contradiction_explainer.py`, `contradiction_resolution_engine.py`.
- Temporal reasoning: LIVE
  - `temporal_reasoner.py` with robust fallbacks in importing modules.
- Causal reasoning: LIVE
  - `causal_reasoner.py` (models, persistence, API).
- CHAMP decision engine: LIVE
  - `champ_decision_engine.py`, integrated across planning/value and retrieval.
- Wonder engine: LIVE (sandboxed)
  - `wonder_engine.py` with containment tags and journaling hooks.
- Speculative Simulation Module: PARTIAL
  - `dream_engine.py` present; tests/stubs mention integration; not wired into core loops by default.
- World model: LIVE (sandbox)
  - `world_model.py` with optional vector push and belief tagging; `world_model_visualizer.py` dashboards.

Constraint verification table

| Constraint | Yes/No | Evidence |
|---|---|---|
| Schema checked & aligned | Yes | `schemas/memory.schema.json` minimal; ingestion validator `qdrant_payload_schema.py::validate_payload` enforces defaults/schema_version; `scripts/verify_schema.py` |
| Additive, non-breaking (strand) | Yes | Strand gated by `ENABLE_STRAND_GRAPH`; local imports; base runs without Neo4j; docs present |
| Env flags present & respected | Yes | See flags inventory below; gating patterns in `qdrant_backend.py`, `world_model.py`, strand modules |
| Dependencies isolated | Yes | Neo4j imported lazily; Qdrant compat helper; optional modules wrapped with try/except |
| README updated | Yes | Optional strand section present, links to docs |
| Docs added (this PR) | Yes | `docs/axiom_architecture_map.md`, `docs/audit_report.md`, `docs/strand_memory_developer_guide.md` |

Risk register
- Qdrant availability or embedding model load failures
  - Likelihood: Medium; Impact: High; Mitigation: fallback cache, health checks, retries.
- Schema drift between belief models/payloads
  - Likelihood: Medium; Impact: Medium; Mitigation: `validate_payload`, backfill scripts, tests.
- Neo4j driver misconfiguration when `ENABLE_STRAND_GRAPH=true`
  - Likelihood: Low; Impact: Low; Mitigation: lazy import, dry-run mode, clear logs.
- Journaling/LLM timeouts affecting pipeline stages
  - Likelihood: Medium; Impact: Medium; Mitigation: async client, try/except, stage isolation.

Observability review
- Logging: Extensive across memory, journaling, CHAMP, vector, strand.
- Metrics: Suggested minimal counters/gauges
  - qdrant_upserts_total, qdrant_query_duration_ms_p95, memory_fallback_active (0/1), strand_sync_attempts_total, strand_sync_latency_ms_p95, champ_decisions_total, champ_execute_ratio, journal_entries_total.
- Tracing: Not present; consider lightweight request IDs for cross-module tracing.

Performance notes
- Qdrant
  - Ensure cosine distance and vector dims validated (already done in `qdrant_backend.initialize`).
  - Indexing: rely on Qdrant HNSW defaults; monitor top-k costs and score_threshold.
- Neo4j
  - Ensure unique constraint on `Memory.id` and indexes as per `memory/strand/schema.cypher`.
- Reranking
  - `memory_response_pipeline` uses MMR variants and quality/causal boosts; tune lambda and thresholds.

Security & privacy
- API keys: `QDRANT_API_KEY` supported; Neo4j creds via env; keys not hardcoded.
- PII: No explicit redaction pipeline; recommend adding redaction filters in journaling and memory ingestion.
- Retention: JSON long-term and vector DB; deletion APIs exist in backend; add clear data retention policy.

Testing & coverage
- Tests present across: journaling, CHAMP, beliefs, contradictions, temporal/causal, Qdrant migration/backends.
- Gaps: end-to-end with strand enabled; security redaction tests; performance regressions.
- Suggested tests
  - Strand: enable flag, verify upsert/link/query dry-run and live.
  - Journaling timeouts: resilience and retries.
  - Schema backfill: `schema_version<3` migration paths.
  - Fallback resync: offline→online convergence.

Config flags inventory (selection)
- Vector/Qdrant: `USE_QDRANT_BACKEND`, `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_USE_HTTPS`, `QDRANT_PREFER_GRPC`, `VECTOR_SYNC`, `EMBEDDING_MODEL`.
- Strand: `ENABLE_STRAND_GRAPH`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- Beliefs/Contradictions: `AXIOM_BELIEF_ENGINE`, `AXIOM_CONTRADICTIONS`, `BELIEF_TAGGING`.
- Journaling: `JOURNAL_MIN_INTERVAL`, `JOURNAL_RECENT_WINDOW`, `JOURNAL_STREAM`, `ENABLE_REFLECTION_PROMPTS`.
- Persistence: `MEMORY_FILE`, `CAUSALITY_FILE`.

Rollback/kill-switch plan
- Disable strand instantly: unset `ENABLE_STRAND_GRAPH`.
- Disable journaling prompts: set `ENABLE_REFLECTION_PROMPTS=0`.
- Force local-only persistence: set `USE_QDRANT_BACKEND=false` and rely on fallback/JSON.

Migration plan (where applicable)
- Qdrant payload schema version pinned to 3; use `scripts/verify_schema.py` and backfill scripts to normalize fields in-place.
- No migration for Neo4j required; schema applied lazily by `ensure_schema` on first use.

Graded rubric (0–10)
- Novelty: 8 — Optional strand graph + CHAMP + rich journaling integrations.
- Architectural coherence: 8 — Clear boundaries and env-gated integrations.
- Modularity: 8 — Interfaces and factories; optional imports.
- Extensibility: 8 — Strand layer, rerankers, reasoners can be added.
- Safety/Alignment: 7 — Containment for Wonder; belief conflicts; more policy tests needed.
- Test coverage: 7 — Broad unit tests; gaps for strand live paths and redaction.
- Observability: 7 — Strong logs; metrics can improve.
- Performance: 7 — Qdrant compat and MMR; monitoring and indexing guidance present.
- Documentation quality: 8 — Extensive docs; this map/report add cross-cut view.
- Non-breaking integration: 9 — Strand fully optional; guards in place.

Likely opinion
- Innovative: optional graph augmentation, CHAMP feedback loop, journaling introspection.
- Brittle spots: dependency versions, env juggling, belief schema drifts.
- Over-engineered: some wrappers and audit scripts are verbose; acceptable for research.
- Missing: formal redaction, unified metrics registry, e2e strand tests.

Comparative analysis (high level)
- Anthropic/Claude memory: Axiom’s journaling + belief conflict pipeline is more introspective; vector parity.
- OpenAI/GPT-5 patterns: Similar tool-augmented memory; Axiom adds CHAMP and optional strand graph.
- LangChain/LlamaIndex: Axiom’s internal stack is bespoke; comparable vector usage; deeper belief/conflict modeling.
- GraphRAG: Strand memory aligns with graph augmentation but is optional and synced post-ingest.
- OpenCog/Hyperon: Orthogonal; Axiom focuses on pragmatic memory + reasoning subsystems.

Team inference
- Skills: applied ML/IR, Python systems, graph DBs, prompt engineering.
- Style: modular with heavy logging/testing; research-grade exploration engines.

Change summary
- Files created: `docs/axiom_architecture_map.md`, `docs/audit_report.md`, `docs/strand_memory_developer_guide.md`.
- Files modified: `README.md` (links/section already present; verified), new links added below.
- Constraint verification: See table above.
- Open questions/TODOs
  - Add minimal metrics (names above) to key modules.
  - Provide example env files for strand enablement.
  - Add redaction pipeline and tests.

What I could not confirm
- Production deployment metrics exporter wiring; only partial references.
- Full live Neo4j integration tests in CI; code supports dry-run but CI wiring unknown.