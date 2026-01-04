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
    "--qdrant_host",
    default=os.getenv("QDRANT_HOST", "axiom_qdrant"),
    help="Qdrant host for vector store (default from env QDRANT_HOST, fallback axiom_qdrant)",
)
parser.add_argument(
    "--qdrant_port",
    type=int,
    default=int(os.getenv("QDRANT_PORT", "6333")),
    help="Qdrant port (default from env QDRANT_PORT, fallback 6333)",
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


# Get Qdrant connection details from environment with fallbacks
def _get_qdrant_connection_info():
    """Get Qdrant connection details from environment variables with fallbacks"""
    qdrant_host = os.getenv("QDRANT_HOST")
    qdrant_port = os.getenv("QDRANT_PORT")

    # Fallback to parsing QDRANT_URL if QDRANT_HOST is not set
    if not qdrant_host:
        vector_pod_url = os.getenv("QDRANT_URL", "")
        if vector_pod_url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(vector_pod_url)
                qdrant_host = parsed.hostname or "localhost"
                # Force port 6333 as specified in requirements
                qdrant_port = "6333"
                logger.info(
                    f"Parsed Qdrant host from QDRANT_URL: {qdrant_host}:{qdrant_port}"
                )
            except Exception as e:
                logger.warning(f"Failed to parse QDRANT_URL: {e}")
                qdrant_host = "localhost"
                qdrant_port = "6333"
        else:
            qdrant_host = "localhost"
            qdrant_port = "6333"

    if not qdrant_port:
        qdrant_port = "6333"

    return qdrant_host, int(qdrant_port)


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
        qdrant_host, qdrant_port = _get_qdrant_connection_info()
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
        logger.info(f"🔗 Qdrant URL: {qdrant_url}")
        logger.info(
            f"📋 Required collections: {QDRANT_MEMORY_COLLECTION}, {QDRANT_BELIEF_COLLECTION}"
        )

        try:
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
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv  # optional
except Exception:

    def load_dotenv():
        return None


from flask import Flask, jsonify, request

# --- Memory pipeline integration ---
import memory_response_pipeline
from flask_cors import CORS
from qdrant_client import QdrantClient

from .goal_types import Goal  # <-- Make sure this exists and is correct
from .memory_manager import Memory
from vector.unified_client import UnifiedVectorClient, VectorSearchRequest

# ===== WEAVIATE REMOVED =====
# Migrated to Qdrant - Weaviate imports removed
# import weaviate  # REMOVED
# from weaviate.exceptions import WeaviateBaseError  # REMOVED


load_dotenv()

# ――― FEATURE FLAG: Memory Class Switch ―――
USE_MEMORY_ARCHIVE = True

import asyncio

import requests


# Optional: single-source config resolver (env-gated, additive)
try:
    from config.resolver import emit_summary_once as _emit_cfg_summary, resolve_vector as _resolve_vector

    if os.getenv("CONFIG_RESOLVER_ENABLED", "true").strip().lower() == "true":
        try:
            _emit_cfg_summary()
            _vec = _resolve_vector()
            logger.info(f"[ConfigResolver] vector={_vec}")
        except Exception:
            pass
except Exception:
    pass

# DEPRECATED: Weaviate class verification removed - using Qdrant now
def verify_vector_backend() -> bool:
    """Verify vector backend connectivity using Qdrant.

    Prefers QDRANT_HOST/QDRANT_PORT. If only QDRANT_URL is set, derives host/port from it.
    Verifies required collections from env and returns True if present.
    """
    try:
        # Resolve host/port
        host = os.getenv("QDRANT_HOST")
        port_str = os.getenv("QDRANT_PORT")
        if not host:
            vp = os.getenv("QDRANT_URL", "")
            if vp:
                from urllib.parse import urlparse

                parsed = urlparse(vp if "://" in vp else f"http://{vp}")
                host = parsed.hostname or "localhost"
                # Respect explicit port in URL; fall back to env/default if absent.
                port_str = str(parsed.port or port_str or "6333")
            else:
                host = "localhost"
                port_str = "6333"
        port = int(port_str or "6333")
        # Required collections
        required_memory = os.getenv("QDRANT_MEMORY_COLLECTION", "axiom_memories")
        required_beliefs = os.getenv("QDRANT_BELIEF_COLLECTION", "axiom_beliefs")
        # Connect and list collections
        try:
            from .qdrant_utils import _list_collection_names, get_qdrant_client
        except Exception:
            # Fallback via axiom_qdrant_client wrapper
            from axiom_qdrant_client import QdrantClient as _AxiomClient

            client = _AxiomClient(host=host, port=port)
            collections = set(client.list_collections())
        else:
            client = get_qdrant_client(host, port)
            collections = _list_collection_names(client)
        missing = [
            c for c in (required_memory, required_beliefs) if c not in collections
        ]
        if missing:
            logger.error(
                f"[RECALL][Vector] ❌ Missing required Qdrant collections: {missing}"
            )
            return False
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
WORLD_MAP_PATH = "memory/world_map.json"


def load_world_map() -> dict:
    try:
        if os.path.exists(WORLD_MAP_PATH):
            with open(WORLD_MAP_PATH, "r") as fh:
                return json.load(fh)
    except Exception as e:
        print(f"[ERROR] Failed to load world map: {e}")
        traceback.print_exc()
    return {}


world_map = load_world_map()

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
        if vector_ready:
            print("✅ Vector backend ready")
        else:
            print("⚠️ Vector backend not available. Proceeding without vector support.")

    except Exception as e:
        vector_ready = False
        print(
            f"⚠️ Unexpected error checking vector backend: {e}. Proceeding without vector support."
        )


# Initialize the backend at startup
initialize_vector_backend()

# --- Vector fallback singletons ---
QDRANT_HOST, QDRANT_PORT = _get_qdrant_connection_info()
_embedder = None
_qdrant_client = None
_unified_vector_client = None


def _get_unified_vector_client() -> UnifiedVectorClient:
    global _unified_vector_client
    if _unified_vector_client is None:
        _unified_vector_client = UnifiedVectorClient(os.environ)
    return _unified_vector_client


def _env_truthy(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return bool(default)
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _embeddings_status() -> dict:
    """
    Lightweight, non-loading embeddings readiness snapshot.
    Does NOT instantiate models.
    """
    base_url = (os.getenv("AXIOM_EMBEDDING_URL") or "").strip().rstrip("/")
    if base_url:
        return {"embeddings_ready": True, "embeddings_mode": "remote", "embeddings_reason": None}

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


class _RemoteEmbedderCompat:
    """
    Minimal SentenceTransformer-compatible shim for memory pod fallback paths.

    Uses the embeddings service HTTP API (POST /embed).
    """

    def __init__(self, base_url: str, model: str, timeout_sec: float = 12.0):
        self._base = (base_url or "").strip().rstrip("/")
        self._model = (model or "").strip() or "BAAI/bge-small-en-v1.5"
        try:
            self._timeout = float(timeout_sec)
        except Exception:
            self._timeout = 12.0

    def encode(self, texts):  # type: ignore[no-untyped-def]
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


def _get_embedder():
    global _embedder
    if _embedder is None:
        # Prefer remote embeddings when configured to avoid SentenceTransformer downloads.
        base_url = (os.getenv("AXIOM_EMBEDDING_URL") or "").strip().rstrip("/")
        model = (os.getenv("AXIOM_EMBEDDING_MODEL") or os.getenv("ST_MODEL") or "").strip()
        if base_url:
            _embedder = _RemoteEmbedderCompat(base_url, model)
        else:
            # Local embeddings only when explicitly allowed.
            if not _env_truthy("AXIOM_USE_SENTENCE_TRANSFORMERS", False):
                raise RuntimeError(
                    "embeddings_unconfigured: set AXIOM_EMBEDDING_URL or enable AXIOM_USE_SENTENCE_TRANSFORMERS=true"
                )
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except Exception as e:
                raise RuntimeError(f"sentence_transformers_unavailable:{type(e).__name__}") from e
            # Prefer canonical env; warn on legacy AXIOM_EMBEDDER
            model_name = os.getenv("AXIOM_EMBEDDING_MODEL")
            if not model_name:
                legacy = os.getenv("AXIOM_EMBEDDER") or os.getenv("EMBEDDING_MODEL")
                if legacy:
                    try:
                        log.warning(
                            "[RECALL][Deprecation] AXIOM_EMBEDDER is deprecated; use AXIOM_EMBEDDING_MODEL"
                        )
                    except Exception:
                        pass
                model_name = legacy or "all-MiniLM-L6-v2"
            _embedder = SentenceTransformer(model_name)
    return _embedder


def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=int(QDRANT_PORT))
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
            log.info(
                f"🔄 Loading memory from Qdrant at {args.qdrant_host}:{args.qdrant_port}"
            )
            memory_data = load_memory_from_qdrant(
                host=args.qdrant_host,
                port=args.qdrant_port,
                collection_name=args.qdrant_collection,
            )
            log.info(
                f"✅ Loaded {len(memory_data)} items from Qdrant collection '{args.qdrant_collection}'"
            )
            return memory_data
        except Exception as e:
            log.error(f"❌ Failed to load from Qdrant: {e}")
            if args.allow_empty_memory:
                log.warning(
                    "⚠️ Continuing with empty memory due to --allow_empty_memory flag"
                )
                memory_data = []
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
        memory.load()
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

# Kubernetes-style probes (additive; keep /health unchanged)
_PROBE_HEADERS = {"Content-Type": "text/plain; charset=utf-8"}


def _is_ready() -> bool:
    # Minimal readiness: relies on existing in-process vector readiness flag.
    try:
        return bool(vector_ready)
    except Exception:
        return False


@app.route("/", methods=["GET"])
def index():
    return jsonify({"service": "axiom_memory", "status": "ok"}), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200, _PROBE_HEADERS


@app.route("/livez", methods=["GET"])
def livez():
    return "ok", 200, _PROBE_HEADERS


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
    # - status == "ok"
    # - vector_ready == True
    # - memory_size > 0
    #
    # Keep this cheap: use already-loaded in-memory state only (no network calls).
    try:
        # Prefer cached snapshot list length (stable, cheap). Fall back to Memory.__len__ only when needed.
        memory_size = int(len(memory_data or []))
        if memory_size <= 0 and memory is not None:
            try:
                memory_size = int(len(memory))
            except Exception:
                pass
        status = "ok"
        vready = bool(vector_ready)
    except Exception as e:
        return jsonify({"status": "not_ready", "error": f"readiness_exception:{type(e).__name__}"}), 503

    checks = {
        "status_ok": status == "ok",
        "vector_ready": vready is True,
        "memory_nonempty": int(memory_size or 0) > 0,
    }
    failed = {k: v for k, v in checks.items() if not bool(v)}
    if not failed:
        return jsonify({"status": "ok", "memory_size": memory_size, "vector_ready": True}), 200
    return jsonify({"status": "not_ready", "failed": failed, "memory_size": memory_size, "vector_ready": bool(vready)}), 503


# Initialize memory data based on the selected mode
memory_data = []
if args.use_qdrant:
    # For Qdrant mode, we manage memory_data directly
    load_memory_data()
    memory = None  # Don't create Memory instance for Qdrant mode
else:
    # For JSON mode, use the existing Memory class
    memory = Memory()
    memory.load()
    memory_data = memory.snapshot(limit=None)  # Cache the data for health endpoint

# Extra: Log Qdrant collection schema if available (distance, dim)
try:
    if args.use_qdrant and QDRANT_AVAILABLE:
        from qdrant_client import QdrantClient

        client = QdrantClient(host=args.qdrant_host, port=args.qdrant_port, timeout=5)
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


@app.route("/health", methods=["GET"])
def health():
    try:
        kurt_facts = world_map.get("ExamplePerson", {})

        # Get memory size based on the current mode
        if args.use_qdrant and QDRANT_AVAILABLE:
            try:
                # Get live count from Qdrant
                memory_size = get_qdrant_collection_count(
                    host=args.qdrant_host,
                    port=args.qdrant_port,
                    collection_name=args.qdrant_collection,
                )
            except Exception as e:
                log.warning(f"Failed to get Qdrant count, using cached data: {e}")
                memory_size = len(memory_data)
        else:
            # Use traditional Memory class
            memory_size = len(memory) if memory else len(memory_data)

        response = {
            "status": "ok",
            "memory_size": memory_size,
            "world_facts": len(kurt_facts),
            "vector_ready": vector_ready,  # Use the global flag
            "memory_source": (
                "json_file"
                if _json_mode_enabled()
                else ("qdrant" if args.use_qdrant else "json_file")
            ),
            "qdrant_config": (
                {
                    "host": args.qdrant_host,
                    "port": args.qdrant_port,
                    "collection": args.qdrant_collection,
                }
                if args.use_qdrant
                else None
            ),
        }
        # New (non-breaking) embeddings readiness fields
        response.update(_embeddings_status())

        return jsonify(response)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "detail": str(e)}), 500


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
        if _json_mode_enabled():
            payload = request.get_json(force=True, silent=True) or {}
            # Accept both `content` and `text`
            if not (payload.get("content") or payload.get("text")):
                return jsonify({"error": "Missing 'content' (or 'text')"}), 400
            rid = _json_append(payload)
            return jsonify({"status": "ok", "id": rid})

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
        content = data.get("content", "").strip()
        if not content:
            return jsonify({"error": "Missing 'content'"}), 400

        entry = {
            "content": content,
            "tags": data.get("tags", []),
            "type": data.get("type", "external_import"),
            "timestamp": datetime.now().isoformat(),
        }
        mem_id = memory.store(entry)

        # Guard vector operations with backend availability check
        if ENABLE_PUSH and vector_ready:
            try:
                # Push to Qdrant via vector adapter
                vector_payload = {
                    "content": content,
                    "metadata": {
                        "memory_id": mem_id,
                        "tags": data.get("tags", []),
                        "type": data.get("type", "external_import"),
                        "timestamp": entry["timestamp"],
                    },
                }
                resp = requests.post(
                    f"{VECTOR_URL}/v1/memories", json=vector_payload, timeout=10
                )
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
        facts = world_map.get("ExamplePerson", {})
        if isinstance(facts, dict):
            fact_block = ". ".join(f"{k}: {v}" for k, v in facts.items())
        else:
            fact_block = "[Facts unavailable]"

        answer = (
            f"Given the summary '{summary}' and the known facts '{fact_block}', "
            f"my answer to '{question}' is based on Axiom's contextual memory."
        )
        return jsonify({"answer": answer, "possible_contradictions": []})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"answer": f"❌ Error: {e}"}), 500


