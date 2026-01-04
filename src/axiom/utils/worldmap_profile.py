"""World map intent + entity resolution (stdlib-only).

This module is used by the Discord bot to decide when to consult deterministic
world-map endpoints before answering.

Keep it small, explicit, and dependency-free so unit tests can import it.
"""

from __future__ import annotations

from typing import Optional


_PROFILE_STARTSWITH = (
    "who is",
    "what is",
    "tell me about",
)

_PROFILE_CONTAINS = (
    "my family",
    "my kids",
    "my pets",
    "axiom",
    "example_person",
    "max",
    "maxi",
    "leo",
    "hev",
    "heather",
)


def is_profile_intent(message: str) -> bool:
    """Heuristic: treat as orientation/profile if it matches a small keyword set."""
    t = (message or "").strip().lower()
    if not t:
        return False

    if any(t.startswith(p) for p in _PROFILE_STARTSWITH):
        return True

    return any(k in t for k in _PROFILE_CONTAINS)


def resolve_profile_entity_id(message: str) -> Optional[str]:
    """Resolve a candidate entity_id based on explicit name mentions.

    Priority order is intentional and deterministic.
    """
    t = (message or "").strip().lower()
    if not t:
        return None

    if "example_person" in t:
        return "example_person"
    if "axiom" in t:
        return "axiom"
    if "maxi" in t or "max" in t:
        return "max"
    if "leo" in t:
        return "leo"
    if "heather" in t or "hev" in t:
        return "hev"

    return None


def build_world_map_prompt_block(*, summary: str, relationships_count: int | None = None, max_chars: int = 900) -> str:
    """Build a bounded deterministic prompt block (no markdown tricks)."""
    s = (summary or "").strip()
    if not s:
        return ""
    if max_chars is None:
        max_chars = 900
    try:
        mc = int(max_chars)
    except Exception:
        mc = 900
    mc = max(120, min(mc, 2000))

    if len(s) > mc:
        s = s[: max(0, mc - 3)] + "..."

    lines = ["World map (deterministic):", s]
    try:
        if relationships_count is not None:
            lines.append(f"Relationships: {int(relationships_count)}")
    except Exception:
        pass
    return "\n".join(lines).strip()
