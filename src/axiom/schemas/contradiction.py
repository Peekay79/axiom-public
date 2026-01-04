#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Dict, Any
import uuid
from datetime import datetime, timezone


@dataclass
class Contradiction:
    conflict_id: str                 # uuid4 hex if missing
    subject_id: Optional[str]        # entity/doc id if known
    claim: str                       # human text of the claim
    predicate: Optional[str] = None  # optional relation name
    observed_at: str = ""            # ISO8601
    logged_at: str = ""              # ISO8601 (now() if missing)
    resolved_at: Optional[str] = None
    status: str = "open"             # open|resolved|ignored
    confidence: float = 1.0          # 0..1 clamped
    source: str = "unknown"
    tags: List[str] = None           # [] if missing
    schema_version: int = 1


_TS_KEYS_OBS = {"timestamp", "detected_at", "created_at", "observed_at"}
_TS_KEYS_LOG = {"logged_at", "created_at"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_iso(val: Any) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(float(val), tz=timezone.utc).isoformat()
        except Exception:
            return None
    if isinstance(val, str):
        # Best-effort: return if looks like ISO or a parseable string; avoid strict parsing to keep no-raise contract
        return val
    return None


def _coerce_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None]
    # scalar -> list
    return [str(value)]


def _uuid_hex() -> str:
    return uuid.uuid4().hex


def normalize(payload: Dict[str, Any]) -> Tuple[Optional[Contradiction], List[str]]:
    warnings: List[str] = []

    try:
        if not isinstance(payload, dict):
            return None, ["payload_not_dict"]

        # Required field: claim
        claim = payload.get("claim") or payload.get("statement") or payload.get("text")
        if not isinstance(claim, str) or not claim.strip():
            return None, ["missing_claim"]
        claim = claim.strip()

        # conflict_id (generate if missing)
        conflict_id = payload.get("conflict_id") or payload.get("id") or payload.get("uuid")
        if not isinstance(conflict_id, str) or not conflict_id:
            conflict_id = _uuid_hex()
            warnings.append("generated_conflict_id")

        # subject_id
        subject_id = payload.get("subject_id") or payload.get("entity_id") or payload.get("doc_id")
        if subject_id is not None and not isinstance(subject_id, str):
            subject_id = str(subject_id)
            warnings.append("coerced_subject_id_string")

        # predicate (optional)
        predicate = payload.get("predicate")
        if predicate is not None and not isinstance(predicate, str):
            predicate = str(predicate)
            warnings.append("coerced_predicate_string")

        # Timestamps
        observed_at = None
        for k in _TS_KEYS_OBS:
            if k in payload and payload.get(k) not in (None, ""):
                observed_at = _coerce_iso(payload.get(k))
                if k != "observed_at":
                    warnings.append(f"mapped_{k}_to_observed_at")
                break
        if observed_at is None:
            observed_at = ""

        logged_at = None
        for k in _TS_KEYS_LOG:
            if k in payload and payload.get(k) not in (None, ""):
                logged_at = _coerce_iso(payload.get(k))
                if k != "logged_at":
                    warnings.append(f"mapped_{k}_to_logged_at")
                break
        if not logged_at:
            logged_at = _now_iso()
            warnings.append("generated_logged_at")

        resolved_at = payload.get("resolved_at")
        if resolved_at is not None:
            resolved_at = _coerce_iso(resolved_at)

        # status
        status = payload.get("status") or "open"
        if not isinstance(status, str):
            status = str(status)
            warnings.append("coerced_status_string")
        status_lower = status.lower()
        if status_lower not in {"open", "resolved", "ignored"}:
            warnings.append("invalid_status_default_open")
            status_lower = "open"

        # confidence
        conf_raw = payload.get("confidence", 1.0)
        try:
            confidence = float(conf_raw)
        except Exception:
            confidence = 1.0
            warnings.append("invalid_confidence_default_1.0")
        clamped = max(0.0, min(1.0, confidence))
        if clamped != confidence:
            warnings.append("clamped_confidence")
        confidence = clamped

        # source
        source = payload.get("source", "unknown")
        if not isinstance(source, str):
            source = str(source)
            warnings.append("coerced_source_string")

        # tags
        tags = _coerce_tags(payload.get("tags"))
        if payload.get("tags") is not None and not isinstance(payload.get("tags"), list):
            warnings.append("coerced_tags_list")

        c = Contradiction(
            conflict_id=conflict_id,
            subject_id=subject_id,
            claim=claim,
            predicate=predicate,
            observed_at=observed_at or "",
            logged_at=logged_at or "",
            resolved_at=resolved_at,
            status=status_lower,
            confidence=confidence,
            source=source,
            tags=tags,
            schema_version=1,
        )

        return c, warnings
    except Exception as e:
        return None, [f"normalize_error:{type(e).__name__}"]


def to_payload(c: Contradiction) -> Dict[str, Any]:
    # Return a plain dict for storage or embedding
    d = asdict(c)
    # Ensure tags is always a list
    if d.get("tags") is None:
        d["tags"] = []
    return d

