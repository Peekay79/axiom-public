from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class RecallHit:
    """Lightweight, pure-Python representation of a vector recall hit.

    Attributes:
        id: Optional identifier for the hit (if available)
        similarity: Similarity score in [0,1] (higher is better)
        text: Primary textual content of the hit
        tags: Optional list of string tags
        embedding: Optional vector embedding (normalized to unit length ideally)
        raw: Original hit object (dict or other) for mapping back without mutation
    """

    id: Optional[str]
    similarity: float
    text: str
    tags: List[str]
    embedding: Optional[List[float]]
    raw: Any


@dataclass
class RecallCfg:
    """Configuration surface for recall candidate selection (env-gated)."""

    threshold: float
    dynamic_threshold: bool = False
    floor_threshold: float = 0.15
    top1_fallback: bool = False
    min_results: int = 0

    keyword_boost: bool = False
    keyword_fields: List[str] = None  # type: ignore[assignment]

    mmr_enabled: bool = False
    mmr_lambda: float = 0.70
    mmr_k: int = 5

    log_telemetry: bool = False
    preview_chars: int = 160


def _env_bool(name: str, default: bool = False) -> bool:
    try:
        return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y"}
    except Exception:
        return bool(default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, str(default))).strip())
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return int(default)


def load_recall_cfg(override_threshold: Optional[float] = None) -> RecallCfg:
    """Read recall configuration from environment with safe defaults.

    Defaults preserve current behavior (no dynamic fallback, no boosts, no MMR).
    """

    # Canonical similarity threshold (default 0.30).
    # Precedence (highest to lowest):
    #   override_threshold → AXIOM_RETRIEVAL_MIN_SIM → RETRIEVAL_MIN_SIM
    #   → AXIOM_SELECTION_THRESHOLD → SIMILARITY_THRESHOLD → 0.30
    def _pick_float(names: Sequence[str], default_val: float) -> float:
        for n in names:
            raw = os.getenv(n)
            if raw is None or str(raw).strip() == "":
                continue
            try:
                return float(str(raw).strip())
            except Exception:
                continue
        return float(default_val)

    if override_threshold is not None:
        base_threshold = float(override_threshold)
    else:
        base_threshold = _pick_float(
            ("AXIOM_RETRIEVAL_MIN_SIM", "RETRIEVAL_MIN_SIM", "AXIOM_SELECTION_THRESHOLD", "SIMILARITY_THRESHOLD"),
            0.30,
        )

    cfg = RecallCfg(
        threshold=base_threshold,
        dynamic_threshold=_env_bool("RECALL_DYNAMIC_THRESHOLD", False),
        floor_threshold=_env_float("RECALL_DYNAMIC_FLOOR", 0.15),
        top1_fallback=_env_bool("RECALL_TOP1_FALLBACK", False),
        min_results=_env_int("RECALL_MIN_RESULTS", 0),
        keyword_boost=_env_bool("RECALL_KEYWORD_BOOST", False),
        keyword_fields=[],
        mmr_enabled=_env_bool("RECALL_MMR_ENABLED", False),
        mmr_lambda=max(0.0, min(1.0, _env_float("RECALL_MMR_LAMBDA", 0.70))),
        mmr_k=max(1, _env_int("RECALL_MMR_K", 5)),
        log_telemetry=_env_bool("RECALL_LOG_TELEMETRY", False),
        preview_chars=max(24, _env_int("RECALL_LOG_PREVIEW_CHARS", 160)),
    )
    # Parse keyword fields list
    raw_fields = os.getenv("RECALL_KEYWORD_FIELDS", "content,tags")
    fields = [f.strip().lower() for f in (raw_fields or "").split(",") if f.strip()]
    cfg.keyword_fields = fields or ["content", "tags"]
    return cfg


# ──────────────────────────────────────────────────────────────────────────────
# Core selection helpers (pure functions)
# ──────────────────────────────────────────────────────────────────────────────


def apply_threshold(hits: Sequence[RecallHit], threshold: float) -> List[RecallHit]:
    return [h for h in hits if float(getattr(h, "similarity", 0.0) or 0.0) >= float(threshold)]


def dynamic_threshold(hits: Sequence[RecallHit], primary: float, floor: float) -> Tuple[float, List[RecallHit]]:
    """If no hits pass the primary threshold, compute a fallback threshold near the top hit.

    Strategy: used_threshold = min(primary, max(floor, top_similarity * 0.98))
    This ensures at least the top hit qualifies (if above floor) while respecting the configured floor.
    """

    if not hits:
        return primary, []
    # Sort by similarity descending for stability
    sorted_hits = sorted(hits, key=lambda h: h.similarity, reverse=True)
    top_sim = float(sorted_hits[0].similarity)
    used = min(float(primary), max(float(floor), top_sim * 0.98))
    after = [h for h in sorted_hits if h.similarity >= used]
    return used, after


