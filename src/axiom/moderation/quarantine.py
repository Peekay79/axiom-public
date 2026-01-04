#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, Tuple


def _truthy(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y", "on"}


def score_trust(text: str, meta: Dict[str, Any] | None = None) -> float:
    """
    Heuristics:
    - Source: external/user (+), model/self (-)
    - URL ratio: many URLs lowers trust
    - Repetition/entropy: heavy repetition and very low entropy lowers trust
    - Length extremes: very short or extremely long lowers trust mildly
    """
    meta = meta or {}
    score = 0.5
    src = str(meta.get("source") or meta.get("origin") or "").lower()
    if src in {"user", "external", "web", "import"}:
        score += 0.2
    if src in {"model", "self", "llm"}:
        score -= 0.1
    # URL ratio
    url_count = len(re.findall(r"https?://", text or ""))
    tokens = max(1, len((text or "").split()))
    url_ratio = url_count / float(tokens)
    if url_ratio > 0.05:
        score -= min(0.2, url_ratio)
    # Repetition
    words = (text or "").split()
    unique = len(set(words))
    if unique and (len(words) / float(unique)) > 3.0:
        score -= 0.2
    # Length extremes
    if len(words) < 3:
        score -= 0.1
    if len(words) > 800:
        score -= 0.1
    # Clamp
    return max(0.0, min(1.0, score))


def detect_injection(text: str) -> bool:
    patterns = [
        r"ignore\s+previous\s+instructions",
        r"^system:\s",
        r"```json[\s\S]*?"\s*:\s*\{",  # tool-call shaped JSON fence
        r"[A-Za-z0-9+/]{200,}={0,2}",  # long base64
    ]
    t = text or ""
    for p in patterns:
        try:
            if re.search(p, t, re.IGNORECASE | re.MULTILINE):
                return True
        except Exception:
            continue
    return False


def classify_reason(score: float, inj: bool) -> str | None:
    if inj:
        return "injection"
    try:
        thr = float(os.getenv("QUARANTINE_TRUST_MIN", "0.4") or "0.4")
    except Exception:
        thr = 0.4
    if score < thr:
        return "low_trust"
    return None


__all__ = ["score_trust", "detect_injection", "classify_reason"]

