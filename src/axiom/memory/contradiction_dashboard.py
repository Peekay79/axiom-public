#!/usr/bin/env python3
# AUDIT: Contradiction Pipeline – contradiction_dashboard.py
# - Purpose: Load conflicts and emit aggregate metrics for dashboards.
# - Findings:
#   - ✅ Async usage: awaits _load_all_contradictions_best_effort in metrics.
#   - ⚠️ Private import: uses monitor._load_pending_contradictions_from_memory; consider a public list API.
#   - ⚠️ Schema variance: pair key derivation mixes 'key' and 'belief_key'; document canonical.
#   - ⚠️ Timestamp parsing overlaps monitor; centralize helper to avoid drift.
#   - Cleanup target: add filtering options (theme, key) and align with monitor.narrate API.
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from memory.utils.journal import safe_log_event
from memory.utils.time_utils import utc_now_iso
from memory.utils.contradiction_utils import resolve_conflict_timestamp

# Optional imports guarded for safety
try:
    from memory.contradiction_monitor import schedule_contradiction_retest  # noqa: F401
except Exception:
    pass


# DEPRECATED: use safe_log_event({...}, default_source="contradiction_dashboard") directly
def _safe_log(event: Dict[str, Any]) -> None:
    safe_log_event(event, default_source="contradiction_dashboard")


async def _load_all_contradictions_best_effort() -> List[Dict[str, Any]]:
    """Best-effort loader for contradiction records.

    Attempts to pull conflicts from the Memory store via the contradiction monitor's
    public getter. Falls back to scanning the Memory snapshot for common shapes.
    This is intentionally defensive and will never raise.
    """
    # Prefer using the monitor's public getter if available
    try:
        from memory.contradiction_monitor import get_all_contradictions  # type: ignore

        # ASYNC-AUDIT: wrap potentially blocking Memory().load() path in to_thread
        return list(await asyncio.to_thread(get_all_contradictions) or [])
    except Exception:
        pass

    # Fallback: try pods memory snapshot and search for contradiction-like entries
    try:
        from pods.memory.memory_manager import Memory  # type: ignore

        mem = Memory()
        # ASYNC-AUDIT: avoid blocking the loop on IO-bound load
        await asyncio.to_thread(mem.load)
        records: List[Dict[str, Any]] = []
        for m in mem.long_term_memory:
            # Common containers used elsewhere in the codebase
            if isinstance(m, dict):
                conflicts = m.get("conflicts") or m.get("detected_contradictions") or []
                if conflicts and isinstance(conflicts, list):
                    for c in conflicts:
                        if isinstance(c, dict):
                            records.append(c)
        return records
    except Exception:
        return []


def _pair_key(conflict: Dict[str, Any]) -> Tuple[str, str]:
    def _k(side: str) -> str:
        meta = conflict.get(f"{side}_meta") or {}
        key = meta.get("key") or meta.get("belief_key")
        if isinstance(key, str) and key.strip():
            return key.strip()
        # Fallback to text hash prefix for stability if no explicit key
        text = (conflict.get(f"belief_{side[-1]}") or "").strip()
        return text[:40] if text else side

    # Normalize ordering to count A/B pairs consistently
    a_k = _k("belief_a")
    b_k = _k("belief_b")
    return (a_k, b_k) if a_k <= b_k else (b_k, a_k)


async def generate_contradiction_metrics() -> None:
    """Compute and emit high-level contradiction metrics.

    Emits a journal event of type "contradiction_metrics_report" with fields:
    - total, resolved, unresolved, frequent_conflicts, oldest_unresolved
    """
    conflicts = await _load_all_contradictions_best_effort()
    total = len(conflicts)
    unresolved = [
        c for c in conflicts if str(c.get("resolution", "pending")) == "pending"
    ]
    resolved = total - len(unresolved)
    # Count frequent conflict key pairs (best-effort)
    pairs = Counter(_pair_key(c) for c in conflicts)

    # Determine oldest unresolved by canonical helper
    # DEPRECATED: local timestamp parsing; prefer resolve_conflict_timestamp()
    def _parse_ts(c: Dict[str, Any]):
        return resolve_conflict_timestamp(c)

    oldest_dt = None
    for c in unresolved:
        when = _parse_ts(c)
        if when and (oldest_dt is None or when < oldest_dt):
            oldest_dt = when

    oldest_iso = oldest_dt.isoformat() if oldest_dt else None

    _safe_log(
        {
            "type": "contradiction_metrics_report",
            "total": total,
            "resolved": resolved,
            "unresolved": len(unresolved),
            "frequent_conflicts": pairs.most_common(5),
            "oldest_unresolved": oldest_iso,
            "created_at": None,  # set in _safe_log
        }
    )


__all__ = ["generate_contradiction_metrics"]


def narrate_contradiction_chain_dashboard(
    *,
    for_belief_key: Optional[str] = None,
    for_theme: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Proxy to monitor.narrate_contradiction_chain for dashboard consumers (safe import)."""
    try:
        from memory.contradiction_monitor import (
            narrate_contradiction_chain,  # type: ignore
        )

        return narrate_contradiction_chain(
            for_belief_key=for_belief_key, for_theme=for_theme, limit=limit
        )
    except Exception:
        return ""
