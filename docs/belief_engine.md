# Belief Engine (Axiom) — Canonicalization, Scope, Safety

This document summarizes the refined Belief Engine behavior.

## Canonicalization
- Key version: `KEY_VERSION = 1`
- Small synonym table for headwords:
  - ai_alignment: [ai_safety, alignment_safety]
  - transparency: [interpretability, explainability]
  - autonomy: [self_direction, self_governance]
- `canonicalize_belief_text(text) -> (key, normalized_text, key_version)`:
  - lowercase, trim, collapse whitespace
  - strip punctuation except `:` and `_`
  - maps known synonyms
  - builds compact `subject:predicate`-style key when obvious, else normalized text

## Belief object fields
- Always clamp confidence to [0,1]
- Polarity ∈ {−1, 0, +1}
- Scope: defaults to `general`; respects `project:<id>`, `self`, `entity:<id>` if provided
- Beliefs carry `key_version`

## Config
- `config/belief_config.yaml` keys:
  - thresholds: `SIM_THRESHOLD`, `STRONG_CONTRADICTION_THRESHOLD`
  - penalties: `BASE_PENALTY`, `OPPOSITE_POLARITY_MULTIPLIER`
  - modes: `TAGGER_MODE`, `ALIGNMENT_ENABLED`
  - `SCOPE_POLICY: intra_only`
  - `REFRESH_SEC: 300`
- Env overrides: `AXIOM_BELIEF_REFRESH_SEC`

## Alignment scoring
- Penalizes only when:
  - key similarity ≥ `SIM_THRESHOLD`
  - opposite polarity
  - combined confidence ≥ `STRONG_CONTRADICTION_THRESHOLD`
  - and, if `SCOPE_POLICY == intra_only`, scopes match
- Final score clamped to [0,1]

## Contradiction detection
- Groups by `(key, scope)` when `intra_only`; otherwise by key
- Includes `key_version`
- Redacts text by default; keeps UUIDs/polarity/confidence/scope

## ActiveBeliefs cache
- Refreshes on boot and when stale: `now - last_refresh > REFRESH_SEC` (env override supported)
- Exposes `size()`, `last_refresh_at()`, `source_counts()` for debug endpoints

## Ingestion & schema
- When `AXIOM_BELIEF_ENGINE=1`, incoming `content` is tagged into structured beliefs
- Always write `schema_version=3` and `last_migrated_at`
- Never write nulls

## Pipeline observability
- `retrieval_id` generated per request
- Counters/timing:
  - belief.alignment.calls, belief.alignment.ms
  - belief.contradictions.detected
  - journal.contradiction_events.emitted
  - rerank.ms_before_belief, rerank.ms_after_belief
- Journal events: `type=contradiction_event` (UUIDs, keys, polarity, confidence, scope, retrieval_id)

## Rollout runbook
1. Snapshot collections
2. Verify schema
3. Backfill dry‑run, then apply for `schema_version < 3`
4. Stage 1: flags off (ingest accumulates)
5. Stage 2: `AXIOM_BELIEF_ENGINE=1`, `AXIOM_CONFLICT_POLICY=neutral`
6. Stage 3: `AXIOM_CONFLICT_POLICY=penalize`
7. Optional: `explore` (boost capped)

Rollback: unset flags; data remains forward‑compatible.