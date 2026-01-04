#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Dict


def _safe_float(value: Any, default: float = 0.5) -> float:
    try:
        x = float(value)
        # clamp 0..1
        if x < 0.0:
            return 0.0
        if x > 1.0:
            return 1.0
        return x
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def coerce_belief_dict(obj: Any) -> Dict[str, Any]:
    """Best-effort normalize a belief-like object to a dict.

    Returned keys include: text, confidence, source, uuid, last_updated, polarity, scope.
    """
    # Extract fields from object or dict
    try:
        text = getattr(obj, "text", None)
        if text is None and isinstance(obj, dict):
            text = obj.get("text") or obj.get("statement")
    except Exception:
        text = None

    try:
        confidence = getattr(obj, "confidence", None)
        if confidence is None and isinstance(obj, dict):
            confidence = obj.get("confidence")
    except Exception:
        confidence = None

    try:
        source = getattr(obj, "source", None)
        if source is None and isinstance(obj, dict):
            source = obj.get("source") or obj.get("provenance")
    except Exception:
        source = None

    try:
        uuid = getattr(obj, "uuid", None)
        if uuid is None and isinstance(obj, dict):
            uuid = obj.get("uuid") or obj.get("id")
    except Exception:
        uuid = None

    try:
        last_updated = getattr(obj, "last_updated", None)
        if last_updated is None and isinstance(obj, dict):
            last_updated = obj.get("last_updated") or obj.get("updated_at")
    except Exception:
        last_updated = None

    try:
        polarity = getattr(obj, "polarity", None)
        if polarity is None and isinstance(obj, dict):
            polarity = obj.get("polarity")
    except Exception:
        polarity = None

    try:
        scope = getattr(obj, "scope", None)
        if scope is None and isinstance(obj, dict):
            scope = obj.get("scope")
    except Exception:
        scope = None

    return {
        "text": (text or "").strip(),
        "confidence": _safe_float(confidence, default=0.5),
        "source": (source or "").strip() or None,
        "uuid": uuid or None,
        "last_updated": last_updated or None,
        "polarity": _safe_int(polarity, default=0),
        "scope": (scope or "").strip() or None,
    }


__all__ = ["coerce_belief_dict"]
