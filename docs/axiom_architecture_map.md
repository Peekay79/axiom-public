# Axiom Cognitive Architecture Map

Executive summary
- Axiom’s cognition is centered on vector memory (Qdrant) with optional strand memory (Neo4j) for graph-native continuity.
- Persistent memory includes JSON-based long-term storage with a resilient SQLite fallback cache.
- Reasoning subsystems include beliefs, contradiction detection/resolution, temporal/causal engines, CHAMP decision engine, and optional Dream/Wonder engines.
- Journaling captures reflective state and integrates with beliefs, ToM, temporal/causal reasoning, and CHAMP metrics.
- The system adheres to additive, env-gated extensions. The Neo4j strand layer is optional and isolated.
- Cerberus (optional): a backup & guard subsystem providing versioned snapshots and pre-risk protection. Enable with `ENABLE_CERBERUS=true`. CLI `cerberus-cli` and HTTP API available.

Mermaid dataflow diagram
```mermaid
graph TD
  U[User/External Stimuli]
  LLM[LLM(s)]
  MGR[Memory Manager<br/>pods/memory/memory_manager.py]
  VEC[Qdrant Vector Memory<br/>qdrant_backend.py<br/>axiom_qdrant_client.py]
  STRAND[(Optional Strand Graph<br/>Neo4j)<br/>memory/strand/*]
  LTM[Long-term JSON Store<br/>pods/memory/memory_manager.py]
  FBACK[(SQLite Fallback Cache)]
  BEL[Belief System<br/>belief_registry.py, memory/belief_engine.py]
  NLI[NLI Conflict Checker<br/>nli_conflict_checker.py]
  CEX[Contradiction Explainer/Resolver<br/>contradiction_explainer.py, contradiction_resolution_engine.py]
  TMP[Temporal Reasoner<br/>temporal_reasoner.py]
  CAU[Causal Reasoner<br/>causal_reasoner.py]
  CHAMP[CHAMP Decision Engine<br/>champ_decision_engine.py]
  JRN[Journaling Systems<br/>journal_engine.py, journaling_enhancer.py]
  WM[World Model<br/>world_model.py]
  WMV[World Model Visualizer<br/>world_model_visualizer.py]
  WON[Wonder Engine<br/>wonder_engine.py]
  DRM[Speculative Simulation Module (optional)<br/>dream_engine.py]

  U -->|Prompts/Events| MGR
  MGR -->|store/query| VEC
  MGR -->|persist| LTM
  MGR -->|fallback| FBACK
  VEC -.env gated sync.-> STRAND
  MGR --> BEL
  BEL --> NLI --> CEX
  MGR --> TMP
  MGR --> CAU
  MGR --> CHAMP
  CHAMP --> WON
  CHAMP --> JRN
  MGR --> JRN
  JRN --> BEL
  JRN --> WM
  WM --> VEC
  WMV --> WM
  DRM -.optional journaling-> JRN
  LLM -.tool use / generation-> MGR
```

Schemas and alignment
- Canonical memory schema: `schemas/memory.schema.json` (required fields: `content`, `speaker`; additionalProperties: true).
- Qdrant payload schema/validator: `qdrant_payload_schema.py` (Memory/Belief/Archive payloads; `validate_payload` enforces defaults and `schema_version=3`). Aligns with canonical schema via compatible extensions, not overrides.
- Collection names: `memory/memory_collections.py` → `axiom_memories`, `axiom_beliefs`, `axiom_memory_archives`.

Subsystems overview
- Vector Memory (Qdrant)
    - Key files: `qdrant_backend.py`, `axiom_qdrant_client.py`, `memory/utils/qdrant_compat.py`, `qdrant_ingest.py`.
  - Functions: upsert/search, batch ops, health/init, schema validation.
  - Inputs/outputs: text embeddings (SentenceTransformers), payloads validated by `PayloadConverter`.
  - Env: `USE_QDRANT_BACKEND`, `QDRANT_HOST/PORT/URL/API_KEY`, `QDRANT_USE_HTTPS`, `QDRANT_PREFER_GRPC`.

- Optional Strand Memory (Neo4j)
  - Key files: `memory/strand/strand_client.py`, `memory/strand/strand_graph.py`, `memory/strand/schema.cypher`.
  - Integration: env-gated calls in `qdrant_backend.py` and `qdrant_ingest.py` under `ENABLE_STRAND_GRAPH`.
  - Env: `ENABLE_STRAND_GRAPH`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.

- Persistent/Long-term Memory
  - Key file: `pods/memory/memory_manager.py` (JSON file `MEMORY_FILE`; fallback SQLite cache `FallbackMemoryStore`).
  - Transactional helpers: `begin_transaction`, `commit_transaction`, `rollback_transaction`.

