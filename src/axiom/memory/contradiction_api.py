from __future__ import annotations

"""
Public facade for contradiction features in the memory subsystem.

Import-safe pass-throughs: each symbol is guarded so that importing this
module never raises if optional modules are missing. Callers should
check for None or wrap usage in try/except.
"""

# Core detection (async in most builds)
try:  # pragma: no cover - import guard
    from .belief_engine import (
        detect_contradictions_pairwise as detect_pairwise,  # type: ignore
    )
except Exception:  # pragma: no cover
    detect_pairwise = None  # type: ignore

# Resolution suggestion
try:  # pragma: no cover - import guard
    from .contradiction_resolver import (
        suggest_contradiction_resolution as suggest_resolution,  # type: ignore
    )
except Exception:  # pragma: no cover
    suggest_resolution = None  # type: ignore

# Resolution application
try:  # pragma: no cover - import guard
    from .contradiction_applier import (
        apply_contradiction_resolution as apply_resolution,  # type: ignore
    )
except Exception:  # pragma: no cover
    apply_resolution = None  # type: ignore

# Monitoring and operations
try:  # pragma: no cover - import guard
    from .contradiction_monitor import (
        get_all_contradictions,
        schedule_contradiction_retest as schedule_retest,  # type: ignore
        retest_unresolved_contradictions as retest_unresolved,  # type: ignore
        narrate_contradiction_story as narrate_story,  # type: ignore
        export_contradiction_graph as export_graph,  # type: ignore
        log_contradiction_nag as nag_summary,  # type: ignore
        cluster_contradictions_by_theme as cluster_by_theme,  # if present
        prioritize_contradictions_by_emotion as prioritize_by_emotion,  # if present
        log_contradiction_outcome as log_outcome,  # if present
    )
except Exception:  # pragma: no cover
    get_all_contradictions = None  # type: ignore
    schedule_retest = None  # type: ignore
    retest_unresolved = None  # type: ignore
    narrate_story = None  # type: ignore
    export_graph = None  # type: ignore
    nag_summary = None  # type: ignore
    cluster_by_theme = None  # type: ignore
    prioritize_by_emotion = None  # type: ignore
    log_outcome = None  # type: ignore

# Safety checks
try:  # pragma: no cover - import guard
    from .contradiction_safety import (
        contradiction_safety_check as safety_check,  # type: ignore
    )
except Exception:  # pragma: no cover
    safety_check = None  # type: ignore

# Boot tasks
try:  # pragma: no cover - import guard
    from .boot_tasks import (
        contradiction_boot_sweep as boot_sweep,  # type: ignore
    )
except Exception:  # pragma: no cover
    boot_sweep = None  # type: ignore


__all__ = [
    # Core flow
    "detect_pairwise",
    "suggest_resolution",
    "apply_resolution",
    # Monitoring / ops
    "get_all_contradictions",
    "schedule_retest",
    "retest_unresolved",
    "narrate_story",
    "export_graph",
    "nag_summary",
    # Optional extras (exposed if present)
    "cluster_by_theme",
    "prioritize_by_emotion",
    "log_outcome",
    # Safety & boot
    "safety_check",
    "boot_sweep",
]