def top1_fallback(hits: Sequence[RecallHit]) -> List[RecallHit]:
    if not hits:
        return []
    return [max(hits, key=lambda h: h.similarity)]


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text.lower())]


def keyword_boost(
    hits: Sequence[RecallHit],
    query: str,
    fields: Iterable[str],
    boost: float = 0.05,
) -> List[RecallHit]:
    """Apply a simple keyword boost for hits containing query tokens.

    - Tokenize query with a simple word regex (no heavy NLP)
    - For each hit, check tokens in the selected text fields (e.g., content, tags)
    - Add up to 3x boost (capped at +0.15) to similarity
    """

    try:
        q_tokens = set(_tokenize(query))
    except Exception:
        q_tokens = set()
    if not q_tokens:
        return list(hits)

    normalized_fields = [str(f).strip().lower() for f in list(fields or [])]

    boosted: List[RecallHit] = []
    for h in hits:
        haystacks: List[str] = []
        for f in normalized_fields:
            if f in {"content", "text"}:
                haystacks.append(h.text or "")
            elif f == "tags":
                try:
                    haystacks.append(" ".join(h.tags or []))
                except Exception:
                    pass
        combined = " \n ".join(haystacks)
        tokens = set(_tokenize(combined))
        overlap = q_tokens.intersection(tokens)
        extra = min(0.15, boost * max(0, len(overlap)))
        if extra > 0:
            boosted.append(RecallHit(id=h.id, similarity=min(1.0, h.similarity + extra), text=h.text, tags=list(h.tags or []), embedding=(list(h.embedding) if h.embedding is not None else None), raw=h.raw))
        else:
            boosted.append(h)
    # Re-sort by new similarity
    boosted.sort(key=lambda x: x.similarity, reverse=True)
    return boosted


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum((float(x) * float(y)) for x, y in zip(a, b))


def mmr_rerank(hits: Sequence[RecallHit], k: int, lam: float) -> List[RecallHit]:
    """Standard MMR (Maximal Marginal Relevance) reranking.

    Requires hit.embedding to be present for all items. When unavailable, returns hits unchanged.
    """

    if not hits:
        return []
    if not all(getattr(h, "embedding", None) for h in hits):
        return list(hits)  # No-op without embeddings

    lam = max(0.0, min(1.0, float(lam)))
    k = max(1, int(k))
    k = min(k, len(hits))

    selected: List[int] = []
    remaining: List[int] = list(range(len(hits)))

    # Precompute self-sim matrix lazily via dot products (assumes embeddings normalized)
    def sim(i: int, j: int) -> float:
        ei = hits[i].embedding or []
        ej = hits[j].embedding or []
        try:
            return float(_dot(ei, ej))
        except Exception:
            return 0.0

    # Precompute relevance from input similarity score
    rel = [float(h.similarity) for h in hits]

    while len(selected) < k and remaining:
        if not selected:
            # Choose the most relevant item first
            idx = max(remaining, key=lambda i: rel[i])
            selected.append(idx)
            remaining.remove(idx)
            continue
        best_idx = None
        best_score = -1e9
        for i in remaining:
            # Diversity term: max similarity to any already selected item
            div = 0.0
            for j in selected:
                s = sim(i, j)
                if s > div:
                    div = s
            mmr_score = lam * rel[i] - (1.0 - lam) * div
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        if best_idx is None:
            break
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [hits[i] for i in selected]


