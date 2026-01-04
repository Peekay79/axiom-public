
# Composite Scoring for Axiom â€“ Expanded Onboarding Guide

## Purpose
Composite scoring combines multiple factors from Qdrant-stored memories into a **single retrieval score**. This allows Axiom to weigh memories more intelligently than pure vector similarity, using dimensions like recency, credibility, usage frequency, and (in the future) belief alignment.

## Where it Runs in the Pipeline
1. **Retrieve Top-K** from Qdrant (vector similarity search).
2. Apply **composite scoring** with weights from `config/composite_weights.yaml`.
3. Optionally apply **MMR (Maximal Marginal Relevance)** to diversify results.
4. Return Top-N to the LLM for context injection.

## Key Files
- `memory/scoring.py` â€“ scoring logic & MMR implementation.
- `config/composite_weights.yaml` â€“ weight profiles (default, news, evergreen, personal, code).
- `memory_response_pipeline.py` â€“ hooks scoring into retrieval.
- `pods/memory/pod2_memory_api.py` â€“ `/memory-debug` route.
- `qdrant_payload_schema.py` â€“ ensures default fields exist at ingest.
- `qdrant_backend.py` â€“ enforces schema validation & vector dim/distance checks.
- `scripts/qdrant_snapshot.py` â€“ snapshot/export tool.
- `scripts/verify_schema.py` â€“ schema field presence checker.
- See also: `docs/belief_engine.md` for belief alignment and contradictions.

## Data Dictionary (Required Fields)
| Field             | Purpose                                      |
|-------------------|----------------------------------------------|
| `timestamp`       | ISO 8601 datetime for recency scoring        |
| `source_trust`    | Source credibility (0â€“1 float)               |
| `confidence`      | Confidence in fact accuracy (0â€“1 float)      |
| `times_used`      | How often this memory has been recalled      |
| `beliefs`         | Belief tags (future: influence belief match) |
| `importance`      | Importance weighting for retrieval           |
| `memory_type`     | Category (fact, code, conversation, etc.)    |
| `schema_version`  | Schema version for migrations                |
| `last_migrated_at`| Timestamp of last schema migration           |

**Note:** When `AXIOM_BELIEF_ENGINE=1`, belief alignment is active and contributes via `w_bel`. Otherwise it defaults to `1.0`.

## Composite Scoring Formula
```python
final = (
  w_sim * sim
) * (
  (1 + w_rec  * rec) *
  (1 + w_cred * (cred - 0.5)) *
  (1 + w_conf * (conf - 0.5)) *
  (1 + w_bel  * (bel  - 0.5)) *
  (1 + w_use  * use) *
  (1 + w_nov  * nov)
)
```
Weights come from the selected profile in `composite_weights.yaml`. Centering (e.g., `cred - 0.5`) avoids runaway multipliers.

## MMR (Maximal Marginal Relevance)
MMR re-ranks results to **balance relevance and diversity**. Controlled by:
- `AXIOM_MMR_LAMBDA` (0 = all relevance, 1 = all diversity).
- Recommended: 0.4 for balanced retrieval.
- Turn off by setting `AXIOM_MMR_LAMBDA=0`.

## Example `/memory-debug` Output
```json
{
  "profile": "default",
  "topK": 20,
  "topN": 8,
  "mmr_lambda": 0.4,
  "composite_enabled": true,
  "items": [
    {
      "id": "1234-uuid",
      "sim": 0.92,
      "rec": 0.8,
      "cred": 0.95,
      "conf": 0.9,
      "use": 0.3,
      "nov": 0.7,
      "bel": 1.0,
      "final_score": 0.876
    }
  ],
  "selected_ids": ["1234-uuid", "..."]
}
```

> Note: In non‑composite mode, `/memory-debug` maintains the same shape. Factor fields in `items` are present with zeros, and `composite_enabled` is `false`.  # parity note