@app.route("/vector/query", methods=["POST"])
def vector_query():
    try:
        # Guard against missing vector backend (expected misconfig → never 500)
        if not vector_ready:
            resp = jsonify({"error": "Vector backend not configured or unavailable"})
            resp.status_code = 503
            resp.headers["X-Axiom-Error-Code"] = "vector_backend_unavailable"
            return resp

        data = request.get_json(force=True) or {}

        # Accept multiple field names for convenience
        query = (
            data.get("question")
            or data.get("query")
            or data.get("content")
            or data.get("text")
            or ""
        ).strip()
        k = int(data.get("k") or data.get("top_k") or 8)

        if not query:
            resp = jsonify({"error": "Empty query"})
            resp.status_code = 400
            return resp

        # Route through unified client only (no direct Qdrant / adapter calls here)
        try:
            sr = _get_unified_vector_client().search(VectorSearchRequest(query=query, top_k=k))
        except Exception as e:
            msg = str(e)
            if "embeddings_unconfigured" in msg or msg.startswith("sentence_transformers_unavailable"):
                resp = jsonify(
                    {
                        "data": {"Get": {memory_collection: []}},
                        "warning": "embeddings_not_configured",
                        "error": msg,
                    }
                )
                resp.status_code = 200
                resp.headers["X-Axiom-Error-Code"] = "embeddings_unconfigured"
                return resp
            # Backend call failure (expected operational issue) → 503 + explicit header.
            logger.exception("[vector/query] unified vector backend call failed")
            resp = jsonify({"error": msg})
            resp.status_code = 503
            resp.headers["X-Axiom-Error-Code"] = "vector_backend_error"
            return resp

        # Preserve legacy response shape (Weaviate-like)
        results: List[Dict[str, Any]] = []
        for h in list(getattr(sr, "hits", []) or []):
            try:
                score = float(getattr(h, "score", 0.0) or 0.0)
            except Exception:
                score = 0.0
            score = max(0.0, min(1.0, score))
            distance = max(0.0, min(1.0, 1.0 - score))
            results.append(
                {
                    "content": getattr(h, "content", "") or "",
                    "tags": list(getattr(h, "tags", []) or []),
                    "_additional": {"score": score, "distance": distance},
                }
            )

        response = {"data": {"Get": {memory_collection: results}}}
        resp = jsonify(response)
        resp.status_code = 200
        return resp

    except Exception as e:
        # Unexpected crash → 500, but log stack trace
        logger.exception("[vector/query] unexpected error")
        resp = jsonify({"error": str(e)})
        resp.status_code = 500
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
                resp = requests.post(
                    f"{VECTOR_URL}/v1/memories", json=vector_payload, timeout=10
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
            return jsonify({}), 200
        return jsonify(m), 200
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
        question = (data.get("question") or data.get("query") or "").strip()
        if not question:
            return jsonify({"error": "Empty query"}), 400

        # Optional per-request overrides
        composite_enabled = data.get("composite_enabled")
        profile = data.get("scoring_profile")
        mmr_lambda = data.get("mmr_lambda")

        # Run through the memory response pipeline
        try:
            response = memory_response_pipeline.retrieve_vector_context(
                question,
                composite_enabled=composite_enabled,
                profile=profile,
                mmr_lambda=mmr_lambda,
            )
            return jsonify(response)
        except Exception as inner_err:
            return jsonify({"error": f"Vector recall failed: {inner_err}"}), 500

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


# ─────────────────────────────────────────────
if __name__ == "__main__":
    PORT = 5000
    print("ROUTES ON START:", [r.rule for r in app.url_map.iter_rules()])
    app.run(host="0.0.0.0", port=PORT)
