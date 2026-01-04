#!/usr/bin/env python3
"""
Axiom Memory & World-Model API
─────────────────────────────────────────────────────────────────────────────
Endpoints
• /health       – basic status
• /memory/add   – add single memory
• /list_ids     – list every memory UUID
• /summarise    – keyword + fact summary
• /answer       – simple contextual answer
• /vector/query – semantic search via Qdrant
• /backfill     – push all local memory into Qdrant
• /goals        – list and add goals
• /beliefs      – list all beliefs
• /journal/latest – get most recent journal entry
• /memories     – list stored memories with speaker filter
• /qdrant-test  – test Qdrant connection (optional)
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Command-line argument parsing for optional Qdrant support
import argparse
import logging
import shutil

# Load vector environment configuration
try:
    from dotenv import load_dotenv

    load_dotenv(".env.vector")  # Load vector-specific config
    load_dotenv()  # Fallback to general .env
except ImportError:
    pass

# Create module-level logger
logger = logging.getLogger(__name__)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Axiom Memory API with optional Qdrant support"
)
parser.add_argument(
    "--use_qdrant",
    action="store_true",
    default=False,
    help="Load memory from Qdrant vector store instead of JSON file",
)
parser.add_argument(
    "--allow_empty_memory",
    action="store_true",
    default=False,
    help="Allow startup with empty memory if Qdrant is unreachable",
)
parser.add_argument(
    "--qdrant_url",
    default=None,
    help="Authoritative Qdrant base URL (e.g., http://host:6333). Overrides host/port when set.",
)
parser.add_argument(
    "--qdrant_host",
    default=None,
    help="Deprecated: Qdrant host (kept for backward compatibility).",
)
parser.add_argument(
    "--qdrant_port",
    type=int,
    default=None,
    help="Deprecated: Qdrant port (kept for backward compatibility).",
)
# Default to unified collection names; CLI --qdrant_collection overrides
try:
    from memory.memory_collections import memory_collection as _memory_collection

    _default_coll = _memory_collection()
except Exception:
    _default_coll = "axiom_memories"
parser.add_argument(
    "--qdrant_collection",
    default=os.getenv("QDRANT_COLLECTION", _default_coll),
    help="Qdrant collection (default from env QDRANT_COLLECTION, fallback axiom_memories)",
)

# Parse known args to allow the script to work with other arguments (like Flask's)
args, unknown = parser.parse_known_args()

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


from urllib.parse import urlparse as _urlparse

# Authoritative Qdrant URL resolution
try:
    from config.resolved_mode import ResolvedMode, resolve_qdrant_url
except Exception:
    ResolvedMode = None  # type: ignore
    def resolve_qdrant_url(cli_url=None):  # type: ignore
        return None, "unset", []


def _parse_host_port_from_url(url: str | None) -> tuple[str | None, int | None]:
    try:
        if not url:
            return None, None
        p = _urlparse(url)
        host = p.hostname
        port = p.port if p.port is not None else 6333
        return host, int(port) if host else (None, None)
    except Exception:
        return None, None


_CLI_CONFLICT_WARNED = False
RESOLVED_QDRANT_URL, _QDRANT_SOURCE, _QDRANT_WARNINGS = resolve_qdrant_url(cli_url=args.qdrant_url)
if args.qdrant_url and (args.qdrant_host is not None or args.qdrant_port is not None):
    logger.warning("[config] Both --qdrant-url and --qdrant-host/--qdrant-port provided; using --qdrant-url")
    _CLI_CONFLICT_WARNED = True
_RESOLVED_HOST, _RESOLVED_PORT = _parse_host_port_from_url(RESOLVED_QDRANT_URL)

# Back-compat: populate args host/port from resolved URL for places that still surface these
try:
    if args.qdrant_host is None and _RESOLVED_HOST:
        args.qdrant_host = _RESOLVED_HOST
    if args.qdrant_port is None and _RESOLVED_PORT:
        args.qdrant_port = int(_RESOLVED_PORT)
except Exception:
    pass


# Get collection names from environment with defaults
QDRANT_MEMORY_COLLECTION = os.getenv("QDRANT_MEMORY_COLLECTION", "axiom_memories")
QDRANT_BELIEF_COLLECTION = os.getenv("QDRANT_BELIEF_COLLECTION", "axiom_beliefs")

# Optional Qdrant imports - only import if using Qdrant
if args.use_qdrant:
    try:
        from .qdrant_utils import (
            _list_collection_names,
            get_qdrant_client,
            get_qdrant_collection_count,
            load_memory_from_qdrant,
            test_qdrant_connection,
        )

        QDRANT_AVAILABLE = True
        log.info("✅ Qdrant utilities loaded successfully")

        # Log Qdrant connection details and verify collections
        qdrant_url = RESOLVED_QDRANT_URL or (f"http://{args.qdrant_host}:{args.qdrant_port}" if (args.qdrant_host and args.qdrant_port) else None)
        logger.info(f"🔗 Qdrant URL: {qdrant_url}")
        logger.info(
            f"📋 Required collections: {QDRANT_MEMORY_COLLECTION}, {QDRANT_BELIEF_COLLECTION}"
        )

        try:
            # Prefer resolved URL; fall back to host/port if URL absent
            if RESOLVED_QDRANT_URL:
                from qdrant_client import QdrantClient as _QC  # type: ignore
                client = _QC(url=RESOLVED_QDRANT_URL, timeout=5)
            else:
                qdrant_host, qdrant_port = (_RESOLVED_HOST or "localhost"), int(_RESOLVED_PORT or (args.qdrant_port or 6333))
                client = get_qdrant_client(qdrant_host, qdrant_port)
            available_collections = _list_collection_names(client)
            logger.info(f"📂 Available collections: {sorted(available_collections)}")

            # Check for required collections
            missing_collections = []
            if QDRANT_MEMORY_COLLECTION not in available_collections:
                missing_collections.append(QDRANT_MEMORY_COLLECTION)
            if QDRANT_BELIEF_COLLECTION not in available_collections:
                missing_collections.append(QDRANT_BELIEF_COLLECTION)

            if missing_collections:
                logger.error(f"❌ Missing required collections: {missing_collections}")
                if not args.allow_empty_memory:
                    logger.error(
                        "Exiting due to missing required collections. Use --allow_empty_memory to continue."
                    )
                    sys.exit(1)
            else:
                logger.info("✅ All required collections are present")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            if not args.allow_empty_memory:
                logger.error(
                    "Exiting due to Qdrant connection failure. Use --allow_empty_memory to continue."
                )
                sys.exit(1)

    except ImportError as e:
        QDRANT_AVAILABLE = False
        log.error(f"❌ Failed to import Qdrant utilities: {e}")
        if not args.allow_empty_memory:
            log.error(
                "Exiting due to missing Qdrant dependencies. Use --allow_empty_memory to continue."
            )
            sys.exit(1)
else:
    QDRANT_AVAILABLE = False

import json

# from weaviate import connect_to_custom  # REMOVED: Migrated to Qdrant
import os
import time
import threading
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv  # optional
except Exception:

    def load_dotenv():
        return None


from flask import Flask, jsonify, request, g, make_response
from security import auth as ax_auth
import re
import uuid

import memory_response_pipeline
from flask_cors import CORS
from qdrant_client import QdrantClient
# ─────────────────────────────────────────────
# Boot integrity flags (soft degraded-mode)
# This system is not intended to fail fast; degraded operation is acceptable in research mode.
# ─────────────────────────────────────────────
try:
    from shared.boot_status import (
        set_boot_status as _set_boot_status,
        get_boot_status as _get_boot_status,
        is_degraded as _is_degraded,
    )
except Exception:
    # Minimal in-module fallback if shared helper is unavailable
    _BOOT_FLAGS = {
        "vector_collections_ready": False,
        "journal_loaded": False,
        "breaker_open": False,
        "identity_primed": False,
    }

    def _set_boot_status(flags):
        try:
            for k, v in (flags or {}).items():
                if k in _BOOT_FLAGS:
                    _BOOT_FLAGS[k] = bool(v)
        except Exception:
            pass
        return dict(_BOOT_FLAGS)

    def _get_boot_status():
        return dict(_BOOT_FLAGS)

    def _is_degraded():
        try:
            return not all(bool(v) for v in _BOOT_FLAGS.values())
        except Exception:
            return True


def set_boot_status(flags):
    """Module-level setter for boot flags (thin wrapper)."""
    # Maintain cheap, in-memory readiness booleans for `/readyz`.
    # This MUST NOT do any IO.
    global journal_loaded, vector_collections_ready, breaker_open, vector_circuit_open
    try:
        if isinstance(flags, dict):
            if "journal_loaded" in flags:
                journal_loaded = bool(flags.get("journal_loaded"))
            if "vector_collections_ready" in flags:
                vector_collections_ready = bool(flags.get("vector_collections_ready"))
            if "breaker_open" in flags:
                breaker_open = bool(flags.get("breaker_open"))
                # Separate boolean for circuit-open awareness without calling any client methods.
                vector_circuit_open = bool(flags.get("breaker_open"))
    except Exception:
        pass
    return _set_boot_status(flags)


# Cheap readiness flags for probe endpoints.
# These are updated via `set_boot_status(...)` and MUST remain in-memory only.
journal_loaded = False
vector_collections_ready = False
breaker_open = False
vector_circuit_open = False

# Initialize boot flags to conservative defaults
set_boot_status(
    {
        "vector_collections_ready": False,
        "journal_loaded": False,
        "breaker_open": False,
        "identity_primed": False,
    }
)


def _log_degraded_if_needed():
    flags = _get_boot_status()
    try:
        if not all(flags.values()):
            logger.warning("🚨 DEGRADED MODE: One or more boot systems incomplete")
            logger.warning(f"[BOOT FLAGS] {flags}")
            try:
                print("🛠️  Axiom booted in DEGRADED MODE. Check vector/journal subsystems.")
            except Exception:
                pass
    except Exception:
        pass

# Governor middleware (additive, optional)
try:
    from governor import governor_enabled, strict_mode
    from governor.middleware import ensure_correlation_and_idempotency
    from pods.cockpit.cockpit_reporter import write_signal as _gov_write
    from governor.validator import validate_payload as _gov_validate
except Exception:
    def governor_enabled():
        return False
    def strict_mode():
        return False
    def ensure_correlation_and_idempotency(h, p, require_cid=True, require_idem=True):
        return h or {}
    def _gov_write(pod, sig, payload):
        pass
    def _gov_validate(kind, payload):
        return True, "validator_unavailable"

# IMPORTANT: Do not import/load SentenceTransformer at startup when remote embeddings are configured.
# Local SentenceTransformer is allowed ONLY when explicitly enabled.
SentenceTransformer = None  # type: ignore

# Utilities for Qdrant filtering and projection
from .qdrant_utils import to_qdrant_filter, post_filter_items, project_fields

from .goal_types import Goal  # <-- Make sure this exists and is correct
from .memory_manager import Memory

# Unified Vector Client (Phase 1 unification)
try:
    from vector.unified_client import (
        UnifiedVectorClient,
        VectorSearchRequest,
        resolved_mode_matrix,
    )

    _UVC_AVAILABLE = True
except Exception:
    _UVC_AVAILABLE = False
    UnifiedVectorClient = None  # type: ignore
    VectorSearchRequest = None  # type: ignore
    resolved_mode_matrix = lambda env: {}  # type: ignore

# Resolved Mode banner (validation + single-line JSON)
try:
    from config.resolved_mode import ResolvedMode
except Exception:
    ResolvedMode = None  # type: ignore

# Lightweight metrics helper (optional)
try:
    from observability import metrics as _metrics
except Exception:
    _metrics = None  # type: ignore

# Vitals (optional): provenance counters
try:
    from cognitive_vitals import vitals as _vitals  # type: ignore
except Exception:
    _vitals = None  # type: ignore

# Canonical contradiction normalizer (internal only)
try:
    from schemas.contradiction import normalize as _normalize_contradiction  # type: ignore
except Exception:  # pragma: no cover - defensive import guard
    _normalize_contradiction = None  # type: ignore

# ===== WEAVIATE REMOVED =====
# Migrated to Qdrant - Weaviate imports removed
# import weaviate  # REMOVED
# from weaviate.exceptions import WeaviateBaseError  # REMOVED


load_dotenv()

# ――― FEATURE FLAG: Memory Class Switch ―――
USE_MEMORY_ARCHIVE = True

import asyncio

import requests
# ─────────────────────────────────────────────
# Retrieval-aware answers: env toggles (read once at import)
# ─────────────────────────────────────────────

def _env_truthy(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return bool(default)
    return str(val).strip().lower() in {"1", "true", "yes", "y"}


RETRIEVAL_AWARE_ANSWERS = _env_truthy("RETRIEVAL_AWARE_ANSWERS", True)
RETRIEVAL_TEMPLATE_STYLE = (os.getenv("RETRIEVAL_TEMPLATE_STYLE", "concise") or "concise").strip()


def _provenance_required() -> bool:
    try:
        return _env_truthy("AXIOM_PROVENANCE_REQUIRED", True)
    except Exception:
        return True


def _extract_provenance(obj: dict) -> object | None:
    try:
        if not isinstance(obj, dict):
            return None
        if obj.get("provenance") not in (None, "", [], {}):
            return obj.get("provenance")
        meta = obj.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("provenance") not in (None, "", [], {}):
            return meta.get("provenance")
    except Exception:
        pass
    return None


def _record_provenance_event(kind: str) -> None:
    try:
        if _vitals is None:
            return
        k = (kind or "").strip().lower()
        if k == "accepted":
            if hasattr(_vitals, "record_provenance_accepted"):
                _vitals.record_provenance_accepted()
        elif k == "rejected":
            if hasattr(_vitals, "record_provenance_rejected"):
                _vitals.record_provenance_rejected()
        elif k == "legacy":
            if hasattr(_vitals, "record_provenance_legacy_override"):
                _vitals.record_provenance_legacy_override()
    except Exception:
        pass

try:
    from prompts.retrieval_templates import decorate_answer as _decorate_answer
except Exception:
    # Fallback no-op if helper not available
    def _decorate_answer(raw: str, status: str, style: str = "concise") -> str:  # type: ignore
        return (raw or "").strip()


def _get_retrieval_thresholds() -> tuple:
    try:
        min_count = int(os.getenv("RETRIEVAL_MIN_COUNT", "3") or "3")
    except Exception:
        min_count = 3
    try:
        # Prefer canonical knob; keep legacy RETRIEVAL_MIN_SIM for backwards compatibility.
        min_sim = float(
            (
                os.getenv("AXIOM_RETRIEVAL_MIN_SIM")
                or os.getenv("RETRIEVAL_MIN_SIM")
                or "0.30"
            )
            or "0.30"
        )
    except Exception:
        min_sim = 0.30
    return int(min_count), float(min_sim)


def _extract_score_from_hit(hit: object) -> float:
    try:
        s = getattr(hit, "score", None)
        if s is not None:
            return max(0.0, min(1.0, float(s)))
    except Exception:
        pass
    try:
        if isinstance(hit, dict):
            add = hit.get("_additional") or {}
            if isinstance(add, dict) and "score" in add:
                return max(0.0, min(1.0, float(add.get("score", 0.0))))
            if "score" in hit:
                return max(0.0, min(1.0, float(hit.get("score", 0.0))))
    except Exception:
        pass
    return 0.0


def compute_retrieval_status(hits: list) -> tuple[str, float]:
    """
    Classify retrieval quality using existing thresholds.
    Returns (status, top_sim) where status in {"ok","thin","none"}.
    """
    min_count, min_sim = _get_retrieval_thresholds()
    try:
        hit_count = len(hits or [])
    except Exception:
        hit_count = 0
    top_sim = 0.0
    try:
        if hit_count > 0:
            sims = [float(_extract_score_from_hit(h)) for h in (hits or [])]
            if sims:
                top_sim = max(sims)
    except Exception:
        top_sim = 0.0
    if hit_count == 0:
        return "none", float(top_sim)
    if hit_count < min_count or float(top_sim) < float(min_sim):
        return "thin", float(top_sim)
    return "ok", float(top_sim)


def _retrieve_hits_for_answer(query: str, top_k: int = 8):
    """
    Minimal retrieval for /answer to assess recall quality.
    Uses unified client when available; otherwise returns empty list.
    Intentionally lightweight and resilient.
    """
    try:
        if not query or not vector_ready:
            return []
        if _unified_vector_client is None:
            return []
        req = VectorSearchRequest(query=str(query), top_k=int(top_k or 8), filter=None)
        rid = getattr(g, "request_id", None)
        try:
            sr = _unified_vector_client.search(
                req,
                request_id=rid,
                auth_header=request.headers.get("Authorization"),
            )
        except TypeError:
            sr = _unified_vector_client.search(req, request_id=rid)
        return list(getattr(sr, "hits", []) or [])
    except Exception:
        return []


def _generate_raw_answer(summary: str, question: str) -> str:
    facts = world_map.get("ExamplePerson", {})
    if isinstance(facts, dict):
        fact_block = ". ".join(f"{k}: {v}" for k, v in facts.items())
    else:
        fact_block = "[Facts unavailable]"
    return (
        f"Given the summary '{summary}' and the known facts '{fact_block}', "
        f"my answer to '{question}' is based on Axiom's contextual memory."
    )



# DEPRECATED: Weaviate class verification removed - using Qdrant now
def verify_vector_backend() -> bool:
    """Verify vector backend connectivity using Qdrant.

    Uses a single authoritative Qdrant URL when available. Falls back to parsed host/port only when URL is unset.
    Verifies required collections from env and returns True if present.
    """
    try:
        # Resolve via authoritative URL first
        if RESOLVED_QDRANT_URL:
            from qdrant_client import QdrantClient as _QC  # type: ignore
            qc = _QC(url=RESOLVED_QDRANT_URL, timeout=2)
            host = qc._client._host if hasattr(qc, "_client") else "url"
            port = qc._client._port if hasattr(qc, "_client") else None
        else:
            # Fallback to parsed host/port when URL is unset
            host = _RESOLVED_HOST or "localhost"
            port = int(_RESOLVED_PORT or 6333)
        # Required collections
        required_memory = os.getenv("QDRANT_MEMORY_COLLECTION", "axiom_memories")
        required_beliefs = os.getenv("QDRANT_BELIEF_COLLECTION", "axiom_beliefs")
        # Connect and list collections
        try:
            from .qdrant_utils import _list_collection_names, get_qdrant_client
            if RESOLVED_QDRANT_URL:
                from qdrant_client import QdrantClient as _QC  # type: ignore
                client = _QC(url=RESOLVED_QDRANT_URL, timeout=2)
            else:
                client = get_qdrant_client(host, port)
            collections = _list_collection_names(client)
        except Exception:
            # Fallback via axiom_qdrant_client wrapper
            from axiom_qdrant_client import QdrantClient as _AxiomClient
            if RESOLVED_QDRANT_URL:
                client = _AxiomClient(url=RESOLVED_QDRANT_URL)
            else:
                client = _AxiomClient(host=host, port=port)
            collections = set(client.list_collections())
        missing = [
            c for c in (required_memory, required_beliefs) if c not in collections
        ]
        if missing:
            logger.error(
                f"[RECALL][Vector] ❌ Missing required Qdrant collections: {missing}"
            )
            return False
        if RESOLVED_QDRANT_URL:
            logger.info(
                f"[RECALL][Vector] ✅ Qdrant ready at {RESOLVED_QDRANT_URL} with required collections present"
            )
        else:
            logger.info(
                f"[RECALL][Vector] ✅ Qdrant ready at {host}:{port} with required collections present"
            )
        return True
    except Exception as e:
        logger.error(f"[RECALL][Vector] ❌ Qdrant readiness check failed: {e}")
        return False


# Use collection name instead of Weaviate class
try:
    from memory.memory_collections import memory_collection as _memory_collection

    memory_collection = _memory_collection()
except Exception:
    memory_collection = "memories"
print(f"📂 Using vector collection: {memory_collection}")

# ─────────────────────────────────────────────
# Static world facts
# ─────────────────────────────────────────────
world_map_path_used: str | None = None
world_map_loaded: bool = False
world_map_obj: dict = {}

# Back-compat: existing endpoints reference world_map.get("ExamplePerson", {})
# Keep a lightweight facts index derived from the canonical world map.
world_map: dict = {}

_WORLD_MAP_LOCK = threading.Lock()


def resolve_world_map_path() -> str | None:
    """
    Resolve world_map.json path deterministically.

    Order (with env override being authoritative):
      1) WORLD_MAP_PATH env var (returned even if missing, to surface misconfig)
      2) /workspace/world_map.json
      3) ./world_map.json (cwd-relative)
      4) memory/world_map.json (legacy)
      else None
    """
    env_path = (os.getenv("WORLD_MAP_PATH") or "").strip()
    if env_path:
        # Treat env override as authoritative for debuggability.
        return env_path

    candidates = [
        "/workspace/world_map.json",
        os.path.abspath(os.path.join(os.getcwd(), "world_map.json")),
        os.path.abspath(os.path.join(os.getcwd(), "memory", "world_map.json")),
    ]
    for p in candidates:
        try:
            if p and os.path.exists(p):
                return p
        except Exception:
            continue
    return None


def load_world_map(path: str | None) -> dict:
    if not path:
        return {}
    try:
        if not os.path.exists(path):
            logger.warning(f"[world_map] WORLD_MAP_PATH does not exist: {path}")
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
        return obj if isinstance(obj, dict) else {}
    except Exception as e:
        logger.warning(f"[world_map] Failed to load JSON from {path}: {type(e).__name__}", exc_info=True)
        return {}


def _build_legacy_world_facts_index(obj: dict) -> dict:
    """
    Derive a minimal legacy dict for existing /summarise and /answer behavior.
    """
    try:
        entities = obj.get("entities")
        if isinstance(entities, list):
            ent_by_id = {str(e.get("id")): e for e in entities if isinstance(e, dict) and e.get("id")}
            example_person = ent_by_id.get("example_person")
            if isinstance(example_person, dict):
                # Preserve the historical key "ExamplePerson" expected by old endpoints.
                return {"ExamplePerson": example_person}
        if isinstance(entities, dict):
            example_person = entities.get("example_person")
            if isinstance(example_person, dict):
                kk = dict(example_person)
                kk.setdefault("id", "example_person")
                return {"ExamplePerson": kk}
    except Exception:
        pass
    return {}


def _reload_world_map_locked() -> None:
    global world_map_path_used, world_map_loaded, world_map_obj, world_map
    path = resolve_world_map_path()
    obj = load_world_map(path)
    world_map_path_used = path
    world_map_obj = obj if isinstance(obj, dict) else {}
    world_map_loaded = bool(world_map_obj)
    world_map = _build_legacy_world_facts_index(world_map_obj)
    logger.info(
        "[world_map] startup"
        + f" path={world_map_path_used!r}"
        + f" loaded={bool(world_map_loaded)}"
        + f" entities={_world_map_entities_count(world_map_obj)}"
        + f" relationships={_world_map_relationships_count(world_map_obj)}"
    )


def reload_world_map() -> None:
    """
    Lightweight reload helper.
    If WORLD_MAP_RELOAD=1, endpoints can call this per-request.
    """
    with _WORLD_MAP_LOCK:
        _reload_world_map_locked()


def _maybe_reload_world_map() -> None:
    try:
        if (os.getenv("WORLD_MAP_RELOAD") or "").strip() == "1":
            reload_world_map()
    except Exception:
        return


def _world_map_entities_count(obj: dict) -> int:
    try:
        ents = (obj or {}).get("entities")
        if isinstance(ents, list):
            return int(len(ents))
        if isinstance(ents, dict):
            return int(len(ents))
    except Exception:
        pass
    return 0


def _world_map_relationships_count(obj: dict) -> int:
    try:
        rels = (obj or {}).get("relationships")
        if isinstance(rels, list):
            return int(len(rels))
        if isinstance(rels, dict):
            return int(len(rels))
    except Exception:
        pass
    return 0


# Load world map at startup (safe even when missing/invalid)
reload_world_map()

# ─────────────────────────────────────────────
# World map writes (proposal → validate → apply → reload)
# Feature-flagged, default OFF.
# ─────────────────────────────────────────────
try:
    # Local helper (side-effect free; unit-testable)
    from world_map_write import (  # type: ignore
        ValidationResult as _WMValidationResult,
        apply_ops_in_memory as _wm_apply_ops_in_memory,
        atomic_write_world_map as _wm_atomic_write,
        should_auto_apply_kurt as _wm_should_auto_apply_kurt,
        validate_ops as _wm_validate_ops,
    )
except Exception:  # pragma: no cover
    _WMValidationResult = None  # type: ignore
    _wm_apply_ops_in_memory = None  # type: ignore
    _wm_atomic_write = None  # type: ignore
    _wm_should_auto_apply_kurt = None  # type: ignore
    _wm_validate_ops = None  # type: ignore


def _world_map_write_enabled() -> bool:
    return _env_truthy("WORLD_MAP_WRITE_ENABLED", False)


def _world_map_auto_apply_enabled() -> bool:
    return _env_truthy("WORLD_MAP_AUTO_APPLY_ENABLED", False)


def _world_map_auto_apply_min_confidence() -> float:
    try:
        return float(os.getenv("WORLD_MAP_AUTO_APPLY_MIN_CONFIDENCE", "0.95") or 0.95)
    except Exception:
        return 0.95


def _world_map_auto_apply_entity_whitelist() -> set[str]:
    raw = (os.getenv("WORLD_MAP_AUTO_APPLY_ENTITY_WHITELIST", "example_person") or "example_person").strip()
    items = [x.strip().lower() for x in raw.split(",") if x.strip()]
    return set(items or ["example_person"])


def _world_map_auto_apply_hard_fact_paths() -> set[str]:
    """
    CSV of allowed ExamplePerson hard-fact paths for auto-apply.
    Defaults to the initial allowlist from the spec.
    """
    default = (
        "/wife_name,/birth_date,/birth_place,/location,/nationality,"
        "/job_title,/works_at,/worked_at,/career_history,/family,/kids"
    )
    raw = (os.getenv("WORLD_MAP_AUTO_APPLY_HARD_FACT_PATHS") or default).strip() or default
    items = [x.strip() for x in raw.split(",") if x.strip()]
    # Keep only canonical-looking paths
    out = set([p for p in items if p.startswith("/") and len(p) <= 64])
    return out or set([p.strip() for p in default.split(",") if p.strip()])


def _world_map_proposal_store_path() -> str:
    return (os.getenv("WORLD_MAP_PROPOSAL_STORE_PATH") or "/app/data/world_map_proposals.jsonl").strip()


def _journal_append_path() -> str:
    return (os.getenv("AXIOM_JOURNAL_APPEND_PATH") or "/app/journal/axiom_journal.jsonl").strip()


def _jsonl_append(path: str, record: dict) -> None:
    p = str(path or "").strip()
    if not p:
        raise ValueError("missing_path")
    parent = os.path.dirname(p) or "."
    os.makedirs(parent, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _jsonl_load_all(path: str) -> list[dict]:
    p = str(path or "").strip()
    if not p or (not os.path.exists(p)):
        return []
    out: list[dict] = []
    try:
        with open(p, "r", encoding="utf-8") as fh:
            for ln in fh:
                s = (ln or "").strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                    if isinstance(obj, dict):
                        out.append(obj)
                except Exception:
                    continue
    except Exception:
        return []
    return out


def _jsonl_update_record(path: str, proposal_id: str, updates: dict) -> dict | None:
    """Rewrite JSONL in-place updating the first matching proposal_id."""
    p = str(path or "").strip()
    if not p:
        return None
    items = _jsonl_load_all(p)
    updated: dict | None = None
    for i, rec in enumerate(items):
        if isinstance(rec, dict) and str(rec.get("proposal_id") or "") == str(proposal_id):
            new_rec = dict(rec)
            new_rec.update({k: v for k, v in (updates or {}).items()})
            items[i] = new_rec
            updated = new_rec
            break
    if updated is None:
        return None
    parent = os.path.dirname(p) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = f"{p}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for rec in items:
            if isinstance(rec, dict):
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, p)
    return updated


def _world_map_entity_exists(entity_id: str) -> bool:
    try:
        _maybe_reload_world_map()
        return _wm_get_entity(str(entity_id)) is not None
    except Exception:
        return False


def _apply_world_map_ops_atomic(*, entity_id: str, ops: list[dict]) -> tuple[bool, dict]:
    """Apply ops to world_map.json with backup+atomic write, then reload."""
    if _wm_apply_ops_in_memory is None or _wm_atomic_write is None:
        return False, {"error": "world_map_write_module_unavailable"}
    path = resolve_world_map_path()
    if not path:
        return False, {"error": "world_map_path_unresolved"}
    if not os.path.exists(path):
        return False, {"error": "world_map_missing", "path": path}

    # Load from disk (source of truth for writes)
    current = load_world_map(path)
    try:
        new_obj, changed_fields = _wm_apply_ops_in_memory(world_map_obj=current, entity_id=entity_id, ops=ops)
    except Exception as e:
        return False, {"error": "apply_failed", "detail": f"{type(e).__name__}: {str(e)[:200]}"}

    # Atomic write + backup
    try:
        _tmp, backup = _wm_atomic_write(world_map_path=path, new_obj=new_obj)
    except Exception as e:
        return False, {"error": "write_failed", "detail": f"{type(e).__name__}: {str(e)[:200]}"}

    # Reload in-memory caches
    try:
        reload_world_map()
    except Exception as e:
        return False, {"error": "reload_failed", "detail": f"{type(e).__name__}: {str(e)[:200]}", "backup": backup}

    return True, {
        "ok": True,
        "world_map_path": path,
        "backup_path": backup,
        "changed_fields": list(changed_fields or []),
        "world_map_loaded": bool(world_map_loaded),
        "entities": _world_map_entities_count(world_map_obj),
        "relationships": _world_map_relationships_count(world_map_obj),
    }

# ─────────────────────────────────────────────
# Vector backend setup - using Qdrant via adapter
# ─────────────────────────────────────────────
VECTOR_DB_HOST = os.getenv("QDRANT_URL", "http://vector:9000")
VECTOR_URL = VECTOR_DB_HOST
ENABLE_PUSH = bool(os.getenv("VECTOR_SYNC", "0") == "1")

# Global flag to track vector connectivity status
vector_ready = False


def initialize_vector_backend():
    """
    Initialize connection to vector backend (Qdrant via adapter).
    """
    global vector_ready

    try:
        print(f"🔌 Checking vector backend at {VECTOR_URL}")
        vector_ready = verify_vector_backend()
        # Update boot flags (soft gating)
        set_boot_status({"vector_collections_ready": bool(vector_ready)})
        if vector_ready:
            print("✅ Vector backend ready")
        else:
            logger.warning("[BOOT] Vector collections unavailable. Entering DEGRADED mode.")
            print("⚠️ Vector backend not available. Proceeding without vector support.")
            _log_degraded_if_needed()

    except Exception as e:
        vector_ready = False
        set_boot_status({"vector_collections_ready": False})
        print(
            f"⚠️ Unexpected error checking vector backend: {e}. Proceeding without vector support."
        )
        _log_degraded_if_needed()


# Initialize the backend at startup
initialize_vector_backend()

# Instantiate unified vector client once (read-only; preserves 503 gating)
_unified_vector_client = None
if _UVC_AVAILABLE:
    try:
        # Pass resolved URL explicitly when constructor supports it; otherwise resolver runs inside client
        try:
            _unified_vector_client = UnifiedVectorClient(os.environ, qdrant_url=RESOLVED_QDRANT_URL)
        except TypeError:
            _unified_vector_client = UnifiedVectorClient(os.environ)
        # Startup JSON mode banner (fail fast on incompatible combos)
        if ResolvedMode is not None:
            try:
                rm = ResolvedMode.from_env(os.environ, default_role="memory")
                print(rm.json_line(component="startup"))
            except Exception as _e:
                # Fail fast: invalid configuration
                raise
    except Exception as _e:
        logger.warning(f"[VectorPath] UnifiedVectorClient init failed: {_e}")

# ─────────────────────────────────────────────
# Startup Canary (non-mutating, optional)
# ─────────────────────────────────────────────
_CANARY_RESULT = {"disabled": True}

def _run_startup_canary():
    global _CANARY_RESULT
    try:
        if os.getenv("AXIOM_CANARIES", "1").strip().lower() in {"0", "false", "no"}:
            _CANARY_RESULT = {"disabled": True}
            return
        if not vector_ready or _unified_vector_client is None:
            _CANARY_RESULT = {"status": "skip", "reason": "vector_not_ready"}
            # Reflect breaker/boot flags for degraded awareness
            try:
                set_boot_status({"breaker_open": True})
            except Exception:
                pass
            return
        # One-shot query with 1s timeout by temporarily overriding client timeout
        try:
            # Save current timeout and retries, then set canary-fast params
            old_timeout = getattr(_unified_vector_client, "_timeout_sec", 8.0)
            old_retries = getattr(_unified_vector_client, "_retry_attempts", 3)
            _unified_vector_client._timeout_sec = 1.0
            _unified_vector_client._retry_attempts = 1
            t0 = time.perf_counter()
            _ = _unified_vector_client.search(
                VectorSearchRequest(query="__canary__", top_k=1),
                auth_header=(getattr(request, "headers", {}) or {}).get("Authorization") if "request" in globals() else None,
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            _CANARY_RESULT = {"status": "ok", "latency_ms": round(dt_ms, 2)}
            print("{" + f"\"component\":\"canary\",\"status\":\"ok\",\"latency_ms\":{round(dt_ms,2)}" + "}")
            # Metrics
            if _metrics is not None:
                _metrics.observe_ms("vector.canary.ms", dt_ms)
        except Exception as e:
            reason = str(e)
            if len(reason) > 200:
                reason = reason[:200]
            _CANARY_RESULT = {"status": "fail", "reason": reason}
            print("{" + f"\"component\":\"canary\",\"status\":\"fail\",\"reason\":\"{reason}\"" + "}")
        finally:
            # Restore client params
            try:
                _unified_vector_client._timeout_sec = old_timeout
                _unified_vector_client._retry_attempts = old_retries
            except Exception:
                pass
    except Exception:
        _CANARY_RESULT = {"status": "fail", "reason": "unexpected"}

import time as _time_mod_guard
time = _time_mod_guard

try:
    _run_startup_canary()
except Exception:
    pass

# --- Vector fallback singletons ---
QDRANT_HOST, QDRANT_PORT = (_RESOLVED_HOST or "localhost"), int(_RESOLVED_PORT or 6333)
_embedder = None
_qdrant_client = None


def _embeddings_status() -> dict:
    """
    Lightweight, non-loading embeddings readiness snapshot.
    Does NOT instantiate models.
    """
    # Remote embeddings (preferred)
    base_url = (
        os.getenv("AXIOM_EMBEDDING_URL", "")
        or os.getenv("EMBEDDINGS_API_URL", "")
        or os.getenv("EMBEDDINGS_POD_URL", "")
        or os.getenv("VECTOR_EMBEDDING_URL", "")
        or ""
    ).strip().rstrip("/")
    if base_url:
        return {"embeddings_ready": True, "embeddings_mode": "remote", "embeddings_reason": None}

    # Local sentence-transformers (explicitly gated)
    if _env_truthy("AXIOM_USE_SENTENCE_TRANSFORMERS", False):
        try:
            import sentence_transformers  # type: ignore  # noqa: F401
            return {"embeddings_ready": True, "embeddings_mode": "sentence_transformers", "embeddings_reason": None}
        except Exception as e:
            return {
                "embeddings_ready": False,
                "embeddings_mode": "sentence_transformers",
                "embeddings_reason": f"sentence_transformers_unavailable:{type(e).__name__}",
            }

    return {
        "embeddings_ready": False,
        "embeddings_mode": "disabled",
        "embeddings_reason": "embeddings_unconfigured: set AXIOM_EMBEDDING_URL or enable AXIOM_USE_SENTENCE_TRANSFORMERS=true",
    }


def _get_embedder():
    global _embedder
    if _embedder is None:
        # Prefer remote embeddings when configured to avoid SentenceTransformer downloads.
        base_url = (
            os.getenv("AXIOM_EMBEDDING_URL", "")
            or os.getenv("EMBEDDINGS_API_URL", "")
            or os.getenv("EMBEDDINGS_POD_URL", "")
            or os.getenv("VECTOR_EMBEDDING_URL", "")
            or ""
        ).strip().rstrip("/")
        model_name = (
            os.getenv("AXIOM_EMBEDDING_MODEL", "")
            or os.getenv("ST_MODEL", "")
            or "BAAI/bge-small-en-v1.5"
        ).strip()

        if base_url:
            # Minimal remote shim (avoid importing sentence_transformers entirely).
            class _RemoteEmbedderCompat:
                def __init__(self, base: str, model: str):
                    self._base = base
                    self._model = model
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
                    timeout = float(os.getenv("AXIOM_EMBEDDING_TIMEOUT_SEC", "12") or 12)
                    r = requests.post(f"{self._base}/embed", json=payload, timeout=timeout)
                    r.raise_for_status()
                    data = r.json() or {}
                    vecs = data.get("vectors") or []
                    if not isinstance(vecs, list) or len(vecs) != len(batch):
                        raise RuntimeError("embeddings_invalid_response")
                    return vecs[0] if single else vecs

            _embedder = _RemoteEmbedderCompat(base_url, model_name)
        else:
            # Local embeddings only when explicitly allowed.
            if not _env_truthy("AXIOM_USE_SENTENCE_TRANSFORMERS", False):
                raise RuntimeError(
                    "embeddings_unconfigured: set AXIOM_EMBEDDING_URL or enable AXIOM_USE_SENTENCE_TRANSFORMERS=true"
                )
            try:
                from sentence_transformers import SentenceTransformer as _ST  # type: ignore
            except Exception as e:
                raise RuntimeError(f"sentence_transformers_unavailable:{type(e).__name__}") from e

            # Prefer canonical env; warn on legacy AXIOM_EMBEDDER
            model_name_local = os.getenv("AXIOM_EMBEDDING_MODEL")
            if not model_name_local:
                legacy = os.getenv("AXIOM_EMBEDDER") or os.getenv("EMBEDDING_MODEL")
                if legacy:
                    try:
                        log.warning("[RECALL][Deprecation] AXIOM_EMBEDDER is deprecated; use AXIOM_EMBEDDING_MODEL")
                    except Exception:
                        pass
                model_name_local = legacy or "all-MiniLM-L6-v2"
            _embedder = _ST(model_name_local)
    return _embedder


def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=RESOLVED_QDRANT_URL) if RESOLVED_QDRANT_URL else QdrantClient(host=QDRANT_HOST, port=int(QDRANT_PORT))
    return _qdrant_client


# ─────────────────────────────────────────────
# Startup composite scoring warnings (non-fatal)
# ─────────────────────────────────────────────
try:
    use_composite = os.getenv("AXIOM_COMPOSITE_SCORING", "0") == "1"
    if not use_composite:
        log.warning(
            "[axiom] Composite scoring disabled (AXIOM_COMPOSITE_SCORING not set or 0)"
        )
    expected_yaml = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "..",
        "config",
        "composite_weights.yaml",
    )
    # Resolve relative to repo root if possible
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    yaml_path = os.path.join(repo_root, "config", "composite_weights.yaml")
    if not os.path.exists(yaml_path):
        # Fallback to nearby relative path
        if not os.path.exists(expected_yaml):
            log.warning(
                "[axiom] Missing config/composite_weights.yaml — composite weights will fallback to defaults"
            )
except Exception as _e:
    log.warning(f"[axiom] Composite scoring startup checks failed: {_e}")


# ─────────────────────────────────────────────
# Memory Loading - Support both JSON and Qdrant modes
# ─────────────────────────────────────────────
def load_memory_data():
    """Load memory data from either JSON file or Qdrant, based on command-line flags."""
    global memory_data

    if args.use_qdrant and QDRANT_AVAILABLE:
        try:
            target_url = RESOLVED_QDRANT_URL or (f"http://{_RESOLVED_HOST}:{_RESOLVED_PORT}")
            log.info(f"🔄 Loading memory from Qdrant at {target_url}")
            # load utility accepts host/port; prefer parsed when URL provided
            host_for_load = _RESOLVED_HOST or "localhost"
            port_for_load = int(_RESOLVED_PORT or 6333)
            memory_data = load_memory_from_qdrant(
                host=host_for_load,
                port=port_for_load,
                collection_name=args.qdrant_collection,
            )
            log.info(
                f"✅ Loaded {len(memory_data)} items from Qdrant collection '{args.qdrant_collection}'"
            )
            # Journal considered loaded when Qdrant-backed load succeeds
            set_boot_status({"journal_loaded": True})
            return memory_data
        except Exception as e:
            log.error(f"❌ Failed to load from Qdrant: {e}")
            if args.allow_empty_memory:
                log.warning(
                    "⚠️ Continuing with empty memory due to --allow_empty_memory flag"
                )
                memory_data = []
                set_boot_status({"journal_loaded": False})
                return memory_data
            else:
                log.error(
                    "💥 Exiting due to Qdrant failure. Use --allow_empty_memory to continue with empty memory."
                )
                sys.exit(1)
    else:
        # Default: Load from JSON file using existing Memory class
        log.info("📁 Loading memory from JSON file (default mode)")
        memory = Memory()
        try:
            memory.load()
            set_boot_status({"journal_loaded": True})
        except Exception as _e:
            # Treat as fatal only if file is corrupt and cannot be loaded
            log.error(f"❌ Journal load error: {_e}")
            set_boot_status({"journal_loaded": False})
            raise
        memory_data = memory.snapshot(limit=None)  # Get all items, not just last 100
        log.info(f"✅ Loaded {len(memory_data)} items from JSON file")
        return memory_data


# ─────────────────────────────────────────────
# JSON Store Helpers for JSON Mode
# ─────────────────────────────────────────────
JSON_STORE_PATH = "/workspace/memory/long_term_memory.json"


def _json_store_path() -> str:
    os.makedirs(os.path.dirname(JSON_STORE_PATH), exist_ok=True)
    if not os.path.exists(JSON_STORE_PATH):
        with open(JSON_STORE_PATH, "w") as f:
            json.dump([], f)
    return JSON_STORE_PATH


def _json_load() -> List[Dict[str, Any]]:
    p = _json_store_path()
    try:
        with open(p, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _json_save(rows: List[Dict[str, Any]]) -> None:
    p = _json_store_path()
    with open(p, "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def _json_append(rec: Dict[str, Any]) -> str:
    rows = _json_load()
    # Normalize & ensure UUID
    rid = str(uuid.uuid4())
    now = time.time()
    rec = {
        "uuid": rid,
        "user_id": rec.get("user_id"),
        "source": rec.get("source", "unknown"),
        "content": rec.get("content") or rec.get("text") or "",
        "created_at": rec.get("created_at", now),
        **{
            k: v
            for k, v in rec.items()
            if k not in {"uuid", "user_id", "source", "content", "text", "created_at"}
        },
    }
    rows.append(rec)
    _json_save(rows)
    return rid


def _json_query(
    ids: List[str] | None = None, user_id: str | None = None, limit: int = 50
) -> List[Dict[str, Any]]:
    rows = _json_load()
    if ids:
        idset = set(ids)
        rows = [r for r in rows if str(r.get("uuid")) in idset]
    if user_id:
        rows = [r for r in rows if r.get("user_id") == user_id]
    # newest-first by created_at if present
    rows.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return rows[: max(0, int(limit or 50))]


def _json_mode_enabled() -> bool:
    return str(os.environ.get("USE_QDRANT_BACKEND", "0")).strip() in (
        "0",
        "",
        "false",
        "False",
    )


# ─────────────────────────────────────────────
# Flask app
# ─────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

_OPEN_PATH_PREFIXES = ("/static/",)
# Keep standard probe endpoints open even when auth is enabled.
# IMPORTANT: keep this minimal; do not open other routes.
_OPEN_PATHS = {"/", "/ping", "/health", "/healthz", "/livez", "/readyz"}

# ─────────────────────────────────────────────
# Correlation ID middleware (configurable header)
# ─────────────────────────────────────────────
_REQID_HEADER = os.getenv("AXIOM_REQUEST_ID_HEADER", "X-Request-ID").strip() or "X-Request-ID"
_REQID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,200}$")


def _new_req_id() -> str:
    return str(uuid.uuid4())


def _sanitize_req_id(val: str | None) -> str:
    if isinstance(val, str) and val and _REQID_RE.match(val):
        return val
    return _new_req_id()


@app.before_request
def _attach_request_id():
    try:
        rid_in = request.headers.get(_REQID_HEADER)
        rid = _sanitize_req_id(rid_in)
        g.request_id = rid
    except Exception:
        g.request_id = _new_req_id()


@app.after_request
def _propagate_request_id(resp):
    try:
        rid = getattr(g, "request_id", None)
        if rid:
            resp.headers[_REQID_HEADER] = rid
    except Exception:
        pass
    return resp

# ---- Auth guard (optional; default OFF); keep after request-id so rid is set ----
@app.before_request
def _auth_guard():
    # Keep some endpoints open even when auth is enabled
    path = request.path or ""
    if path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PATH_PREFIXES):
        return None
    ok, err = ax_auth.verify_request(request)
    if not ok:
        resp = jsonify(err)
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Bearer realm="Axiom"'
        return resp
    return None

# Initialize memory data based on the selected mode
memory_data = []
if args.use_qdrant:
    # For Qdrant mode, we manage memory_data directly
    load_memory_data()
    memory = None  # Don't create Memory instance for Qdrant mode
else:
    # For JSON mode, use the existing Memory class
    memory = Memory()
    try:
        memory.load()
        set_boot_status({"journal_loaded": True})
    except Exception as _e:
        log.error(f"❌ Journal load error: {_e}")
        set_boot_status({"journal_loaded": False})
    memory_data = memory.snapshot(limit=None)  # Cache the data for health endpoint

# Extra: Log Qdrant collection schema if available (distance, dim)
try:
    if args.use_qdrant and QDRANT_AVAILABLE:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=RESOLVED_QDRANT_URL, timeout=5) if RESOLVED_QDRANT_URL else QdrantClient(host=_RESOLVED_HOST or "localhost", port=int(_RESOLVED_PORT or (args.qdrant_port or 6333)), timeout=5)
        info = client.get_collection(args.qdrant_collection)
        metric = None
        dim = None
        vectors_cfg = getattr(info, "vectors", None)
        if vectors_cfg and hasattr(vectors_cfg, "config"):
            cfg = vectors_cfg.config
            dim = getattr(cfg, "size", None)
            metric = getattr(cfg, "distance", None)
        if str(metric).lower().find("cosine") == -1:
            log.warning(f"[axiom] Qdrant collection distance not cosine: {metric}")
        if dim is not None and int(dim) != 384:
            log.warning(f"[axiom] Qdrant vector dimension mismatch: {dim} != 384")
except Exception as _e:
    log.warning(f"[axiom] Qdrant schema introspection failed: {_e}")


# ─────────────────────────────────────────────
# Boot orchestration (additive, flag-gated)
# ─────────────────────────────────────────────
try:
    from boot import BOOT_ORCHESTRATION_ENABLED, BOOT_VERSION_BANNER_ENABLED  # type: ignore
except Exception:
    BOOT_ORCHESTRATION_ENABLED = True  # type: ignore
    BOOT_VERSION_BANNER_ENABLED = True  # type: ignore

try:
    if BOOT_ORCHESTRATION_ENABLED:
        from boot.phases import run_boot  # type: ignore
        from boot.version_banner import collect_banner  # type: ignore
        from pods.cockpit.cockpit_reporter import write_signal  # type: ignore

        def _phase0() -> bool:
            # Fast env/config validation already handled elsewhere
            return True

        def _phase1() -> bool:
            # Local init done during module import
            return True

        def _phase2() -> bool:
            # Optional warmup of caches
            return True

        def _deps_check() -> dict:
            # Memory normal mode requires vector and journal; degraded if journal only
            def _vector_ping_ok() -> bool:
                try:
                    # Prefer unified client health when available
                    from vector.unified_client import UnifiedVectorClient  # type: ignore

                    client = UnifiedVectorClient(os.environ)
                    return bool(client.health())
                except Exception:
                    try:
                        from qdrant_client import QdrantClient  # type: ignore

                        if RESOLVED_QDRANT_URL:
                            qc = QdrantClient(url=RESOLVED_QDRANT_URL, timeout=2)
                        else:
                            qc = QdrantClient(host=_RESOLVED_HOST or "localhost", port=int(_RESOLVED_PORT or 6333), timeout=2)
                        _ = qc.get_collections()
                        return True
                    except Exception:
                        return False

            def _journal_ok() -> bool:
                # Journal considered locally available; if a journal pod exists, readiness is inferred via Cockpit
                return True

            return {"vector": _vector_ping_ok(), "journal": _journal_ok()}

        # Ensure env defaults for memory pod policy
        os.environ.setdefault("BOOT_REQUIRE", "vector,journal")
        os.environ.setdefault("BOOT_DEGRADED_MIN_REQUIRE", "journal")

        _boot_status = run_boot("memory", {"Phase0": _phase0, "Phase1": _phase1, "Phase2": _phase2}, _deps_check)
        if BOOT_VERSION_BANNER_ENABLED:
            try:
                write_signal("memory", "version_banner", collect_banner())
            except Exception:
                pass
except Exception:
    # Never crash on boot wiring
    pass


def _probe_text(body: str, status_code: int = 200):
    """Small helper for K8s-style probe responses (text/plain)."""
    resp = make_response(body, status_code)
    # Preserve request-id middleware behavior; only set content-type.
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    return resp


def is_ready() -> bool:
    """
    Readiness for generic probes.

    IMPORTANT: must be cheap/pure and based only on already-computed in-memory flags.
    No network calls, no filesystem access, no JSON parsing, no lazy init.
    """
    try:
        return bool(
            journal_loaded
            and vector_collections_ready
            and (not breaker_open)
            and (not vector_circuit_open)
        )
    except Exception:
        return False


@app.route("/", methods=["GET"])
def index():
    # Keep small and stable for generic callers (LBs, smoke checks).
    return jsonify({"service": "axiom_memory", "status": "ok"}), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return _probe_text("ok", 200)


@app.route("/livez", methods=["GET"])
def livez():
    return _probe_text("ok", 200)


@app.route("/ping", methods=["GET"])
def ping():
    """
    Ultra-light probe endpoint.

    Must return immediately with 200 and must not invoke Qdrant / embeddings.
    """
    return jsonify({"ok": True}), 200


@app.route("/readyz", methods=["GET"])
def readyz():
    # Minimal acceptable readiness:
    # - status == "ok" (no exceptions evaluating readiness)
    # - vector_ready == True
    # - memory_size > 0
    #
    # IMPORTANT: keep this cheap (no network calls); use already-loaded in-memory state.
    try:
        # Prefer cached snapshot list length (stable, cheap). Fall back to Memory.__len__ only when needed.
        memory_size = int(len(memory_data or []))
        if memory_size <= 0 and memory is not None:
            try:
                memory_size = int(len(memory))
            except Exception:
                pass
        status = "ok"
        vready = bool(vector_ready) and (not bool(vector_circuit_open))
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "not_ready",
                    "error": f"readiness_exception:{type(e).__name__}",
                    "failed": {"status_ok": False},
                }
            ),
            503,
        )

    checks = {
        "status_ok": status == "ok",
        "vector_ready": vready is True,
        "memory_nonempty": int(memory_size or 0) > 0,
    }
    failed = {k: v for k, v in checks.items() if not bool(v)}
    if not failed:
        return jsonify({"status": "ok", "memory_size": memory_size, "vector_ready": True}), 200
    return jsonify({"status": "not_ready", "failed": failed, "memory_size": memory_size, "vector_ready": bool(vready)}), 503


@app.route("/health", methods=["GET"])
def health():
    try:
        kurt_facts = world_map.get("ExamplePerson", {})

        # Get memory size based on the current mode
        if args.use_qdrant and QDRANT_AVAILABLE:
            try:
                # Get live count from Qdrant
                if RESOLVED_QDRANT_URL:
                    # Use a short-timeout client directly when URL is available
                    client = QdrantClient(url=RESOLVED_QDRANT_URL, timeout=2)
                    try:
                        result = client.count(collection_name=args.qdrant_collection)
                    except TypeError:
                        result = client.count(collection_name=args.qdrant_collection, filter=None)
                    memory_size = int(getattr(result, "count", result))
                else:
                    memory_size = get_qdrant_collection_count(
                        host=_RESOLVED_HOST or "localhost",
                        port=int(_RESOLVED_PORT or (args.qdrant_port or 6333)),
                        collection_name=args.qdrant_collection,
                    )
            except Exception as e:
                log.warning(f"Failed to get Qdrant count, using cached data: {e}")
                memory_size = len(memory_data)
        else:
            # Use traditional Memory class
            memory_size = len(memory) if memory else len(memory_data)

        # Compute world_facts truthfully
        world_facts_value = None
        if args.use_qdrant and QDRANT_AVAILABLE:
            try:
                # Fast count with tag filter (world_map_entity OR world_map_event)
                try:
                    from qdrant_client import models as qm  # type: ignore
                except Exception:
                    qm = None  # type: ignore

                # Build filter (prefer MatchAny when available)
                qfilter = None
                tags_any = ["world_map_entity", "world_map_event"]
                if qm is not None:
                    try:
                        if hasattr(qm, "MatchAny"):
                            qfilter = qm.Filter(
                                must=[
                                    qm.FieldCondition(
                                        key="tags", match=qm.MatchAny(any=tags_any)
                                    )
                                ]
                            )
                        else:
                            should_conds = [
                                qm.FieldCondition(key="tags", match=qm.MatchValue(value=v))
                                for v in tags_any
                            ]
                            qfilter = qm.Filter(should=should_conds)
                    except Exception:
                        qfilter = None

                # Use a short timeout client
                client = QdrantClient(url=RESOLVED_QDRANT_URL, timeout=2) if RESOLVED_QDRANT_URL else QdrantClient(host=_RESOLVED_HOST or "localhost", port=int(_RESOLVED_PORT or (args.qdrant_port or 6333)), timeout=2)
                try:
                    # Newer clients
                    result = client.count(collection_name=args.qdrant_collection, count_filter=qfilter)
                except TypeError:
                    # Older clients may use 'filter' kw
                    result = client.count(collection_name=args.qdrant_collection, filter=qfilter)

                try:
                    world_facts_value = int(getattr(result, "count", result))
                except Exception:
                    # As a last resort, coerce to int if possible
                    world_facts_value = int(result) if isinstance(result, (int, float)) else None
            except Exception as _e:
                # Single-line WARN, no stack trace
                log.warning(f"[health] world_facts count failed: {_e}")
                world_facts_value = None

        # Surface circuit breaker state and gate vector_ready when open
        vector_circuit_open = False
        try:
            if _unified_vector_client is not None and hasattr(_unified_vector_client, "is_circuit_open"):
                vector_circuit_open = bool(_unified_vector_client.is_circuit_open())
        except Exception:
            vector_circuit_open = False

        response_vector_ready = bool(vector_ready) and (not vector_circuit_open)

        # Compose boot flags snapshot
        _flags = _get_boot_status()

        response = {
            "status": "ok",
            "memory_size": memory_size,
            "world_facts": world_facts_value,
            "vector_ready": response_vector_ready,  # gate by circuit breaker
            "vector_circuit_open": bool(vector_circuit_open),
            # world map (file-based) status (additive; does not affect world_facts)
            "world_map_loaded": bool(world_map_loaded),
            "world_map_path": world_map_path_used,
            "world_map_entities_count": _world_map_entities_count(world_map_obj),
            "world_map_relationships_count": _world_map_relationships_count(world_map_obj),
            # boot integrity flags (soft degraded awareness)
            "vector_collections_ready": bool(_flags.get("vector_collections_ready", False)),
            "journal_loaded": bool(_flags.get("journal_loaded", False)),
            "breaker_open": bool(_flags.get("breaker_open", False) or vector_circuit_open),
            "identity_primed": bool(_flags.get("identity_primed", False)),
            "memory_source": (
                "json_file"
                if _json_mode_enabled()
                else ("qdrant" if args.use_qdrant else "json_file")
            ),
            "resolved_qdrant_url": RESOLVED_QDRANT_URL if args.use_qdrant else None,
            "config_warnings": _QDRANT_WARNINGS if (_QDRANT_WARNINGS and args.use_qdrant) else None,
        }
        # New (non-breaking) embeddings readiness fields
        response.update(_embeddings_status())

        return jsonify(response)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "detail": str(e)}), 500


def _wm_entities_section() -> Any:
    try:
        return (world_map_obj or {}).get("entities")
    except Exception:
        return None


def _wm_relationships_section() -> Any:
    try:
        return (world_map_obj or {}).get("relationships")
    except Exception:
        return None


def _wm_get_entity(entity_id: str) -> dict | None:
    entities = _wm_entities_section()
    if isinstance(entities, list):
        for ent in entities:
            if isinstance(ent, dict) and str(ent.get("id")) == str(entity_id):
                return ent
        return None
    if isinstance(entities, dict):
        if entity_id in entities and isinstance(entities.get(entity_id), dict):
            ent = dict(entities.get(entity_id) or {})
            ent.setdefault("id", entity_id)
            return ent
        return None
    return None


def _wm_list_relationships() -> List[dict]:
    rels = _wm_relationships_section()
    if isinstance(rels, list):
        return [r for r in rels if isinstance(r, dict)]
    if isinstance(rels, dict):
        out: List[dict] = []
        for rid, rv in rels.items():
            if isinstance(rv, dict):
                r = dict(rv)
                r.setdefault("id", rid)
                out.append(r)
        return out
    return []


def _wm_filter_relationships(entity_id: str, direction: str) -> List[dict]:
    want = str(direction or "any").strip().lower() or "any"
    if want not in {"any", "out", "in"}:
        want = "any"
    ent = str(entity_id)

    rels = _wm_list_relationships()
    out: List[dict] = []
    for r in rels:
        src = str(r.get("source")) if r.get("source") is not None else ""
        tgt = str(r.get("target")) if r.get("target") is not None else ""
        if want == "out" and src == ent:
            out.append(r)
        elif want == "in" and tgt == ent:
            out.append(r)
        elif want == "any" and (src == ent or tgt == ent):
            out.append(r)
    # Deterministic ordering
    out.sort(key=lambda x: (str(x.get("type") or ""), str(x.get("source") or ""), str(x.get("target") or ""), str(x.get("id") or "")))
    return out


def _wm_profile_summary(entity: dict, relationships: List[dict]) -> str:
    bullets: List[str] = []

    eid = str(entity.get("id") or "")
    name = (
        entity.get("display_name")
        or entity.get("name")
        or entity.get("full_name")
        or eid
        or "unknown"
    )
    etype = entity.get("type")
    role = entity.get("role")
    headline = f"{name}"
    if etype:
        headline += f" ({etype})"
    if role:
        headline += f" – {role}"
    bullets.append(headline)

    # Common deterministic fields (only include when present)
    def _add_if(key: str, label: str | None = None):
        if key in entity and entity.get(key) not in (None, "", [], {}):
            v = entity.get(key)
            lbl = label or key
            bullets.append(f"{lbl}: {v}")

    _add_if("alias")
    _add_if("job_title", "job_title")
    _add_if("works_at", "works_at")
    _add_if("location", "location")
    _add_if("nationality", "nationality")
    _add_if("birth_date", "birth_date")
    _add_if("family", "family")
    _add_if("kids", "kids")
    _add_if("pets", "pets")
    _add_if("projects", "projects")
    _add_if("goals", "goals")
    _add_if("identity", "identity")
    _add_if("characteristics", "characteristics")

    # Relationship rollup (bounded and deterministic)
    if relationships:
        # type counts
        counts: Dict[str, int] = {}
        for r in relationships:
            t = str(r.get("type") or "unknown")
            counts[t] = counts.get(t, 0) + 1
        types_line = ", ".join(f"{k}×{counts[k]}" for k in sorted(counts.keys()))
        bullets.append(f"relationships: {types_line}")

        # Show a few concrete edges
        shown = 0
        for r in relationships:
            if shown >= 5:
                break
            t = str(r.get("type") or "related_to")
            src = str(r.get("source") or "")
            tgt = str(r.get("target") or "")
            if src and tgt:
                bullets.append(f"edge: {src} -({t})-> {tgt}")
                shown += 1

    # Bound: ~10 bullets and ~1200 chars total
    bullets = bullets[:10]
    out = "\n".join(f"- {b}" for b in bullets if isinstance(b, str) and b.strip())
    if len(out) > 1200:
        out = out[:1200]
    return out


@app.route("/world_map/entity/<entity_id>", methods=["GET"])
def world_map_entity(entity_id: str):
    _maybe_reload_world_map()
    ent = _wm_get_entity(str(entity_id))
    if ent is None:
        return jsonify({"ok": False, "error": "not_found", "entity_id": str(entity_id)}), 404
    return jsonify({"ok": True, "entity": ent, "entity_id": str(entity_id)}), 200


@app.route("/world_map/relationships", methods=["GET"])
def world_map_relationships():
    _maybe_reload_world_map()
    entity_id = (request.args.get("entity_id") or "").strip()
    if not entity_id:
        return jsonify({"ok": False, "error": "missing_entity_id"}), 400
    direction = (request.args.get("direction") or "any").strip().lower() or "any"
    if direction not in {"any", "out", "in"}:
        return jsonify({"ok": False, "error": "invalid_direction", "direction": direction}), 400
    rels = _wm_filter_relationships(entity_id=entity_id, direction=direction)
    return jsonify({"ok": True, "entity_id": entity_id, "direction": direction, "relationships": rels}), 200


@app.route("/world_map/profile/<entity_id>", methods=["GET"])
def world_map_profile(entity_id: str):
    _maybe_reload_world_map()
    ent = _wm_get_entity(str(entity_id))
    if ent is None:
        return jsonify({"ok": False, "error": "not_found", "entity_id": str(entity_id)}), 404
    rels = _wm_filter_relationships(entity_id=str(entity_id), direction="any")
    summary = _wm_profile_summary(ent, rels)
    return (
        jsonify(
            {
                "ok": True,
                "entity_id": str(entity_id),
                "entity": ent,
                "relationships": rels,
                "summary": summary,
            }
        ),
        200,
    )


@app.route("/world_map/reload", methods=["POST"])
def world_map_reload():
    """Reload world_map.json into memory (lightweight, no deps)."""
    try:
        reload_world_map()
        return (
            jsonify(
                {
                    "ok": True,
                    "world_map_loaded": bool(world_map_loaded),
                    "world_map_path": world_map_path_used,
                    "entities": _world_map_entities_count(world_map_obj),
                    "relationships": _world_map_relationships_count(world_map_obj),
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"ok": False, "error": "reload_failed", "detail": str(e)[:200]}), 500


@app.route("/world_map/propose", methods=["POST"])
def world_map_propose():
    """Create a pending world map proposal; auto-apply only when policy allows."""
    if not _world_map_write_enabled():
        return jsonify({"ok": False, "error": "world_map_write_disabled"}), 403

    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    entity_id = str(payload.get("entity_id") or "").strip()
    ops = payload.get("ops")
    confidence = payload.get("confidence")
    evidence = payload.get("evidence")

    if _wm_validate_ops is None:
        return jsonify({"ok": False, "error": "world_map_write_module_unavailable"}), 500

    # Validate against current in-memory world map (entity must exist for now).
    _maybe_reload_world_map()
    vr = _wm_validate_ops(
        world_map_obj=(world_map_obj or {}),
        entity_id=entity_id,
        ops=ops,
        confidence=confidence,
        evidence=evidence,
        require_entity_exists=True,
        for_auto_apply_kurt=False,
    )
    if not getattr(vr, "ok", False):
        return jsonify({"ok": False, "error": getattr(vr, "error", "invalid_proposal"), "detail": getattr(vr, "detail", None)}), 400

    proposal_id = str(uuid.uuid4())
    ts = datetime.utcnow().isoformat() + "Z"
    actor = (
        (request.headers.get("X-Actor") or "").strip()
        or (request.headers.get("X-Request-ID") or "").strip()
        or (request.headers.get("User-Agent") or "").strip()
        or (request.remote_addr or "unknown")
    )

    rec = {
        "proposal_id": proposal_id,
        "ts": ts,
        "actor": actor[:120],
        "entity_id": entity_id,
        "ops": list(ops or []),
        "confidence": float(confidence),
        "evidence": evidence if isinstance(evidence, dict) else {},
        "status": "pending",
        "applied_ts": None,
        "error": None,
    }
    store_path = _world_map_proposal_store_path()
    try:
        _jsonl_append(store_path, rec)
    except Exception as e:
        return jsonify({"ok": False, "error": "proposal_store_write_failed", "detail": str(e)[:200]}), 500

    # Auto-apply (ExamplePerson hard facts rule) — conservative and env-gated.
    try:
        write_enabled = _world_map_write_enabled()
        auto_enabled = _world_map_auto_apply_enabled()
        min_conf = _world_map_auto_apply_min_confidence()
        wl = _world_map_auto_apply_entity_whitelist()
        can_auto = False
        if _wm_should_auto_apply_kurt is not None:
            if entity_id.strip().lower() in wl:
                hard_paths = _world_map_auto_apply_hard_fact_paths()
                try:
                    if any(str((o or {}).get("path") or "") not in hard_paths for o in list(ops or []) if isinstance(o, dict)):
                        can_auto = False
                    else:
                        can_auto = _wm_should_auto_apply_kurt(
                            write_enabled=write_enabled,
                            auto_apply_enabled=auto_enabled,
                            entity_id=entity_id,
                            confidence=float(confidence),
                            min_confidence=float(min_conf),
                            ops=list(ops or []),
                            evidence=evidence,
                        )
                except Exception:
                    can_auto = False
        if can_auto:
            ok, detail = _apply_world_map_ops_atomic(entity_id=entity_id, ops=list(ops or []))
            if ok:
                _jsonl_update_record(
                    store_path,
                    proposal_id,
                    {
                        "status": "applied",
                        "applied_ts": datetime.utcnow().isoformat() + "Z",
                        "error": None,
                    },
                )
                return jsonify({"ok": True, "proposal_id": proposal_id, "status": "applied", "detail": detail}), 200
            _jsonl_update_record(
                store_path,
                proposal_id,
                {
                    "status": "rejected",
                    "applied_ts": None,
                    "error": detail,
                },
            )
            return jsonify({"ok": False, "proposal_id": proposal_id, "status": "rejected", "error": detail}), 500
    except Exception as e:
        # Fail-open: leave pending if policy evaluation fails
        logger.warning(f"[world_map][auto_apply] policy check failed: {type(e).__name__}", exc_info=True)

    return jsonify({"ok": True, "proposal_id": proposal_id, "status": "pending"}), 200


@app.route("/world_map/pending", methods=["GET"])
def world_map_pending():
    """List pending proposals from the JSONL store (last N)."""
    if not _world_map_write_enabled():
        return jsonify({"ok": False, "error": "world_map_write_disabled"}), 403
    try:
        limit = int((request.args.get("limit") or "50").strip())
    except Exception:
        limit = 50
    limit = max(1, min(limit, 500))

    store_path = _world_map_proposal_store_path()
    items = _jsonl_load_all(store_path)
    pending = [r for r in items if isinstance(r, dict) and r.get("status") == "pending"]
    pending = pending[-limit:]
    return jsonify({"ok": True, "count": len(pending), "proposals": pending}), 200


@app.route("/world_map/apply/<proposal_id>", methods=["POST"])
def world_map_apply(proposal_id: str):
    """Apply a pending proposal by id (re-validate, apply, reload, mark applied)."""
    if not _world_map_write_enabled():
        return jsonify({"ok": False, "error": "world_map_write_disabled"}), 403
    pid = str(proposal_id or "").strip()
    if not pid:
        return jsonify({"ok": False, "error": "missing_proposal_id"}), 400

    store_path = _world_map_proposal_store_path()
    items = _jsonl_load_all(store_path)
    rec = None
    for r in items:
        if isinstance(r, dict) and str(r.get("proposal_id") or "") == pid:
            rec = r
            break
    if rec is None:
        return jsonify({"ok": False, "error": "proposal_not_found", "proposal_id": pid}), 404
    if rec.get("status") != "pending":
        return jsonify({"ok": False, "error": "proposal_not_pending", "proposal_id": pid, "status": rec.get("status")}), 409

    entity_id = str(rec.get("entity_id") or "").strip()
    ops = rec.get("ops") or []
    confidence = rec.get("confidence")
    evidence = rec.get("evidence") or {}

    if _wm_validate_ops is None:
        return jsonify({"ok": False, "error": "world_map_write_module_unavailable"}), 500

    _maybe_reload_world_map()
    vr = _wm_validate_ops(
        world_map_obj=(world_map_obj or {}),
        entity_id=entity_id,
        ops=ops,
        confidence=confidence,
        evidence=evidence,
        require_entity_exists=True,
        for_auto_apply_kurt=False,
    )
    if not getattr(vr, "ok", False):
        _jsonl_update_record(
            store_path,
            pid,
            {"status": "rejected", "error": {"error": getattr(vr, "error", "invalid_proposal"), "detail": getattr(vr, "detail", None)}},
        )
        return jsonify({"ok": False, "error": getattr(vr, "error", "invalid_proposal"), "detail": getattr(vr, "detail", None)}), 400

    ok, detail = _apply_world_map_ops_atomic(entity_id=entity_id, ops=list(ops or []))
    if ok:
        _jsonl_update_record(
            store_path,
            pid,
            {"status": "applied", "applied_ts": datetime.utcnow().isoformat() + "Z", "error": None},
        )
        return jsonify({"ok": True, "proposal_id": pid, "status": "applied", "detail": detail}), 200

    _jsonl_update_record(
        store_path,
        pid,
        {"status": "rejected", "error": detail},
    )
    return jsonify({"ok": False, "proposal_id": pid, "status": "rejected", "error": detail}), 500

@app.route("/list_ids", methods=["GET"])
def list_ids():
    try:
        if _json_mode_enabled():
            ids = [str(r.get("uuid")) for r in _json_load() if r.get("uuid")]
            return jsonify(ids)

        if args.use_qdrant:
            # Extract UUIDs from cached memory_data
            ids = [
                item.get("uuid") or item.get("id")
                for item in memory_data
                if item.get("uuid") or item.get("id")
            ]
            return jsonify(ids), 200
        else:
            return jsonify(memory.all_ids()), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/memory/add", methods=["POST"])
def add_memory():
    try:
        # Governor contract enforcement (soft by default)
        try:
            if governor_enabled():
                headers = ensure_correlation_and_idempotency(
                    dict(request.headers or {}),
                    request.get_json(silent=True) or {},
                    require_cid=True,
                    require_idem=True,
                )
                if strict_mode():
                    if not headers.get("X-Correlation-ID"):
                        _gov_write("governor", "contract_violation.missing_correlation_id", {"route": "/memory/add"})
                        return jsonify({"error": "missing_correlation_id"}), 400
                    if not headers.get("Idempotency-Key"):
                        _gov_write("governor", "contract_violation.missing_idempotency_key", {"route": "/memory/add"})
                        return jsonify({"error": "missing_idempotency_key"}), 400
                else:
                    if not request.headers.get("X-Correlation-ID"):
                        _gov_write("governor", "contract_violation.missing_correlation_id", {"route": "/memory/add"})
                    if not request.headers.get("Idempotency-Key"):
                        _gov_write("governor", "contract_violation.missing_idempotency_key", {"route": "/memory/add"})
        except Exception:
            pass
        if _json_mode_enabled():
            payload = request.get_json(force=True, silent=True) or {}
            # Phase 32: Provenance enforcement (fail-closed by default)
            try:
                prov = _extract_provenance(payload)
                if prov is None:
                    if _provenance_required():
                        logger.error("[RECALL][Provenance] rejected: missing_provenance")
                        _record_provenance_event("rejected")
                        return jsonify({"error": "provenance_required"}), 400
                    else:
                        logger.warning("[RECALL][Provenance] missing provenance accepted under legacy mode")
                        _record_provenance_event("legacy")
                        try:
                            if _metrics is not None:
                                _metrics.inc("provenance.legacy_override")
                        except Exception:
                            pass
                else:
                    try:
                        logger.info(f"[RECALL][Provenance] accepted: source={str(prov)[:120]}")
                    except Exception:
                        logger.info("[RECALL][Provenance] accepted")
                    _record_provenance_event("accepted")
                    try:
                        if _metrics is not None:
                            _metrics.inc("provenance.accepted")
                    except Exception:
                        pass
            except Exception:
                # Never block on logging/metrics errors
                pass
            # Contracts v2 validation (additive, env-gated)
            try:
                if os.getenv("CONTRACTS_V2_ENABLED", "true").strip().lower() in {"1","true","yes","y"}:
                    from contracts.v2.validator import validate as _contracts_validate  # type: ignore
                    res = _contracts_validate({**payload, "schema_version": payload.get("schema_version") or ("v2" if True else "v1")}, "journal")
                    if not res.get("ok"):
                        if os.getenv("CONTRACTS_REJECT_UNKNOWN", "true").strip().lower() in {"1","true","yes","y"}:
                            return jsonify({"error": "schema_version_invalid"}), 400
            except Exception:
                pass
            # Accept both `content` and `text`
            if not (payload.get("content") or payload.get("text")):
                return jsonify({"error": "Missing 'content' (or 'text')"}), 400
            # Governor schema validation (soft by default)
            try:
                if governor_enabled():
                    ok, detail = _gov_validate("journal", payload)
                    if not ok:
                        _gov_write("governor", "contract_violation.schema_violation", {"route": "/memory/add", "detail": detail})
                        if strict_mode():
                            return jsonify({"error": "schema_violation"}), 400
            except Exception:
                pass
            # Eventlog append when enabled
            try:
                if str(os.getenv("EVENTLOG_ENABLED", "true")).strip().lower() in {"1","true","yes","y"}:
                    idem_key = (request.headers.get("Idempotency-Key") or f"idem:{uuid.uuid4()}")
                    cid = (request.headers.get("X-Correlation-ID") or f"cid:{uuid.uuid4()}")
                    # Construct Contracts v2-ish payload for journal.append
                    journal_v2 = {
                        "schema_version": payload.get("schema_version") or "v2",
                        "entry": payload.get("content") or payload.get("text") or "",
                        "context": payload.get("context") or {},
                        "tags": payload.get("tags") or [],
                    }
                    from eventlog.store import append as _ev_append  # type: ignore
                    seq_id = _ev_append(idem_key, cid, "journal.append", journal_v2)
                    return jsonify({"status": "accepted", "event_id": seq_id, "idem_key": idem_key}), 202
            except Exception:
                pass
            rid = _json_append(payload)
            # Outbox integration (flag-gated, and forced in degraded mode)
            try:
                from resilience.degraded import is_active as _degraded_active
            except Exception:
                def _degraded_active() -> bool:  # type: ignore
                    return False
            try:
                from outbox import OUTBOX_ENABLED
                from outbox.models import OutboxItem
                from outbox.store import append as outbox_append
                headers = dict(request.headers or {})
                cid = headers.get("X-Correlation-ID") or "corr_local"
                idem_key = headers.get("Idempotency-Key") or f"idem_{rid}"
                force_outbox = bool(_degraded_active())
                if OUTBOX_ENABLED or force_outbox:
                    out_ids = []
                    oi1 = OutboxItem(id=None, idem_key=idem_key+":vec", cid=cid, type="vector_upsert", payload={"content": payload.get("content") or payload.get("text"), "metadata": {"memory_id": rid, "timestamp": datetime.now().isoformat(), "mode": "degraded" if force_outbox else "normal"}})
                    out_ids.append(outbox_append(oi1))
                    oi2 = OutboxItem(id=None, idem_key=idem_key+":bel", cid=cid, type="belief_recompute", payload={"memory_id": rid, "mode": "degraded" if force_outbox else "normal"})
                    out_ids.append(outbox_append(oi2))
                    return jsonify({"cid": cid, "idem_key": idem_key, "outbox_ids": out_ids, "mode": "degraded" if force_outbox else "normal"}), 202
            except Exception:
                pass
            return jsonify({"status": "ok", "id": rid}), 200

        if args.use_qdrant:
            return (
                jsonify(
                    {
                        "error": "Adding memory not supported in Qdrant mode. Use vector operations or switch to JSON mode."
                    }
                ),
                400,
            )

        data = request.get_json(force=True)
        # Phase 32: Provenance enforcement for legacy path as well
        try:
            prov = _extract_provenance(data)
            if prov is None:
                if _provenance_required():
                    logger.error("[RECALL][Provenance] rejected: missing_provenance")
                    _record_provenance_event("rejected")
                    return jsonify({"error": "provenance_required"}), 400
                else:
                    logger.warning("[RECALL][Provenance] missing provenance accepted under legacy mode")
                    _record_provenance_event("legacy")
                    try:
                        if _metrics is not None:
                            _metrics.inc("provenance.legacy_override")
                    except Exception:
                        pass
            else:
                try:
                    logger.info(f"[RECALL][Provenance] accepted: source={str(prov)[:120]}")
                except Exception:
                    logger.info("[RECALL][Provenance] accepted")
                _record_provenance_event("accepted")
                try:
                    if _metrics is not None:
                        _metrics.inc("provenance.accepted")
                except Exception:
                    pass
        except Exception:
            pass
        # Contracts v2 validation (additive, env-gated)
        try:
            if os.getenv("CONTRACTS_V2_ENABLED", "true").strip().lower() in {"1","true","yes","y"}:
                from contracts.v2.validator import validate as _contracts_validate  # type: ignore
                # Normalize to v2 shape for validation-only; do not mutate persistence shape here
                v2_probe = {
                    "schema_version": data.get("schema_version") or "v1",
                    "text": data.get("content") or data.get("text") or "",
                    "tags": data.get("tags") or [],
                    "metadata": data.get("metadata") or {},
                }
                res = _contracts_validate(v2_probe, "memory_write")
                if not res.get("ok") and os.getenv("CONTRACTS_REJECT_UNKNOWN", "true").strip().lower() in {"1","true","yes","y"}:
                    return jsonify({"error": "schema_version_invalid"}), 400
        except Exception:
            pass
        content = data.get("content", "").strip()
        if not content:
            return jsonify({"error": "Missing 'content'"}), 400
        # Governor schema validation for memory write
        try:
            if governor_enabled():
                ok, detail = _gov_validate("memory_write", data)
                if not ok:
                    _gov_write("governor", "contract_violation.schema_violation", {"route": "/memory/add", "detail": detail})
                    if strict_mode():
                        return jsonify({"error": "schema_violation"}), 400
        except Exception:
            pass

        entry = {
            "content": content,
            "tags": data.get("tags", []),
            "type": data.get("type", "external_import"),
            "timestamp": datetime.now().isoformat(),
        }
        # Quarantine classification (env-gated)
        try:
            if str(os.getenv("QUARANTINE_ENABLED", "true")).strip().lower() in {"1","true","yes","y"}:
                from moderation.quarantine import score_trust, detect_injection, classify_reason  # type: ignore
                tscore = score_trust(content, {"source": entry.get("type")})
                inj = bool(detect_injection(content)) if str(os.getenv("QUARANTINE_INJECTION_FILTER", "true")).strip().lower() in {"1","true","yes","y"} else False
                reason = classify_reason(tscore, inj)
                if reason is not None:
                    entry["quarantined"] = True
                    entry["quarantine_reason"] = reason
                    entry["trust_score"] = float(tscore)
                    try:
                        from pods.cockpit.cockpit_reporter import write_signal as _sig  # type: ignore
                        _sig("quarantine", "flagged", {"reason": reason})
                    except Exception:
                        pass
        except Exception:
            pass
        # Eventlog append when enabled (vectorized path)
        try:
            if str(os.getenv("EVENTLOG_ENABLED", "true")).strip().lower() in {"1","true","yes","y"}:
                idem_key = (request.headers.get("Idempotency-Key") or f"idem:{uuid.uuid4()}")
                cid = (request.headers.get("X-Correlation-ID") or f"cid:{uuid.uuid4()}")
                mem_v2 = {
                    "schema_version": data.get("schema_version") or "v2",
                    "text": content,
                    "tags": data.get("tags") or [],
                    "metadata": {k: v for k, v in data.items() if k not in {"content", "text", "tags"}},
                }
                from eventlog.store import append as _ev_append  # type: ignore
                seq_id = _ev_append(idem_key, cid, "memory.write", mem_v2)
                return jsonify({"status": "accepted", "event_id": seq_id, "idem_key": idem_key}), 202
        except Exception:
            pass
        mem_id = memory.store(entry)

        # Outbox path (forced when degraded)
        try:
            from resilience.degraded import is_active as _degraded_active
        except Exception:
            def _degraded_active() -> bool:  # type: ignore
                return False
        try:
            from outbox import OUTBOX_ENABLED
            from outbox.models import OutboxItem
            from outbox.store import append as outbox_append
            headers = dict(request.headers or {})
            cid = headers.get("X-Correlation-ID") or "corr_local"
            idem_key = headers.get("Idempotency-Key") or f"idem_{mem_id}"
            force_outbox = bool(_degraded_active())
            if OUTBOX_ENABLED or force_outbox:
                out_ids = []
                oi1 = OutboxItem(id=None, idem_key=idem_key+":vec", cid=cid, type="vector_upsert", payload={"content": content, "metadata": {"memory_id": mem_id, "tags": data.get("tags", []), "type": data.get("type", "external_import"), "timestamp": entry["timestamp"], "mode": "degraded" if force_outbox else "normal"}})
                out_ids.append(outbox_append(oi1))
                oi2 = OutboxItem(id=None, idem_key=idem_key+":bel", cid=cid, type="belief_recompute", payload={"memory_id": mem_id, "mode": "degraded" if force_outbox else "normal"})
                out_ids.append(outbox_append(oi2))
                return jsonify({"cid": cid, "idem_key": idem_key, "outbox_ids": out_ids, "mode": "degraded" if force_outbox else "normal"}), 202
        except Exception:
            pass

        # If degraded but no outbox, fail-closed with Retry-After
        try:
            if _degraded_active():
                return jsonify({"error": "degraded_mode", "message": "System in read-only degraded mode. Please retry later."}), 503
        except Exception:
            pass

        # Legacy synchronous push when outbox disabled
        if ENABLE_PUSH and vector_ready:
            try:
                vector_payload = {
                    "content": content,
                    "metadata": {
                        "memory_id": mem_id,
                        "tags": data.get("tags", []),
                        "type": data.get("type", "external_import"),
                        "timestamp": entry["timestamp"],
                        # Carry provenance forward if present
                        "provenance": _extract_provenance(data),
                    },
                }
                headers = {}
                try:
                    rid = getattr(g, "req_id", None)
                    if isinstance(rid, str) and rid:
                        headers[_RID_HEADER] = rid
                except Exception:
                    pass
                auth_header = request.headers.get("Authorization")
                if isinstance(auth_header, str) and auth_header:
                    headers = headers or {}
                    headers["Authorization"] = auth_header
                resp = requests.post(f"{VECTOR_URL}/v1/memories", json=vector_payload, timeout=10, headers=headers or None)
                resp.raise_for_status()
            except Exception as push_err:
                print(f"[WARN] Vector push failed: {push_err}")

        return jsonify({"status": "ok", "id": mem_id}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/goals", methods=["GET"])
def list_goals():
    try:
        if args.use_qdrant:
            # Extract goals from cached memory_data
            goals = [
                item
                for item in memory_data
                if item.get("type") == "goal" or "goal" in item.get("tags", [])
            ]
            return jsonify(goals), 200
        else:
            return jsonify(memory.get_goals()), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/goals/add", methods=["POST"])
def add_goal():
    try:
        if args.use_qdrant:
            return (
                jsonify(
                    {
                        "error": "Adding goals not supported in Qdrant mode. Use vector operations or switch to JSON mode."
                    }
                ),
                400,
            )

        goal_data = request.get_json(force=True)
        goal = Goal(**goal_data)
        memory.add_goal(goal)
        return jsonify({"status": "success", "goal": goal.model_dump()}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/beliefs", methods=["GET"])
def list_beliefs():
    """
    Get all beliefs from memory store.
    Returns empty list if no beliefs found, never 404.
    """
    try:
        if args.use_qdrant:
            # Use cached memory_data for Qdrant mode
            all_memories = memory_data
        else:
            # Use Memory class for JSON mode
            memory.load()  # Ensure fresh data
            all_memories = memory.snapshot()

        # Filter for belief entries using the same logic as other parts of the system
        beliefs = []
        for mem in all_memories:
            is_belief = (
                mem.get("type") == "belief"
                or mem.get("memory_type") == "belief"
                or mem.get("isBelief", False)
                or "belief" in mem.get("tags", [])
            )
            if is_belief:
                beliefs.append(mem)

        return jsonify(beliefs), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify([]), 200  # Return empty list on error, not 500


@app.route("/journal/latest", methods=["GET"])
def get_latest_journal():
    """
    Get the most recent journal entry from memory store.
    Returns empty object if no journal entries found, never 404.
    """
    try:
        if args.use_qdrant:
            # Use cached memory_data for Qdrant mode
            all_memories = memory_data
        else:
            # Use Memory class for JSON mode
            memory.load()  # Ensure fresh data
            all_memories = memory.snapshot()

        # Filter for journal entries and find the latest
        journal_entries = []
        for mem in all_memories:
            is_journal = (
                mem.get("type") == "journal_entry"
                or mem.get("memory_type") == "journal_entry"
                or "journal" in mem.get("tags", [])
            )
            if is_journal:
                journal_entries.append(mem)

        if not journal_entries:
            # Return empty object if no journal entries found
            return jsonify({}), 200

        # Sort by timestamp to find the latest (handle various timestamp formats)
        def get_timestamp(entry):
            timestamp = (
                entry.get("timestamp") or entry.get("created_at") or entry.get("date")
            )
            if not timestamp:
                return datetime.min.isoformat()
            if isinstance(timestamp, str):
                try:
                    # Try to parse ISO format
                    return datetime.fromisoformat(
                        timestamp.replace("Z", "+00:00")
                    ).isoformat()
                except:
                    return timestamp
            return str(timestamp)

        latest_entry = max(journal_entries, key=get_timestamp)
        return jsonify(latest_entry), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({}), 200  # Return empty object on error, not 500


@app.route("/journal/write", methods=["POST"])
def journal_write():
    """Append a journal entry JSON line to disk (bot-driven journaling)."""
    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    ts = payload.get("ts")
    conversation_id = payload.get("conversation_id")
    entries = payload.get("entries")

    if not isinstance(ts, str) or not ts.strip():
        return jsonify({"ok": False, "error": "missing_ts"}), 400
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        return jsonify({"ok": False, "error": "missing_conversation_id"}), 400
    if not isinstance(entries, dict):
        return jsonify({"ok": False, "error": "invalid_entries"}), 400

    rec = {
        "ts": ts.strip(),
        "conversation_id": conversation_id.strip(),
        "entries": entries,
        "actor": (request.headers.get("X-Actor") or request.remote_addr or "unknown"),
    }

    path = _journal_append_path()
    try:
        _jsonl_append(path, rec)
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": "journal_append_failed", "detail": str(e)[:200]}), 500

@app.route("/summarise", methods=["POST"])
def summarise():
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").lower().strip()

        # Get memory data based on current mode
        if args.use_qdrant:
            all_memories = memory_data
        else:
            all_memories = memory.snapshot()

        matched = [
            m
            for m in all_memories
            if question and question in m.get("content", "").lower()
        ]

        raw_facts = world_map.get("ExamplePerson", {})
        if isinstance(raw_facts, dict):
            fact_block = ". ".join(f"{k}: {v}" for k, v in raw_facts.items())
        elif isinstance(raw_facts, list):
            fact_block = ". ".join(
                f"{k}: {v}"
                for d in raw_facts
                if isinstance(d, dict)
                for k, v in d.items()
            )
        else:
            fact_block = "[Invalid facts structure]"

        mem_block = (
            " ".join(m.get("content", "") for m in matched[:3])
            or "No relevant memory found."
        )

        summary = f"{fact_block}. MEMORY: {mem_block}"
        return jsonify(
            {
                "summary": summary.strip(),
                "tags": list({t for m in matched for t in m.get("tags", [])}),
                "possible_contradictions": [],
            }
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"summary": "", "tags": [], "possible_contradictions": []}), 500


@app.route("/answer", methods=["POST"])
def answer():
    try:
        data = request.get_json(force=True)
        summary = data.get("summary", "").strip()
        question = data.get("question", "").strip()

        # 1) Generate raw answer (unchanged semantics)
        raw_answer = _generate_raw_answer(summary=summary, question=question)

        # 2) Optionally compute retrieval status and decorate
        final_answer = raw_answer
        if RETRIEVAL_AWARE_ANSWERS:
            # Attempt a lightweight retrieval to assess recall quality
            hits = _retrieve_hits_for_answer(query=question or summary, top_k=8)
            status, top_sim = compute_retrieval_status(hits)
            final_answer = _decorate_answer(raw_answer, status, RETRIEVAL_TEMPLATE_STYLE)
            # Structured single-line log for observability
            try:
                rid = getattr(g, "request_id", None)
                line = {
                    "component": "retrieval_templating",
                    "status": status,
                    "hits": int(len(hits or [])),
                    "top_sim": round(float(top_sim), 4),
                }
                if isinstance(rid, str) and rid:
                    line["request_id"] = rid
                print(json.dumps(line))
                if _metrics is not None:
                    _metrics.inc(f"retrieval.answer.{status}")
            except Exception:
                pass

        return jsonify({"answer": final_answer, "possible_contradictions": []})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"answer": f"❌ Error: {e}"}), 500


@app.route("/vector/query", methods=["POST"])
def vector_query():
    try:
        # Expected misconfig (no vector) → never 500
        if not vector_ready or _unified_vector_client is None:
            resp = make_response(jsonify({"items": [], "error": "Vector backend not configured or unavailable"}), 503)
            resp.headers["X-Axiom-Retrieval"] = "none"
            resp.headers["X-Axiom-Error-Code"] = "vector_backend_unavailable"
            return resp

        payload = request.get_json(force=True) or {}
        query = (payload.get("query") or payload.get("question") or payload.get("text") or payload.get("content") or "").strip()
        top_k = int(payload.get("top_k") or payload.get("k") or payload.get("limit") or 5)

        if not query:
            resp = make_response(jsonify({"items": [], "warning": "empty query"}), 400)
            resp.headers["X-Axiom-Retrieval"] = "none"
            return resp

        # Route through unified vector client only (no direct Qdrant calls here)
        rid = getattr(g, "request_id", None)
        try:
            sr = _unified_vector_client.search(  # type: ignore[union-attr]
                VectorSearchRequest(query=str(query), top_k=int(top_k or 5), filter=None),
                request_id=(rid if isinstance(rid, str) else None),
                auth_header=request.headers.get("Authorization"),
            )
        except TypeError:
            # Back-compat for older UnifiedVectorClient signatures
            sr = _unified_vector_client.search(VectorSearchRequest(query=str(query), top_k=int(top_k or 5), filter=None))  # type: ignore[union-attr]

        items: list[dict] = []
        for h in list(getattr(sr, "hits", []) or []):
            raw = {}
            try:
                raw = (getattr(h, "meta", {}) or {}).get("raw")  # type: ignore[assignment]
            except Exception:
                raw = {}

            # Best-effort id + payload preservation
            pid = ""
            payload_obj = {}
            try:
                if isinstance(raw, dict):
                    pid = str(raw.get("id") or raw.get("uuid") or "")
                    payload_obj = raw.get("payload") or raw.get("metadata") or {}
                else:
                    pid = str(getattr(raw, "id", "") or "")
                    payload_obj = getattr(raw, "payload", {}) or {}
            except Exception:
                pid = ""
                payload_obj = {}

            if not isinstance(payload_obj, dict):
                payload_obj = {}
            payload_obj.setdefault("text", getattr(h, "content", "") or "")
            payload_obj.setdefault("content", getattr(h, "content", "") or "")
            payload_obj.setdefault("tags", list(getattr(h, "tags", []) or []))

            try:
                score = float(getattr(h, "score", 0.0) or 0.0)
            except Exception:
                score = 0.0

            items.append({"id": pid, "score": score, "payload": payload_obj})

        resp = make_response(jsonify({"items": items}), 200)
        resp.headers["X-Axiom-Retrieval"] = "ok:unified" if items else "thin:unified"
        return resp

    except Exception as e:
        msg = str(e)
        if "embeddings_unconfigured" in msg or msg.startswith("sentence_transformers_unavailable"):
            resp = make_response(
                jsonify(
                    {
                        "items": [],
                        "warning": "embeddings_not_configured",
                        "error": msg,
                    }
                ),
                200,
            )
            resp.headers["X-Axiom-Retrieval"] = "none"
            resp.headers["X-Axiom-Error-Code"] = "embeddings_unconfigured"
            return resp

        # Unexpected exceptions may 500; log stack trace for debugging.
        traceback.print_exc()
        resp = make_response(jsonify({"items": [], "error": msg}), 500)
        resp.headers["X-Axiom-Retrieval"] = "error"
        resp.headers["X-Axiom-Error-Code"] = "vector_query_unexpected_error"
        return resp


@app.route("/backfill", methods=["POST"])
def backfill():
    # Guard against missing vector backend
    if not vector_ready:
        return jsonify({"error": "Vector backend not configured or unavailable"}), 503

    try:
        # Get memory data based on current mode
        if args.use_qdrant:
            all_mems = memory_data
        else:
            all_mems = memory.snapshot()

        pushed = 0

        for m in all_mems:
            content = m.get("content", "")
            memory_id = m.get("uuid") or m.get("id")
            if not content or not memory_id:
                continue
            try:
                # Push to Qdrant via vector adapter
                vector_payload = {
                    "content": content,
                    "metadata": {
                        "memory_id": memory_id,
                        "tags": m.get("tags", []),
                        "type": m.get("type", "memory"),
                        "timestamp": m.get("timestamp", ""),
                        "speaker": m.get("speaker", ""),
                        "persona": m.get("persona", ""),
                    },
                }
                headers = {}
                try:
                    rid = getattr(g, "req_id", None)
                    if isinstance(rid, str) and rid:
                        headers[_RID_HEADER] = rid
                except Exception:
                    pass
                resp = requests.post(
                    f"{VECTOR_URL}/v1/memories", json=vector_payload, timeout=10, headers=headers or None
                )
                resp.raise_for_status()
                pushed += 1
            except Exception as inner:
                print(f"[WARN] Skipped memory {memory_id}: {inner}")

        return jsonify({"status": "ok", "pushed": pushed})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/memories", methods=["GET", "POST"])
def get_memories():
    try:
        if _json_mode_enabled():
            if request.method == "POST":
                body = request.get_json(force=True, silent=True) or {}
                ids = body.get("ids") or body.get("id")
                user_id = body.get("user_id")
                limit = body.get("limit", 50)
            else:
                ids = (
                    request.args.getlist("ids[]")
                    or request.args.get("ids")
                    or request.args.get("id")
                )
                user_id = request.args.get("user_id")
                limit = request.args.get("limit", 50)

            # Normalize ids input
            if isinstance(ids, str):
                ids = [s for s in ids.split(",") if s.strip()]
            elif isinstance(ids, (int, float)):
                ids = [str(ids)]
            elif ids is None:
                ids = []

            out = _json_query(ids=ids or None, user_id=user_id, limit=int(limit or 50))
            return jsonify(out)

        speaker = request.args.get("speaker", "axiom")
        limit = int(request.args.get("limit", 25))

        # Handle both Qdrant and JSON modes
        if args.use_qdrant:
            # Use cached memory_data for Qdrant mode
            results = [m for m in memory_data if m.get("speaker") == speaker]
        else:
            # Use Memory class for JSON mode
            results = [m for m in memory.snapshot() if m.get("speaker") == speaker]
        return jsonify(results[:limit]), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/qdrant-test", methods=["GET"])
def qdrant_test():
    """
    Optional test route to verify Qdrant connection and return first 5 items.
    Only available when Qdrant mode is enabled.
    """
    if not args.use_qdrant:
        return (
            jsonify(
                {
                    "error": "Qdrant test route only available when --use_qdrant is enabled"
                }
            ),
            400,
        )

    if not QDRANT_AVAILABLE:
        return jsonify({"error": "Qdrant utilities not available"}), 503

    try:
        test_data = test_qdrant_connection(
            host=args.qdrant_host,
            port=args.qdrant_port,
            collection_name=args.qdrant_collection,
            limit=5,
        )

        return (
            jsonify(
                {
                    "status": "ok",
                    "connection": "successful",
                    "host": args.qdrant_host,
                    "port": args.qdrant_port,
                    "collection": args.qdrant_collection,
                    "sample_items": test_data,
                    "sample_count": len(test_data),
                }
            ),
            200,
        )

    except Exception as e:
        log.error(f"Qdrant test failed: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "connection": "failed",
                    "host": args.qdrant_host,
                    "port": args.qdrant_port,
                    "collection": args.qdrant_collection,
                    "error": str(e),
                }
            ),
            500,
        )


@app.route("/memory-debug", methods=["GET"])
def memory_debug():
    ALLOW_DEBUG = os.getenv("AXIOM_DEBUG_OPEN", "0") == "1"
    if not ALLOW_DEBUG:
        return jsonify({"error": "debug disabled"}), 403
    try:
        # Resolve from pipeline single source where possible  # parity
        profile = getattr(
            memory_response_pipeline, "_PROFILE", os.getenv("AXIOM_SCORING_PROFILE", "default")
        )
        top_k = getattr(memory_response_pipeline, "TOP_K_FRAGMENTS", int(os.getenv("VECTOR_TOPK", "10")))
        top_n = getattr(memory_response_pipeline, "_TOP_N", int(os.getenv("AXIOM_TOP_N", "8")))
        lambda_mmr = getattr(memory_response_pipeline, "_MMR", float(os.getenv("AXIOM_MMR_LAMBDA", "0.4")))
        use_composite = getattr(
            memory_response_pipeline, "_COMPOSITE", os.getenv("AXIOM_COMPOSITE_SCORING", "0") == "1"
        )
        last = getattr(memory_response_pipeline, "_LAST_MEMORY_DEBUG", None)
        belief_engine = False
        try:
            from memory.belief_engine import ENGINE_ENABLED as _BE

            belief_engine = bool(_BE)
        except Exception:
            belief_engine = False
        active = {
            "profile": profile,
            "belief_engine": belief_engine,
            "topK": top_k,
            "topN": top_n,
            "mmr_lambda": lambda_mmr,
            "composite_enabled": bool(use_composite),
            "weights_path": "config/composite_weights.yaml",
        }
        # include last snapshot and flatten latency for convenience
        if isinstance(last, dict) and "latency_ms" in last:
            active["latency_ms"] = last.get("latency_ms")
        # Optionally include conflict pairs if requested
        include_conflicts = request.args.get("include_conflicts", "0") == "1"
        # Build stable response with top-level items and scoring_profile
        items_list = []
        if isinstance(last, dict):
            items_list = last.get("items") or []
        # Normalize per-item fields for tests: ensure bel and conflict_penalty keys are present
        for it in items_list:
            if "bel" not in it and "belief_align" in it:
                it["bel"] = it.get("belief_align")
            it.setdefault("conflict_penalty", it.get("conflict_penalty", 0.0))
        resp = {
            **active,
            "scoring_profile": profile,
            "items": items_list,
            "last": last or {},
        }
        # Ensure factor keys are present for tests when composite is enabled
        if use_composite and isinstance(resp.get("last"), dict):
            items = resp["last"].get("items") or []
            if items:
                first = items[0]
                for k in (
                    "sim",
                    "rec",
                    "cred",
                    "conf",
                    "bel",
                    "use",
                    "nov",
                    "final_score",
                ):
                    first.setdefault(k, first.get(k, 0))  # ensure keys exist
        # Surface decisive filter results, profile source, and usage feedback flags if present
        if isinstance(last, dict):
            if last.get("selected_decisive_ids") is not None:
                resp["selected_decisive_ids"] = last.get("selected_decisive_ids") or []
            if last.get("profile_source"):
                resp["profile_source"] = last.get("profile_source")
            if last.get("usage_feedback") is not None:
                resp["usage_feedback"] = bool(last.get("usage_feedback"))
        # Optional: metrics visibility
        try:
            _PROM = getattr(memory_response_pipeline, "_PROM", False)
            retry_max = getattr(memory_response_pipeline, "_USAGE_RETRY_MAX", 3)
            resp["metrics"] = {
                "prometheus_enabled": bool(_PROM),
                "usage_retry_max": int(retry_max),
            }
        except Exception:
            pass
        if include_conflicts and isinstance(last, dict) and last.get("conflicts"):
            resp["conflicts"] = [
                {
                    "a_id": c.get("a_id"),
                    "b_id": c.get("b_id"),
                    "note": c.get("note"),
                }
                for c in (last.get("conflicts") or [])
            ]
        return jsonify(resp), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/metrics", methods=["GET"])
def metrics_debug():
    try:
        m = getattr(memory_response_pipeline, "_METRICS", None)
        if not isinstance(m, dict):
            m = {}
        # Extend with lightweight vector metrics if available
        try:
            from observability import metrics as _m  # type: ignore

            snap = _m.snapshot()
            if isinstance(snap, dict):
                m["vector_metrics"] = snap
        except Exception:
            pass
        return jsonify(m), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/canary/status", methods=["GET"])
def canary_status():
    try:
        global _CANARY_RESULT
        return jsonify(_CANARY_RESULT), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/belief-debug", methods=["GET"])
def belief_debug():
    try:
        from memory.belief_engine import ActiveBeliefs as _AB
        from memory.belief_engine import load_belief_config as _load_belief_cfg

        profile = getattr(
            memory_response_pipeline, "_PROFILE", os.getenv("AXIOM_SCORING_PROFILE", "default")
        )
        belief_engine = False
        try:
            from memory.belief_engine import ENGINE_ENABLED as _BE

            belief_engine = bool(_BE)
        except Exception:
            belief_engine = False
        if not belief_engine:
            return jsonify({"belief_engine": False}), 200
        last = getattr(memory_response_pipeline, "_LAST_MEMORY_DEBUG", None) or {}
        items = last.get("items", [])
        resp = {
            "profile": profile,
            "belief_engine": belief_engine,
            "active_beliefs_count": _AB.size(),
            "last_refresh_at": _AB.last_refresh_at(),
            "retrieval_id": last.get("retrieval_id"),
            "items": [
                {
                    "uuid": it.get("id"),
                    "belief_align": it.get("bel") or it.get("belief_align"),
                    "sim": it.get("sim"),
                    "final_score": it.get("final_score"),
                    "conflict_ids": it.get("conflict_ids"),
                    "conflict_notes": it.get("conflict_notes"),
                }
                for it in items[:20]
            ],
        }
        return jsonify(resp), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# simple soft rate limiter for contradictions endpoint
_CONTRA_WINDOW = []  # store timestamps of calls


@app.route("/contradictions", methods=["GET"])
def contradictions_debug():
    try:
        import time as _t
        _t0 = _t.time()
        # rate limit: last 60s allow <= 60 calls
        now = _t.time()
        global _CONTRA_WINDOW
        _CONTRA_WINDOW = [ts for ts in _CONTRA_WINDOW if now - ts < 60.0]
        if len(_CONTRA_WINDOW) >= 60:
            return jsonify({"rate_limited": True, "try_after_sec": 10}), 429
        _CONTRA_WINDOW.append(now)
        _canon = os.getenv("AXIOM_CONTRADICTION_ENABLED")
        if _canon is None and os.getenv("AXIOM_CONTRADICTIONS") is not None:
            try:
                log.warning("[RECALL][Deprecation] AXIOM_CONTRADICTIONS is deprecated; use AXIOM_CONTRADICTION_ENABLED")
            except Exception:
                pass
            try:
                os.environ.setdefault("AXIOM_CONTRADICTION_ENABLED", os.getenv("AXIOM_CONTRADICTIONS", "0"))
            except Exception:
                pass
            _canon = os.getenv("AXIOM_CONTRADICTION_ENABLED")
        if str(_canon or "0").strip() not in {"1","true","True"}:
            return jsonify({"contradictions_enabled": False}), 200
        last = getattr(memory_response_pipeline, "_LAST_CONTRADICTIONS", None) or {"items": []}
        # Internal normalization: do not mutate response body
        try:
            items = list(last.get("items", [])) if isinstance(last, dict) else []
        except Exception:
            items = []
        total = len(items)
        normalized = 0
        warn_count = 0
        err_count = 0
        if _normalize_contradiction is not None and total > 0:
            for it in items:
                if not isinstance(it, dict):
                    continue
                # Only if payload has a candidate claim-like field
                if not any(k in it for k in ("claim", "statement", "text")):
                    continue
                c, warns = _normalize_contradiction(it)  # type: ignore
                if c is None:
                    err_count += 1
                else:
                    normalized += 1
                warn_count += len(warns or [])
        # Emit metrics and structured log
        elapsed_ms = int(((_t.time() - _t0) * 1000.0))
        try:
            if _metrics:
                _metrics.inc("contradictions.req", 1)
                if normalized:
                    _metrics.inc("contradictions.normalized", normalized)
                if warn_count:
                    _metrics.inc("contradictions.warn", warn_count)
                if err_count:
                    _metrics.inc("contradictions.err", err_count)
                _metrics.observe_ms("contradictions.ms", elapsed_ms)
        except Exception:
            pass
        try:
            req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Request-Id") or str(uuid.uuid4())
            log.info(
                json.dumps(
                    {
                        "component": "contradictions",
                        "action": "normalize",
                        "count": total,
                        "normalized": normalized,
                        "warn": warn_count,
                        "error": err_count,
                        "elapsed_ms": elapsed_ms,
                        "request_id": req_id,
                    }
                )
            )
        except Exception:
            pass
        verbose = os.getenv("AXIOM_DEBUG_VERBOSE", "0") == "1"
        if not verbose:
            for it in last.get("items", []):
                # ensure redaction (remove any accidental text fields)
                it.pop("text", None)
                for side in ("positive", "negative"):
                    if side in it:
                        for e in it[side]:
                            e.pop("text", None)
        return jsonify(last), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/retrieve", methods=["POST"])
def retrieve():
    try:
        data = request.get_json(force=True) or {}
        print("[DEBUG] Incoming retrieve request:", request.json)
        question = (data.get("question") or data.get("query") or "").strip()
        if not question:
            return jsonify({"error": "Empty query"}), 400

        # Per-request overrides
        composite_enabled = data.get("composite_enabled")
        profile = data.get("scoring_profile")
        mmr_lambda = data.get("mmr_lambda")
        top_k = data.get("top_k")
        top_n = data.get("top_n")

        # Run pipeline (async) with overrides via a small helper
        async def _run():
            return await memory_response_pipeline.generate_enhanced_context_response(user_question=question)

        # Temporarily override globals on memory_response_pipeline for this call only
        # Capture originals
        orig_composite = getattr(
            memory_response_pipeline, "_COMPOSITE", os.getenv("AXIOM_COMPOSITE_SCORING", "0") == "1"
        )
        orig_profile = getattr(
            memory_response_pipeline, "_PROFILE", os.getenv("AXIOM_SCORING_PROFILE", "default")
        )
        orig_mmr = getattr(memory_response_pipeline, "_MMR", float(os.getenv("AXIOM_MMR_LAMBDA", "0.4")))
        orig_top_n = getattr(memory_response_pipeline, "_TOP_N", int(os.getenv("AXIOM_TOP_N", "8")))
        orig_top_k_frag = getattr(
            memory_response_pipeline, "TOP_K_FRAGMENTS", int(os.getenv("VECTOR_TOPK", "10"))
        )

        try:
            # Apply overrides if provided (None means keep original)
            if composite_enabled is not None:
                setattr(memory_response_pipeline, "_COMPOSITE", bool(composite_enabled))
            if profile is not None:
                setattr(memory_response_pipeline, "_PROFILE", str(profile))
            if mmr_lambda is not None:
                try:
                    val = float(mmr_lambda)
                    setattr(memory_response_pipeline, "_MMR", max(0.0, min(1.0, val)))
                except Exception:
                    pass
            if top_n is not None:
                try:
                    setattr(memory_response_pipeline, "_TOP_N", max(1, int(top_n)))
                except Exception:
                    pass
            if top_k is not None:
                try:
                    setattr(memory_response_pipeline, "TOP_K_FRAGMENTS", max(1, int(top_k)))
                except Exception:
                    pass

            # Execute
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                raw_results = loop.run_until_complete(_run())
                print("[DEBUG] Raw Qdrant results:", raw_results)
            except Exception as e:
                print("[DEBUG] Retrieval error:", repr(e))
                return jsonify({"ok": False, "error": str(e)}), 500
            result = raw_results
        finally:
            # Restore originals to avoid leaking overrides
            setattr(memory_response_pipeline, "_COMPOSITE", orig_composite)
            setattr(memory_response_pipeline, "_PROFILE", orig_profile)
            setattr(memory_response_pipeline, "_MMR", orig_mmr)
            setattr(memory_response_pipeline, "_TOP_N", orig_top_n)
            setattr(memory_response_pipeline, "TOP_K_FRAGMENTS", orig_top_k_frag)

        # Return both the LLM response and the latest memory debug snapshot
        last = getattr(memory_response_pipeline, "_LAST_MEMORY_DEBUG", None)
        return (
            jsonify({"ok": True, "response": result, "memory_debug": last or {}}),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
if __name__ == "__main__":
    PORT = 5000
    print("ROUTES ON START:", [r.rule for r in app.url_map.iter_rules()])
    app.run(host="0.0.0.0", port=PORT)
