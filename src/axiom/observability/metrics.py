#!/usr/bin/env python3
"""
Lightweight in-memory metrics (no external deps).

API:
- inc(name: str) -> None
- observe_ms(name: str, ms: float) -> None
- snapshot() -> { "counters": {name: int}, "timers": { name: {count,p50,p95} } }

Implementation keeps a bounded list per timer (max 256 samples) for percentiles.
Thread-safety is best-effort with a simple lock; precision is not critical.
"""

from __future__ import annotations

import threading
from typing import Dict, List

_COUNTERS: Dict[str, int] = {}
_TIMERS: Dict[str, List[float]] = {}
_LOCK = threading.Lock()
_MAX_SAMPLES = 256


def inc(name: str, value: int = 1) -> None:
    if not isinstance(name, str) or not name:
        return
    with _LOCK:
        _COUNTERS[name] = _COUNTERS.get(name, 0) + int(value)


def observe_ms(name: str, ms: float) -> None:
    if not isinstance(name, str) or not name:
        return
    try:
        v = float(ms)
    except Exception:
        return
    with _LOCK:
        arr = _TIMERS.get(name)
        if arr is None:
            arr = []
            _TIMERS[name] = arr
        arr.append(v)
        # Bounded buffer
        if len(arr) > _MAX_SAMPLES:
            # drop oldest 25% to avoid frequent shifting
            drop = max(1, _MAX_SAMPLES // 4)
            del arr[:drop]


# --- Convenience helpers for common GUT metrics (no-op if unused) ---

def inc_gut_belief_created() -> None:
    inc("gut.beliefs_created")


def inc_gut_contradiction_logged() -> None:
    inc("gut.contradictions_logged")


def inc_gut_dream_enqueued() -> None:
    inc("gut.dreams_enqueued")


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


def snapshot() -> Dict[str, object]:
    with _LOCK:
        counters = dict(_COUNTERS)
        timers_out: Dict[str, Dict[str, float]] = {}
        for name, vals in _TIMERS.items():
            if not vals:
                timers_out[name] = {"count": 0, "p50": 0.0, "p95": 0.0}
                continue
            s = sorted(vals)
            timers_out[name] = {
                "count": len(vals),
                "p50": round(_percentile(s, 0.50), 3),
                "p95": round(_percentile(s, 0.95), 3),
            }
        return {"counters": counters, "timers": timers_out}

