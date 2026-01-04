from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from urllib.parse import urlparse

# Import requests with fallback for minimal environments
try:
    import requests
except ImportError:
    requests = None

from datetime import datetime, timedelta, timezone
from math import exp
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Create module-level logger
logger = logging.getLogger(__name__)

# Standardized logging setup for Memory pod
os.makedirs("data/logs", exist_ok=True)
log = logging.getLogger("MemoryManager")
handler = logging.FileHandler("data/logs/memory.log")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

from memory.embedding_config import (
    embedding_model_name,
    embedding_dim,
    log_embedding_banner,
)


# Robust LOG_LEVEL parsing with validation and fallback
def _get_validated_log_level():
    """Parse and validate LOG_LEVEL environment variable with safe fallback."""
    raw_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}

    if raw_level in valid_levels:
        return raw_level
    else:
        # Log warning about invalid level (but avoid infinite recursion)
        print(
            f"[WARNING] Invalid LOG_LEVEL '{os.getenv('LOG_LEVEL', 'INFO')}', defaulting to INFO. Valid levels: {', '.join(sorted(valid_levels))}"
        )
        return "INFO"


# Set log level with validation
selected_level = _get_validated_log_level()
log.setLevel(selected_level)
log.info(f"🔧 Memory Manager initialized with LOG_LEVEL: {selected_level}")

DEFAULT_IMPORTANCE = 0.1


# --- begin: safe indicator matcher ---
def _matches_indicator(error: BaseException, indicator: Any) -> bool:
    """
    Robustly determine if `indicator` matches the given error.
    Supports:
      - str: substring match against error class name and message (case-insensitive)
      - Exception class/type: isinstance(error, indicator)
      - bytes/bytearray: utf-8 decode then treat as string
      - iterable (list/tuple/set): any() over members
      - None/other: False
    Never raises; returns False on any unexpected issue.
    """
    try:
        if indicator is None:
            return False

        # Type/class indicators e.g. ValueError, SomeLibError
        if isinstance(indicator, type):
            try:
                return isinstance(error, indicator)
            except Exception:
                return False

        # Bytes → decode, then recurse as str
        if isinstance(indicator, (bytes, bytearray)):
            try:
                indicator = indicator.decode("utf-8", "ignore")
            except Exception:
                return False

        # String indicators → check in class name OR message
        if isinstance(indicator, str):
            cls = getattr(error, "__class__", type(error))
            name = getattr(cls, "__name__", str(cls))
            msg = str(error)
            s = indicator.lower()
            return (s in name.lower()) or (s in msg.lower())

        # Iterable of indicators → any
        if isinstance(indicator, (list, tuple, set)):
            for sub in indicator:
                if _matches_indicator(error, sub):
                    return True
            return False

        # Unknown types → no match
        return False
    except Exception:
        # Absolutely never fail from here; just say "no match".
        return False


# --- end: safe indicator matcher ---

import os

# [COGNITIVE_LOGGING] Import cognitive logbook system
import sys

from .decay_policy import decay as decay_score
from .idempotency import canonical_fingerprint, stable_point_id
from .goal_types import Goal  # Adjust import path if necessary
from .memory_types import (
    MemoryType,
    get_storage_characteristics,
    infer_memory_type,
    memory_type_manager,
)

# Add workspace root to path for logbook access
_workspace_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)
# [HEALTH_CHECK] Import health check utilities for memory pod
from axiom_health_check import mark_error, mark_ready, setup_health_cleanup
from logbook import log_memory_pruned, log_memory_retrieved, log_memory_stored

# [QDRANT_BACKEND] Import memory backend interface for Qdrant integration (dynamic)
try:
    from memory_backend_interface import (
        MemoryBackendError,
        MemoryBackendFactory,
        MemoryFilter,
    )
except ImportError as e:
    # Memory backend interface is required; re-raise with context
    raise

# Dynamic import of Qdrant backend to avoid circular imports
import importlib

QdrantMemoryBackend = None
try:
    qmod = importlib.import_module("pods.memory.qdrant_backend")
    QdrantMemoryBackend = getattr(qmod, "QdrantMemoryBackend", None)
    QDRANT_BACKEND_AVAILABLE = QdrantMemoryBackend is not None
    if QDRANT_BACKEND_AVAILABLE:
        log.info("🔧 Qdrant backend interface available for memory manager")
    else:
        log.warning("⚠️ Qdrant backend not found in module pods.memory.qdrant_backend")
except Exception as e:
    QDRANT_BACKEND_AVAILABLE = False
    log.warning("⚠️ Qdrant backend not available in memory manager: %s", e)

# [QDRANT_CONFIG] Configuration for Qdrant backend
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Vector/Qdrant should be opt-in by configuration. If neither QDRANT nor VECTOR_POD_URL
# is set, treat vector as disabled by default (prevents accidental localhost:6333 probes).
def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, "1" if default else "0")).strip().lower() in {"1", "true", "yes", "on"}

VECTOR_RECALL_DISABLED = _env_bool("VECTOR_RECALL_DISABLED", False)
_QDRANT_URL_ENV = (os.getenv("QDRANT_URL", "") or "").strip()
_VECTOR_POD_URL_ENV = (os.getenv("VECTOR_POD_URL", "") or "").strip()
_QDRANT_HOST_ENV = (os.getenv("QDRANT_HOST", "") or "").strip()
_QDRANT_CONFIGURED = bool(_QDRANT_URL_ENV or _VECTOR_POD_URL_ENV or _QDRANT_HOST_ENV)

USE_QDRANT_BACKEND = _env_bool("USE_QDRANT_BACKEND", True)

_QDRANT_DISABLED_LOGGED = False


def _log_qdrant_disabled_once(reason: str) -> None:
    global _QDRANT_DISABLED_LOGGED
    if _QDRANT_DISABLED_LOGGED:
        return
    _QDRANT_DISABLED_LOGGED = True
    try:
        log.warning("[MemoryManager] Vector/Qdrant disabled (%s)", reason)
    except Exception:
        pass

