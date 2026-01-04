# Axiom Deep Audit — 2025-08-15

## ✅ Verified OK
- memory/scoring.py:238–346 — composite_score uses multiplicative formula with centered terms and optional conflict_penalty.
- memory/scoring.py:166–184 — Active beliefs loaded via env-cached `AXIOM_ACTIVE_BELIEFS_JSON` with graceful fallback.
- memory_response_pipeline.py:95–116 — Metrics shim present; counters/histogram degrade safely when prometheus is absent.
- memory_response_pipeline.py:1585–1650 — Decisive filter gated by `AXIOM_DECISIVE_FILTER`; preserves order among kept IDs and safe fallback when too few selected.
- memory_response_pipeline.py:1731–1737, 1821–1825 — Usage feedback is async, with retries/jitter `AXIOM_USAGE_RETRY_*`; trust nudge via `AXIOM_TRUST_NUDGE`.
- memory_response_pipeline.py:1692–1699 — Rerank latency logged; histogram observed when available.
- pods/memory/pod2_memory_api.py:673–742 — `/memory-debug` returns stable shape with composite flags, profile, topK/topN/mmr, items; exposes `selected_decisive_ids`, `profile_source`, `usage_feedback`, and `metrics.prometheus_enabled`.
- qdrant_backend.py:144–168 — Validates vector size and enforces cosine distance; logs schema once at boot.
- world_model.py:176–187 — Ingestion uses `PayloadConverter.validate_payload()` and wrapper `upsert_memory()` with `memory_collection()`.
- pods/vector/vector_adapter.py:145–159 — Ingestion enforces `validate_payload()` and uses wrapper `upsert_memory()`.
- qdrant_ingest.py:424–457, 530–547 — Ingestion path validates payload and uses `upsert_batch()`.
- scripts/backfill_memory_fields.py:36–57 — Default `--collection` resolved via `memory.collections.memory_collection()`; help includes dry‑run/yes.
- scripts/qdrant_snapshot.py:169–201 — Default `--collection` resolves to unified getter; `--print-collections` prints unified names.
- scripts/verify_schema.py:30–44, 53–66 — Defaults resolve unified collection and print distance & vector dim.
- README.md:801–818 — Env var table includes all required vars and retry knobs.
- Guard script `scripts/check_banned_strings.py`: present and runnable; bans `upsert_points` and warns on hard-coded collections.

## ⚠️ Issues
### Critical
1) docs/composite_scoring_for_axiom.md:211–241, 325–329 — Hard‑coded `axiom_memory` in safety toolkit examples.
   - Fix: Use unified getter in examples.
   - Status: Fixed in this audit.
   - Diff snippet:
```211:241:docs/composite_scoring_for_axiom.md
python scripts/verify_schema.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --sample 1000
# ... existing code ...
python scripts/backfill_memory_fields.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --parallel 8 --yes
```

2) pod2_memory_api.py and pods/memory/pod2_memory_api.py — CLI default `--qdrant_collection` used legacy `axiom_memory`.
   - Fix: Default now resolves via `memory.collections.memory_collection()` with fallback to `axiom_memories`.
   - Status: Fixed in this audit.
   - Diff snippet:
```38:46:pod2_memory_api.py
try:
	from memory.memory_collections import memory_collection as _memory_collection
	_default_coll = _memory_collection()
except Exception:
	_default_coll = "axiom_memories"
parser.add_argument("--qdrant_collection", default=_default_coll,
                    help="Qdrant collection name (default: unified memory collection)")
```
```38:46:memory/pod2_memory_api.py
try:
	from memory.memory_collections import memory_collection as _memory_collection
	_default_coll = _memory_collection()
except Exception:
	_default_coll = "axiom_memories"
parser.add_argument("--qdrant_collection", default=_default_coll,
                    help="Qdrant collection name (default: unified memory collection)")
```

3) memory_response_pipeline.py — `profile_source` referenced in debug snapshot but not defined.
   - Fix: Added a minimal assignment based on whether a request override was supplied.
   - Status: Fixed in this audit.
   - Diff snippet:
```1404:1410:memory_response_pipeline.py
resolved_profile = _PROFILE if scoring_profile is None else str(scoring_profile)
# Record profile source for debug API parity
profile_source = "request" if scoring_profile is not None else "env"
```

### Recommended
4) ingest_qdrant.py:L11 — Hard‑coded `COLLECTION_NAME = "axiom_memory"` and low-level `client.upsert(...)` bypass wrapper and validation.
   - Problem: Dev/utility script not using unified collection or wrapper; payload bypasses `PayloadConverter.validate_payload()`.
   - Suggestion: For safety, either guard with a banner “legacy utility; do not use in prod” or refactor to use `AxiomQdrantClient.upsert_batch` and resolve collection via `get_collection_for_type`/unified getters, validating payloads.
   - Lines:
```11:21:ingest_qdrant.py
COLLECTION_NAME = "axiom_memory"
...
97:101:ingest_qdrant.py
client.upsert(collection_name=COLLECTION_NAME, points=qdrant_points)
```

