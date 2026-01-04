"""Memory recall formatting utilities (Discord-safe).

This module intentionally depends only on the Python stdlib.
It is used by the Discord bot to keep memory injection bounded and user-visible
messaging truthful.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable, Optional, Protocol, Tuple, List


class HitLike(Protocol):
    score: float
    content: str
    raw: dict


_LIST_KEYWORDS = (
    "collection",
    "inventory",
    "list",
    "what's in",
    "what’s in",
    "whats in",
    "contains",
    "items",
    "item",
    "all the",
)


def is_list_style_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    if any(k in q for k in _LIST_KEYWORDS):
        return True
    # extra lightweight patterns
    if re.search(r"\bwhat\s+is\s+in\b", q):
        return True
    if re.search(r"\bwhat\s+does\s+.*\bcontain\b", q):
        return True
    return False


def _payload_fingerprint(hit: HitLike) -> Optional[str]:
    try:
        payload = (getattr(hit, "raw", None) or {}).get("payload") or {}
        if isinstance(payload, dict):
            fp = payload.get("fingerprint")
            if fp is None:
                return None
            fp = str(fp).strip()
            return fp or None
    except Exception:
        return None
    return None


def _norm_text(s: str) -> str:
    try:
        s = " ".join((s or "").split())
        s = s.lower()
        # strip most punctuation but keep digits/letters
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = " ".join(s.split())
        return s.strip()
    except Exception:
        return (s or "").strip().lower()


def _text_hash_key(s: str) -> str:
    n = _norm_text(s)
    return hashlib.sha1(n.encode("utf-8", errors="ignore")).hexdigest()


def select_hits_for_recall_block(
    hits: Iterable[HitLike],
    *,
    max_items: int,
    max_chars: int,
    per_item_max_chars: int,
    signature_dedup: bool = True,
) -> Tuple[List[HitLike], str]:
    """Select a deduped/diverse subset of hits and format a bounded recall block.

    - Dedup priority: payload.fingerprint if present; else normalized text hash.
    - Diversity: also suppress near-identical snippets by a short token signature.
    - Safety: never exceeds max_items or max_chars.
    """

    try:
        max_items_i = int(max_items or 0)
    except Exception:
        max_items_i = 0
    try:
        max_chars_i = int(max_chars or 0)
    except Exception:
        max_chars_i = 0
    try:
        per_item_i = int(per_item_max_chars or 0)
    except Exception:
        per_item_i = 0

    # hard caps: keep bounded even if env is mis-set
    max_items_i = max(0, min(max_items_i, 12))
    max_chars_i = max(0, min(max_chars_i, 4000))
    per_item_i = max(64, min(per_item_i, 600))

    if max_items_i <= 0 or max_chars_i <= 0:
        return [], ""

    lines: List[str] = ["Relevant memories:"]
    used = 0
    selected: List[HitLike] = []

    seen_fp: set[str] = set()
    seen_key: set[str] = set()
    seen_sig: set[str] = set()

    for h in list(hits or []):
        try:
            snippet = " ".join((getattr(h, "content", "") or "").split())
        except Exception:
            snippet = ""
        if not snippet:
            continue

        fp = _payload_fingerprint(h)
        if fp and fp in seen_fp:
            continue

        key = _text_hash_key(snippet)
        if key in seen_key:
            continue

        sig = ""
        if signature_dedup:
            norm = _norm_text(snippet)
            sig = " ".join(norm.split()[:24])
            if sig and sig in seen_sig:
                continue

        if len(snippet) > per_item_i:
            snippet = snippet[: max(0, per_item_i - 3)] + "..."

        bullet = f"- {snippet}"
        if used + len(bullet) + 1 > max_chars_i:
            break

        lines.append(bullet)
        used += len(bullet) + 1
        selected.append(h)

        if fp:
            seen_fp.add(fp)
        seen_key.add(key)
        if sig:
            seen_sig.add(sig)

        if len(selected) >= max_items_i:
            break

    if len(lines) <= 1:
        return [], ""

    return selected, "\n".join(lines).strip() + "\n"


def build_memory_banner(
    *,
    retrieved_count: int,
    selected_count: int,
    top_score: float,
    conf_threshold: float,
    world_injected: bool = False,
    world_entity_id: Optional[str] = None,
    guardrail_mode: bool = False,
) -> str:
    """User-visible memory status banner (truthful + non-contradictory)."""

    try:
        r = int(retrieved_count or 0)
    except Exception:
        r = 0
    try:
        s = int(selected_count or 0)
    except Exception:
        s = 0
    try:
        ts = float(top_score or 0.0)
    except Exception:
        ts = 0.0
    try:
        ct = float(conf_threshold or 0.0)
    except Exception:
        ct = 0.0

    lines: List[str] = []

    if bool(world_injected):
        eid = (world_entity_id or "").strip() or "(unknown)"
        lines.append(f"What I’m pulling from world map: {eid}")

    if r <= 0:
        # Only case where '(none)' is allowed.
        lines.append("What I’m pulling from memory: (none)")
        lines.append("No relevant memories found.")
    else:
        if s <= 0:
            # Never print '(none)' here since memories were retrieved.
            lines.append("Memories retrieved but none selected (filters/truncation).")
            lines.append(f"What I’m pulling from memory: 0 selected of {r} retrieved")
        else:
            if ts < ct:
                lines.append("Memories retrieved but confidence is moderate; answering cautiously.")
            lines.append(f"What I’m pulling from memory: {s} selected of {r} retrieved")

    if bool(guardrail_mode):
        lines.append("Not answering as fact without grounding.")

    return "\n".join([ln for ln in lines if ln]).strip()
