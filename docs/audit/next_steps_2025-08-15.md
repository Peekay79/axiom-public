# Next Steps — 2025-08-15

- [P1] Sanitize legacy ingestion utility (`ingest_qdrant.py`)
  - Owner: tools/qdrant
  - Actions: replace hard-coded collection with unified getter; switch to wrapper `AxiomQdrantClient.upsert_batch`; call `PayloadConverter.validate_payload()`.

- [P2] qdrant_utils defaults and docs
  - Owner: pods/memory
  - Actions: update `pods/memory/qdrant_utils.py` arg defaults/docstrings to reference unified collections; cross-link `memory.collections` in `pods/memory/QDRANT_SUPPORT_SUMMARY.md`.

- [P2] Add tests
  - Owner: tests/core
  - Actions:
    - Test decisive filter order preservation.
    - Test `/memory-debug` includes `profile_source` and `metrics.prometheus_enabled` shape.
    - Test pod `--qdrant_collection` default resolves via unified getter.

- [P3] Mark legacy Weaviate docs
  - Owner: docs
  - Actions: add a “Legacy (Weaviate)” banner to `vector1.md`, `upload_missing_memories.py` header comments.

- [P3] Consider implementing Auto-Profile
  - Owner: memory pipeline
  - Actions: if desired, add lightweight heuristic behind `AXIOM_AUTO_PROFILE` that picks profile and sets `profile_source = "auto"` when env/profile not explicitly provided.