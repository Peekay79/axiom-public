from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional


log = logging.getLogger("ingestion_manager")


DEFAULT_MANIFEST_PATH = "ingestion_manifest.json"


def load_ingestion_manifest(path: str = DEFAULT_MANIFEST_PATH) -> Optional[Dict[str, Any]]:
    """
    Load the world map ingestion manifest JSON.

    Returns manifest dict on success, or None on missing/invalid input.
    Emits canonical logs:
    - [RECALL][Manifest] loaded path=...
    - [RECALL][Manifest] mismatch reason=missing|invalid
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if not is_manifest_valid(obj):
            try:
                log.info("[RECALL][Manifest] mismatch reason=invalid")
            except Exception:
                pass
            return None
        try:
            log.info("[RECALL][Manifest] loaded path=%s", path)
        except Exception:
            pass
        return obj
    except FileNotFoundError:
        try:
            log.info("[RECALL][Manifest] mismatch reason=missing")
        except Exception:
            pass
        return None
    except Exception:
        try:
            log.info("[RECALL][Manifest] mismatch reason=invalid")
        except Exception:
            pass
        return None


def is_manifest_valid(obj: Dict[str, Any]) -> bool:
    try:
        return (
            isinstance(obj, dict)
            and isinstance(obj.get("ingestion_timestamp"), str)
            and isinstance(obj.get("world_map_path"), str)
            and isinstance(obj.get("world_map_hash"), str)
            and isinstance(obj.get("statistics"), dict)
        )
    except Exception:
        return False


def filter_memories_by_manifest(
    memories: List[Dict[str, Any]], manifest: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    When manifest is valid, filter memories to those tagged with the manifest's
    world_map_hash via metadata.ingestion_world_map_hash or top-level key.
    Otherwise, return memories unchanged.

    Emits canonical logs:
    - [RECALL][Manifest] filter applied kept=.. total=..
    - [RECALL][Manifest] disabled (when manifest None)
    """
    if not manifest or not is_manifest_valid(manifest):
        try:
            log.info("[RECALL][Manifest] disabled")
        except Exception:
            pass
        return memories

    target = str(manifest.get("world_map_hash") or "").strip()
    if not target:
        try:
            log.info("[RECALL][Manifest] mismatch reason=invalid")
        except Exception:
            pass
        return memories

    kept: List[Dict[str, Any]] = []
    for m in memories:
        try:
            md = m.get("metadata") or {}
            # Accept either nested metadata or top-level field for convenience
            h = str(md.get("ingestion_world_map_hash") or m.get("ingestion_world_map_hash") or "").strip()
            if h == target:
                kept.append(m)
        except Exception:
            continue

    try:
        log.info("[RECALL][Manifest] filter applied kept=%d total=%d", len(kept), len(memories))
    except Exception:
        pass
    return kept

