# Contradiction Pipeline (Phase 2)

This document describes the lightweight contradiction pipeline implemented under `memory/` as of the Phase 2 refactors. It supersedes legacy class-heavy designs for day-to-day inference.

## End-to-End Flow

- Detection: `memory/belief_engine.py`
  - New belief normalized to `Belief`
  - Compared pairwise against recent beliefs
  - Emits standardized events via `memory.utils.journal.safe_log_event`
  - Optionally attaches `proposed_resolution` using `memory/contradiction_resolver.py`
- Resolution suggestion: `memory/contradiction_resolver.py`
  - Strategies: `reframe`, `inhibit`, `flag_for_review`, `dream_resolution`
  - Returns a dict: `created_at`, `source`, `resolution_strategy`, `confidence`, `notes`, optional `reframed_belief` or `inhibit_belief_id`
- Application: `memory/contradiction_applier.py`
  - Applies suggestion best-effort and logs `contradiction_resolution_applied`
  - Annotates beliefs: `inhibited`, `reframed_from`, `needs_review`, or defers for `dream_resolution`
- Monitoring/Scheduling: `memory/contradiction_monitor.py`
  - Schedules retests for stale/pending conflicts
  - Exports graph, clusters conflicts, narrates stories, and logs outcomes
- Boot Sweep: `memory/boot_tasks.py`
  - Loads pending conflicts, schedules retests, runs extended tasks (metrics, safety, dream probe)

## Canonical Utilities

- Use `memory.utils.contradiction_utils.resolve_conflict_timestamp(conflict)` to resolve the canonical timestamp for scheduling, dashboards, and safety checks.
- Use `memory.utils.contradiction_utils.conflict_identity(conflict)` to derive a stable identity for logging and caches.

## Journal Event Schema (canonical fields)

All events are emitted through `safe_log_event(event, default_source=...)`, which ensures `uuid` and `created_at` and fills `source` if missing.

Common event types:
- `contradiction_detected`: `belief_1`, `belief_2`, `confidence`
- `contradiction_resolution_suggested`: `belief_1`, `belief_2`, `strategy`, `confidence`, `notes`
- `dream_contradiction_resolution_queued`: refs to beliefs
- `contradiction_resolution_applied`: `proposed_resolution`, `applied_resolution`
- `contradiction_retest_scheduled`: `count`, thresholds, per-item `conflict_id`
- `contradiction_retest`: `original`, `result`
- `contradiction_resolved` / `contradiction_unresolvable`: `conflict`, optional narrative
- `contradiction_clustered`: `summary` counts
- `contradiction_narrative` / `contradiction_chain_summary`: narrative text/summary
- `contradiction_metrics_report`: totals, frequent pairs, `oldest_unresolved`
- `contradiction_safety_warning`: backlog warning
- `contradiction_staleness_warning`: stale unresolved count

Notes:
- `safe_log_event` tolerates missing journal/logbook; events are best-effort and never raise.

## Belief Format and Coercion

- Canonical belief object: `memory/belief_engine.py:Belief`
- Utility: `memory/utils/belief_coercion.py:coerce_belief_dict(obj)` returns dict with keys:
  - `text`, `confidence` (0..1), `source`, `uuid`, `last_updated`, `polarity`, `scope`
- The resolver and applier use `coerce_belief_dict()` when handling belief-like inputs.

## Environment Variables

All contradiction/belief-related configuration is centralized via `memory/utils/config.py` for typed access. Deprecated aliases emit one-time warnings.

| Variable | Type | Default | Purpose | Aliases (DEPRECATED) |
|---|---|---|---|---|
| `AXIOM_BELIEF_ENGINE` | flag | `0` | Enable belief engine features in `belief_engine.py` | - |
| `AXIOM_BELIEF_TAGGER` | str | `heuristic` | Tagger mode for belief extraction/tagging | - |
| `AXIOM_CONTRADICTION_TAGGING` | flag | `0` | Enable contradiction tagging on beliefs | - |
| `AXIOM_ACTIVE_BELIEF_SEED` | str | `""` | Seed beliefs (split by `||`) to warm active cache | - |
| `AXIOM_BELIEF_REFRESH_SEC` | int | `0` | Override active belief refresh cadence seconds | - |
| `AXIOM_CONTRADICTION_BACKLOG_WARNING` | int | `50` | Safety warning threshold for unresolved backlog | - |
| `AXIOM_CONTRADICTION_STALENESS_DAYS` | int | `7` | Staleness threshold for unresolved contradictions | `STALENESS_DAYS` |

