import os
import pathlib

import yaml

_DEFAULTS = {
    "memory": "axiom_memories",
    "beliefs": "axiom_beliefs",
    "archive": "axiom_memory_archives",
}

# Robust path resolution; scripts can run from any CWD.
_DEF_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "config" / "collections.yaml"
)


def _load_yaml(path: pathlib.Path):
    try:
        if path.exists():
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def load_collections(config_path: str | None = None) -> dict:
    """
    Resolve collection names with precedence:
    1) QDRANT_COLLECTIONS env (comma-separated) → overrides memory/beliefs when provided
    2) Individual envs: QDRANT_MEMORY_COLLECTION, QDRANT_BELIEF_COLLECTION
    3) YAML config (config/collections.yaml)
    4) Built-in defaults
    Logs final resolved list once for observability.
    """
    path = pathlib.Path(config_path) if config_path else _DEF_PATH
    data = _load_yaml(path)
    cfg = (data.get("collections") or {}) if isinstance(data, dict) else {}
    out = _DEFAULTS.copy()

    # YAML overrides
    try:
        out.update({k: v for k, v in cfg.items() if v})
    except Exception:
        pass

    # Individual envs
    mem_env = os.getenv("QDRANT_MEMORY_COLLECTION")
    bel_env = os.getenv("QDRANT_BELIEF_COLLECTION")
    if mem_env:
        out["memory"] = mem_env
    if bel_env:
        out["beliefs"] = bel_env

    # Combined env precedence
    combo = (os.getenv("QDRANT_COLLECTIONS", "") or "").strip()
    if combo:
        parts = [p.strip() for p in combo.split(",") if p.strip()]
        if len(parts) >= 1:
            out["memory"] = parts[0]
        if len(parts) >= 2:
            out["beliefs"] = parts[1]
        if len(parts) >= 3:
            out["archive"] = parts[2]

    # One-time visibility
    try:
        import logging
        from utils.logging_utf8 import emoji

        logging.getLogger(__name__).info(
            emoji("[RECALL][Vector] 📂 Using Qdrant collections: %s", "[RECALL][Vector] Using Qdrant collections: %s"),
            ", ".join([out.get("memory", ""), out.get("beliefs", ""), out.get("archive", "")]).strip(", "),
        )
    except Exception:
        pass

    return out


# Public getters
# Use unified collection names


def memory_collection() -> str:
    return load_collections().get("memory")


def beliefs_collection() -> str:
    return load_collections().get("beliefs")


def archive_collection() -> str:
    return load_collections().get("archive")
