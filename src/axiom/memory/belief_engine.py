#!/usr/bin/env python3
# AUDIT: Contradiction Pipeline – belief_engine.py
# - Purpose: Belief canonicalization, active cache, pairwise and legacy contradiction detection, journaling hooks.
# - Findings:
#   - ❌ Bug: _estimate_pairwise_conflict uses undefined variable 'confidence' when deciding is_conflict; likely 'base_confidence'.
#   - ⚠️ Legacy: detect_contradictions is aliased to legacy aggregate API; consider deprecating in favor of pairwise.
#   - ⚠️ Private API: internal helper _as_belief is imported by other modules; consider public export or wrapper.
#   - ⚠️ Journal dep: imports bare 'journal'; ensure availability or provide memory.journal shim for consistency.
#   - Schema: conflict records use keys belief_a/b, conflict, confidence, resolution; consistent with monitor/dashboard.
#   - Cleanup targets: unify legacy vs pairwise APIs, expose stable public helpers, add tests for key_version handling.
# - No missing awaits found in async functions.

from __future__ import annotations

import math
import os
import re
import string
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4  # AUDIT_OK: used for conflict/event uuids

from memory.utils.time_utils import utc_now_iso
from memory.utils.config import get_env_flag, get_env_str
from memory.utils.journal import safe_log_event

try:
    import yaml  # type: ignore

    _YAML_OK = True
except Exception:
    _YAML_OK = False

try:
    from memory.metacognition import MetacognitionEngine  # additive observer

    _METACOG_OK = True
except Exception:
    MetacognitionEngine = None  # type: ignore
    _METACOG_OK = False

try:
    import journal  # minimal, safe logger  # ⚠️ bare import; consider namespaced memory.journal shim for consistency

    _HAS_JOURNAL = True
except Exception:
    _HAS_JOURNAL = False

# Optional contradiction resolver import (Phase 2)
try:
    from .contradiction_resolver import (
        suggest_contradiction_resolution as _suggest_resolution,  # type: ignore
    )

    _RESOLVER_OK = True
except Exception:
    _RESOLVER_OK = False

# ─────────────────────────────────────────────────────────────
# Config loading
# ─────────────────────────────────────────────────────────────
_DEFAULT_CFG = {
    "thresholds": {
        "SIM_THRESHOLD": 0.85,
        "STRONG_CONTRADICTION_THRESHOLD": 0.7,
    },
    "penalties": {
        "BASE_PENALTY": 0.2,
        "OPPOSITE_POLARITY_MULTIPLIER": 1.5,
    },
    "modes": {
        "TAGGER_MODE": "heuristic",
        "ALIGNMENT_ENABLED": True,
    },
    "SCOPE_POLICY": "intra_only",
    "REFRESH_SEC": 300,
}

_CFG_CACHE: Optional[Dict[str, Any]] = None


def load_belief_config(
    config_path: str = "config/belief_config.yaml",
) -> Dict[str, Any]:
    global _CFG_CACHE
    if _CFG_CACHE is not None:
        return _CFG_CACHE
    cfg = dict(_DEFAULT_CFG)
    if _YAML_OK and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
            # deep merge minimal
            for k in ("thresholds", "penalties", "modes"):
                if k in user_cfg and isinstance(user_cfg[k], dict):
                    cfg[k].update(user_cfg[k])
            # top-level extras
            for k in ("SCOPE_POLICY", "REFRESH_SEC"):
                if k in user_cfg:
                    cfg[k] = user_cfg[k]
        except Exception:
            pass
    # env override for refresh cadence
    # ASYNC-AUDIT: Move env parsing to typed loader
    try:
        from memory.utils.config import get_env_int  # local import to avoid cycles in legacy envs

        _env_refresh = int(get_env_int("AXIOM_BELIEF_REFRESH_SEC", 0))
    except Exception:
        _env_refresh = 0
    if _env_refresh > 0:
        cfg["REFRESH_SEC"] = _env_refresh
    _CFG_CACHE = cfg
    return cfg


# ─────────────────────────────────────────────────────────────
# Core types
# ─────────────────────────────────────────────────────────────
@dataclass
class Belief:
    key: str
    text: str
    polarity: int  # -1, 0, +1
    confidence: float  # 0..1
    scope: str
    source: str
    last_updated: str
    # Optional linkage (not required by schema, useful internally)
    uuid: Optional[str] = None
    # Schema/meta
    key_version: Optional[int] = None


def iso_now() -> str:
    return utc_now_iso()


# ─────────────────────────────────────────────────────────────
# Canonicalization
# ─────────────────────────────────────────────────────────────
# small explicit synonym table
SYNONYMS = {
    "ai_alignment": ["ai_safety", "alignment_safety"],
    "transparency": ["interpretability", "explainability"],
    "autonomy": ["self_direction", "self_governance"],
}
KEY_VERSION = 1