Notes:
- Access with `from memory.utils.config import get_env_flag, get_env_int, get_env_str`.
- Aliases like `STALENESS_DAYS` are supported but will log: "Env var 'STALENESS_DAYS' is DEPRECATED. Use 'AXIOM_CONTRADICTION_STALENESS_DAYS' instead."

## Boot-Time Sweep

- `memory/boot_tasks.py:contradiction_boot_sweep(age_threshold_days=3, fast_mode=False)`
  - Schedules retests using `schedule_contradiction_retest`
  - Runs `generate_contradiction_metrics`, `contradiction_dream_probe`, `contradiction_safety_check`

## Fallback Behavior

- Journal: `safe_log_event` no-ops if journal/logbook sinks absent.
- Resolver: if errors occur, detection proceeds; no exceptions are propagated.
- Speculative Simulation Module: `contradiction_dreamer` enqueues to Wonder only if available; otherwise only logs.

## Tests

- `tests/test_contradiction_applier.py`: strategy application behaviors
- `tests/test_contradiction_monitor.py`: scheduling, narration, graph export
- `test/test_contradictions.py`: end-to-end detection + suggestion + logging stub

Run focused tests:

```bash
PYTHONPATH=/workspace pytest -q tests/test_contradiction_applier.py tests/test_contradiction_monitor.py test/test_contradictions.py
```

### Public API Facade

Prefer importing contradiction features via the facade:

```python
from memory.contradiction_api import detect_pairwise, suggest_resolution, apply_resolution

# example (pseudo):
# conflicts = await detect_pairwise(new_belief, recent_beliefs, cfg)
# for c in conflicts:
#     res = suggest_resolution(c["belief_1"], c["belief_2"])  # adjust to your schema
#     apply_resolution({**c, "proposed_resolution": res})
```

Monitoring/safety/ops are also available:

```python
from memory.contradiction_api import get_all_contradictions, schedule_retest, safety_check
```

The facade is import-safe; symbols may be None if an optional module is disabled.




h---

## Phase 2 Wrap-Up — Professor’s Sign-Off

The contradiction pipeline has been reviewed end-to-end and is considered **Phase 2 complete and production-ready**.  

### Findings
- **Workflow integrity:** Detection → Suggestion → Application → Monitoring → Boot sweep all function as intended, with import-safe guards.  
- **Utilities:** Canonical helpers (`resolve_conflict_timestamp`, `conflict_identity`) centralize timestamp and identity resolution; adopted in monitor, dashboard, and safety.  
- **Logging:** All events journaled via `safe_log_event`, which guarantees `uuid`, `created_at` (UTC), and `source`. Journal injection works for tests.  
- **API Surface:** `memory/contradiction_api.py` provides a stable facade; symbols are import-guarded and re-exported via `__init__.py`.  
- **Tests:** Focused suite (13/13) passes, covering detection, resolution, application, monitoring, and utilities.  
- **Docs:** Updated with Phase 2 pipeline overview, facade usage, canonical utilities, and environment variables.  
- **Hygiene:** No undefined variables or dangling imports; async handling is correct; optional subsystems (e.g. Wonder engine) are guarded.

### Non-blocking improvements (future work)
- Remove or consolidate legacy DEPRECATED timestamp helpers.  
- Add a minimal journal-capture test to assert schema adherence.  
- Add a smoke test for `detect_pairwise` via the facade (complements existing apply-resolution smoke).

### Conclusion
The system is consistent, resilient, and extensible. The Phase 2 pipeline can be considered stable for continued development and safe to expose via the public API facade.  

*— External Audit, Professor’s Report (August 2025)*
