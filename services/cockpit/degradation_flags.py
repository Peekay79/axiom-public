from __future__ import annotations

from typing import Dict, Any


def compute_degradation(status_json: Dict[str, Any]) -> Dict[str, bool]:
    pods = status_json.get("pods", {}) or {}
    vector_blackout = bool(status_json.get("vector_blackout_active"))
    recall_degraded = bool(status_json.get("recall_degraded"))
    mem_blocked = int(status_json.get("blocked_writes_by_role", 0) or 0) > 0
    belief_ready = bool(pods.get("belief", {}).get("ready")) and bool(
        pods.get("belief", {}).get("heartbeat_ok")
    )
    journal_ready = bool(pods.get("journal", {}).get("ready")) and bool(
        pods.get("journal", {}).get("heartbeat_ok")
    )
    belief_unready = not belief_ready
    journal_unready = not journal_ready
    # New flags
    startup_slow_any = bool(status_json.get("startup_slow_any"))
    schema_drift_active = int(status_json.get("schema_normalization_events", 0) or 0) > 0

    cognitive_ok = not (
        vector_blackout
        or recall_degraded
        or mem_blocked
        or belief_unready
        or journal_unready
        or startup_slow_any
        or schema_drift_active
    )

    flags = {
        "vector_blackout_active": vector_blackout,
        "recall_degraded": recall_degraded,
        "memory_persistence_blocked": mem_blocked,
        "belief_pipeline_unready": belief_unready,
        "journal_pipeline_unready": journal_unready,
        "startup_slow_any": startup_slow_any,
        "memory_schema_drift_active": schema_drift_active,
        "cognitive_ok": cognitive_ok,
    }

    # Optional soft flags for Governor (do not flip cognitive_ok by default)
    try:
        gov = status_json.get("governor", {}) or {}
        cv = gov.get("contract_violations", {}) or {}
        flags["contracts_weak"] = bool(
            int(cv.get("missing_correlation_id", 0) or 0) > 0
            or int(cv.get("missing_idempotency_key", 0) or 0) > 0
        )
    except Exception:
        flags["contracts_weak"] = False

    # Reserved future: retrieval_recall_low (soft)
    flags["retrieval_recall_low"] = False

    return flags

