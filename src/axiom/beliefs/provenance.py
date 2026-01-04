#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Dict, List


def _normalize_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": "external", "ref": str(item), "weight": 1.0}
    # Preserve existing keys (e.g., ts) and normalize core fields on top
    out: Dict[str, Any] = dict(item)
    t = item.get("type")
    if t not in ("journal", "external"):
        # best-effort coercion from hints
        if "doi" in item or "url" in item:
            t = "external"
        elif "id" in item or "journal_id" in item:
            t = "journal"
        else:
            t = "external"
    out["type"] = t

    # Reference field: prefer 'ref', then specific keys
    ref = item.get("ref")
    if not ref:
        ref = item.get("doi") or item.get("url") or item.get("id") or item.get("journal_id")
    out["ref"] = str(ref) if ref is not None else ""

    # Optional weight
    try:
        w = float(item.get("weight", 1.0))
    except Exception:
        w = 1.0
    out["weight"] = max(0.0, w)
    return out


def normalize_provenance(p: Any) -> List[Dict[str, Any]]:
    """
    Normalize arbitrary provenance payload into a list of dict items with
    minimal schema: {type: journal|external, ref: str, weight: float}
    """
    if p in (None, "", {}, []):
        return []
    if not isinstance(p, list):
        p = [p]
    out: List[Dict[str, Any]] = []
    for item in p:
        norm = _normalize_item(item)
        # Skip entries without a reference
        if norm.get("ref"):
            out.append(norm)
    return out


def has_external_evidence(prov: Any) -> bool:
    """
    Return True if any provenance item is of type 'external' and has a ref.
    """
    items = normalize_provenance(prov)
    for it in items:
        if it.get("type") == "external" and bool(it.get("ref")):
            return True
    return False

