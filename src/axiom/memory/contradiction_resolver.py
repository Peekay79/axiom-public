#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from memory.utils.belief_coercion import coerce_belief_dict
from memory.utils.time_utils import utc_now_iso


def _coerce_belief_dict(belief: Any) -> Dict[str, Any]:
    # Wrapper retained for backward compatibility; delegates to centralized utility
    return coerce_belief_dict(belief)


_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _looks_time_dependent(text_a: str, text_b: str) -> bool:
    text = f"{text_a} \n {text_b}".lower()
    if _YEAR_RE.search(text):
        return True
    keywords = [
        "before",
        "after",
        "since",
        "as of",
        "currently",
        "now",
        "previously",
        "used to",
        "historically",
        "in the past",
        "recently",
    ]
    return any(kw in text for kw in keywords)


def _looks_opinionated(text: str) -> bool:
    text = text.lower()
    opinion_words = [
        "should",
        "ought",
        "believe",
        "think",
        "prefer",
        "value",
        "must",
        "good",
        "bad",
        "better",
        "worse",
        "ethical",
        "moral",
        "justice",
        "beautiful",
        "ugly",
        "opinion",
        "subjective",
    ]
    return any(w in text for w in opinion_words)


def _source_unclear(source: Optional[str]) -> bool:
    if source is None:
        return True
    s = source.strip().lower()
    return s in {"unknown", "unspecified", "inferred", "auto", "heuristic", "system"}


def _choose_inhibit_target(b1: Dict[str, Any], b2: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer to inhibit the one with lower confidence, otherwise the one with unclear source
    if b1["confidence"] < b2["confidence"] - 0.15:
        return b1
    if b2["confidence"] < b1["confidence"] - 0.15:
        return b2
    if _source_unclear(b1["source"]) and not _source_unclear(b2["source"]):
        return b1
    if _source_unclear(b2["source"]) and not _source_unclear(b1["source"]):
        return b2
    # Fallback: arbitrarily inhibit lower polarity magnitude or the second
    if abs(b1.get("polarity", 0)) < abs(b2.get("polarity", 0)):
        return b1
    return b2


def suggest_contradiction_resolution(
    belief_1: Any, belief_2: Any, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Suggest a resolution strategy for a pair of contradictory beliefs.

    Strategies:
    - reframe: if statements appear time-dependent
    - inhibit: if one belief is notably weaker (low confidence/unclear source)
    - flag_for_review: if both beliefs are low-confidence
    - dream_resolution: if both beliefs are opinionated or abstract
    """
    b1 = _coerce_belief_dict(belief_1)
    b2 = _coerce_belief_dict(belief_2)
    created_at = utc_now_iso()

    text_a = b1["text"]
    text_b = b2["text"]
    conf_a = b1["confidence"]
    conf_b = b2["confidence"]
    avg_conf = 0.5 * (conf_a + conf_b)
    min_conf = min(conf_a, conf_b)

    # Strategy checks
    is_time_dependent = _looks_time_dependent(text_a, text_b)
    both_opinionated = _looks_opinionated(text_a) and _looks_opinionated(text_b)
    weak_source = (
        _source_unclear(b1["source"])
        or _source_unclear(b2["source"])
        or abs(conf_a - conf_b) >= 0.25
    )
    low_conflict_conf = (avg_conf < 0.5) or (min_conf < 0.35)

    strategy: str
    confidence: float
    notes: str
    resolution: Dict[str, Any] = {
        "created_at": created_at,
        "source": "contradiction_resolver",
    }

    if is_time_dependent:
        strategy = "reframe"
        confidence = 0.82
        notes = "Beliefs appear time-dependent; reframe with temporal qualifiers."
        # Provide a minimal reframing suggestion
        reframed = {
            "text": f"Historically: {text_a} | Currently: {text_b}",
            "polarity": b1.get("polarity", 0),
            "confidence": round(max(conf_a, conf_b), 3),
            "scope": b1.get("scope") or b2.get("scope"),
            "source": "reframed_by_resolver",
        }
        resolution["reframed_belief"] = reframed
    elif weak_source:
        strategy = "inhibit"
        # Confidence stronger when the gap is larger
        gap = abs(conf_a - conf_b)
        confidence = 0.65 + min(0.25, max(0.0, gap - 0.1))
        notes = "Inhibit the weaker/uncertain belief to reduce conflict impact."
        target = _choose_inhibit_target(b1, b2)
        resolution["inhibit_belief_id"] = target.get("uuid") or target.get("text")
    elif both_opinionated:
        strategy = "dream_resolution"
        confidence = 0.7
        notes = "Both beliefs are opinionated/abstract; queue dream exploration."
    else:
        strategy = "flag_for_review" if low_conflict_conf else "inhibit"
        confidence = 0.52 if strategy == "flag_for_review" else 0.62
        notes = (
            "Low confidence across beliefs; flag for human review."
            if strategy == "flag_for_review"
            else "Inhibit the weaker belief to mitigate contradiction."
        )
        if strategy == "inhibit":
            target = _choose_inhibit_target(b1, b2)
            resolution["inhibit_belief_id"] = target.get("uuid") or target.get("text")

    resolution.update(
        {
            "resolution_strategy": strategy,
            "confidence": round(max(0.0, min(1.0, float(confidence))), 3),
            "notes": notes,
        }
    )
    return resolution


__all__ = ["suggest_contradiction_resolution"]