# [TEMPORAL] Import temporal reasoning capabilities - minimal core functions
try:
    from temporal_reasoner import (
        enrich_with_temporal_metadata,
        is_expired,
        is_valid_now,
        now_utc,
        parse_timestamp,
    )

    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False

    # Fallback functions if temporal_reasoner is not available
    def is_expired(memory) -> bool:
        return False

    def is_valid_now(memory) -> bool:
        return True

    def enrich_with_temporal_metadata(entry):
        return entry

    def now_utc() -> datetime:
        return datetime.now(timezone.utc)

    def parse_timestamp(timestamp) -> datetime:
        if isinstance(timestamp, datetime):
            return timestamp
        elif timestamp:
            try:
                return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except:
                pass
        return datetime.now(timezone.utc)


MEMORY_FILE = os.getenv("MEMORY_FILE", "memory/long_term_memory.json")

# ─────────────────────────────────────────────
# Heuristic Speaker Detection
# ─────────────────────────────────────────────
USER_PATTERNS = [
    r"\b(yeah|nope|ha|cheers|mate|lol|wtf|reckon)\b",
    r"\b(gonna|wanna|innit|ain't)\b",
    r"\b(fuck|bloody|arse|mum|favourite)\b",
]

AXIOM_PATTERNS = [
    r"\b(indeed|therefore|thus|consequently|let us proceed)\b",
    r"\bcontext retrieval|prompt injection|semantic decay\b",
    r"[–;]",
    r"^#{1,6} ",
]


def detect_speaker(content: str) -> str | None:
    content = content.lower()
    if any(re.search(p, content) for p in USER_PATTERNS):
        return "user"
    if any(re.search(p, content) for p in AXIOM_PATTERNS):
        return "axiom"
    return None


def tag_speaker_if_missing(entry: dict) -> dict:
    current = entry.get("speaker", "").strip().lower()
    if current not in {"axiom", "user"}:
        guess = detect_speaker(entry.get("content", ""))
        if guess:
            entry["speaker"] = guess
    return entry


# ─────────────────────────────────────────────
# Memory Enrichment & Decay Helpers
# ─────────────────────────────────────────────
def enrich_memory(entry: dict) -> dict:
    # Infer hierarchical memory type if not explicitly provided
    if "memory_type" not in entry:
        content = entry.get("content", "")
        source = entry.get("source", "")
        tags = entry.get("tags", [])
        context = {
            "timestamp": entry.get("timestamp"),
            "speaker": entry.get("speaker"),
            "type": entry.get("type"),
            "importance": entry.get("importance", 0.5),
        }

        memory_type = infer_memory_type(content, source, tags, context)
        entry["memory_type"] = memory_type.value

        # Adjust default importance based on memory type
        if "importance" not in entry:
            entry["importance"] = memory_type_manager.get_default_importance(
                memory_type
            )

    # Base memory enrichment
    base_entry = {
        "content": entry.get("content", ""),
        "timestamp": entry.get("timestamp", datetime.utcnow().isoformat()),
        "source": entry.get("source", "unknown"),
        "speaker": entry.get("speaker", "system"),
        "type": entry.get("type", "generic"),
        "importance": entry.get("importance", 0.5),
        "memory_type": entry.get("memory_type", "semantic"),
        "tags": entry.get("tags", []),
        "valid_from": entry.get("valid_from"),  # from temporal_reasoning
        "valid_until": entry.get("valid_until"),
        "temporal_tags": entry.get("temporal_tags", []),
        "temporal_scope": entry.get("temporal_scope"),
        # Dream-specific fields
        "is_dream": entry.get("is_dream", False),
        "dream_type": entry.get("dream_type"),
        "dream_origin_id": entry.get("dream_origin_id"),
        "dream_session_id": entry.get("dream_session_id"),
        "dream_recursion_depth": entry.get("dream_recursion_depth", 0),
        "safety_classification": entry.get("safety_classification", "low_risk"),
    }

    # [TEMPORAL] Add temporal fields if provided
    if entry.get("valid_from"):
        base_entry["valid_from"] = entry["valid_from"]
    if entry.get("valid_until"):
        base_entry["valid_until"] = entry["valid_until"]
    if entry.get("temporal_tags"):
        base_entry["temporal_tags"] = entry["temporal_tags"]
    if entry.get("temporal_scope"):
        base_entry["temporal_scope"] = entry["temporal_scope"]

    # [TEMPORAL] Enrich with temporal metadata if available
    if TEMPORAL_AVAILABLE:
        try:
            return enrich_with_temporal_metadata(base_entry)
        except Exception as e:
            log.warning(f"[TEMPORAL] Failed to enrich temporal metadata: {e}")

    # [EMPATHY_ANALYSIS] Add empathy metadata for agent interactions
    try:
        # Import empathy functions with fallback
        try:
            from axiom.theory_of_mind.engine import (
                AgentModel,
                infer_agent_emotion,
                model_agent_intentions,
            )

            EMPATHY_AVAILABLE = True
        except ImportError:
            EMPATHY_AVAILABLE = False

        if EMPATHY_AVAILABLE:
            content = base_entry.get("content", "")

            # Check if this memory involves agent interactions
            agent_keywords = [
                "said",
                "asked",
                "mentioned",
                "replied",
                "told",
                "explained",
                "user",
                "human",
                "person",
                "colleague",
                "team",
                "someone",
            ]

            if any(keyword in content.lower() for keyword in agent_keywords):
                # Create a simple agent model for empathy analysis
                agent = AgentModel(
                    agent_id="memory_agent",
                    name="Inferred Agent",
                    traits=["communicative"],  # Simple default trait
                    goals=["communicate"],  # Simple default goal
                    beliefs={},
                    memory_refs=[],
                    last_updated=parse_timestamp(base_entry.get("timestamp")),
                )

                # Perform empathy analysis
                try:
                    emotional_state = infer_agent_emotion(agent, content)
                    intentions = model_agent_intentions(agent, content)

                    # Add empathy metadata to memory entry
                    base_entry["empathy_metadata"] = {
                        "emotional_state": emotional_state.emotion,
                        "emotional_intensity": emotional_state.intensity,
                        "emotional_confidence": emotional_state.confidence,
                        "inferred_intentions": intentions.intentions[
                            :3
                        ],  # Top 3 intentions
                        "intention_confidence": intentions.confidence,
                        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                        "memoryType": "simulation",  # Mark as simulation data
                    }

                    # Add empathy tag
                    if "empathy_inference" not in base_entry["tags"]:
                        base_entry["tags"].append("empathy_inference")

                    log.debug(
                        f"[EMPATHY] Added empathy metadata: emotion={emotional_state.emotion}, intentions={intentions.intentions[:2]}"
                    )

                except Exception as e:
                    log.warning(f"[EMPATHY] Failed to perform empathy analysis: {e}")

    except Exception as e:
        log.warning(f"[EMPATHY] Empathy enrichment failed: {e}")

    return base_entry


