#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore

    _YAML_OK = True
except Exception:
    _YAML_OK = False

try:
    from memory.belief_engine import ENGINE_ENABLED as _BELIEF_ENGINE_ENABLED
    from memory.belief_engine import ActiveBeliefs as _ActiveBeliefs
    from memory.belief_engine import belief_alignment_score as _belief_align_impl
    from memory.belief_engine import clamp01 as _clamp01
    from memory.belief_engine import load_belief_config as _load_belief_cfg

    _HAS_BELIEF_ENGINE = True
except Exception:
    _HAS_BELIEF_ENGINE = False
    _BELIEF_ENGINE_ENABLED = False


# Defaults (can be overridden by YAML profiles)
DEFAULT_WEIGHTS = {
    "w_sim": 1.0,
    "w_rec": 0.6,
    "w_cred": 0.5,
    "w_conf": 0.3,
    "w_bel": 0.4,
    "w_use": 0.2,
    "w_nov": 0.1,
    "decay_lambda": 0.015,
    # New knobs (safe defaults)
    "beliefs_enabled": True,
    "belief_alpha": 0.1,
    "belief_importance_boost": 0.1,
    "contradictions_enabled": True,
    "belief_conflict_penalty": 0.05,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp(x: float, lo: float, hi: float) -> float:
    if x is None:
        return lo
    return min(max(x, lo), hi)


def _as_vector(obj: Any) -> Optional[List[float]]:
    if obj is None:
        return None
    if isinstance(obj, (list, tuple)):
        return [float(v) for v in obj]
    # Support Hit-like objects with .vector property
    v = getattr(obj, "vector", None)
    if v is not None:
        return _as_vector(v)
    return None


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if a is None or b is None:
        return 0.0
    if len(a) != len(b):
        raise ValueError(f"Vector dim mismatch: {len(a)} vs {len(b)}")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(len(a)):
        ai = float(a[i])
        bi = float(b[i])
        dot += ai * bi
        norm_a += ai * ai
        norm_b += bi * bi
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def avg_cosine(vec: Sequence[float], others: Iterable[Sequence[float]]) -> float:
    others = list(others)
    if not others:
        return 0.0
    return sum(cosine(vec, o) for o in others) / len(others)


def usage_norm(times_used: int) -> float:
    try:
        t = max(0, int(times_used or 0))
        return 1.0 - math.exp(-0.1 * t)  # saturating curve in [0,1)
    except Exception:
        return 0.0


def belief_alignment_stub(m: Any) -> float:
    # Placeholder fallback when belief engine disabled
    return 1.0


# New lightweight belief alignment based on tag overlap (Jaccard with smoothing)
try:
    from beliefs.active_beliefs import load_active_beliefs as _load_active_beliefs
except Exception:
    _load_active_beliefs = None  # type: ignore

_IMPORTANT_PREFIXES = ("axiom.identity", "axiom.ethic")


def _extract_belief_tags(m: Any) -> List[str]:
    """Extract belief tags from a memory item in a flexible way.
    Supports dict fields where beliefs may be a list of strings or dicts.
    """
    try:
        if isinstance(m, dict):
            vals = m.get("beliefs") or []
        else:
            vals = getattr(m, "beliefs", [])
        if not vals:
            return []
        out: List[str] = []
        for v in vals:
            if isinstance(v, str):
                out.append(v.strip())
            elif isinstance(v, dict):
                # accept tag-like fields or key
                t = v.get("tag") or v.get("label") or v.get("key")
                if isinstance(t, str) and t:
                    out.append(t.strip())
        return [t for t in out if t]
    except Exception:
        return []


def belief_alignment(
    m: Any, active_beliefs: Dict[str, Any], weights: Dict[str, Any]
) -> float:
    """Compute 0..1 alignment using Jaccard similarity over belief tags with smoothing.
    Optionally apply a small boost if overlapping tags include important prefixes.
    """
    alpha = float(weights.get("belief_alpha", 0.1) or 0.1)
    boost = float(weights.get("belief_importance_boost", 0.0) or 0.0)
    mem_tags = set(t for t in _extract_belief_tags(m) if t)
    active_tags = set((active_beliefs or {}).get("tags", []) or [])
    if not mem_tags or not active_tags:
        # Smoothing applied to avoid hard zeros
        return max(
            0.0,
            min(
                1.0,
                (0.0 + alpha)
                / (
                    len(mem_tags | active_tags) + alpha
                    if (mem_tags or active_tags)
                    else 1.0
                ),
            ),
        )
    inter = mem_tags & active_tags
    union = mem_tags | active_tags
    align = (len(inter) + alpha) / (len(union) + alpha)
    # Optional importance boost if any overlapping tag is in important namespace
    if boost > 0.0 and any(tag.startswith(_IMPORTANT_PREFIXES) for tag in inter):
        align = min(1.0, align + boost)
    return float(max(0.0, min(1.0, align)))


# ── v1: Lightweight, environment-backed active beliefs loader and alignment
_ACTIVE_BELIEFS: set[str] | None = None


def load_active_beliefs() -> set[str]:
    """Load a cached set of active beliefs from a JSON file path in env.
    Env: AXIOM_ACTIVE_BELIEFS_JSON -> JSON array of strings. Graceful fallback to empty set.
    """
    global _ACTIVE_BELIEFS
    if _ACTIVE_BELIEFS is not None:
        return _ACTIVE_BELIEFS
    path = os.getenv("AXIOM_ACTIVE_BELIEFS_JSON")
    if not path or not os.path.exists(path):
        _ACTIVE_BELIEFS = set()
        return _ACTIVE_BELIEFS
    try:
        with open(path, "r", encoding="utf-8") as fh:
            arr = json.load(fh) or []
            _ACTIVE_BELIEFS = set([str(x).lower() for x in arr])
    except Exception:
        _ACTIVE_BELIEFS = set()
    return _ACTIVE_BELIEFS


def _belief_alignment_score(mem_beliefs: List[str], active_beliefs: set[str]) -> float:
    """Compute conservative 0.25..0.75 score centered at 0.5 using Jaccard overlap.
    Returns 0.5 when either side is empty to keep neutral effect.
    """
    if not mem_beliefs or not active_beliefs:
        return 0.5
    m = set([b.lower() for b in mem_beliefs if isinstance(b, str) and b])
    if not m:
        return 0.5
    inter = len(m & active_beliefs)
    uni = len(m | active_beliefs)
    jacc = (inter / uni) if uni else 0.0
    return 0.25 + 0.5 * jacc


def novelty_bonus(m: Any, selected: List[Any]) -> float:
    # Encourage diversity vs. already selected items
    mv = _as_vector(m)
    if not selected or mv is None:
        return 0.0
    selected_vecs = [v for v in (_as_vector(s) for s in selected) if v is not None]
    if not selected_vecs:
        return 0.0
    # High novelty when average similarity to selected is low
    avg_sim = avg_cosine(mv, selected_vecs)
    return max(0.0, 1.0 - avg_sim)


def load_weights(
    profile_name: Optional[str] = None,
    config_path: str = "config/composite_weights.yaml",
) -> Dict[str, Any]:
    weights: Dict[str, Any] = dict(DEFAULT_WEIGHTS)
    if not profile_name:
        return weights
    if not _YAML_OK:
        return weights
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        profiles = (cfg or {}).get("profiles", {})
        prof = profiles.get(profile_name, {}) or {}
        for k, v in prof.items():
            # Preserve booleans/strings; cast numeric types to float
            try:
                if isinstance(v, (int, float)):
                    weights[k] = float(v)
                else:
                    weights[k] = v
            except Exception:
                weights[k] = v
        return weights
    except Exception:
        return weights


def composite_score(
    m: Any,
    qv: Sequence[float],
    selected: Optional[List[Any]] = None,
    w: Optional[Dict[str, float]] = None,
    now_fn=utc_now,
) -> Tuple[float, Dict[str, float]]:
    """Compute composite score and return (score, components)."""
    weights = w or DEFAULT_WEIGHTS
    mv = _as_vector(m)
    if mv is None:
        return 0.0, {
            "sim": 0.0,
            "rec": 0.0,
            "cred": 0.0,
            "conf": 0.0,
            "bel": 0.0,
            "use": 0.0,
            "nov": 0.0,
        }

    # Similarity
    sim = cosine(mv, qv)
    # Recency exponential decay
    try:
        # Allow dict or attribute access
        ts = (
            m.get("timestamp") if isinstance(m, dict) else getattr(m, "timestamp", None)
        )
        if isinstance(ts, str):
            # Normalize Z
            if ts.endswith("Z"):
                ts = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
        elif isinstance(ts, datetime):
            dt = ts
        else:
            dt = now_fn()
        age_days = max(
            0.0,
            (
                now_fn() - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
            ).total_seconds()
            / 86400.0,
        )
    except Exception:
        age_days = 0.0
    rec = math.exp(-float(weights["decay_lambda"]) * age_days)

    # Credibility/confidence/belief alignment/usage
    cred_val = (
        m.get("source_trust")
        if isinstance(m, dict)
        else getattr(m, "source_trust", 0.6)
    )
    cred = clamp(float(cred_val if cred_val is not None else 0.6), 0.0, 1.0)
    conf_val = (
        m.get("confidence") if isinstance(m, dict) else getattr(m, "confidence", 0.5)
    )
    conf = clamp(float(conf_val if conf_val is not None else 0.5), 0.0, 1.0)

    # Belief alignment (v1, lightweight, env-backed)
    bel = 1.0
    try:
        flag_enabled = bool(weights.get("beliefs_enabled", True))
        if flag_enabled:
            active = load_active_beliefs()
            # Extract memory beliefs (list[str]) in a tolerant way
            mem_beliefs: List[str] = []
            try:
                if isinstance(m, dict):
                    mem_beliefs = m.get("beliefs", []) or []
                else:
                    mem_beliefs = getattr(m, "beliefs", []) or []
                if not mem_beliefs and hasattr(m, "payload"):
                    payload = getattr(m, "payload")
                    if isinstance(payload, dict):
                        mem_beliefs = payload.get("beliefs", []) or []
            except Exception:
                mem_beliefs = []
            bel = _belief_alignment_score(
                [b for b in mem_beliefs if isinstance(b, str)], active
            )
            bel = clamp(bel, 0.0, 1.0)
        else:
            bel = 0.5  # neutral when disabled
    except Exception:
        bel = 0.5

    # Explore policy safeguard: cap contradictory boosts
    policy = os.getenv("AXIOM_CONFLICT_POLICY", "penalize").lower()
    if policy == "explore" and bel < 0.5:
        # tiny positive factor to avoid drowning relevance
        w_conflict = min(0.05, float(os.getenv("AXIOM_W_CONFLICT", "0.03")))
        bel = 0.5 + (bel - 0.5) * w_conflict / max(1e-6, abs(bel - 0.5))

    use = usage_norm(
        (m.get("times_used") if isinstance(m, dict) else getattr(m, "times_used", 0))
        or 0
    )
    nov = novelty_bonus(mv, selected or [])

    # Optional contradictions penalty via payload flags (lightweight)
    conflict_penalty = 0.0
    try:
        _contra_enabled_env = os.getenv("AXIOM_CONTRADICTION_ENABLED")
        if _contra_enabled_env is None and os.getenv("AXIOM_CONTRADICTIONS") is not None:
            # Legacy fallback with deprecation log; map into canonical for this process
            try:
                import logging as _logging  # local to avoid global top deps
                _logging.getLogger(__name__).warning("[RECALL][Deprecation] AXIOM_CONTRADICTIONS is deprecated; use AXIOM_CONTRADICTION_ENABLED")
            except Exception:
                pass
            try:
                os.environ.setdefault("AXIOM_CONTRADICTION_ENABLED", os.getenv("AXIOM_CONTRADICTIONS", "0"))
            except Exception:
                pass
            _contra_enabled_env = os.getenv("AXIOM_CONTRADICTION_ENABLED")
        if bool(weights.get("contradictions_enabled", True)) and str(_contra_enabled_env or "0").strip() in {"1","true","True"}:
            cf = None
            cs = None
            if isinstance(m, dict):
                cf = m.get("contradiction_flag")
                cs = m.get("conflict_score")
            else:
                cf = getattr(m, "contradiction_flag", None)
                cs = getattr(m, "conflict_score", None)
            if cf is True or (isinstance(cs, (int, float)) and cs > 0):
                conflict_penalty = float(weights.get("belief_conflict_penalty", 0.05))
    except Exception:
        conflict_penalty = 0.0

    base = float(weights["w_sim"]) * sim
    mult = (
        (1 + float(weights["w_rec"]) * rec)
        * (1 + float(weights["w_cred"]) * (cred - 0.5))
        * (1 + float(weights["w_conf"]) * (conf - 0.5))
        * (1 + float(weights["w_bel"]) * (bel - 0.5))
        * (1 + float(weights["w_use"]) * use)
        * (1 + float(weights["w_nov"]) * nov)
    )
    if conflict_penalty:
        mult = max(0.0, mult * (1.0 - conflict_penalty))
    final = base * mult
    return final, {
        "sim": sim,
        "rec": rec,
        "cred": cred,
        "conf": conf,
        "bel": bel,
        "use": use,
        "nov": nov,
        "conflict_penalty": conflict_penalty,
    }


def mmr_select(
    items: List[Any], query_vec: Sequence[float], k: int, lambda_: float = 0.5
) -> List[int]:
    """Maximal Marginal Relevance selection over provided items using cosine."""
    k = min(k, len(items))
    if k <= 0:
        return []
    selected: List[int] = []
    candidates = list(range(len(items)))
    item_vecs = [_as_vector(it) for it in items]

    for _ in range(k):
        best_idx = None
        best_score = -1e9
        for i in candidates:
            v = item_vecs[i]
            if v is None:
                continue
            rel = cosine(v, query_vec)
            div = 0.0
            if selected:
                div = (
                    max(
                        cosine(v, item_vecs[j])
                        for j in selected
                        if item_vecs[j] is not None
                    )
                    if any(item_vecs[j] is not None for j in selected)
                    else 0.0
                )
            score = lambda_ * rel - (1.0 - lambda_) * div
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is None:
            break
        selected.append(best_idx)
        candidates.remove(best_idx)
    return selected
