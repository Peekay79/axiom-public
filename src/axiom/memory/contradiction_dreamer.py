#!/usr/bin/env python3
# AUDIT: Contradiction Pipeline – contradiction_dreamer.py
# - Purpose: Select unresolved conflicts and emit a dream probe; optional Wonder integration.
# - Findings:
#   - ✅ Async calls: awaits internal loader as expected.
#   - ⚠️ Private import: uses monitor._load_pending_contradictions_from_memory; request public list API.
#   - ⚠️ Schema: emits journal event {type, prompt, uuid}; ensure downstream dreamer reads same shape.
#   - Cleanup target: rate-limit or dedupe probes; add tags/context fields consistently with journal schema.
from __future__ import annotations

from random import choice
import asyncio
from typing import Any, Dict, List

from memory.utils.journal import safe_log_event

# Optional Wonder Engine import (graceful fallback if unavailable)
try:
    import wonder_engine as _wonder_engine  # type: ignore

    _HAS_WONDER = hasattr(_wonder_engine, "enqueue_dream_conflict")
except Exception:
    _HAS_WONDER = False
    _wonder_engine = None  # type: ignore


def _safe_log(event: Dict[str, Any]) -> None:
    safe_log_event(event, default_source="contradiction_dreamer")


async def _load_unresolved_best_effort() -> List[Dict[str, Any]]:
    try:
        from memory.contradiction_monitor import get_all_contradictions  # type: ignore

        # ASYNC-AUDIT: wrap potentially blocking Memory().load() path in to_thread
        records = await asyncio.to_thread(get_all_contradictions)
        return [c for c in records if str(c.get("resolution", "pending")) == "pending"]
    except Exception:
        return []


async def contradiction_dream_probe() -> None:
    """Emit a dream probe prompt for a randomly selected unresolved contradiction."""
    unresolved = await _load_unresolved_best_effort()
    if not unresolved:
        return

    selected = choice(unresolved)
    belief_a = selected.get("belief_a", "")
    belief_b = selected.get("belief_b", "")
    probe = {
        "type": "dream_contradiction_probe",
        "prompt": (
            "Simulate a scenario where both of these beliefs could be tested:\n"
            f"A: {belief_a}\nB: {belief_b}"
        ),
        "uuid": selected.get("uuid") or selected.get("id") or None,
        # created_at is set in _safe_log
    }
    _safe_log(probe)

    # Optionally enqueue directly to Wonder Engine if available; never fail boot on errors
    try:
        if _HAS_WONDER and hasattr(_wonder_engine, "enqueue_dream_conflict"):
            # Pass the full contradiction object if possible, with an optional context string
            context_str = probe.get("prompt") or "dream_probe"
            _wonder_engine.enqueue_dream_conflict(selected, context=context_str)  # type: ignore[attr-defined]
    except Exception:
        # Graceful fallback: journaling already performed above
        pass


__all__ = ["contradiction_dream_probe"]
