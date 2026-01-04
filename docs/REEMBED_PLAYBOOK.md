## Re-embedding Playbook

### When to re-embed

- **Model update**: New embedding model or tokenizer change
- **Drift alarm**: Retrieval drift KL or cosine shift exceeds thresholds
- **Hygiene**: Quarterly maintenance to refresh indices

### Safety model

- Use a dedicated **shadow namespace** to re-embed documents
- Validate against **canary queries** and latency
- Perform **atomic alias switch** on pass; live namespace untouched on failure
- **Rollback** is a single alias switch back to the previous target

### Threshold guidance

- **KL max**: Start with 0.10–0.15; tighten if stable
- **Recall delta min**: Allow a small negative delta (≥ -0.01). Prefer ≥ 0.00
- **Latency delta max**: 10–25 ms depending on traffic SLOs

### Runbook

1. Ensure `REEMBED_ENABLED=true`; confirm canary set exists at `DRIFT_CANARY_SET`
2. Run CLI in staging; inspect `/status/cockpit` for `governor.sagas.reembed` and `reembed.summary`
3. If pass, run in prod during low traffic
4. Rollback: switch alias back to previous namespace using Qdrant alias APIs

### Blue/Green Controls

- `BLUEGREEN_ENABLED` (true) – enable alias switch when canary passes thresholds
- `BG_ALIAS` (`mem_current`) – alias to cut over
- `BG_SHADOW` (`mem_shadow`) – shadow collection name
- `BG_MIN_RECALL_DELTA` (`-0.01`) – minimum recall delta required to cut over

Signals emitted:
- `bluegreen.recall_eval` – per-run recall delta record
- `bluegreen.switch` – emitted when alias switches from source to shadow

### Troubleshooting

- **Slow batches**: Reduce `REEMBED_BATCH_SIZE` or increase Qdrant resources
- **High KL**: Confirm tokenizer/model pinned and consistent normalization
- **Recall drop**: Review BM25 weight/rerank or revisit canary coverage

