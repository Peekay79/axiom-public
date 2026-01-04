#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field, asdict, replace
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Belief:
    """
    Minimal, evidence-aware belief view used by governance and recompute passes.

    This is an additive, derived view that does not replace existing models in
    belief_models.py. It is intentionally tolerant and focused on governance
    semantics only.
    """

    id: str
    statement: str
    confidence: float
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    last_recompute: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        """Serialize to a dict payload suitable for storage/transport.

        Fields not present in this dataclass are not included. Values are kept as-is.
        """
        payload = asdict(self)
        return payload

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> "Belief":
        """Create a Belief from an arbitrary payload, tolerating extra fields.

        Missing optional fields default to sensible values. Unknown fields are ignored.
        """
        pid = str(payload.get("id", ""))
        statement = str(payload.get("statement", ""))
        try:
            conf = float(payload.get("confidence", 0.0))
        except Exception:
            conf = 0.0

        prov = payload.get("provenance") or []
        if not isinstance(prov, list):
            prov = []
        tags = payload.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        last_rec = payload.get("last_recompute")
        if last_rec is not None:
            last_rec = str(last_rec)

        # Clamp confidence to [0,1] defensively
        conf = max(0.0, min(1.0, conf))

        return Belief(
            id=pid,
            statement=statement,
            confidence=conf,
            provenance=prov,
            tags=tags,
            last_recompute=last_rec,
        )

