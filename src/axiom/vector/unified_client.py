#!/usr/bin/env python3
"""
Unified Vector Client
─────────────────────

Minimal adapter that resolves to either:
- Direct Qdrant client (preferred), or
- Vector Adapter HTTP shim (compat)

Environment resolution (backward compatible):
- VECTOR_PATH={qdrant|adapter} (new; default: qdrant)
- If USE_QDRANT_BACKEND is truthy → force qdrant
- If VECTOR_PATH=adapter and QDRANT_URL is set → adapter

This file intentionally keeps a tiny surface with no repo-wide refactors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import os
import time
import random
import contextlib
import json
import os


# Lazily-import heavy deps to keep import-time light
_SentenceTransformer = None
_qdrant_client = None
_qmodels = None


def _lazy_imports():
    global _SentenceTransformer, _qdrant_client, _qmodels
    if _SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception:  # pragma: no cover - optional path for tests
            SentenceTransformer = None  # type: ignore
        _SentenceTransformer = SentenceTransformer
    if _qdrant_client is None:
        try:
            import qdrant_client as qdr  # type: ignore
        except Exception:  # pragma: no cover
            qdr = None  # type: ignore
        _qdrant_client = qdr
    if _qmodels is None:
        try:
            from qdrant_client import models as qm  # type: ignore
        except Exception:  # pragma: no cover
            qm = None  # type: ignore
        _qmodels = qm


def _env_truthy(env: Dict[str, str], name: str, default: bool = False) -> bool:
    v = env.get(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class VectorSearchRequest:
    query: str
    top_k: int = 5
    filter: Optional[Dict[str, Any]] = None  # supports tags.any within {must: [{key:'tags', match:{any:[..]}}]}
    fields: Optional[List[str]] = None


@dataclass
class VectorHit:
    score: float
    content: str
    tags: List[str]
    meta: Dict[str, Any]


@dataclass
class VectorSearchResponse:
    hits: List[VectorHit]


class UnifiedVectorClient:
    """
    Resolves to Qdrant direct OR Vector Adapter HTTP, based on env.
    Defaults to Qdrant direct for simplicity and reliability.
    """

    def __init__(self, env: Dict[str, str], qdrant_url: Optional[str] = None):
        # Keep original env around for embedding config + feature flags.
        self._env: Dict[str, str] = dict(env or {})
        # Resolution order
        use_qdrant_backend = str(env.get("USE_QDRANT_BACKEND", "")).strip().lower() in {"1", "true", "yes"}
        vector_path = (env.get("VECTOR_PATH", "") or "").strip().lower()

        # Resolve adapter URL (use QDRANT_URL)
        self.adapter_url: Optional[str] = (env.get("QDRANT_URL", "") or "").strip().rstrip("/") or None

        # Authoritative Qdrant URL resolution (do not read HOST/PORT directly; derive only from URL)
        chosen_url: Optional[str] = None
        warnings: List[Dict[str, Any]] = []
        try:
            from config.resolved_mode import resolve_qdrant_url as _resolve_qdrant_url  # type: ignore
            chosen_url, _src, warnings = _resolve_qdrant_url(env=env, cli_url=qdrant_url)
        except Exception:
            chosen_url, warnings = None, []
        if not chosen_url:
            chosen_url = "http://localhost:6333"
        self._qdrant_url: str = str(chosen_url)
        self._config_warnings: List[Dict[str, Any]] = list(warnings or [])

        # Back-compat host/port fields derived from URL only (no env reads here)
        try:
            from urllib.parse import urlparse as _urlparse
            _p = _urlparse(self._qdrant_url)
            self.qdrant_host = _p.hostname or "localhost"
            self.qdrant_port = int(_p.port or 6333)
        except Exception:
            self.qdrant_host = "localhost"
            self.qdrant_port = 6333

        # Determine mode
        if use_qdrant_backend:
            self.mode = "qdrant"
        elif vector_path == "adapter" and self.adapter_url:
            self.mode = "adapter"
        else:
            self.mode = "qdrant"  # default

        # Embedding model (lazy init)
        self._embedder = None
        # Embedding model name: prefer canonical AXIOM_EMBEDDING_MODEL; keep legacy alias with deprecation log
        canon_embed = env.get("AXIOM_EMBEDDING_MODEL")
        if canon_embed:
            self._embed_model_name = canon_embed
        else:
            legacy_embed = env.get("AXIOM_EMBEDDER") or env.get("EMBEDDING_MODEL")
            if legacy_embed:
                try:
                    (self._config_warnings if hasattr(self, "_config_warnings") else [] ).append("[RECALL][Deprecation] AXIOM_EMBEDDER is deprecated; use AXIOM_EMBEDDING_MODEL")
                except Exception:
                    pass
                self._embed_model_name = legacy_embed
            else:
                self._embed_model_name = "all-MiniLM-L6-v2"

        # Optional remote embeddings service (preferred when present).
        self._embedding_url: Optional[str] = (
            (env.get("AXIOM_EMBEDDING_URL") or "")
            or (env.get("EMBEDDINGS_API_URL") or "")
            or (env.get("EMBEDDINGS_POD_URL") or "")
            or (env.get("VECTOR_EMBEDDING_URL") or "")
            or ""
        ).strip().rstrip("/") or None

        # Collection name (keep defaults; do not change schemas)
        try:
            from memory.memory_collections import memory_collection as _memory_collection

            self._memory_collection = _memory_collection()
        except Exception:  # pragma: no cover - fallback in tests
            self._memory_collection = "axiom_memories"

        # Qdrant direct client (lazy)
        self._qdr_client = None

        # Resiliency controls
        self._cb_fail_count: int = 0
        self._cb_open_until: float = 0.0
        self._cb_probe_allowed: bool = False
        # Defaults
        self._timeout_sec: float = 8.0
        self._retry_attempts: int = 3  # initial + 2 retries
        self._cb_threshold: int = 3
        self._cb_open_seconds: float = 20.0

        # Optional Qdrant score threshold (unset by default → no server-side filtering)
        _thr_raw = str(env.get("AXIOM_VECTOR_SCORE_THRESHOLD", "")).strip()
        try:
            self._qdrant_score_threshold: Optional[float] = float(_thr_raw) if _thr_raw else None
        except Exception:
            self._qdrant_score_threshold = None

    # Lightweight visibility for tests and health logging
    def get_debug_config(self) -> Dict[str, Any]:  # used by tests only
        try:
            return {
                "qdrant_url": self._qdrant_url,
                "warnings": list(self._config_warnings or []),
                "mode": self.mode,
            }
        except Exception:
            return {"qdrant_url": None, "warnings": None, "mode": getattr(self, "mode", None)}

    # ── Public API ─────────────────────────────────────────────
    def health(self) -> bool:
        if not self._cb_can_execute():
            return False
        if self.mode == "adapter":
            if not self.adapter_url:
                return False
            import requests

            try:
                r = requests.get(f"{self.adapter_url}/health", timeout=self._timeout_sec)
                return r.status_code == 200
            except Exception:
                self._cb_record_failure("adapter")
                return False
        else:  # qdrant
            _lazy_imports()
            if _qdrant_client is None:
                return False
            try:
                client = self._get_qdrant()
                _ = client.get_collections()
                self._cb_record_success()
                return True
            except Exception:
                self._cb_record_failure("qdrant")
                return False

    def is_circuit_open(self) -> bool:
        """Return True if the circuit breaker is currently open.

        Non-blocking; does not mutate breaker state.
        """
        try:
            return float(self._cb_open_until or 0.0) > time.time()
        except Exception:
            return False
            try:
                client = self._get_qdrant()
                # list collections as basic health
                _ = client.get_collections()
                self._cb_record_success()
                return True
            except Exception:
                self._cb_record_failure("qdrant")
                return False

    def search(self, req: VectorSearchRequest, request_id: Optional[str] = None, auth_header: Optional[str] = None) -> VectorSearchResponse:
        if not req or not isinstance(req.query, str) or not req.query.strip():
            return VectorSearchResponse(hits=[])
        if self.mode == "adapter":
            return self._search_via_adapter(req, request_id=request_id, auth_header=auth_header)
        return self._search_via_qdrant(req)

    def insert(self, items: List[Dict[str, Any]], request_id: Optional[str] = None, auth_header: Optional[str] = None) -> Dict[str, Any]:
        if not items:
            return {"inserted": 0}
        if self.mode == "adapter":
            return self._insert_via_adapter(items, request_id=request_id, auth_header=auth_header)
        return self._insert_via_qdrant(items)

    # Back-compat shim for journal vectorization
    def upsert(self, collection: str, items: List[Dict[str, Any]], request_id: Optional[str] = None, auth_header: Optional[str] = None) -> Dict[str, Any]:
        # Current implementation uses a unified collection internally; collection arg is ignored safely.
        return self.insert(items, request_id=request_id, auth_header=auth_header)

    # ── Internal helpers ───────────────────────────────────────
    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        # Prefer remote embeddings when configured to avoid local torch/ST deps.
        if self._embedding_url:
            import requests

            class _RemoteEmbedderCompat:
                def __init__(self, base: str, model: str, timeout_sec: float):
                    self._base = str(base).strip().rstrip("/")
                    self._model = str(model or "").strip() or "BAAI/bge-small-en-v1.5"
                    try:
                        self._timeout = float(timeout_sec)
                    except Exception:
                        self._timeout = 12.0

                def encode(self, texts, normalize_embeddings: bool = True):  # type: ignore[no-untyped-def]
                    single = False
                    if isinstance(texts, str):
                        single = True
                        batch = [texts]
                    else:
                        batch = list(texts or [])
                    if not batch:
                        return [] if not single else []
                    payload = {"texts": batch, "model": self._model}
                    r = requests.post(f"{self._base}/embed", json=payload, timeout=self._timeout)
                    r.raise_for_status()
                    data = r.json() or {}
                    vecs = data.get("vectors") or []
                    if not isinstance(vecs, list) or len(vecs) != len(batch):
                        raise RuntimeError("embeddings_invalid_response")
                    return vecs[0] if single else vecs

            timeout_sec = float(self._env.get("AXIOM_EMBEDDING_TIMEOUT_SEC", "12") or 12)
            self._embedder = _RemoteEmbedderCompat(self._embedding_url, self._embed_model_name, timeout_sec)
            return self._embedder

        # Local embeddings are explicitly gated.
        if not _env_truthy(self._env, "AXIOM_USE_SENTENCE_TRANSFORMERS", False):
            raise RuntimeError(
                "embeddings_unconfigured: set AXIOM_EMBEDDING_URL or enable AXIOM_USE_SENTENCE_TRANSFORMERS=true"
            )

        _lazy_imports()
        if _SentenceTransformer is None:
            raise RuntimeError("sentence_transformers_unavailable")
        self._embedder = _SentenceTransformer(self._embed_model_name)
        return self._embedder

    def _get_qdrant(self):
        if self._qdr_client is not None:
            return self._qdr_client
        _lazy_imports()
        if _qdrant_client is None:
            raise RuntimeError("qdrant-client not available")
        try:
            self._qdr_client = _qdrant_client.QdrantClient(url=self._qdrant_url, timeout=self._timeout_sec)  # type: ignore[attr-defined]
        except TypeError:
            # Older client signatures
            self._qdr_client = _qdrant_client.QdrantClient(host=self.qdrant_host, port=self.qdrant_port, timeout=self._timeout_sec)
        return self._qdr_client

    @staticmethod
    def _extract_tags_any(filter_obj: Optional[Dict[str, Any]]) -> List[str]:
        try:
            must = (filter_obj or {}).get("must")
            if not isinstance(must, list):
                return []
            for clause in must:
                if not isinstance(clause, dict):
                    continue
                if clause.get("key") == "tags":
                    match = clause.get("match", {}) or {}
                    any_vals = match.get("any")
                    if isinstance(any_vals, list):
                        return [str(v) for v in any_vals if isinstance(v, (str, int))]
        except Exception:
            return []
        return []

    @staticmethod
    def _jittered_sleep(attempt: int):
        # 2 retries target backoff: 200ms then 800ms
        if attempt <= 0:
            base = 0.2
        else:
            base = 0.8
        time.sleep(base + random.uniform(0, 0.1))

    # ── Circuit Breaker helpers ───────────────────────────────
    def _cb_can_execute(self) -> bool:
        now = time.time()
        if self._cb_open_until > now:
            return False
        if self._cb_open_until > 0 and now >= self._cb_open_until:
            # half-open probe window
            if not self._cb_probe_allowed:
                self._cb_probe_allowed = True
            return True
        return True

    def _cb_record_success(self):
        self._cb_fail_count = 0
        self._cb_open_until = 0.0
        self._cb_probe_allowed = False

    def _cb_record_failure(self, path: str):
        self._cb_fail_count += 1
        if self._cb_fail_count >= self._cb_threshold:
            self._cb_mark_open(path)

    def _cb_mark_open(self, path: str):
        self._cb_open_until = time.time() + self._cb_open_seconds
        self._cb_fail_count = 0
        self._cb_probe_allowed = False
        # Structured warn
        try:
            print("{" + f"\"component\":\"vector\",\"event\":\"circuit_open\",\"path\":\"{path}\"" + "}")
        except Exception:
            pass

    # ── Adapter mode ───────────────────────────────────────────
    def _search_via_adapter(self, req: VectorSearchRequest, request_id: Optional[str] = None, auth_header: Optional[str] = None) -> VectorSearchResponse:
        import requests

        if not self._cb_can_execute():
            return VectorSearchResponse(hits=[])

        url = f"{self.adapter_url}/v1/search"
        payload = {
            "query": req.query,
            "top_k": int(req.top_k or 5),
        }
        if req.filter:
            payload["filter"] = req.filter

        last_exc = None
        for attempt in range(0, self._retry_attempts):
            try:
                t0 = time.perf_counter()
                # Attempt to read correlation id from Flask g if available
                # Build correlation header if provided
                headers: Dict[str, str] = {}
                _hdr_name = (os.getenv("AXIOM_REQUEST_ID_HEADER") or "X-Request-ID").strip() or "X-Request-ID"
                rid = request_id
                if rid is None:
                    try:
                        from flask import g  # type: ignore

                        rid = getattr(g, "request_id", None)
                    except Exception:
                        rid = None
                if isinstance(rid, str) and rid:
                    headers[_hdr_name] = rid
                if isinstance(auth_header, str) and auth_header:
                    headers["Authorization"] = auth_header
                else:
                    # Fallback: read from Flask request if available
                    try:
                        from flask import request as _req  # type: ignore

                        _ah = _req.headers.get("Authorization")
                        if isinstance(_ah, str) and _ah:
                            headers["Authorization"] = _ah
                    except Exception:
                        pass
                r = requests.post(url, json=payload, timeout=self._timeout_sec, headers=(headers or None))
                r.raise_for_status()
                data = r.json() or {}
                hits = []
                for p in data.get("hits", []):
                    # Shape: { payload:{text|content,tags}, score }
                    payload_obj = p.get("payload", {}) if isinstance(p, dict) else {}
                    text = (
                        payload_obj.get("text")
                        or payload_obj.get("content")
                        or ""
                    )
                    tags = payload_obj.get("tags", []) if isinstance(payload_obj, dict) else []
                    score = float(p.get("score", 0.0)) if isinstance(p, dict) else 0.0
                    hits.append(VectorHit(score=score, content=text, tags=tags, meta={"raw": p}))
                # Metrics
                with contextlib.suppress(Exception):
                    from observability import metrics as _m  # type: ignore

                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    _m.observe_ms("vector.recall.ms", dt_ms)
                    if not hits:
                        _m.inc("vector.recall.empty")
                    else:
                        _m.inc("vector.recall.ok")
                # Structured log with correlation id
                try:
                    rid = request_id
                    if rid is None:
                        try:
                            from flask import g  # type: ignore

                            rid = getattr(g, "request_id", None)
                        except Exception:
                            rid = None
                    line = {"component": "vector", "event": "recall", "ok": True, "ms": int((time.perf_counter() - t0) * 1000)}
                    try:
                        line["qdrant_url"] = self._qdrant_url
                        if self._config_warnings:
                            line["config_warnings"] = self._config_warnings
                    except Exception:
                        pass
                    if isinstance(rid, str) and rid:
                        line["request_id"] = rid
                    print(json.dumps(line))
                except Exception:
                    pass
                self._cb_record_success()
                return VectorSearchResponse(hits=hits)
            except Exception as e:  # pragma: no cover - network path
                last_exc = e
                if attempt < self._retry_attempts - 1:
                    self._jittered_sleep(attempt)
                    continue
        # Failure across attempts
        with contextlib.suppress(Exception):
            from observability import metrics as _m  # type: ignore

            _m.inc("vector.recall.err")
        # Structured failure log
        try:
            rid = request_id
            if rid is None:
                try:
                    from flask import g  # type: ignore

                    rid = getattr(g, "request_id", None)
                except Exception:
                    rid = None
            line = {"component": "vector", "event": "recall", "ok": False}
            try:
                line["qdrant_url"] = self._qdrant_url
                if self._config_warnings:
                    line["config_warnings"] = self._config_warnings
            except Exception:
                pass
            if isinstance(rid, str) and rid:
                line["request_id"] = rid
            print(json.dumps(line))
        except Exception:
            pass
        self._cb_record_failure("adapter")
        return VectorSearchResponse(hits=[])

    def _insert_via_adapter(self, items: List[Dict[str, Any]], request_id: Optional[str] = None, auth_header: Optional[str] = None) -> Dict[str, Any]:
        import requests

        if not self._cb_can_execute():
            return {"inserted": 0}

        url = f"{self.adapter_url}/v1/memories"
        payload = {"items": items}
        last_exc = None
        for attempt in range(0, self._retry_attempts):
            try:
                headers: Dict[str, str] = {}
                _hdr_name = (os.getenv("AXIOM_REQUEST_ID_HEADER") or "X-Request-ID").strip() or "X-Request-ID"
                rid = request_id
                if rid is None:
                    try:
                        from flask import g  # type: ignore

                        rid = getattr(g, "request_id", None)
                    except Exception:
                        rid = None
                if isinstance(rid, str) and rid:
                    headers[_hdr_name] = rid
                if isinstance(auth_header, str) and auth_header:
                    headers["Authorization"] = auth_header
                else:
                    # Fallback: read from Flask request if available
                    try:
                        from flask import request as _req  # type: ignore

                        _ah = _req.headers.get("Authorization")
                        if isinstance(_ah, str) and _ah:
                            headers["Authorization"] = _ah
                    except Exception:
                        pass
                t0 = time.perf_counter()
                r = requests.post(url, json=payload, timeout=self._timeout_sec, headers=(headers or None))
                r.raise_for_status()
                data = r.json() or {}
                inserted = int(data.get("inserted", 0))
                # Structured upsert log
                try:
                    rid = request_id
                    if rid is None:
                        try:
                            from flask import g  # type: ignore

                            rid = getattr(g, "request_id", None)
                        except Exception:
                            rid = None
                    line = {"component": "vector", "event": "upsert", "ok": True, "ms": int((time.perf_counter() - t0) * 1000), "count": inserted}
                    try:
                        line["qdrant_url"] = self._qdrant_url
                        if self._config_warnings:
                            line["config_warnings"] = self._config_warnings
                    except Exception:
                        pass
                    if isinstance(rid, str) and rid:
                        line["request_id"] = rid
                    print(json.dumps(line))
                except Exception:
                    pass
                self._cb_record_success()
                return {"inserted": inserted}
            except Exception as e:  # pragma: no cover - network path
                last_exc = e
                if attempt < self._retry_attempts - 1:
                    self._jittered_sleep(attempt)
                    continue
        # Failure log
        try:
            rid = request_id
            if rid is None:
                try:
                    from flask import g  # type: ignore

                    rid = getattr(g, "request_id", None)
                except Exception:
                    rid = None
            line = {"component": "vector", "event": "upsert", "ok": False}
            try:
                line["qdrant_url"] = self._qdrant_url
                if self._config_warnings:
                    line["config_warnings"] = self._config_warnings
            except Exception:
                pass
            if isinstance(rid, str) and rid:
                line["request_id"] = rid
            print(json.dumps(line))
        except Exception:
            pass
        self._cb_record_failure("adapter")
        return {"inserted": 0}

    # ── Qdrant mode ───────────────────────────────────────────
    def _search_via_qdrant(self, req: VectorSearchRequest) -> VectorSearchResponse:
        _lazy_imports()
        if not self._cb_can_execute():
            return VectorSearchResponse(hits=[])
        embedder = self._get_embedder()
        client = self._get_qdrant()
        # Guarded by resilience breaker: if open, activate degraded mode and short-circuit
        try:
            from resilience.breakers import build_breaker_from_env as _build_breaker
            from resilience.degraded import activate as _degrade_activate
            _brk = getattr(self, "_resilience_breaker", None)
            if _brk is None:
                _brk = _build_breaker()
                setattr(self, "_resilience_breaker", _brk)
            if not _brk.allow():
                _degrade_activate()
                return VectorSearchResponse(hits=[])
        except Exception:
            pass

        # Build query vector (support numpy arrays and plain lists)
        qv_raw = embedder.encode(req.query, normalize_embeddings=True)
        try:
            qv = qv_raw.tolist()  # type: ignore[union-attr]
        except Exception:
            qv = list(qv_raw or [])

        def _qdrant_dense_search_points(
            *,
            query_vector: list[float],
            qfilter: Any,
            limit: int,
            score_threshold: Optional[float],
        ):
            """
            Compatibility shim:
            - Prefer modern qdrant-client query_points(...)
            - Fallback to older search(...)

            Returns a list of ScoredPoint-like objects with at least: id, payload, score.
            """
            # Modern clients (qdrant-client >= 1.10+) expose query_points
            if hasattr(client, "query_points"):
                resp = client.query_points(
                    collection_name=self._memory_collection,
                    query=query_vector,
                    limit=int(limit or 5),
                    with_payload=True,
                    with_vectors=False,
                    query_filter=qfilter or None,
                    score_threshold=score_threshold,
                )
                # query_points returns an object with `.points`
                pts = getattr(resp, "points", None)
                if pts is None:
                    # Defensive: some older betas returned list directly
                    if isinstance(resp, list):
                        return resp
                    return []
                return list(pts or [])

            # Legacy clients
            kwargs: Dict[str, Any] = dict(
                collection_name=self._memory_collection,
                query_vector=query_vector,
                limit=int(limit or 5),
                with_payload=True,
                with_vectors=False,
                query_filter=qfilter or None,
            )
            if score_threshold is not None:
                kwargs["score_threshold"] = float(score_threshold)
            return list(client.search(**kwargs) or [])

        # Translate filter (tags.any) to Qdrant Filter when possible
        qfilter = None
        tags_any = self._extract_tags_any(req.filter)
        if _qmodels is not None and tags_any:
            try:
                # Prefer MatchAny if available
                if hasattr(_qmodels, "MatchAny"):
                    qfilter = _qmodels.Filter(
                        must=[_qmodels.FieldCondition(key="tags", match=_qmodels.MatchAny(any=tags_any))]
                    )
                else:
                    # Fallback to should OR list of values (older clients)
                    should = [
                        _qmodels.FieldCondition(key="tags", match=_qmodels.MatchValue(value=v))
                        for v in tags_any
                    ]
                    qfilter = _qmodels.Filter(should=should)
            except Exception:
                qfilter = None

        # Execute search (2 short retries)
        last_exc = None
        for attempt in range(0, self._retry_attempts):
            try:
                t0 = time.perf_counter()
                results = _qdrant_dense_search_points(
                    query_vector=qv,
                    qfilter=qfilter,
                    limit=int(req.top_k or 5),
                    score_threshold=self._qdrant_score_threshold,
                )
                hits: List[VectorHit] = []
                # Normalize scores to similarity-space for downstream consumers.
                def _clamp01(x: float) -> float:
                    try:
                        return max(0.0, min(1.0, float(x)))
                    except Exception:
                        return 0.0

                def _to_similarity(raw_score: float) -> float:
                    """
                    Convert ambiguous Qdrant scores to similarity in [0,1].
                    If QDRANT_SCORE_IS_DISTANCE=true, treat score as distance and map to (1 - d).
                    Otherwise, if score > 1.0, heuristically treat as distance. Else assume similarity.
                    """
                    try:
                        s = float(raw_score)
                    except Exception:
                        return 0.0
                    try:
                        if str(os.getenv("QDRANT_SCORE_IS_DISTANCE", "")).strip().lower() in {"1", "true", "yes", "y"}:
                            return _clamp01(1.0 - s)
                    except Exception:
                        pass
                    if s > 1.0:
                        return _clamp01(1.0 - s)
                    return _clamp01(s)

                for r in results or []:
                    payload = getattr(r, "payload", {}) or {}
                    text = payload.get("text") or payload.get("content") or ""
                    tags = payload.get("tags", []) if isinstance(payload, dict) else []
                    score_raw = float(getattr(r, "score", 0.0) or 0.0)
                    score_sim = _to_similarity(score_raw)
                    hits.append(VectorHit(score=score_sim, content=text, tags=tags, meta={"raw": r}))

                # Client-side post-filter for tags.any to ensure correctness across versions
                if tags_any:
                    tagset = set(tags_any)
                    hits = [h for h in hits if any(t in tagset for t in (h.tags or []))]
                # Metrics
                with contextlib.suppress(Exception):
                    from observability import metrics as _m  # type: ignore

                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    _m.observe_ms("vector.recall.ms", dt_ms)
                    if not hits:
                        _m.inc("vector.recall.empty")
                    else:
                        _m.inc("vector.recall.ok")
                # Local structured log including correlation id if available
                try:
                    rid = None
                    try:
                        from flask import g  # type: ignore

                        rid = getattr(g, "request_id", None)
                    except Exception:
                        rid = None
                    line = {"component": "vector", "event": "recall", "mode": "qdrant", "ok": True, "ms": int((time.perf_counter() - t0) * 1000)}
                    try:
                        line["qdrant_url"] = self._qdrant_url
                        if self._config_warnings:
                            line["config_warnings"] = self._config_warnings
                    except Exception:
                        pass
                    try:
                        line["threshold"] = (float(self._qdrant_score_threshold) if self._qdrant_score_threshold is not None else None)
                    except Exception:
                        line["threshold"] = None
                    if isinstance(rid, str) and rid:
                        line["request_id"] = rid
                    print(json.dumps(line))
                except Exception:
                    pass
                self._cb_record_success()
                try:
                    _brk.success()  # type: ignore[name-defined]
                except Exception:
                    pass
                return VectorSearchResponse(hits=hits)
            except Exception as e:  # pragma: no cover - network path
                last_exc = e
                if attempt < self._retry_attempts - 1:
                    self._jittered_sleep(attempt)
                    continue
        with contextlib.suppress(Exception):
            from observability import metrics as _m  # type: ignore

            _m.inc("vector.recall.err")
        try:
            rid = None
            try:
                from flask import g  # type: ignore

                rid = getattr(g, "request_id", None)
            except Exception:
                rid = None
            line = {"component": "vector", "event": "recall", "mode": "qdrant", "ok": False}
            try:
                line["qdrant_url"] = self._qdrant_url
                if self._config_warnings:
                    line["config_warnings"] = self._config_warnings
            except Exception:
                pass
            try:
                line["threshold"] = (float(self._qdrant_score_threshold) if self._qdrant_score_threshold is not None else None)
            except Exception:
                line["threshold"] = None
            if isinstance(rid, str) and rid:
                line["request_id"] = rid
            print(json.dumps(line))
        except Exception:
            pass
        self._cb_record_failure("qdrant")
        try:
            _brk.failure()  # type: ignore[name-defined]
        except Exception:
            pass
        return VectorSearchResponse(hits=[])

    def _insert_via_qdrant(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Use axiom_qdrant_client wrapper for convenience
        try:
            from axiom_qdrant_client import QdrantClient as AxiomQdrantClient  # type: ignore
        except Exception as e:  # pragma: no cover
            return {"inserted": 0}

        try:
            from uuid import uuid4
        except Exception:  # pragma: no cover
            uuid4 = None  # type: ignore

        if not self._cb_can_execute():
            return {"inserted": 0}
        # Resilience breaker guard
        try:
            from resilience.breakers import build_breaker_from_env as _build_breaker
            from resilience.degraded import activate as _degrade_activate
            _brk = getattr(self, "_resilience_breaker", None)
            if _brk is None:
                _brk = _build_breaker()
                setattr(self, "_resilience_breaker", _brk)
            if not _brk.allow():
                _degrade_activate()
                return {"inserted": 0}
        except Exception:
            pass

        try:
            ax = AxiomQdrantClient(url=self._qdrant_url)
        except TypeError:
            ax = AxiomQdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        embedder = self._get_embedder()
        inserted = 0
        # Single upsert path with 3 attempts per item (keeps behavior identical otherwise)
        for it in items:
            try:
                content = (it.get("content") or "").strip()
                meta = it.get("metadata", {}) or {}
                if not content:
                    continue
                vec = embedder.encode(content, normalize_embeddings=True).tolist()
                pid = meta.get("memory_id") or (str(uuid4()) if uuid4 else None) or str(int(time.time()*1000))
                payload = {
                    "text": content,
                    "content": content,
                    "tags": meta.get("tags", []),
                    "type": meta.get("type", "memory"),
                    "timestamp": meta.get("timestamp"),
                    "speaker": meta.get("speaker"),
                    "persona": meta.get("persona"),
                    "source": meta.get("source"),
                }
                success = False
                for attempt in range(0, self._retry_attempts):
                    try:
                        ok = ax.upsert_memory(self._memory_collection, pid, vec, payload)
                        if ok:
                            success = True
                            break
                    except Exception:
                        if attempt < self._retry_attempts - 1:
                            self._jittered_sleep(attempt)
                            continue
                        else:
                            pass
                if success:
                    inserted += 1
                else:
                    self._cb_record_failure("qdrant")
                    try:
                        _brk.failure()  # type: ignore[name-defined]
                    except Exception:
                        pass
            except Exception:  # pragma: no cover
                continue
        if inserted > 0:
            self._cb_record_success()
            try:
                _brk.success()  # type: ignore[name-defined]
            except Exception:
                pass
        return {"inserted": inserted}


def _redact_host_port(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        from urllib.parse import urlparse

        p = urlparse(url if "://" in url else f"http://{url}")
        if p.hostname and p.port:
            return f"{p.hostname}:{p.port}"
        if p.hostname:
            return p.hostname
    except Exception:
        pass
    return url


def resolved_mode_matrix(env: Dict[str, str]) -> Dict[str, Any]:
    """Return a tiny dict for startup logging (read-only)."""
    client = UnifiedVectorClient(env)
    return {
        "VECTOR_PATH": client.mode,
        "QDRANT_HOST_PORT": f"{client.qdrant_host}:{client.qdrant_port}",
        "VECTOR_ADAPTER_URL": _redact_host_port(env.get("QDRANT_URL", "")) if client.mode == "adapter" else None,
        "COMPOSITE_SCORING": str(env.get("AXIOM_COMPOSITE_SCORING", "0")).strip() in {"1", "true", "yes"},
    }