- Journaling Systems
  - `journal_engine.py` (async reflective journaling; ToM/temporal/causal/contradiction/LLM integration).
  - `journaling_enhancer.py` (rich, structured entries; trend analysis; integrates CHAMP, ToM, belief influence, planning).

- Belief Engine & Registry
  - `memory/belief_engine.py` (extraction/normalization), `belief_registry.py` (NLI conflicts; journaling on conflicts), `belief_models.py`.
  - Contradiction: `nli_conflict_checker.py`, `contradiction_explainer.py`, `contradiction_resolution_engine.py`, `contradiction_resolver.py`.

- Temporal & Causal Reasoning
  - `temporal_reasoner.py` (validity, pattern detection, tags).
  - `causal_reasoner.py` (link data model/API; persistence; query functions).

- Decision & Exploration
  - `champ_decision_engine.py` (scoring, thresholding, feedback logger).
  - `wonder_engine.py` (sandbox curiosity; containment tags; optional journaling).
  - `dream_engine.py` (autonomous idea generation; optional integration).

- World Model / Visualization
  - `world_model.py` (entities/events, optional Qdrant push, belief tagging feature flag).
  - `world_model_visualizer.py` (graph assembly; contradiction overlays; dashboards).
  - `worldmap_simulator.py` (non-destructive future state simulation for strategic planning and goal selection, integrating with CHAMP decision engine).
  - `worldmap_diff.py` (worldmap comparison and change analysis utility).

- Tools & Prompt Modes
  - Tools: `tools/cognitive_engine_tool.py`, ingestion/reingest scripts in `tools/`, diagnostics in `qdrant_vector_diagnose.py`.
  - Prompt modes: `prompt_generator.py` with reflective/speculative/analytical modes; simulation scripts in `simulation/`.

Integration highlights
- Memory flows: `pods/memory/memory_manager.py` interacts with `qdrant_backend.py` through `memory_backend_interface.py` and falls back to JSON/SQLite.
- Journaling → Beliefs: `journal_engine.py` and `journaling_enhancer.py` can create/annotate beliefs and log conflict events through `belief_registry.py`.
- CHAMP influences journaling and wonder triggers and is used by planning/value inference modules.
- Worldmap Simulation: `worldmap_simulator.py` enables non-destructive future state modeling for strategic planning and goal selection, integrating with CHAMP decision engine.
- Strand graph sync is optional and does not affect Qdrant flows if disabled or the driver is missing.

Key environment flags (selection)
- Vector: `USE_QDRANT_BACKEND`, `QDRANT_HOST/PORT/URL/API_KEY`, `QDRANT_USE_HTTPS`, `QDRANT_PREFER_GRPC`, `VECTOR_SYNC`, `EMBEDDING_MODEL`.
- Strand: `ENABLE_STRAND_GRAPH`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- Beliefs/Contradictions: `AXIOM_BELIEF_ENGINE`, `AXIOM_CONTRADICTIONS`, `BELIEF_TAGGING`.
- Journaling: `JOURNAL_MIN_INTERVAL`, `JOURNAL_RECENT_WINDOW`, `JOURNAL_STREAM`, `ENABLE_REFLECTION_PROMPTS`.
- Persistence: `MEMORY_FILE`, `CAUSALITY_FILE`.

Call graph highlights (representative)
- `pods/memory/memory_manager.Memory.save_*` → `qdrant_backend.QdrantMemoryBackend.store_memory` → `axiom_qdrant_client.QdrantClient.upsert_memory` → (optional) `memory/strand/strand_graph.sync_strand`.
- `journal_engine.generate_journal_entry` → ToM/temporal/causal/contradiction modules → `Memory.add_to_long_term` and belief registry updates.
- `memory_response_pipeline` uses CHAMP, temporal/causal engines, belief validators, and vector adapter for relevance.

Appendix A: Files and modules
- Vector/Qdrant: `qdrant_backend.py`, `axiom_qdrant_client.py`, `memory/utils/qdrant_compat.py`, `qdrant_payload_schema.py`.
- Strand/Neo4j: `memory/strand/*` (client, graph, schema, demo).
- Journaling: `journal_engine.py`, `journaling_enhancer.py`.
- Beliefs: `memory/belief_engine.py`, `belief_registry.py`, `belief_models.py`, `nli_conflict_checker.py`, `contradiction_*`.
- Reasoners: `temporal_reasoner.py`, `causal_reasoner.py`.
- Decision/Exploration: `champ_decision_engine.py`, `wonder_engine.py`, `dream_engine.py`.
- World Model: `world_model.py`, `world_model_visualizer.py`.
- Memory Manager: `pods/memory/memory_manager.py`.

Appendix B: Diagrams and dashboards
- Belief graph viewer: `web/belief_graph_viewer.html` (contradiction highlighting, local JSON loader).