def days_since(dt_str: str) -> float:
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return 0.0


def is_belief(entry: dict) -> bool:
    return entry.get("type") == "belief" or entry.get("belief_status") != "unverified"


def is_protected(entry: dict) -> bool:
    return entry.get("is_protected", False)


def parse_confidence(entry: dict) -> float:
    try:
        return float(entry.get("confidence", 0.8))
    except:
        return 0.8


def parse_created(entry: dict) -> str:
    return entry.get("timestamp") or datetime.now(timezone.utc).isoformat()


class FallbackMemoryStore:
    """
    In-memory fallback storage with SQLite persistence for when Qdrant is unavailable.
    Provides temporary storage with automatic resync capabilities.
    """

    def __init__(self, db_path: str = "data/fallback_memory.db"):
        self.db_path = db_path
        self.fallback_memories: List[Dict[str, Any]] = []
        self.is_fallback_mode = False
        self.fallback_start_time: Optional[datetime] = None
        self.lock = threading.Lock()

        # Initialize SQLite database
        self._init_db()

        # Load any existing fallback memories from disk
        self._load_fallback_memories()

        log.info("🔄 Fallback memory store initialized")

    def _init_db(self):
        """Initialize SQLite database for fallback storage"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fallback_memories (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """
                )
                conn.commit()
            try:
                log.info("[RECALL][Fallback] initialized path=%s", self.db_path)
            except Exception:
                pass
        except Exception as e:
            log.error(f"❌ Failed to initialize fallback database: {e}")
            try:
                log.info("[RECALL][Fallback] disabled reason=init_failed err=%s", e)
            except Exception:
                pass

    def _load_fallback_memories(self):
        """Load existing fallback memories from SQLite"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT metadata FROM fallback_memories ORDER BY created_at"
                )
                for (metadata_json,) in cursor.fetchall():
                    memory = json.loads(metadata_json)
                    self.fallback_memories.append(memory)

            if self.fallback_memories:
                log.info(
                    f"🔄 Loaded {len(self.fallback_memories)} fallback memories from disk"
                )
                try:
                    log.info("[RECALL][Fallback] loaded count=%d", len(self.fallback_memories))
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"⚠️ Failed to load fallback memories: {e}")
            try:
                log.info("[RECALL][Fallback] disabled reason=load_failed err=%s", e)
            except Exception:
                pass

    def enter_fallback_mode(self, reason: str = "Qdrant connection failed"):
        """Enter fallback mode due to Qdrant failure"""
        with self.lock:
            if not self.is_fallback_mode:
                self.is_fallback_mode = True
                self.fallback_start_time = datetime.now(timezone.utc)
                log.warning(f"🚨 ENTERING FALLBACK MODE: {reason}")
                log.warning(
                    f"🔄 Memory operations will be cached locally until Qdrant recovers"
                )
                try:
                    log.warning("[RECALL][Fallback] entering reason=%s", reason)
                except Exception:
                    pass

    def exit_fallback_mode(self, reason: str = "Qdrant connection restored"):
        """Exit fallback mode when Qdrant is available again"""
        with self.lock:
            if self.is_fallback_mode:
                duration = (
                    datetime.now(timezone.utc) - self.fallback_start_time
                    if self.fallback_start_time
                    else timedelta(0)
                )
                self.is_fallback_mode = False
                self.fallback_start_time = None
                log.info(f"✅ EXITING FALLBACK MODE: {reason}")
                log.info(f"🕒 Fallback mode duration: {duration}")
                try:
                    log.info("[RECALL][Fallback] exiting reason=%s duration=%s", reason, duration)
                except Exception:
                    pass

    def store_fallback_memory(self, memory: Dict[str, Any]) -> str:
        """Store a memory in fallback mode"""
        memory_id = memory.get("id", str(uuid4()))

        # Add fallback metadata
        memory = memory.copy()
        memory["id"] = memory_id
        memory["memory_type"] = "fallback"
        memory["metadata"] = memory.get("metadata", {})
        memory["metadata"]["fallback"] = True
        memory["metadata"]["fallback_timestamp"] = datetime.now(
            timezone.utc
        ).isoformat()
        memory["confidence"] = 0.0  # Zero confidence for fallback memories

        with self.lock:
            self.fallback_memories.append(memory)

            # Persist to SQLite
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO fallback_memories (id, content, timestamp, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                        (
                            memory_id,
                            memory.get("content", ""),
                            memory.get("timestamp", ""),
                            json.dumps(memory),
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    conn.commit()
            except Exception as e:
                log.error(f"❌ Failed to persist fallback memory: {e}")

        log.info(f"🔄 Stored fallback memory (ID: {memory_id[:8]}...)")
        try:
            log.info("[RECALL][Fallback] stored id=%s", memory_id)
        except Exception:
            pass
        return memory_id

    def get_fallback_memories(self) -> List[Dict[str, Any]]:
        """Get all cached fallback memories"""
        with self.lock:
            return self.fallback_memories.copy()

    def clear_fallback_memories(self):
        """Clear all fallback memories after successful sync"""
        with self.lock:
            count = len(self.fallback_memories)
            self.fallback_memories.clear()

            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM fallback_memories")
                    conn.commit()
            except Exception as e:
                log.error(f"❌ Failed to clear fallback database: {e}")

        log.info(f"🧹 Cleared {count} fallback memories after successful sync")
        try:
            log.info("[RECALL][Fallback] cleared count=%d", count)
        except Exception:
            pass

    def get_fallback_duration(self) -> Optional[timedelta]:
        """Get how long the system has been in fallback mode"""
        if self.is_fallback_mode and self.fallback_start_time:
            return datetime.now(timezone.utc) - self.fallback_start_time
        return None

    def check_long_fallback_mode(self, threshold_minutes: int = 10) -> bool:
        """Check if system has been in fallback mode too long"""
        duration = self.get_fallback_duration()
        if duration and duration.total_seconds() / 60 > threshold_minutes:
            log.warning(
                f"⚠️ EXTENDED FALLBACK MODE: {duration} - Consider investigating Qdrant connectivity"
            )
            return True
        return False


class Memory:
    def __init__(self):
        self.long_term_memory: list[dict] = []

        # [TRANSACTION_SUPPORT] Transaction state management
        self.transaction_active = False
        self.transaction_id = None
        self.transaction_buffer = []  # Buffer for uncommitted memories
        self.transaction_snapshot = None  # Snapshot for rollback

        # [FALLBACK_SYSTEM] Initialize fallback memory store
        self.fallback_store = FallbackMemoryStore()

        # [QDRANT_BACKEND] Initialize memory backend for vector operations
        self.memory_backend = None
        # Sticky flag: once we detect Qdrant is unreachable, stop trying and stay fallback-only.
        self._vector_unavailable = False

        if VECTOR_RECALL_DISABLED:
            _log_qdrant_disabled_once("VECTOR_RECALL_DISABLED=true")
        elif not _QDRANT_CONFIGURED:
            _log_qdrant_disabled_once("QDRANT/VECTOR_POD_URL unset")
        elif USE_QDRANT_BACKEND and QDRANT_BACKEND_AVAILABLE:
            try:
                # Register Qdrant backend if not already registered
                try:
                    MemoryBackendFactory.register_backend("qdrant", QdrantMemoryBackend)
                except:
                    pass  # Already registered

                # 🔄 Qdrant patch - Robust Qdrant URL handler
                qdrant_url = (os.getenv("QDRANT_URL") or os.getenv("VECTOR_POD_URL") or "").strip()
                if not qdrant_url:
                    # Defensive: treat as disabled when no explicit URL is provided.
                    _log_qdrant_disabled_once("no_qdrant_url")
                    return
                parsed = urlparse(qdrant_url)
                
                host = parsed.hostname or "localhost"
                port = parsed.port or 6333
                self.memory_backend = MemoryBackendFactory.create_backend(
                    "qdrant", host=host, port=port
                )

                # Initialize backend (create collections if needed)
                if self.memory_backend.health_check():
                    self.memory_backend.initialize()
                    log.info(
                        f"🎯 Memory manager initialized with Qdrant backend at {host}:{port}"  # 🔄 Qdrant patch
                    )

                    # Attempt to sync any existing fallback memories
                    self._attempt_fallback_sync()
                else:
                    log.error(
                        f"❌ Qdrant backend health check failed in memory manager"
                    )
                    self.memory_backend = None
                    self._vector_unavailable = True
                    self.fallback_store.enter_fallback_mode(
                        "Initial Qdrant health check failed"
                    )
            except Exception as e:
                log.error(
                    f"❌ Failed to initialize Qdrant backend in memory manager: {e}"
                )
                self.memory_backend = None
                self._vector_unavailable = True
                self.fallback_store.enter_fallback_mode(
                    f"Qdrant initialization failed: {e}"
                )

    def _detect_qdrant_failure(self, error: Exception) -> bool:
        """Detect if an error indicates Qdrant is unavailable"""
        error_indicators = [
            # Connection errors
            # requests may be None in minimal envs
            *((
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectTimeout,
            ) if requests is not None else ()),
            ConnectionError,
            TimeoutError,
            # Qdrant-specific errors
            "MemoryBackendConnectionError",
            "MemoryBackendError",
        ]

        # Check exception type
        for indicator in error_indicators:
            if _matches_indicator(error, indicator):
                return True

        # Check error message for network issues
        error_msg = str(error).lower()
        network_keywords = [
            "connection",
            "timeout",
            "refused",
            "unreachable",
            "network",
            "unavailable",
            "down",
            "failed to connect",
        ]

        if any(keyword in error_msg for keyword in network_keywords):
            return True

        # Check for HTTP errors indicating server issues
        if hasattr(error, "response") and error.response:
            status_code = getattr(error.response, "status_code", 0)
            if status_code >= 500:  # 5xx server errors
                return True

        return False

    def _attempt_qdrant_operation(self, operation_func, *args, **kwargs):
        """Wrapper to attempt Qdrant operations with fallback detection"""
        if not self.memory_backend:
            return None
        if self._vector_unavailable:
            return None

        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            if self._detect_qdrant_failure(e):
                log.warning("🚨 Qdrant operation failed; switching to fallback-only mode (%s)", type(e).__name__)
                self.fallback_store.enter_fallback_mode(f"Qdrant operation failed: {e}")
                self.memory_backend = None  # Disable backend
                self._vector_unavailable = True
                return None
            else:
                # Re-raise non-connection errors
                raise e

    def _attempt_fallback_sync(self):
        """Attempt to sync cached fallback memories to Qdrant"""
        if not self.memory_backend or not self.fallback_store.fallback_memories:
            return
        if self._vector_unavailable:
            return

        fallback_memories = self.fallback_store.get_fallback_memories()
        if not fallback_memories:
            return

        log.info(
            f"🔄 Attempting to sync {len(fallback_memories)} fallback memories to Qdrant"
        )

        successful_syncs = 0
        failed_syncs = 0

        for memory in fallback_memories:
            try:
                # Remove fallback metadata and restore original state
                sync_memory = memory.copy()
                sync_memory["metadata"] = sync_memory.get("metadata", {})
                sync_memory["metadata"]["fallback"] = False
                sync_memory["metadata"]["synced_from_fallback"] = True
                sync_memory["metadata"]["sync_timestamp"] = datetime.now(
                    timezone.utc
                ).isoformat()

                # Restore original memory type if available
                original_type = sync_memory["metadata"].get("original_memory_type")
                if original_type and original_type != "fallback":
                    sync_memory["memory_type"] = original_type
                else:
                    # Infer memory type from content
                    from .memory_types import infer_memory_type

                    inferred_type = infer_memory_type(
                        sync_memory.get("content", ""),
                        sync_memory.get("source"),
                        sync_memory.get("tags", []),
                        {
                            "timestamp": sync_memory.get("timestamp"),
                            "speaker": sync_memory.get("speaker"),
                            "type": sync_memory.get("type"),
                        },
                    )
                    sync_memory["memory_type"] = inferred_type.value

                # Restore confidence
                sync_memory["confidence"] = sync_memory["metadata"].get(
                    "original_confidence", 0.8
                )

                # Store in Qdrant
                memory_id = self.memory_backend.store_memory(sync_memory)
                log.info(f"✅ Synced fallback memory to Qdrant (ID: {memory_id})")
                successful_syncs += 1

            except Exception as e:
                # If Qdrant is unreachable, stop retrying after the first failure.
                if self._detect_qdrant_failure(e):
                    log.warning(
                        "❌ Qdrant unreachable during fallback sync; stopping further attempts (%s)",
                        type(e).__name__,
                    )
                    self.fallback_store.enter_fallback_mode("Qdrant unreachable during fallback sync")
                    self.memory_backend = None
                    self._vector_unavailable = True
                    failed_syncs += 1
                    break
                else:
                    log.error(
                        f"❌ Failed to sync fallback memory {memory.get('id', 'unknown')}: {e}"
                    )
                    failed_syncs += 1

        if successful_syncs > 0:
            log.info(
                f"🎯 Successfully synced {successful_syncs} fallback memories to Qdrant"
            )
            if failed_syncs == 0:
                # All memories synced successfully, clear fallback cache
                self.fallback_store.clear_fallback_memories()
                self.fallback_store.exit_fallback_mode(
                    "All fallback memories synced successfully"
                )
            else:
                log.warning(
                    f"⚠️ {failed_syncs} fallback memories failed to sync - keeping in cache"
                )

        if failed_syncs > 0:
            log.warning(f"❌ Failed to sync {failed_syncs} fallback memories")

    def _periodic_qdrant_check(self):
        """Periodically check if Qdrant is available again and attempt resync"""
        if not self.fallback_store.is_fallback_mode:
            return
        # Sticky: do not auto-retry once we've decided Qdrant is unavailable.
        if self._vector_unavailable:
            return

        try:
            # Try to reconnect to Qdrant
            if (
                not self.memory_backend
                and USE_QDRANT_BACKEND
                and QDRANT_BACKEND_AVAILABLE
            ):
                # 🔄 Qdrant patch - Use environment variables for configuration
                host = os.getenv("QDRANT_HOST", "localhost")  # 🔄 Qdrant patch
                port = int(os.getenv("QDRANT_PORT", "6333"))  # 🔄 Qdrant patch
                self.memory_backend = MemoryBackendFactory.create_backend(
                    "qdrant", host=host, port=port
                )

                if self.memory_backend.health_check():
                    log.info("✅ Qdrant connection restored!")
                    self.memory_backend.initialize()
                    self._attempt_fallback_sync()
                else:
                    self.memory_backend = None
        except Exception as e:
            log.debug(f"🔄 Qdrant still unavailable: {e}")
            self.memory_backend = None

    def is_fallback_mode(self) -> bool:
        """Check if memory manager is currently in fallback mode"""
        return self.fallback_store.is_fallback_mode

    def _store_in_fallback(self, memory: Dict[str, Any]):
        """Store memory in fallback cache with proper metadata"""
        # Preserve original memory type and confidence for later restoration
        fallback_memory = memory.copy()
        fallback_memory["metadata"] = fallback_memory.get("metadata", {})
        fallback_memory["metadata"]["original_memory_type"] = memory.get("memory_type")
        fallback_memory["metadata"]["original_confidence"] = memory.get(
            "confidence", 0.8
        )

        # Store in fallback
        fallback_id = self.fallback_store.store_fallback_memory(fallback_memory)

        # Log fallback storage
        log.warning(
            f"🔄 Memory stored in fallback cache due to Qdrant unavailability (ID: {fallback_id[:8]}...)"
        )

    def validate_metadata(self, entry: dict) -> dict:
        """
        Validate and normalize metadata fields, ensuring they have safe defaults.
        This prevents .lower() errors on None or missing fields.

        Args:
            entry: Memory entry dictionary

        Returns:
            dict: Validated entry with safe defaults for metadata fields
        """
        # Ensure essential metadata fields have safe defaults
        entry.setdefault("type", "external_import")
        entry.setdefault("source", "unknown")
        entry.setdefault("speaker", "unknown")

        # Defensively handle None values that could cause .lower() errors
        if entry.get("type") is None:
            entry["type"] = "external_import"
        if entry.get("source") is None:
            entry["source"] = "unknown"
        if entry.get("speaker") is None:
            entry["speaker"] = "unknown"

        return entry

    def load(self):
        try:
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.long_term_memory = data
                    else:
                        self.long_term_memory = data.get("memories", [])
        except Exception as e:
            log.error(f"Failed to load memory: {e}")
            self.long_term_memory = []

    def save(self):
        try:
            os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
            with open(MEMORY_FILE, "w") as f:
                json.dump(self.long_term_memory, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save memory: {e}")

    def __len__(self):
        return len(self.long_term_memory)

    def snapshot(self, limit: Optional[int] = None) -> list[dict]:
        if limit is None:
            return self.long_term_memory[:]
        return self.long_term_memory[-limit:]

    def store(self, entry: dict) -> str:
        # Validate and normalize metadata to prevent .lower() errors
        entry = self.validate_metadata(entry)

        # [SIMULATION_FIREWALL] Validate belief creation against simulation contamination
        if (
            entry.get("type") == "belief"
            or entry.get("memory_type") == "belief"
            or entry.get("isBelief", False)
            or "belief" in entry.get("tags", [])
        ):
            try:
                from simulation_belief_isolation_audit import validate_belief_creation

                validation_result = validate_belief_creation(entry)
                log.debug(f"🛡️ Belief creation validated: {validation_result['status']}")
            except Exception as e:
                log.error(
                    f"🚨 BLOCKED BELIEF CREATION - Simulation contamination detected: {e}"
                )
                # Convert to regular memory with simulation tags to preserve content for audit
                entry["type"] = "memory"
                entry["memory_type"] = "simulation"
                entry["tags"] = entry.get("tags", []) + [
                    "#blocked_belief_attempt",
                    "#simulation_firewall",
                ]
                entry["metadata"] = entry.get("metadata", {})
                entry["metadata"]["original_violation"] = str(e)
                entry["metadata"]["memoryType"] = "simulation"
                entry["confidence"] = 0.0  # Zero confidence
                log.info(
                    "🔄 Converted blocked belief to simulation memory for audit trail"
                )

        # [CLAIMS] Check if this is a claim and route appropriately
        if entry.get("type") == "claim":
            log.info(
                f"📋 Routing entry to claim store: {entry.get('content', '')[:50]}..."
            )
            try:
                from claims import route_to_claim_store

                return route_to_claim_store(entry)
            except Exception as e:
                log.warning(
                    f"Failed to route to claim store, storing as regular memory: {e}"
                )
                # Fall through to regular storage

        entry = tag_speaker_if_missing(entry)
        # Estimate importance if missing
        if "importance" not in entry or entry["importance"] is None:
            entry_length = len(entry.get("content", ""))
            entry["importance"] = DEFAULT_IMPORTANCE + min(entry_length / 1000, 0.4)

        # Enrich memory
        enriched = enrich_memory(entry)

        # Idempotency: compute canonical fingerprint and stable ID if absent
        try:
            fp = canonical_fingerprint(enriched)
            if not enriched.get("fingerprint"):
                enriched["fingerprint"] = fp
            if not enriched.get("id"):
                enriched["id"] = stable_point_id(enriched)
        except Exception as _e:
            # Non-fatal; proceed without idempotency features
            pass

        # [JUNK_DETECTION] Apply automatic junk detection and tagging
        try:
            from memory_response_pipeline import process_junk_memory

            content = enriched.get("content", "")
            enriched = process_junk_memory(content, enriched)
        except Exception as e:
            log.warning(f"Failed to apply junk detection: {e}")

        # Enhance with causal data if available
        try:
            from causal_reasoner import enhance_memory_with_causal_data

            enriched = enhance_memory_with_causal_data(enriched)
        except Exception as e:
            log.warning(f"Failed to enhance memory with causal data: {e}")

        # Check for duplicates by ID
        entry_id = enriched.get("id")
        if entry_id:
            for i, existing in enumerate(self.long_term_memory):
                if existing.get("id") == entry_id:
                    self.long_term_memory[i] = enriched
                    self.save()
                    return entry_id

        self.long_term_memory.append(enriched)

        # [QDRANT_BACKEND] Store in vector database if available, or fallback if not
        if self.memory_backend:
            try:
                # Attempt Qdrant storage with fallback detection
                memory_id = self._attempt_qdrant_operation(
                    self.memory_backend.store_memory, enriched
                )
                if memory_id:
                    log.info(f"🎯 Memory stored in Qdrant backend (ID: {memory_id})")
                else:
                    # Qdrant failed, store in fallback
                    self._store_in_fallback(enriched)
            except Exception as e:
                if self._detect_qdrant_failure(e):
                    log.warning(f"⚠️ Qdrant storage failed, using fallback: {e}")
                    self._store_in_fallback(enriched)
                else:
                    log.warning(f"⚠️ Failed to store memory in Qdrant backend: {e}")
        elif self.fallback_store.is_fallback_mode:
            # Already in fallback mode, store directly in fallback
            self._store_in_fallback(enriched)

            # Periodically check if Qdrant is back online
            self._periodic_qdrant_check()

            # Check for extended fallback mode
            self.fallback_store.check_long_fallback_mode()

        # [COGNITIVE_LOGGING] Log memory storage
        log_memory_stored(
            memory_id=enriched.get("id", "unknown"),
            content_preview=enriched.get("content", ""),
            memory_type=enriched.get("type"),
            importance=enriched.get("importance"),
            source="memory_manager",
        )

        self.save()
        # [OBSERVER] Non-blocking, env-gated JSON log to stdout
        try:
            from axiom.hooks.observer import observe

            observe(
                enriched.get("content", ""),
                kind="memory",
                meta={
                    "memory_id": enriched.get("id"),
                    "type": enriched.get("type"),
                    "importance": enriched.get("importance"),
                    "request_id": enriched.get("request_id"),
                },
            )
        except Exception:
            pass
        return entry.get("id", "unknown")

    def add_to_long_term(self, entry: dict):
        # [TRANSACTION_SUPPORT] Buffer memory operations during transactions
        if self.transaction_active:
            enriched_entry = enrich_memory(entry)
            enriched_entry = tag_speaker_if_missing(enriched_entry)
            self.transaction_buffer.append(enriched_entry)
            log.debug(
                f"🔄 Memory buffered in transaction {self.transaction_id}: {enriched_entry.get('id', 'unknown')}"
            )
        else:
            self.store(entry)

    def all_ids(self) -> list[str]:
        return [m.get("id", "") for m in self.long_term_memory if m.get("id")]

    def get(self, mem_id: str) -> dict | None:
        result = next((m for m in self.long_term_memory if m.get("id") == mem_id), None)

        # [COGNITIVE_LOGGING] Log memory retrieval
        if result:
            log_memory_retrieved(
                memory_id=mem_id,
                query=f"get_by_id:{mem_id}",
                relevance=1.0,  # Direct ID lookup has 100% relevance
                source="memory_manager",
            )

        return result

    def get_goals(self) -> list[dict]:
        return [m for m in self.long_term_memory if m.get("type") == "goal"]

    def add_goal(self, goal: Goal):
        self.store(goal.to_dict())

    def scored_goals(self, relevance_threshold: float = 0.5) -> list[dict]:
        return [
            g
            for g in self.get_goals()
            if g.get("importance", 0.0) >= relevance_threshold
        ]

    def find_beliefs_by_tag(self, tag: str) -> list[dict]:
        return [
            b
            for b in self.long_term_memory
            if b.get("type") == "belief" and tag in b.get("tags", [])
        ]

    def find_beliefs_by_type(self, belief_type: str) -> list[dict]:
        return [
            b
            for b in self.long_term_memory
            if b.get("type") == "belief" and b.get("belief_type") == belief_type
        ]

    def get_high_importance_beliefs(self, min_importance: float = 0.8) -> list[dict]:
        return [
            b
            for b in self.long_term_memory
            if b.get("type") == "belief" and b.get("importance", 0.0) >= min_importance
        ]

    def get_decayed_beliefs(
        self, min_confidence: float = 0.3, max_confidence: float = 0.7
    ) -> list[dict]:
        return [
            b
            for b in self.long_term_memory
            if b.get("type") == "belief"
            and min_confidence <= b.get("confidence", 1.0) <= max_confidence
        ]

    def decay(self, rate: float = 0.01):
        for entry in self.long_term_memory:
            old = entry.get("importance", 1.0)
            entry["importance"] = round(max(0.0, old - rate), 4)
        log.info("🧪 Applied semantic decay to memory.")
        self.save()

    def prune(self, threshold: float = 0.2):
        before = len(self.long_term_memory)
        self.long_term_memory = [
            m for m in self.long_term_memory if m.get("importance", 1.0) > threshold
        ]
        after = len(self.long_term_memory)
        if after < before:
            log.info(f"🧹 Pruned {before - after} low-importance memory entries.")
            self.save()

    def get_memories_by_type(self, memory_type: MemoryType) -> list[dict]:
        """Get all memories of a specific hierarchical type"""
        return [
            mem
            for mem in self.long_term_memory
            if mem.get("memory_type") == memory_type.value
        ]

    def get_memories_by_types(self, memory_types: list[MemoryType]) -> list[dict]:
        """Get all memories matching any of the specified types"""
        type_values = [mt.value for mt in memory_types]
        return [
            mem
            for mem in self.long_term_memory
            if mem.get("memory_type") in type_values
        ]

    def promote_memory(self, memory_id: str) -> dict | None:
        """Promote a memory to a higher hierarchical level if applicable"""
        memory = self.get(memory_id)
        if not memory:
            return None

        new_type = memory_type_manager.should_promote_memory(memory)
        if new_type:
            old_type = memory.get("memory_type")
            memory["memory_type"] = new_type.value

            # Update importance based on new type
            memory["importance"] = max(
                memory.get("importance", 0.5),
                memory_type_manager.get_default_importance(new_type),
            )

            self.save()
            return {
                "memory_id": memory_id,
                "promoted_from": old_type,
                "promoted_to": new_type.value,
                "new_importance": memory["importance"],
            }

        return None

    def decay_by_type(self, memory_type: MemoryType, rate: float = None):
        """Apply decay to memories of a specific type using type-specific decay rates"""
        if rate is None:
            characteristics = get_storage_characteristics(memory_type)
            rate = characteristics.get("decay_rate", 0.01)

        # Ensure rate is a float
        if not isinstance(rate, (int, float)):
            rate = 0.01

        memories = self.get_memories_by_type(memory_type)
        for mem in memories:
            current_importance = mem.get("importance", 0.5)
            days_old = days_since(mem.get("timestamp", ""))

            # Apply exponential decay
            new_importance = current_importance * exp(-rate * days_old)
            mem["importance"] = max(new_importance, 0.01)  # Minimum threshold

        self.save()
        return len(memories)


def decay_beliefs(self):
    updated = 0
    expired_flagged = 0
    now_iso = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    for entry in self.long_term_memory:
        if not is_belief(entry) or is_protected(entry):
            continue

        # [TEMPORAL] Check if belief has expired (if temporal reasoning is available)
        if TEMPORAL_AVAILABLE and is_expired(entry):
            # Flag as expired but don't delete
            temporal_tags = entry.get("temporal_tags", [])
            if "expired" not in temporal_tags:
                temporal_tags.append("expired")
                entry["temporal_tags"] = temporal_tags
                entry["updated_at"] = now_iso
                expired_flagged += 1
            continue

        # [TEMPORAL] Skip decay if belief is not currently valid (if temporal reasoning is available)
        if TEMPORAL_AVAILABLE and not is_valid_now(entry):
            continue

        prev_conf = parse_confidence(entry)
        created_str = parse_created(entry)
        try:
            created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except Exception:
            created_dt = datetime.now(timezone.utc)

        age = datetime.now(timezone.utc) - created_dt
        new_conf = decay_score(prev_conf, age)

        if new_conf < prev_conf:
            entry["confidence"] = new_conf
            entry["updated_at"] = now_iso
            updated += 1

    if TEMPORAL_AVAILABLE and expired_flagged > 0:
        log.info(
            f"🧠 Decayed {updated} belief confidence values, flagged {expired_flagged} as expired."
        )
    else:
        log.info(f"🧠 Decayed {updated} belief confidence values.")

    if updated or expired_flagged:
        self.save()


Memory.decay_beliefs = decay_beliefs


# [TRANSACTION_SUPPORT] Add transaction methods to Memory class
def begin_transaction(self, transaction_id: str):
    """Begin a transaction for atomic memory operations"""
    if self.transaction_active:
        raise RuntimeError(f"Transaction already active: {self.transaction_id}")

    self.transaction_active = True
    self.transaction_id = transaction_id
    self.transaction_buffer = []

    # Create snapshot for rollback (shallow copy of current state)
    self.transaction_snapshot = {
        "long_term_memory": self.long_term_memory.copy(),
        "fallback_store_state": (
            self.fallback_store.get_state_snapshot()
            if hasattr(self.fallback_store, "get_state_snapshot")
            else {}
        ),
    }

    log.info(f"🔄 Memory transaction {transaction_id} started")


def commit_transaction(self, transaction_id: str):
    """Commit all buffered memory operations"""
    if not self.transaction_active:
        raise RuntimeError("No active transaction to commit")

    if self.transaction_id != transaction_id:
        raise RuntimeError(
            f"Transaction ID mismatch: expected {self.transaction_id}, got {transaction_id}"
        )

    try:
        # Apply all buffered operations
        for buffered_memory in self.transaction_buffer:
            self._commit_memory_operation(buffered_memory)

        # Clear transaction state
        self._clear_transaction_state()

        log.info(
            f"✅ Memory transaction {transaction_id} committed with {len(self.transaction_buffer)} operations"
        )

    except Exception as e:
        log.error(f"❌ Failed to commit memory transaction {transaction_id}: {e}")
        raise


def rollback_transaction(self, transaction_id: str):
    """Rollback transaction and restore previous state"""
    if not self.transaction_active:
        log.warning(
            f"⚠️ Attempted rollback on inactive memory transaction {transaction_id}"
        )
        return

    if self.transaction_id != transaction_id:
        log.warning(
            f"⚠️ Transaction ID mismatch during rollback: expected {self.transaction_id}, got {transaction_id}"
        )

    try:
        # Restore from snapshot
        if self.transaction_snapshot:
            self.long_term_memory = self.transaction_snapshot["long_term_memory"]

            # Restore fallback store state if available
            if hasattr(self.fallback_store, "restore_from_snapshot"):
                self.fallback_store.restore_from_snapshot(
                    self.transaction_snapshot["fallback_store_state"]
                )

        # Clear transaction state
        self._clear_transaction_state()

        log.info(f"🔄 Memory transaction {transaction_id} rolled back")

    except Exception as e:
        log.error(f"❌ Failed to rollback memory transaction {transaction_id}: {e}")
        raise


def get_transaction_state(self) -> Dict[str, Any]:
    """Get current transaction state for external snapshot"""
    return {
        "transaction_active": self.transaction_active,
        "transaction_id": self.transaction_id,
        "buffered_count": (
            len(self.transaction_buffer) if self.transaction_buffer else 0
        ),
        "long_term_memory_count": len(self.long_term_memory),
    }


def restore_from_snapshot(self, snapshot_state: Dict[str, Any]):
    """Restore memory state from external snapshot"""
    try:
        if "long_term_memory" in snapshot_state:
            self.long_term_memory = snapshot_state["long_term_memory"]

        log.info("🔄 Memory state restored from external snapshot")

    except Exception as e:
        log.error(f"❌ Failed to restore memory from snapshot: {e}")
        raise


def _commit_memory_operation(self, memory_entry: dict):
    """Actually commit a memory operation to storage"""
    # This would normally call the original add_to_long_term logic
    # For now, just add to long_term_memory
    self.long_term_memory.append(memory_entry)

    # Also try to store in Qdrant if available
    if self.memory_backend:
        try:
            self.memory_backend.store_memory(memory_entry)
        except Exception as e:
            log.warning(f"⚠️ Failed to store committed memory in Qdrant: {e}")


def _clear_transaction_state(self):
    """Clear all transaction state"""
    self.transaction_active = False
    self.transaction_id = None
    self.transaction_buffer = []
    self.transaction_snapshot = None


# Attach transaction methods to Memory class
Memory.begin_transaction = begin_transaction
Memory.commit_transaction = commit_transaction
Memory.rollback_transaction = rollback_transaction
Memory.get_transaction_state = get_transaction_state
Memory.restore_from_snapshot = restore_from_snapshot
Memory._commit_memory_operation = _commit_memory_operation
Memory._clear_transaction_state = _clear_transaction_state

# ─────────────────────────────────────────────
# MemoryManager Implementation
# ─────────────────────────────────────────────


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
                # Best-effort dynamic usage of Qdrant backend
                if QdrantMemoryBackend is not None:
                    from os import getenv  # 🔄 Qdrant patch
                    url = getenv("QDRANT_URL")  # 🔄 Qdrant patch
                    # Embedding defaults
                    model_name = embedding_model_name()
                    dim = embedding_dim()
                    try:
                        log_embedding_banner("MemoryManager")
                    except Exception:
                        pass
                    self._backend = QdrantMemoryBackend(  # 🔄 Qdrant patch
                        url=url,  # 🔄 Qdrant patch
                        embedding_model=model_name,
                        vector_size=dim,
                        **kwargs
                    )  # kwargs for host/port/etc if the app passes them
                    log.info("✅ MemoryManager: Qdrant backend initialized")
                else:
                    log.warning(
                        "Vector sync requested but Qdrant backend not available; using fallback."
                    )
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

        # Idempotency: derive fingerprint and stable id unless explicitly provided
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
                elif hasattr(self._backend, "store_memory"):
                    getattr(self._backend, "store_memory")(rec)
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

    # Public attribute access for tests and callers expecting `.backend`
    @property
    def backend(self):  # type: ignore[override]
        return self._backend


# Fallback: If main implementation can't load due to dependencies,
# ensure MemoryManager is available from minimal implementation
try:
    # Test if our main implementation is working
    _test_mm = MemoryManager(vector_sync=False)
    _test_mm.close()
except Exception as e:
    # Main implementation failed, import from minimal
    log.warning(f"Main MemoryManager failed, using minimal implementation: {e}")
    try:
        from .memory_manager_minimal import MemoryManager as MinimalMemoryManager

        MemoryManager = MinimalMemoryManager
        log.info("✅ Using minimal MemoryManager implementation")
    except ImportError:
        log.error("❌ Both main and minimal MemoryManager implementations failed")
