Embedder Registry & Blue/Green
==============================

Overview
--------
The embedder registry pins the active embedding configuration and stores metadata with each vector. On recall, results are checked against the current registry to prevent silent drift or dimension mismatches.

Env Flags
---------
- EMBEDDER_REGISTRY_ENABLED: true | Attach embedder metadata on upsert; enforce on recall
- EMBEDDER_NAME: text-embedding-3-large (example)
- EMBEDDER_VERSION: 3.0.0
- EMBEDDER_DIM: 3072
- BLUEGREEN_ENABLED: true | Allow alias cutovers after canary eval
- BG_ALIAS: mem_current
- BG_SHADOW: mem_shadow
- BG_MIN_RECALL_DELTA: -0.01 | Minimum recall delta to cut over

Behavior
--------
- Write path: `axiom_qdrant_client` adds `payload.embedder = {name,version,dim,hash}` when enabled.
- Recall path: mismatched or missing embedder metadata emits Cockpit signals:
  - `retrieval.embedder_mismatch`
  - `retrieval.embedder_missing`
  When enabled, mismatches are excluded from ranking (fail-closed).

Cockpit Signals & Gauges
------------------------
- Signals: `retrieval.embedder_mismatch`, `retrieval.embedder_missing`, `governor.retrieval.embedder`
- Exported metrics include `cockpit.governor.retrieval.embedder_dim` (best-effort)

Blue/Green Cutover
------------------
- `retrieval/bluegreen.py` exposes:
  - `record_recall_eval(source, shadow, k, delta_recall)`
  - `maybe_cutover(client, alias, shadow, min_delta)`
- The re-embed job records canary deltas and, when `BLUEGREEN_ENABLED` and thresholds pass, switches alias to the shadow collection.

Smoke Checklist
---------------
- Write a vector with wrong dim/hash in payload → recall flags mismatch and excludes it (when enabled)
- Run the re-embed job with canary that passes thresholds → alias switch recorded as `bluegreen.switch`

