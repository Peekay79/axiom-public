from __future__ import annotations

import hashlib
import uuid
from typing import Any, Mapping


def _norm_text(s: str | None) -> str:
    if not s:
        return ""
    # normalize whitespace + lowercase for stable comparisons
    return " ".join(str(s).split()).strip().lower()


def canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    """
    Build a stable fingerprint over the semantic parts of a memory.
    Keep conservative to avoid accidental collisions while collapsing exact dupes.
    """
    # Prefer 'content' (primary schema), fall back to 'text'
    content = _norm_text(payload.get("content") or payload.get("text"))
    # Bound with a few stabilizers to reduce cross-domain collisions
    kind = _norm_text(payload.get("type"))
    source = _norm_text(payload.get("source") or (payload.get("metadata") or {}).get("source"))
    speaker = _norm_text(payload.get("speaker"))
    # Scope by memory_type to avoid cross-type collapse unless intentionally removed
    mtype = _norm_text(payload.get("memory_type"))

    canonical = "||".join([kind, mtype, source, speaker, content])
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def stable_point_id(payload: Mapping[str, Any]) -> str:
    """
    Generate a deterministic Qdrant point ID from the fingerprint using UUIDv5.
    This remains stable across runs and is human-inspectable.
    """
    fp = canonical_fingerprint(payload)
    return uuid.uuid5(uuid.NAMESPACE_URL, f"axiom://memory/{fp}").hex

