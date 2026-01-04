#!/usr/bin/env python3
from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any, Dict


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, str(default))).strip())
    except Exception:
        return float(default)


WEIGHTS = {
    "RECENCY": _env_float("CONTEXT_WEIGHTS_RECENCY", 0.35),
    "SALIENCE": _env_float("CONTEXT_WEIGHTS_SALIENCE", 0.35),
    "TRUST": _env_float("CONTEXT_WEIGHTS_TRUST", 0.20),
    "DIVERSITY": _env_float("CONTEXT_WEIGHTS_DIVERSITY", 0.10),
}


def recency_score(ts_iso: str | None, half_life_days: float = 14.0) -> float:
    if not ts_iso:
        return 0.5
    try:
        t = datetime.fromisoformat(ts_iso)
        if not t.tzinfo:
            t = t.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 86400.0)
        lam = math.log(2.0) / float(max(0.1, half_life_days))
        return float(math.exp(-lam * age_days))
    except Exception:
        return 0.5


def salience_score(item: Dict[str, Any]) -> float:
    imp = float(item.get("importance") or 0.5)
    conf = float(item.get("confidence") or 0.5)
    return max(0.0, min(1.0, 0.6 * imp + 0.4 * conf))


def trust_score(item: Dict[str, Any]) -> float:
    if item.get("quarantined"):
        return 0.0
    src = str(item.get("source") or item.get("origin") or "").lower()
    base = 0.5
    if src in {"user", "external", "web"}:
        base += 0.2
    if src in {"model", "self", "llm"}:
        base -= 0.1
    return max(0.0, min(1.0, base))


def diversity_key(item: Dict[str, Any]) -> str:
    # Topic/source based key; keep simple
    tags = item.get("tags") or []
    src = str(item.get("source") or item.get("origin") or "").lower()
    topic = None
    for t in tags:
        if isinstance(t, str) and t:
            topic = t
            break
    return f"{src or 'unknown'}::{topic or 'general'}"


def score(item: Dict[str, Any], now_iso: str | None = None) -> float:
    r = recency_score(item.get("updated_at") or item.get("timestamp") or None)
    s = salience_score(item)
    t = trust_score(item)
    # diversity score is used as a bucket spread; include a small term to encourage spread
    d = 1.0
    return float(WEIGHTS["RECENCY"] * r + WEIGHTS["SALIENCE"] * s + WEIGHTS["TRUST"] * t + WEIGHTS["DIVERSITY"] * 0.1 * d)


__all__ = ["score", "diversity_key", "recency_score", "salience_score", "trust_score", "WEIGHTS"]

