#!/usr/bin/env python3
# AUDIT: Contradiction Pipeline – contradiction_safety.py
# - Purpose: Emit safety warnings for backlog size and staleness.
# - Findings:
#   - ✅ Async usage: awaits internal loader correctly.
#   - ⚠️ Timestamp parsing overlaps with monitor/dashboard; centralize helper to avoid drift.
#   - ⚠️ Thresholds: backlog>50 and age>7d hard-coded; consider config/env.
#   - Cleanup target: emit structured fields (e.g., oldest_iso), include 'source' consistently.
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from memory.utils.journal import safe_log_event
from memory.utils.time_utils import utc_now_iso
from memory.utils.contradiction_utils import resolve_conflict_timestamp
from memory.utils.config import get_env_int


# DEPRECATED: use safe_log_event({...}, default_source="contradiction_safety") directly
def _safe_log(event: Dict[str, Any]) -> None:
    safe_log_event(event, default_source="contradiction_safety")


async def _load_unresolved_best_effort() -> List[Dict[str, Any]]:
    # Prefer the monitor's public getter if available
    try:
        from memory.contradiction_monitor import get_all_contradictions  # type: ignore

        # ASYNC-AUDIT: wrap potentially blocking Memory().load() path in to_thread
        records = await asyncio.to_thread(get_all_contradictions)
        return [c for c in records if str(c.get("resolution", "pending")) == "pending"]
    except Exception:
        return []


# DEPRECATED: local timestamp parsing; prefer resolve_conflict_timestamp()
def _parse_any_timestamp(conflict: Dict[str, Any]) -> Optional[datetime]:
    try:
        return resolve_conflict_timestamp(conflict)
    except Exception:
        return None


async def contradiction_safety_check() -> None:
    """Emit warnings for backlog size and stale unresolved contradictions."""
    unresolved = await _load_unresolved_best_effort()
    if not unresolved:
        return

    # Thresholds via environment variables with sensible defaults
    # ASYNC-AUDIT: Config moved to typed loader with alias support
    backlog_warn = get_env_int("AXIOM_CONTRADICTION_BACKLOG_WARNING", 50)
    staleness_days = get_env_int("AXIOM_CONTRADICTION_STALENESS_DAYS", 7)

    # High backlog warning
    if len(unresolved) > backlog_warn:
        _safe_log(
            {
                "type": "contradiction_safety_warning",
                "message": "High volume of unresolved contradictions detected.",
                "count": len(unresolved),
                "threshold": backlog_warn,
                "created_at": utc_now_iso(),  # AUDIT_OK
            }
        )

    # Staleness warning (> staleness_days)
    now = datetime.now(timezone.utc)
    aged = []
    threshold = now - timedelta(days=staleness_days)
    for c in unresolved:
        when = _parse_any_timestamp(c)
        if when and when < threshold:
            aged.append(c)

    if aged:
        _safe_log(
            {
                "type": "contradiction_staleness_warning",
                "message": f"{len(aged)} contradictions unresolved >{staleness_days} days.",
                "count": len(aged),
                "threshold_days": staleness_days,
                "created_at": utc_now_iso(),  # AUDIT_OK
            }
        )


__all__ = ["contradiction_safety_check"]
