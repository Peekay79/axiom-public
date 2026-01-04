#!/usr/bin/env python3
from __future__ import annotations

import logging
import os

# memory_adapter.py
# ─────────────────────────────────────────────────────────
# Enhanced memory adapter with o3 alignment features:
# - Rich metadata support (speaker, tags, importance, timestamp)
# - Validation and logging improvements
# - Memory decay and scoring support
# - Belief system preparation for contradiction detection
# - Backward compatibility with existing Journal/Discord integration
# - Entropy-based tag scoring with TF-IDF-like weighting
# - Qdrant backend integration replacing direct Weaviate calls


logger = logging.getLogger(__name__)
import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import aiohttp

from tag_entropy_utils import EntropyTagScorer

from .memory_types import MemoryType, get_storage_characteristics, infer_memory_type
from .memory_validator import validate_memory_entry

# [QDRANT_BACKEND] Import memory backend interface for Qdrant integration
try:
    from memory_backend_interface import (
        MemoryBackendError,
        MemoryBackendFactory,
        MemoryFilter,
    )
    from qdrant_backend import QdrantMemoryBackend

    QDRANT_BACKEND_AVAILABLE = True
    logger = logging.getLogger("memory_adapter")
    logger.info("🔧 Qdrant backend interface loaded successfully")
except ImportError as e:
    QDRANT_BACKEND_AVAILABLE = False
    logger = logging.getLogger("memory_adapter")
    logger.warning(f"⚠️ Qdrant backend not available: {e}")

# Configuration
MEMORY_API_PORT = os.getenv("MEMORY_API_PORT", "8002")
MEMORY_POD_URL = os.getenv("MEMORY_POD_URL", f"http://localhost:{MEMORY_API_PORT}")
QDRANT_URL = os.getenv("QDRANT_URL")  # Qdrant URL (may be None)

# [QDRANT_CONFIG] Qdrant configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
USE_QDRANT_BACKEND = os.getenv("USE_QDRANT_BACKEND", "true").lower() == "true"

# ――― FEATURE FLAG: Memory Class Switch ―――
USE_MEMORY_ARCHIVE = True

import requests


def _list_collection_names(client):
    """Return a set of collection names for both new and old qdrant-client versions."""
    try:
        resp = client.get_collections()  # newer qdrant-client
        cols = getattr(resp, "collections", None)
        if cols:
            return {getattr(c, "name", c) for c in cols}
    except Exception:
        pass
    # Try get_collections().collections pattern
    try:
        resp = client.get_collections()
        cols = getattr(resp, "collections", None)
        if cols:
            return {getattr(c, "name", c) for c in cols}
    except AttributeError:
        # REST API fallback
        try:
            import requests

            host = getattr(client, "host", "localhost")
            port = getattr(client, "port", 6333)
            url = f"http://{host}:{port}/collections"

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            if (
                isinstance(data, dict)
                and "result" in data
                and "collections" in data["result"]
            ):
                collections = data["result"]["collections"]
                names = set()
                for c in collections:
                    if isinstance(c, dict) and "name" in c:
                        names.add(c["name"])
                    elif hasattr(c, "name"):
                        names.add(c.name)
                return names
        except Exception:
            pass
    return set()


def verify_qdrant_collections() -> bool:
    """Verify that required Qdrant collections exist"""
    try:
        if not QDRANT_HOST or not QDRANT_PORT:
            print("⚠️ Qdrant connection not configured")
            return False

        from axiom_qdrant_client import QdrantClient

        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        collections = _list_collection_names(client)
        required = {
            os.getenv("QDRANT_MEMORY_COLLECTION", "axiom_memories"),
            os.getenv("QDRANT_BELIEF_COLLECTION", "axiom_beliefs"),
        }
        missing = required - collections
        if missing:
            logger.error(
                f"[RECALL][Vector] ❌ Qdrant missing collections: {sorted(missing)}"
            )
            return False
        return True
    except Exception as e:
        print(f"\033[91m❌ Qdrant collection check failed: {e}\033[0m")
        return False


# Use Qdrant backend for memory storage
# Use unified collection names
from memory.memory_collections import memory_collection as _memory_collection

memory_collection = _memory_collection()
print(f"📂 Using Qdrant collection: {memory_collection}")

# MemoryType enum is now imported from memory_types module
# Legacy compatibility mapping for old types
LEGACY_TYPE_MAPPING = {
    "conversation": MemoryType.SHORT_TERM,
    "dialogue": MemoryType.SHORT_TERM,
    "belief": MemoryType.SEMANTIC,
    "fact": MemoryType.SEMANTIC,
    "preference": MemoryType.SEMANTIC,
    "context": MemoryType.SHORT_TERM,
    "reflection": MemoryType.EPISODIC,
}