## Runbook
**Enable composite scoring:**
```bash
export AXIOM_COMPOSITE_SCORING=1
export AXIOM_SCORING_PROFILE=default
export AXIOM_MMR_LAMBDA=0.4
export AXIOM_TOP_N=8
```

**Safety / validation:**
```bash
python scripts/qdrant_snapshot.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())")
python scripts/verify_schema.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --sample 1000
python scripts/backfill_memory_fields.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --batch-size 500 --dry-run
```

**Apply backfill:**
```bash
python scripts/backfill_memory_fields.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --batch-size 500 --yes
```

**Test:**
```bash
pytest tests/test_scoring.py
```

## Rollback
- Disable composite scoring: `unset AXIOM_COMPOSITE_SCORING`.
- Switch retrieval to vector-only mode (default pipeline).
- Revert `config/composite_weights.yaml` if modified.

## Pitfalls & Gotchas
- Vector dim & distance **must match** (cosine enforced).
- Backfill is idempotent but must be run **before** enabling composite scoring for consistent results.
- Timestamps in wrong format will break recency scoring.
- Belief alignment currently has no effect.

## FAQ
**Q:** Why not always use MMR?  
**A:** It can over-diversify and drop highly relevant but similar results.

**Q:** Where do weights come from?  
**A:** `config/composite_weights.yaml` â€” tuned per use case.

**Q:** How do I change scoring behaviour?  
**A:** Edit the YAML, reload, and watch `/memory-debug` output for factor balance.

## Belief alignment factor
- Enabled when `AXIOM_BELIEFS_ENABLED=1` (default). Can also be toggled per-profile via `beliefs_enabled`.
- Lightweight v0.1 uses Jaccard similarity on belief tags: `align = (|overlap| + α) / (|union| + α)` with `α=belief_alpha` (default 0.1) to avoid hard zeros.
- Optional boost when any overlapping tag is under important namespaces (e.g., `axiom.identity`, `axiom.ethic.*`) via `belief_importance_boost`.
- Applied as `(1 + w_bel * (bel - 0.5))` inside the multiplicative scorer.

### Belief Alignment v0.1
- Source of active beliefs is provided by `beliefs/active_beliefs.py`, which aggregates:
  - Boot journal beliefs (most recent entry in `stevebot/journal/axiom_journal.jsonl` if available)
  - Per-session/system tags (optional)
  - Env override: `AXIOM_ACTIVE_BELIEFS_JSON` (JSON string of tags)
- New YAML knobs in `config/composite_weights.yaml` under each profile:
  - `beliefs_enabled: true`
  - `belief_alpha: 0.1`
  - `belief_importance_boost: 0.1`

### Contradiction Surfacing v0.1
- Heuristic detector in `beliefs/contradictions.py` scans the top ~20 candidates after composite scoring and before final Top‑N.
- If two items share ≥1 belief tag and contain opposing polarity claims about the same entity (regex on “is/was/has/does not…”), a conflict is surfaced.
- We do not drop items. We slightly penalize the older item by a multiplicative factor `(1 - belief_conflict_penalty)` (default 0.05).
- Feature flags and knobs:
  - Env: `AXIOM_CONTRADICTIONS=1` (default on)
  - YAML per-profile: `contradictions_enabled: true`, `belief_conflict_penalty: 0.05`
  - Env override for penalty: `AXIOM_BELIEF_CONFLICT_PENALTY=0.05`

### /memory-debug enrichment
- Payload now includes:
  - `active_beliefs`: the list of active belief tags used for alignment
  - Per-item fields: `belief_align` (aliased from `bel`), `conflict_penalty` (0..1 when applied)
  - `selected_decisive_ids` when LLM decisive filter is enabled and used
  - `profile_source`: one of `env`, `auto`, `request`, `default`
  - `usage_feedback`: true when updates were dispatched
  - Use `GET /memory-debug?include_conflicts=1` to include the detailed conflict pairs `{a_id, b_id, note}`