# legacy table retained but applied after headword mapping
_SYNONYM_TABLE = {
    "ai": "artificial_intelligence",
    "humans": "people",
    "shouldn't": "should_not",
    "should not": "should_not",
    "must not": "should_not",
}

_PUNCT_TABLE = str.maketrans(
    "", "", string.punctuation.replace("_", "").replace(":", "")
)


def clamp01(x: float, default=0.5):
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return default


def _normalize_text(text: str) -> str:
    t = " ".join(text.lower().strip().split())
    # apply headword mapping first
    for head, alts in SYNONYMS.items():
        for alt in alts:
            t = t.replace(alt, head)
    # then apply legacy small mappings
    for a, b in _SYNONYM_TABLE.items():
        t = t.replace(a, b)
    # preserve underscores/colons; strip other punctuation
    t = t.translate(_PUNCT_TABLE)
    # collapse extra whitespace again
    t = " ".join(t.split())
    return t


def canonicalize_belief_text(text: str) -> Tuple[str, str, int]:
    """Return (key, normalized_text, KEY_VERSION).
    - lowercase, collapse whitespace
    - synonym mapping to canonical headwords
    - strip punctuation except : and _
    - build simple subject:predicate style key where possible by token join
    """
    norm = _normalize_text(text or "")
    # very small heuristic to build subject:predicate form
    # split by common modal verbs to create predicate emphasis
    candidate = norm
    candidate = re.sub(
        r"\b(should|must|ought|need to|needs to|need)\b", "should", candidate
    )
    # key: allow a:z_ pattern
    key = re.sub(r"[^a-z0-9:_]+", "_", candidate)[:128]
    key = "_".join([tok for tok in key.split("_") if tok])
    return key, norm, KEY_VERSION


# ─────────────────────────────────────────────────────────────
# Extraction (heuristic or LLM stub)
# ─────────────────────────────────────────────────────────────

_DEF_SCOPE = "general"
_DEF_SOURCE = "ingest"


def _mk_belief(
    text: str,
    *,
    polarity: int,
    confidence: float,
    scope: str = _DEF_SCOPE,
    source: str = _DEF_SOURCE,
) -> Belief:
    key, norm, kv = canonicalize_belief_text(text)
    polarity = -1 if polarity < 0 else (1 if polarity > 0 else 0)
    return Belief(
        key=key,
        text=text.strip(),
        polarity=int(polarity),
        confidence=clamp01(confidence, default=0.5),
        scope=scope or _DEF_SCOPE,
        source=source or _DEF_SOURCE,
        last_updated=iso_now(),
        key_version=kv,
    )


def extract_beliefs_from_text(text: str) -> List[Belief]:
    """Heuristic extractor: identify simple normative/propositional forms.
    Rules: presence of should/must/need → polarity +1; negations → -1; contains "not"/"no" negates.
    Returns ≤5 beliefs.
    """
    if not text or not str(text).strip():
        return []
    t = str(text).strip()
    polarity = +1
    lower = t.lower()
    neg_hint = any(
        tok in lower
        for tok in ["should_not", " shouldn't ", " must not ", " not ", " no "]
    )
    if neg_hint:
        polarity = -1
    # confidence heuristic, then clamp
    confidence = 0.5
    if any(
        w in lower for w in ["must", "definitely", "always", "clearly", "obviously"]
    ):
        confidence = 0.65
    if any(
        w in lower for w in ["maybe", "perhaps", "uncertain", "not sure", "possibly"]
    ):
        confidence = 0.4
    belief = _mk_belief(t, polarity=polarity, confidence=confidence)
    return [belief]


# ─────────────────────────────────────────────────────────────
# Utilities to coerce to structured belief list
# ─────────────────────────────────────────────────────────────


def _as_belief(obj: Any) -> Optional[Belief]:
    if obj is None:
        return None
    if isinstance(obj, Belief):
        return obj
    if isinstance(obj, dict):
        # Prefer provided key verbatim if present to preserve caller semantics/tests
        provided_key = obj.get("key")
        raw_text = obj.get("text") or obj.get("statement") or ""
        if provided_key:
            key = str(provided_key)
            kv = int(obj.get("key_version") or KEY_VERSION)
        else:
            key, _, kv = canonicalize_belief_text(raw_text)
        text = (
            obj.get("text")
            or obj.get("statement")
            or str(provided_key or "").replace("_", " ")
        )
        pol = int(obj.get("polarity", +1) or +1)
        pol = -1 if pol < 0 else (1 if pol > 0 else 0)
        conf = clamp01(obj.get("confidence", 0.5))
        scope = obj.get("scope") or _DEF_SCOPE
        source = obj.get("source") or obj.get("provenance") or _DEF_SOURCE
        last = obj.get("last_updated") or obj.get("updated_at") or iso_now()
        uuid = obj.get("uuid") or obj.get("id")
        kv_src = obj.get("key_version")
        return Belief(
            key=key,
            text=text,
            polarity=pol,
            confidence=conf,
            scope=scope,
            source=source,
            last_updated=last,
            uuid=uuid,
            key_version=int(kv_src) if kv_src is not None else kv,
        )
    if isinstance(obj, str):
        return _mk_belief(obj, polarity=+1, confidence=0.5)
    return None