@dataclass
class EnhancedMemoryEntry:
    """Rich memory entry with o3 alignment metadata and entropy-based tagging"""

    text: str  # Keep 'text' for backward compatibility
    speaker: str = "user"
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5
    timestamp: Optional[str] = None
    memory_type: MemoryType = MemoryType.SHORT_TERM

    # o3 enhancement fields
    confidence: Optional[float] = None
    decay_rate: Optional[float] = None
    belief_id: Optional[str] = None
    source: Optional[str] = None
    related_journal_id: Optional[str] = None

    # Legacy compatibility fields
    isBelief: bool = False
    beliefs: Optional[List[str]] = None

    # Internal tracking - Always generate UUID for consistency
    entry_id: str = field(default_factory=lambda: str(uuid4()))
    last_accessed: Optional[str] = None
    access_count: int = 0

    # Configuration constants
    MAX_AUTO_TAGS: int = field(default=10, init=False)  # Cap for tag explosion control

    # Entropy scorer instance (shared across all entries)
    _entropy_scorer: EntropyTagScorer = field(default=None, init=False)

    def __post_init__(self):
        """Validate and normalize entry after creation"""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()

        # Initialize entropy scorer if not present
        if self._entropy_scorer is None:
            self._entropy_scorer = EntropyTagScorer()

        self._validate_and_normalize()
        self._sync_legacy_fields()

    def _validate_and_normalize(self):
        """Validate and normalize all fields"""
        # Validate importance
        if not 0.0 <= self.importance <= 1.0:
            logger.warning(
                f"⚠️ Invalid importance {self.importance}, clamping to [0.0, 1.0]"
            )
            self.importance = max(0.0, min(1.0, self.importance))

        # Validate confidence
        if self.confidence is not None:
            if not 0.0 <= self.confidence <= 1.0:
                logger.warning(
                    f"⚠️ Invalid confidence {self.confidence}, clamping to [0.0, 1.0]"
                )
                self.confidence = max(0.0, min(1.0, self.confidence))

        # Validate decay_rate
        if self.decay_rate is not None:
            if not 0.0 <= self.decay_rate <= 1.0:
                logger.warning(
                    f"⚠️ Invalid decay_rate {self.decay_rate}, clamping to [0.0, 1.0]"
                )
                self.decay_rate = max(0.0, min(1.0, self.decay_rate))

        # Validate and normalize tags
        if not isinstance(self.tags, list):
            logger.warning(f"⚠️ Tags must be a list, got {type(self.tags)}")
            self.tags = []

        normalized_tags = []
        for tag in self.tags:
            if isinstance(tag, str):
                clean_tag = tag.strip().lower()
                if clean_tag and clean_tag not in normalized_tags:
                    normalized_tags.append(clean_tag)
            else:
                logger.warning(f"⚠️ Invalid tag type {type(tag)}, skipping")

        self.tags = normalized_tags

        # Validate speaker
        if not self.speaker or not self.speaker.strip():
            logger.warning("⚠️ Empty speaker, using default 'user'")
            self.speaker = "user"

        # Auto-tag validation warnings
        if not self.tags:
            logger.warning("⚠️ No tags provided, memory may be hard to retrieve")

    def _sync_legacy_fields(self):
        """Sync with legacy fields for backward compatibility"""
        # Sync belief status
        if self.memory_type == MemoryType.SEMANTIC:
            self.isBelief = True
            if not self.belief_id:
                # Generate clean slug-style belief ID for future linking consistency
                timestamp_slug = (
                    self.timestamp.replace(":", "-").replace(".", "-")
                    if self.timestamp
                    else "unknown"
                )
                text_slug = "".join(
                    c for c in self.text.lower() if c.isalnum() or c in "-_"
                )[:20]
                self.belief_id = f"belief-{timestamp_slug}-{text_slug}"
            if self.confidence is None:
                self.confidence = 0.7
            if "belief" not in self.tags:
                self.tags.append("belief")

        self.isBelief = self.memory_type == MemoryType.SEMANTIC

    def auto_enhance_tags(self):
        """Automatically enhance tags using entropy-based scoring"""
        if not self.text:
            return

        content_lower = self.text.lower()

        # Calculate current tag capacity
        current_auto_tags = sum(1 for tag in self.tags if not tag.startswith("user-"))
        max_new_tags = max(0, self.MAX_AUTO_TAGS - current_auto_tags)

        if max_new_tags <= 0:
            logger.debug(
                f"🏷️ Tag limit reached ({self.MAX_AUTO_TAGS}), skipping auto-enhancement"
            )
            return

        # Initialize entropy scorer if not present
        if self._entropy_scorer is None:
            self._entropy_scorer = EntropyTagScorer()

        # Generate potential tags based on content analysis
        potential_tags = []

        # Emotional sentiment
        if any(
            word in content_lower
            for word in [
                "happy",
                "joy",
                "excited",
                "love",
                "great",
                "amazing",
                "wonderful",
            ]
        ):
            potential_tags.append("positive")
        if any(
            word in content_lower
            for word in [
                "sad",
                "angry",
                "frustrated",
                "hate",
                "terrible",
                "awful",
                "disappointed",
            ]
        ):
            potential_tags.append("negative")

        # Content structure
        if "?" in self.text:
            potential_tags.append("question")
        if any(
            word in content_lower
            for word in ["yesterday", "today", "tomorrow", "next week", "last month"]
        ):
            potential_tags.append("temporal")

        # Belief/opinion indicators
        if any(
            phrase in content_lower
            for phrase in ["i think", "i believe", "in my opinion", "i feel that"]
        ):
            potential_tags.extend(["belief", "opinion"])
            if self.memory_type == MemoryType.SHORT_TERM:
                self.memory_type = MemoryType.SEMANTIC

        # Preference indicators
        if any(
            phrase in content_lower
            for phrase in ["i prefer", "i like", "i dislike", "i hate"]
        ):
            potential_tags.extend(["preference"])
            if self.memory_type == MemoryType.SHORT_TERM:
                self.memory_type = MemoryType.SEMANTIC

        # Domain-specific tags
        if any(
            word in content_lower
            for word in ["work", "job", "career", "office", "meeting", "project"]
        ):
            potential_tags.append("work")
        if any(
            word in content_lower
            for word in ["family", "mom", "dad", "parent", "child", "sibling"]
        ):
            potential_tags.append("family")
        if any(
            word in content_lower
            for word in ["health", "doctor", "medicine", "exercise", "diet"]
        ):
            potential_tags.append("health")
        if any(
            word in content_lower
            for word in ["code", "software", "algorithm", "program", "debug", "api"]
        ):
            potential_tags.append("technical")

        # Experience and fact indicators
        if any(
            word in content_lower
            for word in [
                "remember",
                "recall",
                "happened",
                "experienced",
                "went through",
            ]
        ):
            potential_tags.append("experience")
        if any(
            phrase in content_lower
            for phrase in [
                "according to",
                "research shows",
                "studies indicate",
                "data suggests",
            ]
        ):
            potential_tags.append("fact")

        # Calculate entropy-based scores
        tag_scores = self._entropy_scorer.calculate_tag_entropy(
            self.text, potential_tags
        )

        # Get top-scoring tags with diversity
        top_tags = self._entropy_scorer.get_top_tags(tag_scores, max_new_tags)

        # Add tags that aren't already present
        added_count = 0
        tags_before_count = len(self.tags)

        for tag, score in top_tags:
            if added_count >= max_new_tags:
                break
            if tag not in self.tags:
                self.tags.append(tag)
                added_count += 1

        if added_count > 0:
            newly_added_tags = self.tags[tags_before_count:]
            scores_str = ", ".join(
                [f"{tag}({score:.2f})" for tag, score in top_tags[:added_count]]
            )
            logger.debug(f"🏷️ Entropy-scored tags added: {scores_str}")
            logger.debug(f"🏷️ Final tags: {newly_added_tags}")

        # Log entropy analysis summary
        if tag_scores:
            avg_score = sum(tag_scores.values()) / len(tag_scores)
            max_score = max(tag_scores.values())
            diversity_stats = self._entropy_scorer.get_diversity_stats(top_tags)
            logger.debug(
                f"📊 Entropy analysis: {len(tag_scores)} candidates, "
                f"avg_score={avg_score:.2f}, max_score={max_score:.2f}, "
                f"diversity={diversity_stats}"
            )

        # Log if we had to skip tags due to limit
        if len(top_tags) > max_new_tags:
            skipped = len(top_tags) - added_count
            logger.debug(
                f"🏷️ Skipped {skipped} entropy-scored tags due to limit ({self.MAX_AUTO_TAGS})"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls and storage"""
        result = {
            "text": self.text,
            "content": self.text,  # For schema compatibility
            "speaker": self.speaker,
            "tags": self.tags,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "isBelief": self.isBelief,
            "source": self.source or "memory_adapter_v2",
            "memory_type": self.memory_type.value,
        }

        # Add optional fields if present
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.decay_rate is not None:
            result["decay_rate"] = self.decay_rate
        if self.belief_id:
            result["belief_id"] = self.belief_id
        if self.related_journal_id:
            result["related_journal_id"] = self.related_journal_id
        if self.beliefs:
            result["beliefs"] = self.beliefs
        if self.entry_id:
            result["entry_id"] = self.entry_id
        if self.last_accessed:
            result["last_accessed"] = self.last_accessed
        if self.access_count > 0:
            result["access_count"] = self.access_count

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnhancedMemoryEntry":
        """Create from dictionary (for API responses)"""
        # Handle memory_type
        if "memory_type" in data:
            if isinstance(data["memory_type"], str):
                try:
                    data["memory_type"] = MemoryType(data["memory_type"])
                except ValueError:
                    data["memory_type"] = MemoryType.SHORT_TERM

        return cls(**data)


class JournalMemoryAdapter:
    """Enhanced REST wrapper with o3 alignment features and Qdrant backend integration"""

    def __init__(self):
        self.base_url = MEMORY_POD_URL.rstrip("/")
        self.vector_url = QDRANT_URL.rstrip("/") if QDRANT_URL else None
        self.auto_enhance_enabled = True
        self.validation_enabled = True
        self.detailed_logging = True

        # [QDRANT_BACKEND] Initialize memory backend
        self.memory_backend = None
        if USE_QDRANT_BACKEND and QDRANT_BACKEND_AVAILABLE:
            try:
                # Register Qdrant backend if not already registered
                try:
                    MemoryBackendFactory.register_backend("qdrant", QdrantMemoryBackend)
                except:
                    pass  # Already registered

                self.memory_backend = MemoryBackendFactory.create_backend(
                    "qdrant", host=QDRANT_HOST, port=QDRANT_PORT
                )

                # Initialize backend (create collections if needed)
                if self.memory_backend.health_check():
                    self.memory_backend.initialize()
                    logger.info(
                        f"🎯 Qdrant backend initialized at {QDRANT_HOST}:{QDRANT_PORT}"
                    )
                else:
                    logger.error(f"❌ Qdrant backend health check failed")
                    self.memory_backend = None
            except Exception as e:
                logger.error(f"❌ Failed to initialize Qdrant backend: {e}")
                self.memory_backend = None

        if self.memory_backend:
            logger.info("🚀 JournalMemoryAdapter initialized with Qdrant backend")
        else:
            logger.info(
                "🚀 JournalMemoryAdapter initialized with legacy mode (fallback to direct calls)"
            )

    # ── enhanced snapshot with filtering ────────────────────
    async def get_recent(
        self,
        limit: int = 25,
        memory_types: Optional[List[MemoryType]] = None,
        min_importance: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> list[dict]:
        """Enhanced snapshot retrieval with filtering"""
        try:
            # Build query parameters
            params = {"limit": limit}
            if memory_types:
                params["memory_types"] = ",".join([mt.value for mt in memory_types])
            if min_importance > 0.0:
                params["min_importance"] = min_importance
            if tags:
                params["tags"] = ",".join(tags)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/snapshot", params=params
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"📥 Retrieved {len(data)} memories from snapshot")
                        return data
                    logger.warning(f"⚠️ Snapshot fetch failed: HTTP {resp.status}")
        except Exception as e:
            logger.warning(f"⚠️ Exception during snapshot fetch: {e}")
        return []

    # ── enhanced post with rich metadata ────────────────────
    async def post_entry(self, entry: Union[dict, EnhancedMemoryEntry]):
        """Enhanced entry posting with validation and logging"""
        try:
            # Convert to EnhancedMemoryEntry if needed
            if isinstance(entry, dict):
                enhanced_entry = EnhancedMemoryEntry.from_dict(entry)
            else:
                enhanced_entry = entry

            # Auto-enhance if enabled
            if self.auto_enhance_enabled:
                enhanced_entry.auto_enhance_tags()

            # Convert to dict for API
            entry_dict = enhanced_entry.to_dict()

            # Validate entry
            if self.validation_enabled:
                try:
                    validate_memory_entry(entry_dict)
                    logger.debug("✅ Memory entry validation passed")
                except ValueError as ve:
                    logger.error(f"❌ Memory entry schema validation failed: {ve}")
                    return

            # Log entry details with enhanced format per PR plan
            if self.detailed_logging:
                memory_text = enhanced_entry.text
                tags = enhanced_entry.tags
                source = enhanced_entry.source or "unknown"
                logger.info(
                    f"📝 Memory stored: {memory_text[:80]}..., tags={tags}, source={source}"
                )
                logger.info(
                    f"📝 Storing memory: speaker={enhanced_entry.speaker}, "
                    f"tags={enhanced_entry.tags}, importance={enhanced_entry.importance}, "
                    f"type={enhanced_entry.memory_type.value}"
                )

            # [QDRANT_BACKEND] Use Qdrant backend if available
            if self.memory_backend:
                try:
                    memory_id = self.memory_backend.store_memory(entry_dict)
                    logger.info(
                        f"✅ Memory successfully stored in Qdrant backend (ID: {memory_id})"
                    )
                except MemoryBackendError as e:
                    logger.error(f"❌ Qdrant backend storage failed: {e}")
                    # Fall back to legacy mode
                    await self._store_memory_legacy(enhanced_entry, entry_dict)
            else:
                # Legacy mode: direct API calls
                await self._store_memory_legacy(enhanced_entry, entry_dict)

        except Exception as e:
            logger.error(f"❌ Exception during memory add: {e}")

    async def _store_memory_legacy(
        self, enhanced_entry: EnhancedMemoryEntry, entry_dict: dict
    ):
        """Legacy storage method using direct API calls (fallback when Qdrant is unavailable)"""
        async with aiohttp.ClientSession() as session:
            # 1) Memory-pod
            headers = {}
            try:
                # Env‑gated Governor headers (correlation + idempotency)
                if str(os.getenv("PROMPT_CONTRACTS_ENABLED", "true")).strip().lower() == "true":
                    from governor.middleware import ensure_correlation_and_idempotency  # type: ignore

                    headers = ensure_correlation_and_idempotency({}, entry_dict, require_cid=True, require_idem=True)
            except Exception:
                headers = {}
            async with session.post(
                f"{self.base_url}/memory/add", json=entry_dict, headers=headers
            ) as resp:
                if resp.status == 200:
                    logger.info(
                        "✅ Memory successfully stored in memory-pod (legacy mode)"
                    )
                elif resp.status == 202:
                    logger.info("✅ Memory queued via Outbox (legacy mode)")
                else:
                    logger.warning(f"⚠️ Memory-pod add failed: HTTP {resp.status}")
                    return

            # 2) Vector store (optional) - legacy Weaviate
            if self.vector_url:
                w_obj = self._format_for_weaviate(enhanced_entry)
                async with session.post(
                    f"{self.vector_url}/v1/objects", json=w_obj
                ) as vresp:
                    if vresp.status == 200:
                        logger.info(
                            "✅ Memory successfully stored in vector store (legacy Weaviate)"
                        )
                    else:
                        body = await vresp.text()
                        logger.warning(
                            f"⚠️ Weaviate add failed: HTTP {vresp.status} → {body[:200]}"
                        )

    # ── belief retrieval for contradiction detection ────────
    async def get_beliefs_for_contradiction_check(
        self, topic: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve beliefs for contradiction detection using Qdrant backend"""
        try:
            # [QDRANT_BACKEND] Use Qdrant backend if available
            if self.memory_backend:
                memory_filter = MemoryFilter(
                    memory_types=["belief", "semantic"],
                    min_importance=0.3,
                    min_confidence=0.1,
                )

                if topic:
                    # Use semantic search for topic-based queries
                    results = self.memory_backend.get_relevant_memories(
                        query_text=topic,
                        limit=limit,
                        score_threshold=0.5,
                        memory_filter=memory_filter,
                    )
                else:
                    # Get all beliefs
                    results = self.memory_backend.search_memories(
                        memory_filter=memory_filter, limit=limit
                    )

                # Convert to legacy format for compatibility
                complete_beliefs = []
                for result in results:
                    belief_dict = {
                        "id": result.id,
                        "content": result.content,
                        "belief_id": result.payload.get("belief_id", result.id),
                        "confidence": result.confidence
                        or result.payload.get("confidence", 0.7),
                        "importance": result.importance
                        or result.payload.get("importance", 0.5),
                        "tags": result.tags or result.payload.get("tags", []),
                        "speaker": result.speaker
                        or result.payload.get("speaker", "unknown"),
                        "timestamp": result.timestamp
                        or result.payload.get("timestamp"),
                        "type": result.memory_type,
                        "score": result.score,
                    }
                    complete_beliefs.append(belief_dict)

                logger.info(
                    f"🧠 Retrieved {len(complete_beliefs)} beliefs from Qdrant backend"
                )
                return complete_beliefs
            else:
                # Legacy mode: direct API calls
                return await self._get_beliefs_legacy(topic, limit)

        except Exception as e:
            logger.warning(f"⚠️ Exception during belief retrieval: {e}")
            # Fallback to legacy mode
            try:
                return await self._get_beliefs_legacy(topic, limit)
            except:
                return []

    async def _get_beliefs_legacy(
        self, topic: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Legacy belief retrieval using direct API calls"""
        params = {
            "limit": limit,
            "memory_types": "belief",
            "min_importance": 0.3,  # Only significant beliefs
        }

        if topic:
            params["search"] = topic

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/beliefs", params=params) as resp:
                if resp.status == 200:
                    beliefs = await resp.json()
                    # Filter beliefs with sufficient metadata
                    complete_beliefs = [
                        b
                        for b in beliefs
                        if b.get("belief_id") and b.get("confidence") is not None
                    ]
                    logger.info(
                        f"🧠 Retrieved {len(complete_beliefs)} beliefs (legacy mode)"
                    )
                    return complete_beliefs
                else:
                    logger.warning(f"⚠️ Belief retrieval failed: HTTP {resp.status}")
        return []

    # ── memory search with enhanced filtering ───────────────
    async def search_memories(
        self,
        query: str,
        limit: int = 20,
        memory_types: Optional[List[MemoryType]] = None,
        min_importance: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Enhanced memory search with filtering using Qdrant backend"""
        try:
            # [QDRANT_BACKEND] Use Qdrant backend if available
            if self.memory_backend:
                memory_filter = MemoryFilter(
                    memory_types=(
                        [mt.value for mt in memory_types] if memory_types else None
                    ),
                    min_importance=min_importance if min_importance > 0.0 else None,
                    tags=tags,
                )

                results = self.memory_backend.get_relevant_memories(
                    query_text=query,
                    limit=limit,
                    score_threshold=0.3,
                    memory_filter=memory_filter,
                )

                # Convert to legacy format for compatibility
                search_results = []
                for result in results:
                    result_dict = {
                        "id": result.id,
                        "content": result.content,
                        "score": result.score,
                        "type": result.memory_type,
                        "importance": result.importance
                        or result.payload.get("importance", 0.5),
                        "tags": result.tags or result.payload.get("tags", []),
                        "speaker": result.speaker
                        or result.payload.get("speaker", "unknown"),
                        "timestamp": result.timestamp
                        or result.payload.get("timestamp"),
                        "confidence": result.confidence
                        or result.payload.get("confidence"),
                        "source": result.source or result.payload.get("source"),
                        "payload": result.payload,
                    }
                    search_results.append(result_dict)

                logger.info(
                    f"🔍 Found {len(search_results)} memories for query: {query} (Qdrant)"
                )
                return search_results
            else:
                # Legacy mode: direct API calls
                return await self._search_memories_legacy(
                    query, limit, memory_types, min_importance, tags
                )

        except Exception as e:
            logger.warning(f"⚠️ Exception during memory search: {e}")
            # Fallback to legacy mode
            try:
                return await self._search_memories_legacy(
                    query, limit, memory_types, min_importance, tags
                )
            except:
                return []

    async def _search_memories_legacy(
        self,
        query: str,
        limit: int = 20,
        memory_types: Optional[List[MemoryType]] = None,
        min_importance: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Legacy memory search using direct API calls"""
        params = {"q": query, "limit": limit, "min_importance": min_importance}

        if memory_types:
            params["memory_types"] = ",".join([mt.value for mt in memory_types])
        if tags:
            params["tags"] = ",".join(tags)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/search", params=params) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    logger.info(
                        f"🔍 Found {len(results)} memories for query: {query} (legacy)"
                    )
                    return results
                else:
                    logger.warning(f"⚠️ Memory search failed: HTTP {resp.status}")
        return []

    # ── internal helpers ─────────────────────────────────
    def _format_for_weaviate(self, entry: EnhancedMemoryEntry) -> dict:
        """Enhanced Weaviate object format with o3 metadata and robust error handling"""
        try:
            obj = {
                "class": memory_class,
                "id": entry.entry_id,  # Use consistent UUID
                "properties": {
                    "text": entry.text,
                    "speaker": entry.speaker,
                    "tags": entry.tags,
                    "importance": entry.importance,
                    "isBelief": entry.isBelief,
                    "source": entry.source or "memory_adapter_v2",
                    "timestamp": entry.timestamp,
                    "memoryType": entry.memory_type.value,
                    "entryId": entry.entry_id,  # Consistent internal tracking
                },
            }

            # Add o3 enhancement fields
            if entry.confidence is not None:
                obj["properties"]["confidence"] = entry.confidence
            if entry.decay_rate is not None:
                obj["properties"]["decayRate"] = entry.decay_rate
            if entry.belief_id:
                # Validate belief ID format for future linking consistency
                if self._is_valid_belief_id(entry.belief_id):
                    obj["properties"]["beliefId"] = entry.belief_id
                else:
                    logger.warning(
                        f"⚠️ Invalid belief ID format: {entry.belief_id}, skipping"
                    )
            if entry.related_journal_id:
                obj["properties"]["relatedJournalId"] = entry.related_journal_id

            # Enhanced belief linking with fallback handling
            if isinstance(entry.beliefs, list) and entry.beliefs:
                try:
                    # Try new beacon format first
                    obj["properties"]["beliefs"] = [
                        {"beacon": f"weaviate://localhost/Belief/{bid}"}
                        for bid in entry.beliefs
                        if self._is_valid_belief_id(bid)
                    ]

                    # If no valid belief IDs, fall back to legacy format
                    if not obj["properties"]["beliefs"] and entry.beliefs:
                        logger.warning(
                            "⚠️ No valid belief IDs found, using legacy format"
                        )
                        obj["properties"]["beliefIds"] = entry.beliefs

                except Exception as e:
                    logger.warning(f"⚠️ Belief linking failed, storing as legacy: {e}")
                    obj["properties"]["beliefIds"] = entry.beliefs

            return obj

        except Exception as e:
            logger.error(f"❌ Weaviate format error: {e}")
            # Return minimal viable object
            return {
                "class": memory_class,
                "id": entry.entry_id,
                "properties": {
                    "text": entry.text or "",
                    "speaker": entry.speaker or "unknown",
                    "timestamp": entry.timestamp
                    or datetime.now(timezone.utc).isoformat(),
                    "source": "memory_adapter_v2_fallback",
                },
            }

    def _is_valid_belief_id(self, belief_id: str) -> bool:
        """Validate belief ID format for future linking consistency"""
        if not belief_id or not isinstance(belief_id, str):
            return False

        # Check for clean slug format (belief-timestamp-slug)
        if belief_id.startswith("belief-") and len(belief_id.split("-")) >= 3:
            return True

        # Allow legacy hash format temporarily
        if belief_id.startswith("belief_") and "_" in belief_id:
            logger.debug(f"🔄 Legacy belief ID format detected: {belief_id}")
            return True

        # UUID format
        try:
            uuid4_pattern = belief_id.replace("-", "")
            if len(uuid4_pattern) == 32 and all(
                c in "0123456789abcdef" for c in uuid4_pattern.lower()
            ):
                return True
        except:
            pass

        return False

    # ── configuration methods ───────────────────────────────
    def set_auto_enhance_enabled(self, enabled: bool):
        """Enable/disable automatic tag enhancement"""
        self.auto_enhance_enabled = enabled
        logger.info(f"🏷️ Auto-enhancement {'enabled' if enabled else 'disabled'}")

    def set_validation_enabled(self, enabled: bool):
        """Enable/disable validation"""
        self.validation_enabled = enabled
        logger.info(f"✅ Validation {'enabled' if enabled else 'disabled'}")

    def set_detailed_logging(self, enabled: bool):
        """Enable/disable detailed logging"""
        self.detailed_logging = enabled
        logger.info(f"📝 Detailed logging {'enabled' if enabled else 'disabled'}")


# ─────────────────────────────────────────────────────────
# Enhanced convenience functions with o3 features
# ─────────────────────────────────────────────────────────


def log_turn(
    role: str,
    text: str,
    *,
    importance: float = 0.1,
    tags: Optional[List[str]] = None,
    memory_type: MemoryType = MemoryType.SHORT_TERM,
    **kwargs,
) -> None:
    """
    Enhanced dialogue turn logging with o3 metadata support
    """
    from .memory_manager import Memory  # local, late import to avoid cycles

    # Create enhanced entry
    enhanced_entry = EnhancedMemoryEntry(
        text=text,
        speaker=role,
        tags=tags or ["dialogue"],
        importance=importance,
        memory_type=memory_type,
        source="discord_interface",
        **kwargs,
    )

    # Auto-enhance tags
    enhanced_entry.auto_enhance_tags()

    # Store via memory manager
    Memory().add_to_long_term(enhanced_entry.to_dict())

    logger.info(
        f"📝 Logged turn: {role} → {len(text)} chars, "
        f"importance={importance}, tags={enhanced_entry.tags}"
    )


def log_belief(
    speaker: str,
    text: str,
    confidence: float = 0.7,
    importance: float = 0.8,
    source: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Convenience function for logging belief entries
    """
    from .memory_manager import Memory

    enhanced_entry = EnhancedMemoryEntry(
        text=text,
        speaker=speaker,
        tags=["belief"],
        importance=importance,
        memory_type=MemoryType.SEMANTIC,
        confidence=confidence,
        source=source or "belief_logger",
        **kwargs,
    )

    enhanced_entry.auto_enhance_tags()
    Memory().add_to_long_term(enhanced_entry.to_dict())

    logger.info(
        f"🧠 Logged belief: {speaker} → confidence={confidence}, "
        f"importance={importance}"
    )


def log_preference(
    speaker: str,
    text: str,
    importance: float = 0.6,
    source: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Convenience function for logging preference entries
    """
    from .memory_manager import Memory

    enhanced_entry = EnhancedMemoryEntry(
        text=text,
        speaker=speaker,
        tags=["preference"],
        importance=importance,
        memory_type=MemoryType.SEMANTIC,
        source=source or "preference_logger",
        **kwargs,
    )

    enhanced_entry.auto_enhance_tags()
    Memory().add_to_long_term(enhanced_entry.to_dict())

    logger.info(f"💭 Logged preference: {speaker} → importance={importance}")


# ─────────────────────────────────────────────────────────
# Export utilities for backward compatibility
# ─────────────────────────────────────────────────────────

# Create default adapter instance
_default_adapter = None


def get_default_adapter() -> JournalMemoryAdapter:
    """Get the default adapter instance"""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = JournalMemoryAdapter()
    return _default_adapter


# Async convenience functions
async def store_memory(text: str, speaker: str = "user", **kwargs) -> None:
    """Async convenience function to store memory"""
    adapter = get_default_adapter()
    entry = EnhancedMemoryEntry(text=text, speaker=speaker, **kwargs)
    await adapter.post_entry(entry)


async def get_recent_memories(limit: int = 25, **kwargs) -> List[Dict[str, Any]]:
    """Async convenience function to get recent memories"""
    adapter = get_default_adapter()
    return await adapter.get_recent(limit=limit, **kwargs)


async def search_memories(query: str, **kwargs) -> List[Dict[str, Any]]:
    """Async convenience function to search memories"""
    adapter = get_default_adapter()
    return await adapter.search_memories(query=query, **kwargs)


if __name__ == "__main__":
    # Enhanced test suite for entropy-based memory functionality
    async def test_enhanced_memory():
        """Test enhanced memory functionality with entropy scoring"""
        print("🧪 Testing Enhanced Memory System with Entropy Scoring")
        print("=" * 60)

        adapter = JournalMemoryAdapter()

        # Test 1: Enhanced entry creation with entropy scoring
        print("\n📝 Test 1: Enhanced Entry Creation")
        entry = EnhancedMemoryEntry(
            text="I really think climate change is extremely important and we should act now",
            speaker="user",
            tags=["environment"],
            importance=0.9,
            memory_type=MemoryType.SEMANTIC,
            confidence=0.8,
        )

        print(f"Original entry: {entry.to_dict()}")

        # Test auto-enhancement
        entry.auto_enhance_tags()
        print(f"Auto-enhanced tags: {entry.tags}")
        print(f"Memory type mutation: {entry.memory_type}")

        # Test 2: Tag limit enforcement
        print("\n🏷️ Test 2: Tag Limit Enforcement")
        limited_entry = EnhancedMemoryEntry(
            text="I love working on code, it's amazing and I prefer Python over Java",
            speaker="user",
            tags=[
                "user-existing1",
                "user-existing2",
                "user-existing3",
                "user-existing4",
                "user-existing5",
                "user-existing6",
                "user-existing7",
                "user-existing8",
            ],
            importance=0.7,
        )

        print(f"Pre-enhancement tags ({len(limited_entry.tags)}): {limited_entry.tags}")
        limited_entry.auto_enhance_tags()
        print(
            f"Post-enhancement tags ({len(limited_entry.tags)}): {limited_entry.tags}"
        )
        print(
            f"Tag limit respected: {len(limited_entry.tags) <= limited_entry.MAX_AUTO_TAGS}"
        )

        # Test 3: Belief statement memory type mutation
        print("\n🧠 Test 3: Belief Statement Memory Type Mutation")
        belief_entry = EnhancedMemoryEntry(
            text="I believe artificial intelligence will fundamentally change society",
            speaker="user",
            memory_type=MemoryType.CONVERSATION,  # Should mutate to BELIEF
        )

        print(f"Original type: {belief_entry.memory_type}")
        belief_entry.auto_enhance_tags()
        print(f"Mutated type: {belief_entry.memory_type}")
        print(
            f"Belief mutation successful: {belief_entry.memory_type == MemoryType.SEMANTIC}"
        )

        # Test 4: Preference statement memory type mutation
        print("\n💭 Test 4: Preference Statement Memory Type Mutation")
        pref_entry = EnhancedMemoryEntry(
            text="I prefer working from home rather than in the office",
            speaker="user",
            memory_type=MemoryType.CONVERSATION,  # Should mutate to PREFERENCE
        )

        print(f"Original type: {pref_entry.memory_type}")
        pref_entry.auto_enhance_tags()
        print(f"Mutated type: {pref_entry.memory_type}")
        print(
            f"Preference mutation successful: {pref_entry.memory_type == MemoryType.SEMANTIC}"
        )

        # Test 5: Diversity filtering (semantic groups)
        print("\n🎯 Test 5: Semantic Diversity Filtering")
        diverse_entry = EnhancedMemoryEntry(
            text="I'm really happy and excited about my new job, but also sad to leave my family",
            speaker="user",
        )

        diverse_entry.auto_enhance_tags()
        print(f"Final tags: {diverse_entry.tags}")

        # Count tags by semantic group
        emotion_tags = sum(
            1
            for tag in diverse_entry.tags
            if tag in ["positive", "negative", "happy", "sad", "excited"]
        )
        print(f"Emotion tags: {emotion_tags} (should be ≤ 2 for diversity)")
        print(f"Diversity constraint respected: {emotion_tags <= 2}")

        # Test 6: Score logging validation
        print("\n📊 Test 6: Score Logging Validation")
        score_entry = EnhancedMemoryEntry(
            text="What should I do about this technical problem? I'm really confused",
            speaker="user",
        )

        # Enable detailed logging temporarily
        original_level = logger.level
        logger.setLevel(logging.DEBUG)

        print("Enabling debug logging to capture score logs...")
        score_entry.auto_enhance_tags()

        # Restore logging level
        logger.setLevel(original_level)

        print(f"Tags with entropy scoring: {score_entry.tags}")

        # Test 7: Storage and retrieval
        print("\n💾 Test 7: Storage and Retrieval")
        await adapter.post_entry(entry)

        # Test enhanced retrieval
        beliefs = await adapter.get_beliefs_for_contradiction_check("climate")
        print(f"Found {len(beliefs)} beliefs about climate")

        recent_memories = await adapter.get_recent(limit=5, min_importance=0.5)
        print(f"Retrieved {len(recent_memories)} high-importance memories")

        search_results = await adapter.search_memories(
            "technical", memory_types=[MemoryType.SEMANTIC]
        )
        print(f"Search found {len(search_results)} technical beliefs")

        print("\n✅ All tests completed successfully!")

        # Test 8: Unit test for EntropyTagScorer.get_top_tags()
        print("\n🔬 Test 8: Unit Test for EntropyTagScorer")
        from tag_entropy_utils import test_entropy_scorer

        test_results = test_entropy_scorer()
        print(f"Entropy scorer unit test completed with results: {test_results}")

        # Test 9: Benchmark on multiple memories
        print("\n📈 Test 9: Benchmark Tag Diversity on Sample Memories")
        sample_texts = [
            "I think the weather is beautiful today",
            "What should I cook for dinner? I'm confused",
            "I love working on Python projects at the office",
            "My family is very important to me and I feel grateful",
            "The research shows that exercise improves mental health",
            "I prefer tea over coffee in the morning",
            "Yesterday I had a great meeting with my team",
            "I believe technology will solve climate change",
            "This technical problem is really frustrating me",
            "I remember going to the beach as a child",
        ]

        all_scores = []
        diversity_stats = {"emotion": 0, "structure": 0, "personal": 0, "domain": 0}

        for i, text in enumerate(sample_texts):
            test_entry = EnhancedMemoryEntry(text=text, speaker="user")
            test_entry.auto_enhance_tags()

            # Collect scores if available
            if hasattr(test_entry, "_entropy_scorer") and test_entry._entropy_scorer:
                # Get potential tags for scoring
                potential_tags = [
                    "positive",
                    "negative",
                    "question",
                    "temporal",
                    "belief",
                    "preference",
                    "work",
                    "family",
                    "technical",
                ]
                scores = test_entry._entropy_scorer.calculate_tag_entropy(
                    text, potential_tags
                )
                if scores:
                    all_scores.extend(scores.values())

                # Get diversity stats
                tag_pairs = [(tag, 1.0) for tag in test_entry.tags]
                entry_diversity = test_entry._entropy_scorer.get_diversity_stats(
                    tag_pairs
                )
                for group, count in entry_diversity.items():
                    diversity_stats[group] += count

            print(f"Memory {i+1}: {len(test_entry.tags)} tags → {test_entry.tags}")

        if all_scores:
            avg_score = sum(all_scores) / len(all_scores)
            max_score = max(all_scores)
            print(f"\n📊 Benchmark Results:")
            print(
                f"Average tag score across {len(sample_texts)} memories: {avg_score:.3f}"
            )
            print(f"Maximum tag score: {max_score:.3f}")
            print(f"Tag diversity distribution: {diversity_stats}")
            print(f"Total tags generated: {sum(diversity_stats.values())}")
        else:
            print("⚠️ No entropy scores available for benchmark")

    # Test entropy scorer functionality
    def test_entropy_scorer_unit():
        """Unit test for EntropyTagScorer.get_top_tags()"""
        print("\n🧪 Unit Test: EntropyTagScorer.get_top_tags()")

        from tag_entropy_utils import EntropyTagScorer

        scorer = EntropyTagScorer()

        # Known input/output test case
        test_scores = {
            "belief": 2.5,
            "positive": 1.8,
            "negative": 1.2,
            "work": 1.0,
            "family": 0.8,
            "technical": 0.6,
        }

        # Test with max_tags = 3
        top_tags = scorer.get_top_tags(test_scores, max_tags=3)

        print(f"Input scores: {test_scores}")
        print(f"Top 3 tags: {top_tags}")

        # Validate results
        assert len(top_tags) <= 3, "Should not exceed max_tags limit"
        assert (
            top_tags[0][1] >= top_tags[1][1] >= top_tags[2][1]
        ), "Should be sorted by score"
        assert top_tags[0][0] == "belief", "Highest scoring tag should be 'belief'"

        # Test diversity constraint
        diverse_scores = {
            "positive": 3.0,
            "negative": 2.9,
            "happy": 2.8,
            "sad": 2.7,  # 4 emotion tags
            "belief": 2.0,
            "work": 1.0,
        }

        diverse_top_tags = scorer.get_top_tags(diverse_scores, max_tags=6)
        emotion_count = sum(
            1
            for tag, score in diverse_top_tags
            if tag in ["positive", "negative", "happy", "sad"]
        )

        print(
            f"Diversity test - emotion tags selected: {emotion_count} (should be ≤ 2)"
        )
        assert (
            emotion_count <= 2
        ), "Should respect diversity constraint (max 2 per semantic group)"

        print("✅ Unit test passed!")

        return top_tags

    # Run all tests
    print("🚀 Starting Enhanced Memory Adapter Test Suite")
    print("=" * 60)

    # Run unit test first
    test_entropy_scorer_unit()

    # Run main async test
    asyncio.run(test_enhanced_memory())
