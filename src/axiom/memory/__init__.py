"""Compatibility shim: route `memory.*` to both `pods.memory.*` and local `memory/*`.

AUDIT: Contradiction Pipeline – memory/__init__.py
- Purpose: Shim and re-export convenience helpers from contradiction_monitor.
- Findings:
- ⚠️ Export set omits belief_engine helpers used elsewhere (e.g., detect_contradictions_pairwise).
- ⚠️ No __all__ for dreamer/dashboard/safety public APIs; consider curated exports for stability.
- Cleanup target: add stable public surface for contradiction pipeline to reduce private imports.
"""

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_THIS = Path(__file__).resolve().parent
_REAL = _ROOT / "pods" / "memory"

# Search in pods/memory first, then local memory/
__path__ = [str(_REAL), str(_THIS)]
__package__ = __name__

# If pods.memory exists, alias it as 'memory' (harmless if missing)
try:
    pm = importlib.import_module("pods.memory")
    sys.modules.setdefault("memory", pm)
except Exception:
    pass


def __repr__():
    return f"<shim package 'memory' -> [{str(_REAL)}, {str(_THIS)}]>"


# Re-export selected helpers for convenience
try:
    from .belief_engine import (  # type: ignore
        as_belief,
        detect_contradictions,
        detect_contradictions_pairwise,
    )
    from .contradiction_dreamer import contradiction_dream_probe  # type: ignore
    from .contradiction_monitor import (  # type: ignore
        cluster_contradictions_by_theme,
        export_contradiction_graph,
        log_contradiction_nag,
        log_contradiction_outcome,
        narrate_contradiction_chain,
        narrate_contradiction_story,
        prioritize_contradictions_by_emotion,
        schedule_contradiction_retest,
    )
    from .contradiction_resolver import suggest_contradiction_resolution  # type: ignore

    __all__ = [
        "cluster_contradictions_by_theme",
        "log_contradiction_outcome",
        "prioritize_contradictions_by_emotion",
        "schedule_contradiction_retest",
        "export_contradiction_graph",
        "narrate_contradiction_story",
        "log_contradiction_nag",
        "narrate_contradiction_chain",
        # Public API hygiene additions
        "contradiction_dream_probe",
        "detect_contradictions",
        "detect_contradictions_pairwise",
        "as_belief",
        "suggest_contradiction_resolution",
    ]
except Exception:
    # Keep module import-safe even if local implementations are missing
    __all__ = []

# Public facade re-exports (safe, import-guarded)
try:
    from .contradiction_api import (
        detect_pairwise,
        suggest_resolution,
        apply_resolution,
        get_all_contradictions,
        schedule_retest,
        retest_unresolved,
        narrate_story,
        export_graph,
        nag_summary,
        cluster_by_theme,
        prioritize_by_emotion,
        log_outcome,
        safety_check,
        boot_sweep,
    )

    __all__ += [
        "detect_pairwise",
        "suggest_resolution",
        "apply_resolution",
        "get_all_contradictions",
        "schedule_retest",
        "retest_unresolved",
        "narrate_story",
        "export_graph",
        "nag_summary",
        "cluster_by_theme",
        "prioritize_by_emotion",
        "log_outcome",
        "safety_check",
        "boot_sweep",
    ]
except Exception:
    pass
