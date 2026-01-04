#!/usr/bin/env python3
"""
Minimal MemoryManager implementation for ingest_world_map.py

This provides the exact surface needed by the ingester:
- store(...) and store_memory(...) methods
- long_term_memory list-like attribute
- close() method
- Optional vector sync with lazy imports
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Idempotent upsert helpers (local-only, no heavy deps)
try:
    from .idempotency import canonical_fingerprint, stable_point_id
except Exception:  # pragma: no cover - best-effort import
    def canonical_fingerprint(payload: Dict[str, Any]) -> str:
        return ""

    def stable_point_id(payload: Dict[str, Any]) -> str:
        from uuid import uuid4

        return str(uuid4())


class _ListFallbackStore:
    """
    Ultra-light local fallback when no other store is available.
    """

    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def store(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        if "id" not in rec:
            rec = {**rec, "id": f"noop_{len(self.items)+1}"}
        self.items.append(rec)
        return rec

    # Compat for older call sites we might encounter
    def store_memory(self, *args, **kwargs) -> Dict[str, Any]:
        # assume first arg is the record dict; be forgiving
        rec = {}
        if args and isinstance(args[0], dict):
            rec = args[0]
        rec.update(kwargs or {})
        return self.store(rec)


class MemoryManager:
    """
    Minimal manager that the ingester expects.
    - store(...), store_memory(...), long_term_memory, close()
    - Vector path optional and lazy.
    """

    def __init__(self, *, vector_sync: bool = False, **kwargs: Any) -> None:
        self._vector_enabled = bool(vector_sync)
        self._fallback = _ListFallbackStore()
        self._backend = None  # type: ignore[assignment]
        self.long_term_memory = self._fallback.items  # used by ingester for counts

        if self._vector_enabled:
            try:
                # Lazy import / init; keep best-effort
                # NOTE: If qdrant backend wrapper is available in this module
                # as QdrantMemoryBackend, use it; otherwise keep fallback.

                # Try to import from the main memory manager if available
                try:
                    from . import memory_manager as mm

                    backend_cls = getattr(mm, "QdrantMemoryBackend", None)
                except (ImportError, AttributeError):
                    backend_cls = None

                if backend_cls is None:
                    log.warning(
                        "Vector sync requested but Qdrant backend not available; using fallback."
                    )
                else:
                    self._backend = backend_cls(
                        **kwargs
                    )  # kwargs for host/port/etc if the app passes them
                    log.info("✅ MemoryManager: Qdrant backend initialized")
            except Exception as e:
                log.error(
                    "❌ MemoryManager: failed to initialize vector backend: %s", e
                )
                self._backend = None

    def _coerce(self, obj: Any, **extra: Any) -> Dict[str, Any]:
        # Accept dict, pydantic BaseModel, objects, or strings
        if obj is None:
            rec = {}
        elif isinstance(obj, dict):
            rec = dict(obj)
        elif hasattr(obj, "model_dump"):
            try:
                rec = obj.model_dump()
            except Exception:
                rec = {"value": str(obj)}
        elif hasattr(obj, "dict"):
            try:
                rec = obj.dict()
            except Exception:
                rec = {"value": str(obj)}
        elif hasattr(obj, "__dict__") and isinstance(obj.__dict__, dict):
            rec = dict(obj.__dict__)
        elif isinstance(obj, str):
            rec = {"text": obj}
        else:
            rec = {"value": str(obj)}
        if extra:
            rec.update(extra)
        return rec

    def store(self, record: Any = None, **kwargs: Any) -> Dict[str, Any]:
        rec = self._coerce(record, **kwargs)
        # Derive fingerprint and stable id if not provided
        try:
            fp = canonical_fingerprint(rec)
            rec.setdefault("fingerprint", fp)
            if not rec.get("id"):
                rec["id"] = stable_point_id(rec)
        except Exception:
            pass
        # Always persist to local fallback list for counting
        out = self._fallback.store(rec)
        # Best-effort delegate to vector backend if available
        if self._backend is not None:
            try:
                # Try common method names; ignore if not present
                if hasattr(self._backend, "store"):
                    getattr(self._backend, "store")(rec)
                elif hasattr(self._backend, "upsert"):
                    getattr(self._backend, "upsert")(rec)
                elif hasattr(self._backend, "add"):
                    getattr(self._backend, "add")(rec)
            except Exception as e:
                log.warning("⚠️ MemoryManager: vector backend store failed: %s", e)
        return out

    def store_memory(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        # Alias some callers use
        rec = args[0] if args else None
        return self.store(rec, **kwargs)

    def close(self) -> None:
        try:
            if self._backend and hasattr(self._backend, "close"):
                self._backend.close()
        except Exception:
            pass