### When to disable
- For neutral benchmarking or ablation studies, disable via env:
  - `AXIOM_BELIEFS_ENABLED=0`
  - `AXIOM_CONTRADICTIONS=0`
- Or per-profile by toggling the YAML switches listed above.

## Evaluation Modes & How to Run

The evaluator runs three modes across profiles:
- VectorOnly: `composite_enabled=0`, MMR ignored
- Composite-NoMMR: `composite_enabled=1`, `mmr_lambda=0`
- Composite-MMR: `composite_enabled=1`, `mmr_lambda∈{0.2,0.4,0.6}`

Create or edit queries in `tests/resources/sample_queries.json`, then run:
```bash
python scripts/evaluate_scoring_profiles.py \
  --host localhost --port 5000 \
  --queries tests/resources/sample_queries.json \
  --profiles default evergreen personal \
  --topn 8 --topk 80
```
Artifacts are written to `logs/scoring_eval/`:
- Per-query JSON logs under `logs/scoring_eval/{profile}/{mode}_mmr{lambda}/...json`
- Summary CSV: `logs/scoring_eval/summary.csv`

### Reading summary.csv
Columns:
- query_slug, profile, mode, mmr_lambda, topN
- avg_final_score, std_final_score
- mean_pairwise_cosine, redundancy_rate
- sim_avg, rec_avg, cred_avg, conf_avg, bel_avg, use_avg, nov_avg
- latency_ms

### Diversity metrics
- mean_pairwise_cosine: average cosine similarity across all pairs in TopN. Lower means more diverse.
- redundancy_rate: fraction of pairs with cosine ≥ 0.95. Lower is better (fewer near-duplicates).

> If VectorOnly mode lacks factor parts in `/memory-debug`, the evaluator still logs similarity/diversity and latency; factor averages will be zero.

## Schema Safety & Backfill

Use these tools to ensure Qdrant payloads remain schema-compliant and to remediate older data.

- **Verify schema (sample):**
```bash
python scripts/verify_schema.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --sample 1000
```
- **Verify schema (full, CI-fail on missing):**
```bash
python scripts/verify_schema.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --full
```
  - Prints total point count, missing count and percent per required field, and flags mixed-type payload fields.
  - In `--full` mode, exits with code 1 if any required fields are missing.

- **Backfill missing fields (dry-run by default):**
```bash
python scripts/backfill_memory_fields.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --batch-size 500 --dry-run
```
- **Apply backfill (idempotent, resumable):**
```bash
python scripts/backfill_memory_fields.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --batch-size 500 --yes
```
- **Target specific fields:**
```bash
python scripts/backfill_memory_fields.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --fields source_trust,confidence,timestamp --yes
```
- **Skip/overwrite present fields:**
  - Default is `--skip-present` (do not overwrite non-null values).
  - To force overwrite: add `--overwrite-present`.
- **Parallel updates:**
```bash
python scripts/backfill_memory_fields.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --parallel 8 --yes
```

- **Snapshot and metadata:**
```bash
python scripts/qdrant_snapshot.py --host localhost --port 6333 --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --dir snapshots/
```
  - Saves under `snapshots/{collection}_YYYYMMDD_HHMMSS/`.
  - Writes `snapshot_meta.json` with vector dimension, distance, field list (sampled), and collection size.
  - Restore basics: for native snapshots, use Qdrant's snapshot restore endpoint; for scroll dumps, stream `points.jsonl` and upsert with the `id`, `payload`, and vector from each line.

### Required fields and defaults
Enforced at ingestion in `qdrant_payload_schema.py` and used by backfill defaults:
- `timestamp`: ISO 8601 current time if missing
- `source_trust`: 0.6
- `confidence`: 0.5
- `times_used`: 0
- `beliefs`: []
- `importance`: 0.5
- `memory_type`: "default"
- `schema_version`: 3
- `last_migrated_at`: set to current time when migrated/backfilled

These defaults maintain non-breaking ingestion: enforcement still occurs at ingest; backfill is safe, idempotent, and resumable.

