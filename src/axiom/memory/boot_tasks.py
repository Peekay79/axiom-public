#!/usr/bin/env python3
# AUDIT: Contradiction Pipeline – boot_tasks.py
# - Purpose: Boot-time sweep to schedule and retest contradictions; run metrics/safety/dream tasks.
# - Findings:
#   - ✅ Async: awaits retest and extended tasks; uses gather for fan-out.
#   - ⚠️ API divergence: retest_unresolved_contradictions called with and without args; only no-arg variant exists now.
#   - ⚠️ Private import: uses monitor._load_pending_contradictions_from_memory; prefer public list API.
#   - ⚠️ Event schema: logs 'contradiction_retest_scheduled' with count/threshold; align with monitor's fields.
#   - Cleanup target: fast_mode switch documented; consider passing hours_threshold for finer cadence.
from __future__ import annotations

"""
Boot-time tasks for the memory subsystem.

This module provides an additive, import-safe contradiction sweep that runs at
startup. It scans for unresolved contradictions (resolution == "pending"),
re-evaluates them with the current belief state, and journals outcomes using
the lightweight journal interface.
"""

import asyncio
from typing import Any, Dict, List

from memory.utils.time_utils import utc_now_iso

# Safe imports: prefer shimmed memory package and minimal journal
try:
    from memory.contradiction_monitor import (
        get_all_contradictions,
        log_contradiction_nag,
        narrate_contradiction_story,
        retest_unresolved_contradictions,
        schedule_contradiction_retest,
    )

    _HAS_CONTR_MON = True
except Exception:
    _HAS_CONTR_MON = False

from memory.utils.journal import safe_log_event

# Extended contradiction tasks (safe import)
try:
    from memory.contradiction_dashboard import generate_contradiction_metrics
    from memory.contradiction_dreamer import contradiction_dream_probe
    from memory.contradiction_safety import contradiction_safety_check

    _HAS_EXT_TASKS = True
except Exception:
    _HAS_EXT_TASKS = False


def _safe_log(event: Dict[str, Any]) -> None:
    safe_log_event(event, default_source="boot_tasks")


async def contradiction_boot_sweep(
    age_threshold_days: int = 3, *, fast_mode: bool = False
) -> None:
    """
    On startup, scan for unresolved contradictions.
    Re-test their validity with updated beliefs, and narrate results.
    """
    if not _HAS_CONTR_MON:
        _safe_log(
            {
                "type": "contradiction_retest_skipped",
                "reason": "contradiction_monitor_unavailable",
                "note": "Boot-time scan could not run",
            }
        )
        # Continue to extended tasks even if monitor is unavailable (unless fast mode)
        if not fast_mode:
            await run_extended_contradiction_tasks()
        return

    # Step 1: Load all pending from memory (best-effort)
    _candidates: List[Dict[str, Any]] = []
    try:
        _records = get_all_contradictions()  # type: ignore
        _candidates = [
            c
            for c in (_records or [])
            if str(c.get("resolution", "pending")) == "pending"
        ]
    except Exception:
        _candidates = []

    # Step 2: Schedule based on age threshold
    try:
        # schedule_contradiction_retest filters by age and pending state.
        # If we have no explicit candidates, pass an empty list which returns [].
        scheduled = schedule_contradiction_retest(
            _candidates, age_threshold=age_threshold_days
        )
    except Exception:
        scheduled = []

    _safe_log(
        {
            "type": "contradiction_retest_scheduled",
            "count": len(scheduled),
            "note": "Boot-time scan triggered",
            "threshold_days": age_threshold_days,
            "created_at": None,  # set in _safe_log
        }
    )

    # If nothing scheduled, skip re-test but still run extended tasks
    if scheduled:
        # Step 3: Re-test unresolved contradictions for the scheduled set
        try:
            # The retest helper in contradiction_monitor currently takes no args and will
            # retest all pending conflicts it can find. Use it, then narrate results.
            retest_results = await retest_unresolved_contradictions()
        except TypeError:
            # Backward compatibility: if a variant supports taking a list
            try:
                retest_results = await retest_unresolved_contradictions(scheduled)  # type: ignore
            except Exception:
                retest_results = []
        except Exception:
            retest_results = []

        for conflict in retest_results or []:
            try:
                story = narrate_contradiction_story(conflict)
                _safe_log(
                    {
                        "type": "contradiction_narrative",
                        "uuid": conflict.get("uuid"),
                        "story": story,
                        "created_at": None,  # set in _safe_log
                    }
                )
            except Exception:
                pass

    # Run extended tasks at the end of the boot sweep unless fast mode
    if not fast_mode:
        await run_extended_contradiction_tasks()


async def run_extended_contradiction_tasks() -> None:
    """Run additional background contradiction tasks concurrently (best-effort)."""
    if not _HAS_EXT_TASKS:
        return
    try:
        # Run metrics/safety/dream probes; also emit a daily nag from monitor when available
        tasks = [
            generate_contradiction_metrics(),
            contradiction_dream_probe(),
            contradiction_safety_check(),
        ]
        try:
            # log_contradiction_nag is imported conditionally with _HAS_CONTR_MON
            if _HAS_CONTR_MON:
                # Run nag in a background task once; do not mutate tasks list inside the task
                async def _nag():
                    try:
                        log_contradiction_nag()  # type: ignore
                    except Exception:
                        pass
                tasks.append(_nag())
        except Exception:
            pass
        await asyncio.gather(*tasks)
    except Exception:
        # Do not raise on boot
        pass


__all__ = ["contradiction_boot_sweep"]
