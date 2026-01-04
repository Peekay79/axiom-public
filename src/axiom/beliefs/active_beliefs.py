#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

JOURNAL_PATHS = [
    "stevebot/journal/axiom_journal.jsonl",
    "journal/axiom_journal.jsonl",
]


@dataclass
class ActiveBeliefs:
    tags: Set[str]
    # Future fields: importance map, sources, etc.


def _normalize_tag(s: str) -> str:
    return "".join(
        ch if ch.isalnum() or ch in {":", "_", "."} else "_" for ch in s.strip()
    ).strip("_")


def _load_boot_journal_tags() -> Set[str]:
    for path in JOURNAL_PATHS:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    lines = [ln.strip() for ln in fh if ln.strip()]
                    if not lines:
                        return set()
                    last = json.loads(lines[-1])
                    vals = last.get("beliefs") or []
                    out: Set[str] = set()
                    for v in vals:
                        if isinstance(v, str):
                            out.add(_normalize_tag(v.lower()))
                    return out
            except Exception:
                return set()
    return set()


def _load_env_override() -> Set[str]:
    data = os.getenv("AXIOM_ACTIVE_BELIEFS_JSON", "")
    if not data:
        return set()
    try:
        obj = json.loads(data)
        tags: Set[str] = set()
        if isinstance(obj, list):
            for it in obj:
                if isinstance(it, str) and it.strip():
                    tags.add(_normalize_tag(it))
        elif isinstance(obj, str) and obj.strip():
            tags.add(_normalize_tag(obj))
        return tags
    except Exception:
        return set()


def load_active_beliefs(
    session_tags: Optional[Iterable[str]] = None,
    system_tags: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Aggregate active belief tags from multiple sources.
    - Boot journal (if present)
    - Session/system provided tags (if any)
    - Env override AXIOM_ACTIVE_BELIEFS_JSON (JSON list or string)
    Returns a dict with a `tags` list to keep it JSON-serializable for debug.
    """
    agg: Set[str] = set()
    agg |= _load_boot_journal_tags()
    if session_tags:
        for t in session_tags:
            if isinstance(t, str) and t.strip():
                agg.add(_normalize_tag(t))
    if system_tags:
        for t in system_tags:
            if isinstance(t, str) and t.strip():
                agg.add(_normalize_tag(t))
    agg |= _load_env_override()
    return {"tags": sorted(list(agg))}
