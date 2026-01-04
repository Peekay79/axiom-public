#!/usr/bin/env python3
from __future__ import annotations

"""Canonical helpers for contradiction records.

Phase 2 standardizes conflict identity and timestamp resolution across
monitor/dashboard/safety components. These helpers are intentionally
pure and dependency-light.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import hashlib
import json

from memory.utils.time_utils import parse_timestamp


def resolve_conflict_timestamp(conflict: Dict[str, Any]) -> datetime:
    """Return the best-effort originating timestamp for a conflict.

    Preference order (first match wins):
      1) conflict["timestamp"|"detected_at"|"created_at"|"logged_at"|"observed_at"]
      2) conflict["last_attempt_at"|"retested_at"|"resolved_at"]
      3) conflict["belief_a_meta"|"belief_b_meta"]["last_updated"|"created_at"]

    Always returns an aware UTC datetime. Falls back to epoch.
    """
    # Primary conflict-level fields
    for key in (
        "timestamp",
        "detected_at",
        "created_at",
        "logged_at",
        "observed_at",
    ):
        val = conflict.get(key)
        if val:
            return parse_timestamp(val)

    # Resolution-related timestamps
    for key in ("last_attempt_at", "retested_at", "resolved_at"):
        val = conflict.get(key)
        if val:
            return parse_timestamp(val)

    # Embedded belief metadata
    try:
        a_meta = conflict.get("belief_a_meta") or {}
        b_meta = conflict.get("belief_b_meta") or {}
        for k in ("last_updated", "created_at"):
            if a_meta.get(k):
                return parse_timestamp(a_meta.get(k))
            if b_meta.get(k):
                return parse_timestamp(b_meta.get(k))
    except Exception:
        pass

    # Epoch fallback
    return datetime.fromtimestamp(0, tz=timezone.utc)


def conflict_identity(conflict: Dict[str, Any]) -> str:
    """Return a stable identifier for a contradiction record.

    Preference order:
      - explicit conflict["uuid"|"id"]
      - a/b-side metadata uuid/id/belief_uuid with side tag ("a:"/"b:")
      - hash of normalized belief_a/b text (order-insensitive)
      - hash of full record as JSON (sorted keys)
      - process-unique fallback using id()
    """
    try:
        uid = str(conflict.get("uuid") or conflict.get("id") or "").strip()
        if uid:
            return uid

        a_meta = conflict.get("belief_a_meta") or {}
        b_meta = conflict.get("belief_b_meta") or {}
        for k in ("uuid", "id", "belief_uuid"):
            if a_meta.get(k):
                return f"a:{a_meta.get(k)}"
            if b_meta.get(k):
                return f"b:{b_meta.get(k)}"

        a_text = (conflict.get("belief_a") or "").strip()
        b_text = (conflict.get("belief_b") or "").strip()
        if a_text or b_text:
            combo = "|".join(sorted([a_text, b_text]))
            return "h:" + hashlib.sha1(combo.encode("utf-8")).hexdigest()[:16]

        # As a last structured attempt, hash the JSON form
        return "h:" + hashlib.sha1(
            json.dumps(conflict, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
    except Exception:
        # Absolute fallback to a process-unique marker
        return f"anon:{id(conflict)}"


__all__ = ["resolve_conflict_timestamp", "conflict_identity"]

