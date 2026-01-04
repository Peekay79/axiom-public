### Chaos Drills and Nightly Canary CI

This document describes how to run chaos drills safely and how the nightly canary evaluation works. Both are env-gated and fail-closed.

#### Chaos Drills

- Purpose: validate resilience and recovery by pausing critical pods such as `vector` or `memory`, then resuming.
- Safety: reversible pause via Docker Compose. If Docker is not present, the drill is skipped. Disabled by env.

Env knobs:

```
CHAOS_ENABLED=true
CHAOS_MAX_DURATION_SEC=120
CHAOS_TARGETS=["vector","memory"]
CHAOS_DRY_RUN=false
```

Manual run:

```
python -m chaos.drills --once --target vector --duration 60
```

Behavior:
- Emits Cockpit signals:
  - `chaos.drill.began {target,duration}`
  - `chaos.drill.ended {target,ok}`
- If Docker is unavailable, logs and emits `drill.skipped`.
- Use `CHAOS_DRY_RUN=true` to validate signaling without pausing containers.

Scheduling:
- Prefer staging. In prod, start with short durations (≤15s) during low-traffic windows.
- Ensure breakers and degraded paths are healthy before enabling.

#### Nightly Canary Evaluation

- Purpose: detect retrieval drift/regressions by computing recall@k on a fixed canary set.
- Source: dataset loaded via `retrieval/canary.py` JSONL loader.

Env knobs:

```
CANARY_CI_ENABLED=true
CANARY_DATASET=canaries/default.jsonl
CANARY_RECALL_AT=10
CANARY_ALERT_DROP=0.05
```

Manual run:

```
python -m ci.nightly_canary --dataset canaries/default.jsonl --k 10
```

Behavior:
- Runs retrieval (hybrid if enabled) and measures recall@k.
- Compares to last baseline (`ci/last_canary.json`), emits Cockpit signals:
  - `ci.canary.recall_at_k {recall,k,n}`
  - `ci.canary.delta {delta,baseline}`
- If drop exceeds `CANARY_ALERT_DROP`, a Discord alert is raised via Cockpit.
- Read-only: does not mutate data or configs.

#### Cockpit Observability

- Aggregator exposes under:
  - `chaos`: `{ "last_drill": {...} }`
  - `ci`: `{ "canary": { "recall": <float>, "delta": <float> } }`
- Optional gauges exported:
  - `cockpit.chaos.last_duration_sec`
  - `cockpit.ci.canary_recall`
  - `cockpit.ci.canary_delta`

#### Operational Safety

- Chaos is disabled by default and fails closed when Docker is absent.
- Canary CI is read-only and safe for prod; schedule nightly.
- Keep canary datasets stable; update baseline only after intentional improvements.

