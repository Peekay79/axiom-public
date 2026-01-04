Belief Governance (Contradictions, Provenance, Recompute)

Rationale
- Prevent confidence ratcheting and the “confidently wrong historian” effect by making beliefs evidence‑aware and time‑aware.
- Journal contradictions and surface them to operators; periodically recompute confidence with caps, decay, and counter‑evidence penalties.

Provenance schema
- Minimal normalized item: {type: journal|external, ref: string, weight?: number}
- Examples:
  - journal: {"type":"journal","ref":"evt:2025-01-28T10:00:00Z","weight":1.0}
  - external: {"type":"external","ref":"doi:10.1145/123456","weight":2.0}
  - external: {"type":"external","ref":"https://example.com/paper"}

Recompute math
- Cap rule (no external evidence): confidence = min(confidence, CAP_NO_EXTERNAL)
- Exponential dormancy decay: confidence *= 0.5 ** (days_since / HALFLIFE_DAYS)
- Counter‑evidence penalty: if contradictions exist since last recompute, confidence -= PENALTY (floored at 0)

Ops guide
- Enable flags via environment:
  - BELIEF_GOVERNANCE_ENABLED=true
  - BELIEF_RECOMPUTE_ENABLED=true
  - BELIEF_RECOMPUTE_INTERVAL_CRON="0 * * * *" (if using your scheduler)
  - BELIEF_CONFIDENCE_CAP_NO_EXTERNAL=0.6
  - BELIEF_DORMANCY_HALFLIFE_DAYS=30
  - BELIEF_COUNTEREVIDENCE_PENALTY=0.2
- Run once ad‑hoc: `python -m beliefs.recompute --once --batch-size 200`
- Monitor Cockpit:
  - governor.belief.contradictions is surfaced automatically (from signals)
  - Counters emitted: beliefs.recomputed, beliefs.capped_no_external, beliefs.decayed_by_dormancy, beliefs.penalized_counterevidence
  - Optional gauge: beliefs.avg_confidence (rolling after recompute)

Safety
- All integrations are additive and flag‑gated; failures are fail‑closed.
- Recompute is idempotent and updates include a fresh updated_at; when routed via the HTTP API, callers should attach Idempotency‑Key headers.

