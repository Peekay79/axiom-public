"""Anti-hallucination guardrail heuristics (stdlib-only).

Used by the Discord bot to avoid confident factual answers when:
- no deterministic world-map grounding was injected, and
- vector recall is empty/low-confidence, and
- the user asked a factual lookup.

No external dependencies by design (unit-test friendly).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


_CREATIVE_MARKERS = (
    "write",
    "story",
    "scene",
    "roleplay",
    "imagine",
    "pretend",
    "continue the saga",
    "choose a",
    "choose b",
    "choose c",
    "choose d",
    "douglas",
)

_META_MARKERS = (
    # Self / open chat / planning (should NOT require grounding)
    "what are you interested in",
    "what are we talking about",
    "what should we talk about",
    "what do you want to talk about",
    "what would you like to talk about",
    "what should we do next",
    "what do we do next",
    "what's next",
    "whats next",
    "how should we proceed",
    "how do you want to proceed",
    "what would be useful",
    "what info would be useful",
    "what information would be useful",
    "what should i tell you",
    "what do you need from me",
    "tell me a memory",
    "tell me one of your memories",
    "tell me your personal memories",
    "tell me a personal memory",
    "do you remember",
    "what do you remember",
    "what can you do",
    "what are your capabilities",
    "how do you work",
    "how do you think",
)

# Requests to write/update the world map (the deployed bot has read-only endpoints).
_WORLD_MAP_PERSIST_MARKERS = (
    "save to world map",
    "save this to world map",
    "add to world map",
    "put this in the world map",
    "update the world map",
    "write to world map",
    "store in world map",
    "persist to world map",
    "remember this in the world map",
)

_FACTUAL_MARKERS = (
    "who is",
    "what is",
    "what do you know about",
    "have you heard of",
    "tell me about",
    "define",
)

_ENTITY_QUERY_PREFIXES = (
    "what do you know about",
    "have you heard of",
    "tell me about",
    "who is",
    "what is",
    "define",
)


def is_creative_prompt(message: str) -> bool:
    t = (message or "").strip().lower()
    if not t:
        return False
    return any(k in t for k in _CREATIVE_MARKERS)

def is_meta_self_open_chat(message: str) -> bool:
    """Return True for non-factual/meta questions that shouldn't require grounding."""
    t = (message or "").strip().lower()
    if not t:
        return False
    return any(k in t for k in _META_MARKERS)


def is_world_map_persist_request(message: str) -> bool:
    """Return True when the user asks to write/save/update the world map."""
    t = (message or "").strip().lower()
    if not t:
        return False
    # Must mention world map + a persist marker (avoid false positives like "world map profile")
    if "world map" not in t and "world_map" not in t:
        return False
    return any(k in t for k in _WORLD_MAP_PERSIST_MARKERS)


def is_factual_lookup(message: str) -> bool:
    t = (message or "").strip().lower()
    if not t:
        return False

    # Meta/open-chat questions are explicitly NOT treated as factual lookups.
    if is_meta_self_open_chat(t):
        return False

    if any(k in t for k in _FACTUAL_MARKERS):
        return True

    # Simple short-question heuristic.
    if t.endswith("?"):
        words = [w for w in t.replace("?", " ").split() if w]
        if len(words) <= 12:
            return True

    return False


def classify_message_intent(message: str) -> str:
    """Return one of: creative|meta|factual|neutral."""
    if is_creative_prompt(message):
        return "creative"
    if is_meta_self_open_chat(message):
        return "meta"
    if is_factual_lookup(message):
        return "factual"
    return "neutral"


@dataclass(frozen=True)
class GroundingStatus:
    world_injected: bool
    selected_count: int
    retrieved_count: int
    top_score: Optional[float]


def should_trigger_guardrail(
    *,
    enabled: bool,
    allow_general_knowledge: bool,
    message: str,
    grounding: GroundingStatus,
    low_score_threshold: float,
    min_selected: int = 1,
) -> bool:
    if not enabled:
        return False
    if allow_general_knowledge:
        return False
    if grounding.world_injected:
        return False

    if classify_message_intent(message) != "factual":
        return False

    try:
        ms = int(min_selected)
    except Exception:
        ms = 1
    ms = max(1, ms)

    try:
        low = float(low_score_threshold)
    except Exception:
        low = 0.78

    selected = int(grounding.selected_count or 0)

    low_confidence = False
    if selected < ms:
        low_confidence = True
    else:
        if grounding.top_score is not None:
            try:
                low_confidence = float(grounding.top_score) < low
            except Exception:
                low_confidence = True

    return bool(low_confidence)