5) pods/memory/qdrant_utils.py:L20, L110, L140 — Defaults mention `axiom_memory` in docstrings/args.
   - Problem: Legacy naming in helper defaults; could confuse operators.
   - Suggestion: Update help strings/defaults to use unified names or resolve via `memory.collections`.

### Optional
6) Vector docs still reference Weaviate API in `vector1.md` and `upload_missing_memories.py`. Not in scope of Qdrant pipeline but could be confusing.
   - Suggestion: Add a note at the top of those docs marking them legacy for Weaviate and not applicable to current Qdrant setup.

## 🧭 Integration Map
- Retrieval: Qdrant via `axiom_qdrant_client.QdrantClient` → `memory_response_pipeline.fetch_vector_hits` → composite scoring (`memory/scoring.py`) → optional decisive filter → MMR → usage feedback updater (async) → `/memory-debug` snapshot in `pods/memory/pod2_memory_api.py`.
- Ingestion: `world_model.py` / `pods/vector/vector_adapter.py` / `qdrant_backend.py` / `qdrant_ingest.py` → always `PayloadConverter.validate_payload()` → wrapper upserts (`upsert_memory`, `upsert_batch`).
- Collections: Unified via `memory/collections.py` getters; safety scripts default to getters.
- Metrics: Prometheus shim optional; in-process counters otherwise.

## 🧪 Test Coverage Gaps
- No explicit test for `AXIOM_DECISIVE_FILTER` order preservation when applied; consider a small unit test asserting kept IDs maintain relative order from pre-filter list.
- No test exercising `/memory-debug` with `metrics.prometheus_enabled` true (shim path is covered).
- Lacking a test that ensures `pods/memory/pod2_memory_api.py`’s default `--qdrant_collection` resolves to unified getter.
- No test covering profile_source reporting; add a unit test that calls pipeline with and without explicit scoring_profile and inspects `/memory-debug`.

## 📚 Docs Gaps
- `pods/memory/QDRANT_SUPPORT_SUMMARY.md` and helper `qdrant_utils.py` still show `axiom_memory` in examples and defaults; update lines 33–34, 73–89 accordingly.
- `Axion_memory_pod_guide.txt` references `axiom_memory`; mark as legacy or update examples.
- `vector1.md` and related Weaviate docs should be clearly marked legacy.

## 🔌 Env Var Map
| Var | Where read | Default | Documented? | Used? |
| AXIOM_COMPOSITE_SCORING | memory_response_pipeline.py:136; pods/memory/pod2_memory_api.py:166 | 0 | Yes (README) | Yes |
| AXIOM_SCORING_PROFILE | memory_response_pipeline.py:137; pods/memory/pod2_memory_api.py:677 | default | Yes | Yes |
| AXIOM_MMR_LAMBDA | memory_response_pipeline.py:139–145; pods/memory/pod2_memory_api.py:680 | 0.4 | Yes | Yes |
| AXIOM_TOP_N | memory_response_pipeline.py:146–151; pods/memory/pod2_memory_api.py:679 | 8 | Yes | Yes |
| SIMILARITY_THRESHOLD | memory_response_pipeline.py:77 | 0.3 | Yes | Yes |
| VECTOR_POD_URL | world_model.py:55; pods/memory/pod2_memory_api.py:98 | required | Yes | Yes |
| EMBEDDING_MODEL | world_model.py:106; qdrant_backend.py:71 | all‑MiniLM‑L6‑v2 | Yes | Yes |
| AXIOM_CONTRADICTIONS | memory/scoring.py:310; memory_response_pipeline.py:1635–1639; pods/memory/pod2_memory_api.py:803 | 0 | Yes | Yes |
| AXIOM_DECISIVE_FILTER | memory_response_pipeline.py:1591 | 0 | Yes | Yes |
| AXIOM_AUTO_PROFILE | N/A in code scan | 1 | Yes | No (not implemented) |
| AXIOM_USAGE_FEEDBACK | memory_response_pipeline.py:1732, 1822 | 1 | Yes | Yes |
| AXIOM_TRUST_NUDGE | memory_response_pipeline.py:1733, 1823 | 0 | Yes | Yes |
| AXIOM_USAGE_RETRY_MAX | memory_response_pipeline.py:126 | 3 | Yes | Yes |
| AXIOM_USAGE_RETRY_BASE_MS | memory_response_pipeline.py:127 | 100 | Yes | Yes |
| AXIOM_USAGE_RETRY_JITTER_MS | memory_response_pipeline.py:128 | 100 | Yes | Yes |
| AXIOM_ACTIVE_BELIEFS_JSON | memory/scoring.py:173 | None | Mentioned in docs | Yes |
| AXIOM_BELIEFS_ENABLED | tests only | N/A | Mentioned in docs | Indirect via weights |
| AXIOM_BELIEF_ENGINE | qdrant_payload_schema.py:450; pods/memory/pod2_memory_api.py:685 | 0 | Mentioned | Yes |
| AXIOM_BELIEF_CONFLICT_PENALTY | memory_response_pipeline.py:1638 | 0.05 | Mentioned | Yes |

Notes:
- Single contradictions flag standardization confirmed: only `AXIOM_CONTRADICTIONS` used.
- `AXIOM_AUTO_PROFILE` is documented but not found in code; mark as “documented but unused”.