# Public alias for _as_belief to avoid private import usage in other modules
as_belief = _as_belief  # AUDIT_OK: public re-export


def ensure_structured_beliefs(beliefs_field: Any) -> List[Dict[str, Any]]:
    """Normalize arbitrary beliefs payload to a list of belief dicts compliant with schema."""
    result: List[Dict[str, Any]] = []
    if not beliefs_field:
        return result
    items: Iterable[Any]
    if isinstance(beliefs_field, (list, tuple)):
        items = beliefs_field
    else:
        # single value
        items = [beliefs_field]
    for it in items:
        b = _as_belief(it)
        if b is None:
            continue
        result.append(
            {
                "key": b.key,
                "text": b.text,
                "polarity": int(b.polarity),
                "confidence": float(b.confidence),
                "scope": b.scope,
                "source": b.source,
                "last_updated": b.last_updated,
                "uuid": b.uuid,
                "key_version": b.key_version,
            }
        )
    return result


# ─────────────────────────────────────────────────────────────
# Alignment scoring
# ─────────────────────────────────────────────────────────────


def _similarity_key(a: str, b: str) -> float:
    """Very small similarity for keys: Jaccard over tokens as a proxy for cosine."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta = set(a.split("_"))
    tb = set(b.split("_"))
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _to_belief_list(items: Iterable[Any]) -> List[Belief]:
    out: List[Belief] = []
    for it in items or []:
        b = _as_belief(it)
        if b:
            out.append(b)
    return out


def _same_scope(a: Belief, b: Belief, policy: str) -> bool:
    if policy != "intra_only":
        return True
    return (a.scope or _DEF_SCOPE) == (b.scope or _DEF_SCOPE)


def belief_alignment_score(
    candidate_beliefs: Iterable[Any],
    active_beliefs: Iterable[Any],
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = cfg or load_belief_config()
    if not candidate_beliefs:
        return 1.0
    act = _to_belief_list(active_beliefs)
    cand = _to_belief_list(candidate_beliefs)
    if not act:
        return 1.0
    penalty = 0.0
    base = float(cfg.get("penalties", {}).get("BASE_PENALTY", 0.2))
    opp_mult = float(cfg.get("penalties", {}).get("OPPOSITE_POLARITY_MULTIPLIER", 1.5))
    sim_thr = float(cfg.get("thresholds", {}).get("SIM_THRESHOLD", 0.85))
    contr_thr = float(
        cfg.get("thresholds", {}).get("STRONG_CONTRADICTION_THRESHOLD", 0.7)
    )
    scope_policy = str(cfg.get("SCOPE_POLICY", "intra_only"))
    for cb in cand:
        for ab in act:
            sim = _similarity_key(cb.key or "", ab.key or "")
            if sim < sim_thr:
                continue
            if not _same_scope(cb, ab, scope_policy):
                continue
            if (cb.polarity * ab.polarity) < 0:
                cconf = 0.5 * (clamp01(cb.confidence) + clamp01(ab.confidence))
                if cconf >= contr_thr:
                    penalty += base * opp_mult * cconf
    return max(0.0, min(1.0, 1.0 - penalty))


# ─────────────────────────────────────────────────────────────
# Contradiction detection (legacy aggregate)
# ─────────────────────────────────────────────────────────────


def detect_contradictions_legacy(
    belief_list: Iterable[Any], cfg: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    cfg = cfg or load_belief_config()
    beliefs = _to_belief_list(belief_list)
    if not beliefs:
        return []
    scope_policy = str(cfg.get("SCOPE_POLICY", "intra_only"))
    by_group: Dict[Tuple[str, str], List[Belief]] = {}
    for b in beliefs:
        key = b.key
        scope = b.scope or _DEF_SCOPE
        grp = (key, scope) if scope_policy == "intra_only" else (key, "*")
        by_group.setdefault(grp, []).append(b)
    contradictions: List[Dict[str, Any]] = []
    thr = float(cfg.get("thresholds", {}).get("STRONG_CONTRADICTION_THRESHOLD", 0.7))
    for (k, sc), items in by_group.items():
        pos = [i for i in items if i.polarity > 0]
        neg = [i for i in items if i.polarity < 0]
        if not pos or not neg:
            continue
        conf = max(clamp01(i.confidence) for i in items)
        if conf >= thr:
            contradictions.append(
                {
                    "key": k,
                    "scope": sc,
                    "confidence": conf,
                    "key_version": KEY_VERSION,
                    "positive": [
                        {
                            k: v
                            for k, v in asdict(i).items()
                            if k
                            in (
                                "uuid",
                                "polarity",
                                "confidence",
                                "scope",
                                "last_updated",
                                "key_version",
                            )
                        }
                        for i in pos
                    ],
                    "negative": [
                        {
                            k: v
                            for k, v in asdict(i).items()
                            if k
                            in (
                                "uuid",
                                "polarity",
                                "confidence",
                                "scope",
                                "last_updated",
                                "key_version",
                            )
                        }
                        for i in neg
                    ],
                    "created_at": iso_now(),
                }
            )
    return contradictions


def detect_contradictions_legacy_api(
    belief_list: Iterable[Any], cfg: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Deprecated aggregate contradiction detector (kept for reference/testing)."""
    cfg = cfg or load_belief_config()
    items = _to_belief_list(belief_list)
    if not items:
        return []
    # Group by key/scope and surface strong conflicts (legacy behavior)
    by_group: Dict[Tuple[str, str], List[Belief]] = {}
    scope_policy = str(cfg.get("SCOPE_POLICY", "intra_only"))
    for b in items:
        grp = (
            (b.key, b.scope or _DEF_SCOPE)
            if scope_policy == "intra_only"
            else (b.key, "*")
        )
        by_group.setdefault(grp, []).append(b)
    contradictions: List[Dict[str, Any]] = []
    thr = float(cfg.get("thresholds", {}).get("STRONG_CONTRADICTION_THRESHOLD", 0.7))
    for (k, sc), group_items in by_group.items():
        pos = [i for i in group_items if i.polarity > 0]
        neg = [i for i in group_items if i.polarity < 0]
        if not pos or not neg:
            continue
        conf = max(clamp01(i.confidence) for i in group_items)
        if conf >= thr:
            contradictions.append(
                {
                    "key": k,
                    "scope": sc,
                    "confidence": conf,
                    "key_version": KEY_VERSION,
                    "positive": [
                        {
                            k: v
                            for k, v in asdict(i).items()
                            if k
                            in (
                                "uuid",
                                "polarity",
                                "confidence",
                                "scope",
                                "last_updated",
                                "key_version",
                            )
                        }
                        for i in pos
                    ],
                    "negative": [
                        {
                            k: v
                            for k, v in asdict(i).items()
                            if k
                            in (
                                "uuid",
                                "polarity",
                                "confidence",
                                "scope",
                                "last_updated",
                                "key_version",
                            )
                        }
                        for i in neg
                    ],
                    "created_at": iso_now(),
                }
            )
    return contradictions