## Additional toggles

- Belief & Contradiction Signals (v1): conservative alignment using Jaccard overlap on string tags; optional penalty when payload flags indicate contradiction. Keys in `config/composite_weights.yaml` (per-profile):
  - `beliefs_enabled`, `belief_alpha`, `belief_conflict_penalty`.
- Usage feedback loop: after selection, increments `times_used` and optionally applies a tiny `source_trust` nudge when `AXIOM_TRUST_NUDGE=1`. Guarded by `AXIOM_USAGE_FEEDBACK` (default 1).
- Decisive filter: when `AXIOM_DECISIVE_FILTER=1` and Top‑K is large, a tiny LLM pass can mark decisive snippets; we keep original order among kept IDs and fall back if too few are selected.
- Auto profile: when `AXIOM_AUTO_PROFILE=1` (default), a lightweight heuristic selects a profile based on the query unless explicitly overridden by `AXIOM_SCORING_PROFILE` or request.

## Search Relevance QA Harness

The harness provides a fast way to test and debug search relevance with vector-only vs composite scoring modes.

- **Script**: `scripts/search_relevance_qa.py`
- **Sample queries**: `qa/sample_queries.txt`

### Example usage

```bash
# Single query, composite scoring (default)
python scripts/search_relevance_qa.py --query "recent deployment timeline"

# Vector-only baseline
python scripts/search_relevance_qa.py --query "telemetry default" --baseline

# Explicit composite mode with factor breakdowns and weights
python scripts/search_relevance_qa.py --query "privacy policy" --composite --show-weights

# Compare baseline vs composite, side-by-side
python scripts/search_relevance_qa.py --query "benchmark results last week" --compare

# Multiple queries from a file, save JSON results
python scripts/search_relevance_qa.py --query-file qa/sample_queries.txt --compare --json --save qa/results.json

# Apply Qdrant filters (JSON) and profile timings
python scripts/search_relevance_qa.py --query "belief alignment" --filters '{"type": "belief"}' --profile

# Test recency effects by filtering out old results client-side
python scripts/search_relevance_qa.py --query "daily stand-up" --max-age-days 7
```

### Reading the output

- The default console table shows, per result:
  - **Rank, UUID, Preview**
  - **Vec**: raw vector similarity score from Qdrant
  - **Meta**: metadata contribution = (composite − sim*w_sim)
  - **Comp**: final composite score
  - **rec/cred/conf/bel/use/nov**: per-factor values contributing to composite
  - **Missing**: key fields absent in payload; consider running the backfill if many are missing

- In `--compare` mode, the table aligns results by UUID and shows rank shifts (ΔRank), baseline vector score, and composite score.

### JSON output

- Add `--json` to emit structured results suitable for programmatic analysis. Use `--save <file>` to persist.
- Each query entry includes arrays for `baseline` and/or `composite` with per-item fields: `rank`, `id`, `preview`, `vector_score`, `composite_score`, `metadata_contrib`, `factors`, `weights`, `payload_missing`, `payload`.

### Required fields and backfill

- The harness expects the following payload fields for full breakdowns: `timestamp`, `source_trust`, `confidence`, `times_used`, `beliefs`, `importance`.
- Missing fields are handled gracefully but will reduce composite fidelity. If many are missing, run:

```bash
python scripts/verify_schema.py --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --sample 1000
python scripts/backfill_memory_fields.py --collection $(python -c "from memory.memory_collections import memory_collection; print(memory_collection())") --batch-size 500 --yes
```

### Tips

- Use environment variables to control the scoring profile without changing the script:
  - `AXIOM_COMPOSITE_SCORING=1`
  - `AXIOM_SCORING_PROFILE=default`
  - `AXIOM_MMR_LAMBDA=0.4`
- The harness computes composite scores with `memory/scoring.py` directly to reflect live logic; it does not duplicate scoring.
- For large-scale evaluations across profiles and MMR settings, see `scripts/evaluate_scoring_profiles.py`.
