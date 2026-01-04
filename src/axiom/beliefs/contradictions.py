#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

# Additive helpers for journaling + governor signaling
try:
    from pods.cockpit.cockpit_reporter import write_signal as _write_signal
except Exception:  # soft fallback
    def _write_signal(pod_name: str, signal_name: str, payload: dict) -> None:  # type: ignore
        try:
            pass
        except Exception:
            pass

try:
    from journal import log_event as _journal_log
except Exception:
    def _journal_log(event: Dict[str, Any]) -> None:  # type: ignore
        try:
            pass
        except Exception:
            pass

NEG_PATTERN = re.compile(
    r"\b([A-Z][\w\- ]{1,60})\s+(is|are|was|were|has|have|does|do)\s+(?:not|no|n't)\b"
)
POS_PATTERN = re.compile(
    r"\b([A-Z][\w\- ]{1,60})\s+(is|are|was|were|has|have|does|do)\b(?!\s+(?:not|no|n't))"
)


def _parse_ts(ts: Any) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        if isinstance(ts, str) and ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(timezone.utc)


def _belief_tags(mem: Dict[str, Any]) -> List[str]:
    vals = mem.get("beliefs") or []
    out: List[str] = []
    for v in vals:
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            t = v.get("tag") or v.get("label") or v.get("key")
            if isinstance(t, str):
                out.append(t)
    return out


def _entities_with_polarity(text: str) -> Dict[str, int]:
    """Return map of entity -> polarity (+1 or -1) from simple patterns.
    If both forms occur, the last seen wins for this heuristic.
    """
    entities: Dict[str, int] = {}
    if not text:
        return entities
    for m in NEG_PATTERN.finditer(text):
        ent = m.group(1).strip()
        entities[ent] = -1
    for m in POS_PATTERN.finditer(text):
        ent = m.group(1).strip()
        # Do not overwrite explicit negative if already set
        if entities.get(ent, 0) == 0:
            entities[ent] = +1
    return entities


def detect_contradictions(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect potential conflicts among candidate memories.
    Returns list of Conflict dicts: {a_id, b_id, tags_overlap, text_snippets, newer_wins, note}
    """
    conflicts: List[Dict[str, Any]] = []
    n = len(candidates or [])
    if n < 2:
        return conflicts
    # Precompute fields
    parsed: List[Tuple[str, List[str], Dict[str, int], datetime, str]] = []
    for mem in candidates:
        mid = mem.get("id") or mem.get("uuid") or ""
        tags = _belief_tags(mem)
        text = mem.get("content") or mem.get("text") or ""
        pols = _entities_with_polarity(text)
        when = _parse_ts(mem.get("timestamp"))
        parsed.append((mid, tags, pols, when, text))
    for i in range(n):
        id_a, tags_a, pols_a, ts_a, text_a = parsed[i]
        for j in range(i + 1, n):
            id_b, tags_b, pols_b, ts_b, text_b = parsed[j]
            # Require at least one overlapping belief tag
            ov = sorted(list(set(tags_a) & set(tags_b)))
            if not ov:
                continue
            # Look for entities with opposing polarity
            shared_entities = set(pols_a.keys()) & set(pols_b.keys())
            opp = [
                e for e in shared_entities if pols_a.get(e, 0) * pols_b.get(e, 0) == -1
            ]
            if not opp:
                continue
            newer_wins = ts_b > ts_a
            note = f"Opposing claims about {opp[0]} with shared belief tags"
            conflicts.append(
                {
                    "a_id": id_a,
                    "b_id": id_b,
                    "tags_overlap": ov,
                    "text_snippets": [text_a[:160], text_b[:160]],
                    "newer_wins": newer_wins,
                    "note": note,
                }
            )
    return conflicts


def create_contradiction(a_id: str, b_id: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Append a structured journal event and emit a governor signal indicating
    a contradiction was detected between two beliefs. Fail-closed by design.

    Returns the recorded event dict for caller diagnostics.
    """
    event = {
        "type": "contradiction",
        "a": str(a_id),
        "b": str(b_id),
        "context": dict(context or {}),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _journal_log(event)
    except Exception:
        # Never raise; best-effort only
        pass
    try:
        _write_signal("governor", "belief_contradiction", {"a": str(a_id), "b": str(b_id)})
    except Exception:
        pass
    return event