# ─────────────────────────────────────────────────────────────
# Active beliefs cache (in-memory) with refresh
# ─────────────────────────────────────────────────────────────
class ActiveBeliefs:
    """In-memory cache of currently relevant beliefs."""

    _cache: List[Belief] = []
    _loaded: bool = False
    _last_refresh_at: Optional[str] = None
    _metrics: Dict[str, int] = {"refreshes": 0}

    @classmethod
    def _seed_from_env(cls) -> None:
        # ASYNC-AUDIT: typed env access
        seed_text = get_env_str("AXIOM_ACTIVE_BELIEF_SEED", "")
        if seed_text:
            for part in seed_text.split("||"):
                part = part.strip()
                if part:
                    cls._cache.extend(extract_beliefs_from_text(part))

    @classmethod
    def refresh(cls, cfg: Optional[Dict[str, Any]] = None) -> None:
        cfg = cfg or load_belief_config()
        if not cls._loaded:
            cls._seed_from_env()
            cls._loaded = True
        # For now, refresh is a noop except updating timestamp; future: load from store
        cls._last_refresh_at = iso_now()
        cls._metrics["refreshes"] = cls._metrics.get("refreshes", 0) + 1

    @classmethod
    def current(cls, cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        cfg = cfg or load_belief_config()
        # Boot refresh
        if not cls._loaded:
            cls.refresh(cfg)
        # Cadence-based refresh
        try:
            refresh_sec = int(cfg.get("REFRESH_SEC", 300))
        except Exception:
            refresh_sec = 300
        if cls._last_refresh_at:
            try:
                last_dt = datetime.fromisoformat(
                    cls._last_refresh_at.replace("Z", "+00:00")
                )
            except Exception:
                last_dt = datetime.now(timezone.utc)
            age = (
                datetime.now(timezone.utc)
                - (last_dt if last_dt.tzinfo else last_dt.replace(tzinfo=timezone.utc))
            ).total_seconds()
            if age > refresh_sec:
                cls.refresh(cfg)
        else:
            cls.refresh(cfg)
        return [asdict(b) for b in cls._cache]

    @classmethod
    def extend(cls, beliefs: Iterable[Any]) -> None:
        for b in _to_belief_list(beliefs):
            cls._cache.append(b)

    @classmethod
    def size(cls) -> int:
        return len(cls._cache)

    @classmethod
    def last_refresh_at(cls) -> Optional[str]:
        return cls._last_refresh_at

    @classmethod
    def source_counts(cls) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for b in cls._cache:
            counts[b.source] = counts.get(b.source, 0) + 1
        return counts


# ─────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────
ENGINE_ENABLED = get_env_flag("AXIOM_BELIEF_ENGINE", False)
TAGGER_MODE = get_env_str("AXIOM_BELIEF_TAGGER", "heuristic").lower()
BELIEF_CONTRADICTION_TAGGING = get_env_flag("AXIOM_CONTRADICTION_TAGGING", False)


def observe_belief_application_success(
    belief_id: str,
    domain: str,
    *,
    args: Optional[Iterable[Any]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    belief_lookup: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
) -> None:
    """Observer helper to report a successful belief application to metacognition.
    Safe no-op if metacognition/journal are unavailable.
    """
    if not _METACOG_OK or MetacognitionEngine is None:
        return
    try:
        MetacognitionEngine.observe_belief_usage(
            belief_id=belief_id,
            domain=domain,
            ok=True,
            meta={"args": str(args), "kwargs": str(kwargs)},
            journal_hook=(
                journal.log_event
                if _HAS_JOURNAL and hasattr(journal, "log_event")
                else None
            ),
            belief_lookup=(
                belief_lookup
                or (
                    globals().get("get_belief_by_id")
                    if "get_belief_by_id" in globals()
                    else None
                )
            ),
        )
    except Exception:
        # Never raise from observer path
        return


def observe_belief_application_failure(
    belief_id: str,
    domain: str,
    *,
    args: Optional[Iterable[Any]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    belief_lookup: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
) -> None:
    """Observer helper to report a failed belief application to metacognition.
    Safe no-op if metacognition/journal are unavailable.
    """
    if not _METACOG_OK or MetacognitionEngine is None:
        return
    try:
        MetacognitionEngine.observe_belief_usage(
            belief_id=belief_id,
            domain=domain,
            ok=False,
            meta={"args": str(args), "kwargs": str(kwargs)},
            journal_hook=(
                journal.log_event
                if _HAS_JOURNAL and hasattr(journal, "log_event")
                else None
            ),
            belief_lookup=(
                belief_lookup
                or (
                    globals().get("get_belief_by_id")
                    if "get_belief_by_id" in globals()
                    else None
                )
            ),
        )
    except Exception:
        # Never raise from observer path
        return


# ─────────────────────────────────────────────────────────────
# Recent beliefs access and contradiction hook
# ─────────────────────────────────────────────────────────────


def get_recent_beliefs(limit: int = 25) -> List[Dict[str, Any]]:
    """Return the most recent beliefs from the in-memory cache.

    Sorted by last_updated descending; safe if cache is empty.
    """
    items = ActiveBeliefs.current()
    try:
        items_sorted = sorted(
            items,
            key=lambda x: x.get("last_updated", ""),
            reverse=True,
        )
        return items_sorted[: max(0, int(limit))]
    except Exception:
        return items[: max(0, int(limit))]


def format_contradictions_for_journal(contradictions: List[Dict[str, Any]]) -> str:
    """Format contradictions into a concise markdown list for journaling."""
    if not contradictions:
        return ""
    lines: List[str] = []
    for c in contradictions:
        belief_a = c.get("belief_a", "")
        belief_b = c.get("belief_b", "")
        cause = c.get("conflict", "")
        resolution = c.get("resolution", "pending")
        conf = c.get("confidence")
        conf_str = f" ({conf:.2f})" if isinstance(conf, (int, float)) else ""
        lines.append(
            f'- **Conflict{conf_str}:** "{belief_a}" vs "{belief_b}"\n  - Cause: {cause}\n  - Resolution: {resolution.capitalize()}'
        )
    return "\n".join(lines)


def _contains_negation(text: str) -> bool:
    """Lightweight negation cue detector."""
    t = (text or "").lower()
    return any(
        tok in t
        for tok in [
            " not ",
            "n't",
            " never ",
            " no ",
            " cannot ",
            " can't ",
            " shouldn't ",
            " must not ",
        ]
    )


def _emphasis_score(text: str) -> float:
    """Return emphasis score based on absolutes/hedges.
    + absolutes increase confidence; hedges decrease.
    """
    t = (text or "").lower()
    abs = ["always", "never", "must", "definitely", "certainly", "undoubtedly"]
    hedges = [
        "maybe",
        "perhaps",
        "sometimes",
        "often",
        "rarely",
        "possibly",
        "might",
        "could",
    ]
    score = 0.0
    if any(w in t for w in abs):
        score += 0.15
    if any(w in t for w in hedges):
        score -= 0.10
    return score


def _estimate_pairwise_conflict(
    a: Belief, b: Belief, cfg: Optional[Dict[str, Any]] = None
) -> Tuple[bool, float, str]:
    """Heuristic contradiction estimator between two beliefs.
    Returns (is_conflict, confidence, cause_summary).
    """
    cfg = cfg or load_belief_config()
    sim_thr = float(cfg.get("thresholds", {}).get("SIM_THRESHOLD", 0.85))
    base_thr = float(
        cfg.get("thresholds", {}).get("STRONG_CONTRADICTION_THRESHOLD", 0.7)
    )

    sim = _similarity_key(a.key, b.key)
    opposite = (a.polarity * b.polarity) < 0
    neg_mismatch = _contains_negation(a.text) != _contains_negation(b.text)

    # Compose base confidence (without belief confidence weighting)
    emphasis = 0.5 * (_emphasis_score(a.text) + _emphasis_score(b.text))

    polarity_component = 1.0 if opposite else (0.5 if neg_mismatch else 0.0)
    base_confidence = 0.6 * sim + 0.4 * polarity_component + emphasis
    base_confidence = max(0.0, min(1.0, base_confidence))

    # Decide conflict
    is_similar_enough = sim >= max(0.6, sim_thr - 0.2)
    # AUDIT_FIX: use computed base_confidence instead of undefined variable
    is_conflict = (
        (opposite or neg_mismatch)
        and is_similar_enough
        and base_confidence >= (base_thr - 0.2)
    )

    cause_parts: List[str] = []
    if opposite:
        cause_parts.append("Opposite polarity")
    if neg_mismatch and not opposite:
        cause_parts.append("Negation mismatch")
    if sim >= 0.8:
        cause_parts.append("High semantic similarity")
    elif sim >= 0.6:
        cause_parts.append("Moderate semantic similarity")
    if emphasis > 0:
        cause_parts.append("Emphatic language (always/never/must)")
    if _emphasis_score(a.text) < 0 or _emphasis_score(b.text) < 0:
        cause_parts.append("Hedged language present (reduced certainty)")
    cause = ", ".join(cause_parts) or "Heuristic contradiction"

    return is_conflict, float(base_confidence), cause


async def detect_contradictions_pairwise(
    new_belief: Any, recent_beliefs: Iterable[Any], cfg: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Detect contradictions between a new belief and a set of recent beliefs.

    Returns list of dicts with structure:
    {
      "belief_a": str,
      "belief_b": str,
      "conflict": str,
      "confidence": float,
      "resolution": "pending"
    }
    """
    cfg = cfg or load_belief_config()
    orig_a_dict = new_belief if isinstance(new_belief, dict) else None
    try:
        recent_items_list = list(recent_beliefs)
    except Exception:
        recent_items_list = list(recent_beliefs or [])
    orig_recent_by_uuid: Dict[str, Any] = {}
    for _it in recent_items_list:
        try:
            if isinstance(_it, dict) and _it.get("uuid"):
                orig_recent_by_uuid[str(_it.get("uuid"))] = _it
        except Exception:
            continue
    a_belief = _as_belief(new_belief)
    if a_belief is None:
        return []
    b_list = _to_belief_list(recent_items_list)
    if not b_list:
        return []
    # Optionally restrict by scope policy
    scope_policy = str(cfg.get("SCOPE_POLICY", "intra_only"))

    results: List[Dict[str, Any]] = []
    for b in b_list:
        # Skip self-same text
        if b.text.strip().lower() == a_belief.text.strip().lower():
            continue
        if scope_policy == "intra_only" and not _same_scope(a_belief, b, scope_policy):
            continue
        is_conflict, base_conf, cause = _estimate_pairwise_conflict(a_belief, b, cfg)
        if not is_conflict:
            continue

        # Integrate belief confidences into final conflict scoring
        confidence_a = clamp01(getattr(a_belief, "confidence", 0.5))
        confidence_b = clamp01(getattr(b, "confidence", 0.5))
        avg_belief_conf = 0.5 * (confidence_a + confidence_b)
        effective_confidence = base_conf * avg_belief_conf

        # Optional decay/age weighting (if available in config)
        decay_weight = float((cfg.get("decay", {}) or {}).get("DECAY_WEIGHT", 1.0))
        if decay_weight != 1.0:
            try:
                # If beliefs include last_updated timestamps, reduce confidence for very old beliefs
                from datetime import datetime as _dt
                from datetime import timezone as _tz

                def _age_days(ts: str | None) -> float:
                    if not ts:
                        return 0.0
                    try:
                        when = _dt.fromisoformat(str(ts).replace("Z", "+00:00"))
                        return max(
                            0.0, (_dt.now(_tz.utc) - when).total_seconds() / 86400.0
                        )
                    except Exception:
                        return 0.0

                age_a = _age_days(getattr(a_belief, "last_updated", None))
                age_b = _age_days(getattr(b, "last_updated", None))
                avg_age = 0.5 * (age_a + age_b)
                age_factor = 1.0 / (1.0 + 0.01 * decay_weight * avg_age)
                effective_confidence *= max(0.5, min(1.0, age_factor))
            except Exception:
                pass
        # AUDIT_OK: enrich conflict record with standardized fields
        conflict_record = {
            "uuid": str(uuid4()),
            "belief_a": a_belief.text,
            "belief_b": b.text,
            "belief_1": getattr(a_belief, "uuid", None),
            "belief_2": getattr(b, "uuid", None),
            "conflict": cause,
            "confidence": float(max(0.0, min(1.0, effective_confidence))),
            "resolution": "pending",
            "created_at": iso_now(),
        }

        # Phase 2: propose a resolution strategy (best-effort, additive field)
        if _RESOLVER_OK:
            try:
                resolution = _suggest_resolution(a_belief, b, config=cfg)
                if isinstance(resolution, dict):
                    conflict_record["proposed_resolution"] = resolution
                    # Journal the resolution suggestion
                    try:
                        bel1 = (
                            getattr(a_belief, "uuid", None)
                            or getattr(a_belief, "key", None)
                            or a_belief.text
                        )
                        bel2 = (
                            getattr(b, "uuid", None)
                            or getattr(b, "key", None)
                            or b.text
                        )
                        safe_log_event(
                            {
                                "type": "contradiction_resolution_suggested",
                                "uuid": str(uuid4()),
                                "belief_1": str(bel1),
                                "belief_2": str(bel2),
                                "strategy": resolution.get("resolution_strategy"),
                                "confidence": resolution.get("confidence"),
                                "notes": resolution.get("notes", ""),
                                "created_at": resolution.get("created_at") or iso_now(),
                                "source": "contradiction_resolver",
                            },
                            default_source="belief_engine",
                        )
                        # Optionally queue dream resolution if applicable
                        try:
                            if (
                                resolution.get("resolution_strategy")
                                == "dream_resolution"
                            ):
                                safe_log_event(
                                    {
                                        "type": "dream_contradiction_resolution_queued",
                                        "uuid": str(uuid4()),
                                        "belief_1": str(bel1),
                                        "belief_2": str(bel2),
                                        "created_at": resolution.get("created_at")
                                        or iso_now(),
                                        "source": "contradiction_resolver",
                                    },
                                    default_source="belief_engine",
                                )
                        except Exception:
                            pass
                    except Exception:
                        # Never raise on journal path
                        pass
            except Exception:
                # Resolution suggestion failures should never break detection
                pass

        # Emit standardized detection event for journals (best-effort)
        try:
            bel1 = (
                getattr(a_belief, "uuid", None)
                or getattr(a_belief, "key", None)
                or a_belief.text
            )
            bel2 = getattr(b, "uuid", None) or getattr(b, "key", None) or b.text
            safe_log_event(
                {
                    "type": "contradiction_detected",
                    "uuid": str(uuid4()),
                    "belief_1": str(bel1),
                    "belief_2": str(bel2),
                    "confidence": float(max(0.0, min(1.0, effective_confidence))),
                    "created_at": iso_now(),
                    "source": "belief_engine",
                },
                default_source="belief_engine",
            )
        except Exception:
            pass

        if BELIEF_CONTRADICTION_TAGGING:
            try:
                a_uuid = getattr(a_belief, "uuid", None)
                b_uuid = getattr(b, "uuid", None)
                if a_uuid and b_uuid:
                    try:
                        cw_a = getattr(a_belief, "contradicted_with", None)
                        if not isinstance(cw_a, list):
                            setattr(a_belief, "contradicted_with", [])
                            cw_a = getattr(a_belief, "contradicted_with", None)
                        if isinstance(cw_a, list) and b_uuid not in cw_a:
                            cw_a.append(b_uuid)
                    except Exception:
                        pass
                    try:
                        cw_b = getattr(b, "contradicted_with", None)
                        if not isinstance(cw_b, list):
                            setattr(b, "contradicted_with", [])
                            cw_b = getattr(b, "contradicted_with", None)
                        if isinstance(cw_b, list) and a_uuid not in cw_b:
                            cw_b.append(a_uuid)
                    except Exception:
                        pass
                    try:
                        if isinstance(orig_a_dict, dict):
                            lst = orig_a_dict.setdefault("contradicted_with", [])
                            if isinstance(lst, list) and b_uuid not in lst:
                                lst.append(b_uuid)
                    except Exception:
                        pass
                    try:
                        if b_uuid in orig_recent_by_uuid:
                            ob = orig_recent_by_uuid[b_uuid]
                            if isinstance(ob, dict):
                                lstb = ob.setdefault("contradicted_with", [])
                                if isinstance(lstb, list) and a_uuid not in lstb:
                                    lstb.append(a_uuid)
                    except Exception:
                        pass
                    try:
                        safe_log_event(
                            {
                                "type": "contradiction_linked",
                                "source": "belief_engine",
                                "uuid": str(uuid4()),
                                "belief_1": a_uuid,
                                "belief_2": b_uuid,
                                "created_at": iso_now(),
                            },
                            default_source="belief_engine",
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        results.append(conflict_record)
    return results


# AUDIT_OK: Backward-compatible wrapper
# - If called with a single iterable -> legacy aggregate API (sync list return)
# - If called with (new_belief, recent_beliefs[, cfg]) -> pairwise (returns awaitable)
def detect_contradictions(*args, **kwargs):
    """Unified detection entrypoint.

    Usage:
    - detect_contradictions(list_of_beliefs, cfg=None) -> List[dict]
    - detect_contradictions(new_belief, recent_beliefs, cfg=None) -> Coroutine[List[dict]]
    """
    # Pairwise path when provided two primary args
    if len(args) >= 2:
        new_belief = args[0]
        recent_beliefs = args[1]
        cfg = (
            kwargs.get("cfg")
            if "cfg" in kwargs
            else (args[2] if len(args) >= 3 else None)
        )
        return detect_contradictions_pairwise(new_belief, recent_beliefs, cfg)
    # Legacy aggregate path (single positional entries argument)
    entries = args[0] if args else None
    cfg = kwargs.get("cfg")
    return detect_contradictions_legacy_api(entries, cfg)


async def add_belief(
    new_belief: Any, *, log_to_journal: bool = True, limit_recent: int = 25
) -> Dict[str, Any]:
    """Add a belief to the active cache, trigger contradiction detection, optionally log to journal.

    This is an in-memory helper that complements external registries. It canonicalises
    inputs via `_as_belief`, updates `ActiveBeliefs`, and scans recent context for
    conflicts using a lightweight heuristic with confidence scoring.
    """
    # Normalise incoming belief first
    b = _as_belief(new_belief)
    if b is None:
        return {"ok": False, "reason": "invalid_belief"}

    # Snapshot recent beliefs before adding the new one to avoid self-matches
    recent = get_recent_beliefs(limit=limit_recent)
    contradictions = await detect_contradictions_pairwise(b, recent)

    # Add to active set afterwards
    ActiveBeliefs.extend([b])

    # Journal if requested
    if log_to_journal and contradictions:
        try:
            # AUDIT_OK: add created_at and standardized summary field; keep formatted for backward compat
            safe_log_event(
                {
                    "type": "contradiction",
                    "source": "belief_engine",
                    "created_at": iso_now(),
                    "conflicts": contradictions,
                    "summary": format_contradictions_for_journal(contradictions),
                    "formatted": format_contradictions_for_journal(contradictions),
                    "belief": {
                        k: v
                        for k, v in asdict(b).items()
                        if k
                        in (
                            "key",
                            "text",
                            "polarity",
                            "confidence",
                            "scope",
                            "source",
                            "last_updated",
                            "key_version",
                            "uuid",
                        )
                    },
                },
                default_source="belief_engine",
            )
        except Exception:
            # Never raise on journal path
            pass

    return {"ok": True, "contradictions": contradictions}


__all__ = [
    "Belief",
    "iso_now",
    "canonicalize_belief_text",
    "extract_beliefs_from_text",
    "ensure_structured_beliefs",
    "belief_alignment_score",
    "detect_contradictions",
    "detect_contradictions_pairwise",
    "detect_contradictions_legacy",
    # Public helper alias for callers previously importing private _as_belief
    "as_belief",
    "ActiveBeliefs",
    "ENGINE_ENABLED",
    "TAGGER_MODE",
    "load_belief_config",
    "clamp01",
    "KEY_VERSION",
    "SYNONYMS",
    "observe_belief_application_success",
    "observe_belief_application_failure",
    "get_recent_beliefs",
    "format_contradictions_for_journal",
    "add_belief",
]
