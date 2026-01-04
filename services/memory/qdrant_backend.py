from __future__ import annotations

from typing import Any, Dict


def _build_payload(mem: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Canonical payload builder: preserve source/tags and mirror source into metadata.source.
    Do NOT drop existing keys your backend already uses.
    """
    keep_keys = {
        "id",
        "type",
        "memory_type",
        "speaker",
        "timestamp",
        "importance",
        "content",
        "text",
        "context",
        "metadata",
        "tags",
        "source",
        "ingested_by",
        "beliefs",
        "goal_refs",
        "schema_version",
        "processed",
        "quality_score",
        "junk_score",
        "times_used",
        "updated_at",
        "created_at",
        "ingested_at",
    }

    payload: Dict[str, Any] = {
        k: v for k, v in (mem or {}).items() if k in keep_keys and v is not None
    }

    # Normalize tags to a unique list (preserve order)
    tags = list(dict.fromkeys((payload.get("tags") or (mem or {}).get("tags") or [])))
    if tags:
        payload["tags"] = tags

    # Mirror top-level source into metadata.source (additive)
    src = payload.get("source") or (mem or {}).get("source")
    md = payload.get("metadata") or (mem or {}).get("metadata") or {}
    if isinstance(md, dict) and src and not md.get("source"):
        md["source"] = src
    if md:
        payload["metadata"] = md

    return payload


import os, logging
logger = logging.getLogger(__name__)

# Optional inclusion gate (checks both type and memory_type, env-driven)
_DEFAULT_INCLUDE_TYPES = {
    "entity","event","relationship","goal_statement",
    "capability_statement","creation","employment","system_event",
    "memory","episodic","semantic","short_term"
}

def _env_bool(name: str, default: bool=False) -> bool:
    v = os.getenv(name, str(default)).strip().lower()
    return v in {"1","true","yes","y","on"}

def _split_list(name: str) -> set[str]:
    raw = os.getenv(name, "") or os.getenv("AX_VECTOR_INCLUDE_TYPES","")
    return {x.strip() for x in raw.split(",") if x.strip()}

# Always-vectorize conversational memory families
ALWAYS_VECTORIZE: set[str] = {
    "short_term",
    "episodic",
    "semantic",
    "relationship",
    "entity",
}

def _should_index(payload: Dict[str, Any]) -> bool:
    try:
        mem_type = str(payload.get("memory_type") or payload.get("type") or "").lower()
        dec_type = str(payload.get("type") or "").lower()
        if mem_type in ALWAYS_VECTORIZE or dec_type == "external_import":
            # Loud, explicit RAG log for decision transparency
            try:
                print(
                    f"[RAG] vector_decision: id={payload.get('id')} type={mem_type} decision={dec_type} -> VECTORIZE"
                )
            except Exception:
                pass
            logger.info(
                "vector_decision: id=%s type=%s memory_type=%s include=%s decision=%s",
                payload.get("id"),
                dec_type,
                mem_type,
                "<ALWAYS_VECTORIZE>",
                "ALLOW",
            )
            return True
    except Exception:
        # Fall through to legacy include gate
        pass

    if _env_bool("AX_VECTOR_FORCE_ALL", False):
        logger.info(
            "vector_decision: id=%s type=%s memory_type=%s include=%s decision=%s",
            payload.get("id"),
            payload.get("type"),
            payload.get("memory_type"),
            "<ALL>",
            "ALLOW",
        )
        return True
    include = _split_list("AX_VECTOR_SYNC_INCLUDE_TYPES") or _DEFAULT_INCLUDE_TYPES
    item_type = payload.get("type") or payload.get("memory_type")
    ok = True if not include else (item_type in include)
    logger.info(
        "vector_decision: id=%s type=%s memory_type=%s include=%s decision=%s",
        payload.get("id"),
        item_type,
        payload.get("memory_type"),
        ",".join(sorted(include)) if include else "<ALL>",
        "ALLOW" if ok else "SKIP",
    )
    return ok

__all__ = ["_build_payload","_should_index"]

# --- Lazy re-exports to avoid circular imports with the root backend -------
def __getattr__(name: str):
    # Only forward these names; leave local helpers (_build_payload, _should_index) alone
    if name in {"QdrantMemoryBackend", "QdrantVectorStore", "create_qdrant_backend"}:
        import importlib
        try:
            # Your moved backend lives here
            mod = importlib.import_module("tools.qdrant_backend_root")
        except Exception:
            # Fallback if you bring back a root shim later
            mod = importlib.import_module("qdrant_backend")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    "_build_payload",
    "_should_index",
    "QdrantMemoryBackend",
    "QdrantVectorStore",
    "create_qdrant_backend",
]
# --------------------------------------------------------------------------


