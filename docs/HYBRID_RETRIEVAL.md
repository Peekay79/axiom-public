# Hybrid Retrieval (BM25 + Dense + Dedupe + Rerank)

Hybrid Retrieval combines lexical (BM25) and dense ANN results, deduplicates near‑duplicates, and reranks using a cross‑encoder (flag‑gated) or heuristic fallback.

Note: In this repository, BM25 is a placeholder stub unless a lexical index is wired in. The pipeline fails‑closed to dense‑only if BM25 is unavailable.

## Configuration
- HYBRID_RETRIEVAL_ENABLED: true|false (default: false)
- HYBRID_WEIGHTS: split into env keys for ops:
  - HYBRID_WEIGHTS_LEXICAL (default 0.3)
  - HYBRID_WEIGHTS_DENSE (default 0.7)
- HYBRID_DEDUPE_THRESHOLD: Jaccard threshold for near‑dupe drop (default 0.85)
- RERANK_ENABLED: true|false (default: false)
- RERANK_MODEL: cross‑encoder model id (default: cross-encoder/ms-marco-MiniLM-L-6-v2)

## Integration
- When enabled, `memory_response_pipeline` executes:
  1) BM25 `k_lex` and Dense `k_dense`
  2) Union → `dedupe.cluster_drop(threshold)`
  3) Rerank via cross‑encoder if enabled, else heuristic
  4) Return top‑k to CHAMP
- Retrieval stats (recall cohort, embedding norms) are emitted via Governor when available.

## Calibration
- Start with weights `{lexical: 0.3, dense: 0.7}`.
- Increase `lexical` for code or exact‑match heavy domains.
- Tune `HYBRID_DEDUPE_THRESHOLD` between 0.8–0.9; lower to drop more.

## Canary Evals
- Measure: recall@k against dense baseline, MRR with reranking.
- Expect: hybrid ≥ dense recall@k; rerank improves MRR.
- Run canary queries periodically and track via Cockpit.

## Fail‑Closed
- If disabled or errors occur, pipeline falls back to dense‑only.