#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any, Dict


def _truthy(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y", "on"}


def _journal_append_handler(ev):
    try:
        # Idempotent journal append; reuse existing helper
        from pods.memory.pod2_memory_api import _json_append as _append  # type: ignore

        payload = ev.payload or {}
        content = payload.get("entry") or payload.get("text") or payload.get("content")
        if not content:
            return
        _append({"content": content, **{k: v for k, v in payload.items() if k not in {"entry", "text", "content"}}})
    except Exception as e:
        raise


def _memory_write_handler(ev):
    try:
        from axiom_qdrant_client import QdrantClient  # type: ignore
        from memory.memory_collections import memory_collection as _memory_collection
        from vector.embedder_registry import current as _embedder  # may fail if disabled
    except Exception:
        QdrantClient = None  # type: ignore
        _memory_collection = lambda: "axiom_memories"  # type: ignore

    # Build vector and payload; rely on existing ingestion utils where possible
    payload = ev.payload or {}
    text = payload.get("text") or payload.get("content") or ""
    if not text:
        return
    # Embedding best-effort (use existing pipeline if available)
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model_name = os.getenv("AXIOM_EMBEDDER") or os.getenv("EMBEDDING_MODEL") or "all-MiniLM-L6-v2"
        embedder = SentenceTransformer(model_name)
        vec = embedder.encode(text, normalize_embeddings=True).tolist()
    except Exception as e:
        raise RuntimeError(f"embedder_unavailable: {e}")
    # Upsert
    try:
        client = QdrantClient()
        client.upsert_memory(collection_name=_memory_collection(), memory_id=payload.get("id") or ev.idem_key, vector=vec, payload={k: v for k, v in payload.items() if k != "text"})
    except Exception as e:
        raise RuntimeError(f"vector_upsert_failed: {e}")


def main() -> int:
    if not _truthy("EVENTLOG_ENABLED", True):
        print("[eventlog] disabled")
        return 0
    from eventlog.consumer import EventConsumer  # type: ignore

    handlers: Dict[str, Any] = {
        "journal.append": _journal_append_handler,
        "memory.write": _memory_write_handler,
    }
    cons = EventConsumer(handlers)
    cons.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