def _extract_subject(message: str) -> str:
    """Best-effort subject phrase for the guardrail response."""
    raw = (message or "").strip()
    if not raw:
        return "that"

    t = raw.strip()
    low = t.lower()

    for prefix in ("what do you know about", "have you heard of", "tell me about", "who is", "what is", "define"):
        if prefix in low:
            idx = low.find(prefix)
            subj = t[idx + len(prefix) :].strip(" :\t\n\r\"'`")
            if subj:
                return subj[:80]

    # Otherwise, quote a short chunk.
    return t[:80]

def _looks_like_entity_term(message: str) -> bool:
    """Heuristic: is the user asking about a named thing (proper noun-ish)."""
    raw = (message or "").strip()
    if not raw:
        return False

    low = raw.lower()
    if not any(p in low for p in _ENTITY_QUERY_PREFIXES):
        return False

    subj = _extract_subject(raw)
    if not subj or subj.lower() in {"you", "me", "us", "this", "that"}:
        return False

    # Proper noun-ish: contains uppercase letters, digits+caps, or multiple words.
    has_upper = any(c.isalpha() and c.isupper() for c in subj)
    multi_word = len([w for w in subj.split() if w]) >= 2
    return bool(has_upper or multi_word)


def should_trigger_canon_disambiguation(
    *,
    message: str,
    grounding: GroundingStatus,
    conf_threshold: float = 0.25,
) -> bool:
    """Ask a single clarifying question for canon/saga entities when recall is weak.

    This is deliberately separate from the factual-lookup guardrail so it still
    works when "general knowledge" answering is enabled.
    """
    if grounding.world_injected:
        return False

    # Only for entity-style "tell me about / what do you know about ..." prompts.
    if not _looks_like_entity_term(message):
        return False

    # If we have any selected recall, let the system answer in-context.
    if int(grounding.selected_count or 0) > 0:
        return False

    # Weak/no recall → disambiguate.
    ts = grounding.top_score
    if ts is None:
        return True
    try:
        return float(ts) < float(conf_threshold)
    except Exception:
        return True


def build_canon_disambiguation_reply(message: str) -> str:
    subj = _extract_subject(message)
    subj = subj if subj else "that"
    # Single question (multiple-choice phrasing still counts as one clarifier).
    return (
        f"Quick check: when you say {subj!r}, is that from **Daddy & Maxi canon**, an **Axiom/internal project** thing, or the **real world**?"
    ).strip()


def build_world_map_persist_reply() -> str:
    write_enabled = (os.getenv("WORLD_MAP_WRITE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "y"}
    auto_enabled = (os.getenv("WORLD_MAP_AUTO_APPLY_ENABLED") or "").strip().lower() in {"1", "true", "yes", "y"}
    min_conf = (os.getenv("WORLD_MAP_AUTO_APPLY_MIN_CONFIDENCE") or "0.95").strip() or "0.95"

    if not write_enabled:
        # Truthful default: writes are feature-flagged OFF.
        return (
            "World map writes are **disabled** right now, so I can’t save/update it from chat.\n"
            "If you want to persist something, edit `world_map.json` and restart the memory pod.\n"
            "Paths checked by the resolver:\n"
            "- `WORLD_MAP_PATH` env var (authoritative)\n"
            "- `/workspace/world_map.json`\n"
            "- `./world_map.json`\n"
            "- `./memory/world_map.json` (legacy)"
        ).strip()

    # Writes enabled: explain auto-apply vs queueing, and how to review/apply.
    if auto_enabled:
        return (
            "World map writes are **enabled**.\n"
            f"- I can **auto-apply** a small set of ExamplePerson “hard facts” only when they’re **directly quoted** from your message and confidence ≥ {min_conf}.\n"
            "- Otherwise I **queue** a proposal for review.\n\n"
            "Review pending proposals:\n"
            "- `GET /world_map/pending`\n"
            "Apply a proposal:\n"
            "- `POST /world_map/apply/<proposal_id>`"
        ).strip()

    return (
        "World map writes are **enabled**, but **auto-apply is off**.\n"
        "I can only **queue** proposals for review.\n\n"
        "Review pending proposals:\n"
        "- `GET /world_map/pending`\n"
        "Apply a proposal:\n"
        "- `POST /world_map/apply/<proposal_id>`"
    ).strip()


def build_guardrail_reply(message: str) -> str:
    subj = _extract_subject(message)
    return (
        f"I don’t have high-confidence context for {subj!r} from our world map or recall.\n"
        "Is this a person, a project/codename, or something from our saga?\n"
        "If you tell me an alias/keyword or where we discussed it (channel/when), I can pull the right memory."
    ).strip()