def select_recall_candidates(query: str, hits: Sequence[RecallHit], cfg: RecallCfg) -> List[RecallHit]:
    """Select recall candidates using a configurable, additive strategy.

    This function is designed to be drop-in safe. When all feature flags are disabled,
    the behavior reduces to simple threshold filtering identical to prior logic.
    """

    # 1) initial threshold
    filtered = apply_threshold(hits, cfg.threshold)

    # 2) dynamic fallback
    if cfg.dynamic_threshold and not filtered and hits:
        _used, filtered = dynamic_threshold(hits, cfg.threshold, cfg.floor_threshold)

    # 3) keyword boost (optional)
    if cfg.keyword_boost:
        filtered = keyword_boost(filtered or hits, query, cfg.keyword_fields)

    # 4) MMR rerank (optional)
    if cfg.mmr_enabled and filtered:
        filtered = mmr_rerank(filtered, cfg.mmr_k, cfg.mmr_lambda)

    # 5) top1 fallback
    if cfg.top1_fallback and not filtered and hits:
        filtered = top1_fallback(hits)

    # 6) respect RECALL_MIN_RESULTS
    if not filtered and cfg.min_results > 0 and hits:
        # Sort by similarity descending before truncating
        sorted_hits = sorted(hits, key=lambda h: h.similarity, reverse=True)
        filtered = sorted_hits[: cfg.min_results]

    return list(filtered or [])


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry helpers (stdout only)
# ──────────────────────────────────────────────────────────────────────────────


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://[^\s]+")
_API_KEY_RE = re.compile(r"(sk-[A-Za-z0-9]{16,}|api[_-]?key[:=][^\s]+|Bearer\s+[A-Za-z0-9._-]{16,})", re.IGNORECASE)


def scrub(text: str) -> str:
    """Lightweight scrubber to avoid leaking PII/Secrets in previews."""

    if not isinstance(text, str) or not text:
        return ""
    try:
        s = _EMAIL_RE.sub("[EMAIL]", text)
        s = _URL_RE.sub("[URL]", s)
        s = _API_KEY_RE.sub("[SECRET]", s)
        return s
    except Exception:
        return text[:160]


def emit_recall_telemetry(query: str, hits: Sequence[RecallHit], selected: Sequence[RecallHit], cfg: RecallCfg) -> None:
    """Emit a single JSON line to stdout describing recall selection."""

    if not cfg.log_telemetry:
        return
    try:
        above = 0
        thr = float(cfg.threshold)
        for h in hits:
            try:
                if float(h.similarity) >= thr:
                    above += 1
            except Exception:
                pass
        preview_chars = int(cfg.preview_chars)
        log = {
            "ts": time.time(),
            "event": "vector_recall",
            "query": (query or "")[:200],
            "cfg": {
                "threshold": cfg.threshold,
                "dynamic": bool(cfg.dynamic_threshold),
                "floor": cfg.floor_threshold,
                "top1": bool(cfg.top1_fallback),
                "min_results": int(cfg.min_results),
                "keyword_boost": bool(cfg.keyword_boost),
                "mmr": bool(cfg.mmr_enabled),
            },
            "counts": {
                "raw": int(len(hits or [])),
                "above_threshold": int(above),
                "selected": int(len(selected or [])),
            },
            "top_samples": [
                {
                    "id": getattr(h, "id", None),
                    "score": round(float(getattr(h, "similarity", 0.0) or 0.0), 4),
                    "preview": scrub(getattr(h, "text", "") or "")[:preview_chars],
                }
                for h in list(selected or [])[:3]
            ],
            "source": "recall",
            "version": 1,
        }
        print(json.dumps(log, ensure_ascii=False))
    except Exception:
        # Fail-closed: never raise from telemetry path
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Convenience adapter: convert generic dict hits to RecallHit for selection
# ──────────────────────────────────────────────────────────────────────────────


def to_recall_hits_from_adapter_dicts(items: Sequence[dict]) -> List[RecallHit]:
    """Best-effort conversion from adapter/Qdrant shaped dicts to RecallHit.

    Supports dicts that contain either:
      - { "text"|"content", "tags", "_additional": {"certainty", "vector"?}, "_similarity"? }
      - or { "score", "content", "tags" }
    """

    out: List[RecallHit] = []
    for x in items or []:
        if not isinstance(x, dict):
            continue
        add = x.get("_additional") or {}
        similarity = None
        try:
            if isinstance(add, dict) and add.get("certainty") is not None:
                similarity = float(add.get("certainty"))
            elif x.get("_similarity") is not None:
                similarity = float(x.get("_similarity"))
            elif x.get("score") is not None:
                similarity = float(x.get("score"))
        except Exception:
            similarity = 0.0
        if similarity is None:
            similarity = 0.0
        text = x.get("content") or x.get("text") or ""
        tags = x.get("tags") or []
        if not isinstance(tags, list):
            try:
                tags = list(tags)
            except Exception:
                tags = []
        emb = None
        try:
            emb = add.get("vector") if isinstance(add, dict) else None
        except Exception:
            emb = None
        rid = x.get("id")
        out.append(RecallHit(id=rid, similarity=float(similarity), text=str(text), tags=[str(t) for t in tags], embedding=(list(emb) if isinstance(emb, list) else None), raw=x))
    # Sort by similarity descending for stable behavior
    out.sort(key=lambda h: h.similarity, reverse=True)
    return out

