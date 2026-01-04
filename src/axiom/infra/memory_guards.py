#!/usr/bin/env python3
"""
memory_guards.py - Memory resource exhaustion guards for Axiom MemoryManager

This module adds resource monitoring and backpressure mechanisms to the
MemoryManager to prevent memory exhaustion and maintain system stability.
"""

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import (
    MEMORY_CACHE_SIZE_LIMIT_MB,
    MEMORY_LIMIT_DEFAULT,
    MemoryOverloadException,
    infra_logger,
)


@dataclass
class MemoryUsageStats:
    """Statistics about memory usage"""

    in_ram_count: int = 0
    fallback_cache_size_mb: float = 0.0
    total_memories: int = 0
    last_update: Optional[datetime] = None
    is_stressed: bool = False
    backpressure_active: bool = False


class MemoryResourceGuard:
    """
    Resource monitoring and protection for MemoryManager.

    Features:
    - Monitor in-RAM memory count and fallback cache size
    - Trigger soft backpressure when limits are exceeded
    - Archive least recent memories to disk
    - Provide stress indicators to other components
    """

    def __init__(
        self,
        memory_limit: int = MEMORY_LIMIT_DEFAULT,
        cache_size_limit_mb: float = MEMORY_CACHE_SIZE_LIMIT_MB,
        check_interval: int = 30,
    ):
        """
        Initialize memory resource guard.

        Args:
            memory_limit: Maximum number of in-RAM memories
            cache_size_limit_mb: Maximum fallback cache size in MB
            check_interval: Seconds between usage checks
        """
        self.memory_limit = memory_limit
        self.cache_size_limit_mb = cache_size_limit_mb
        self.check_interval = check_interval

        # State tracking
        self.stats = MemoryUsageStats()
        self.lock = threading.Lock()
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Backpressure configuration
        self.backpressure_threshold = 0.9  # 90% of limit triggers backpressure
        self.archive_threshold = 0.95  # 95% triggers archiving
        self.warning_threshold = 0.8  # 80% triggers warnings

        # Archive configuration
        self.archive_db_path = "data/memory_archive.db"
        self.archive_batch_size = 100

        # Usage tracking
        self.last_warning_time = None
        self.warning_interval = 300  # 5 minutes between warnings

        infra_logger.info(
            f"🛡️ Memory resource guard initialized (limit: {memory_limit}, cache: {cache_size_limit_mb}MB)"
        )

        # Initialize archive database
        self._init_archive_db()

    def _init_archive_db(self):
        """Initialize SQLite database for memory archiving"""
        try:
            os.makedirs(os.path.dirname(self.archive_db_path), exist_ok=True)

            with sqlite3.connect(self.archive_db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS archived_memories (
                        id TEXT PRIMARY KEY,
                        content TEXT,
                        timestamp TEXT,
                        source TEXT,
                        memory_type TEXT,
                        importance REAL,
                        tags TEXT,
                        metadata TEXT,
                        archived_at TEXT,
                        archive_reason TEXT
                    )
                """
                )
                conn.commit()

            infra_logger.info(
                f"📁 Memory archive database initialized: {self.archive_db_path}"
            )

        except Exception as e:
            infra_logger.error(f"❌ Failed to initialize memory archive database: {e}")

    def check_memory_usage(self, memory_manager) -> MemoryUsageStats:
        """
        Check current memory usage and update statistics.

        Args:
            memory_manager: The Memory instance to monitor

        Returns:
            Updated MemoryUsageStats
        """
        with self.lock:
            try:
                # Count in-RAM memories
                in_ram_count = (
                    len(memory_manager.long_term_memory)
                    if hasattr(memory_manager, "long_term_memory")
                    else 0
                )

                # Check fallback cache size
                fallback_size_mb = 0.0
                if hasattr(memory_manager, "fallback_store"):
                    fallback_size_mb = self._get_fallback_cache_size(
                        memory_manager.fallback_store
                    )

                # Calculate stress indicators
                memory_usage_ratio = (
                    in_ram_count / self.memory_limit if self.memory_limit > 0 else 0
                )
                cache_usage_ratio = (
                    fallback_size_mb / self.cache_size_limit_mb
                    if self.cache_size_limit_mb > 0
                    else 0
                )

                is_stressed = (
                    memory_usage_ratio > self.warning_threshold
                    or cache_usage_ratio > self.warning_threshold
                )

                backpressure_active = (
                    memory_usage_ratio > self.backpressure_threshold
                    or cache_usage_ratio > self.backpressure_threshold
                )

                # Update stats
                self.stats = MemoryUsageStats(
                    in_ram_count=in_ram_count,
                    fallback_cache_size_mb=fallback_size_mb,
                    total_memories=in_ram_count,  # Could include archived count if needed
                    last_update=datetime.now(timezone.utc),
                    is_stressed=is_stressed,
                    backpressure_active=backpressure_active,
                )

                # Generate warnings if needed
                if is_stressed and self._should_send_warning():
                    self._send_memory_warning(memory_usage_ratio, cache_usage_ratio)

                # Trigger archiving if critically high
                if (
                    memory_usage_ratio > self.archive_threshold
                    or cache_usage_ratio > self.archive_threshold
                ):
                    self._trigger_memory_archiving(memory_manager)

                infra_logger.debug(
                    f"🛡️ Memory usage: {in_ram_count}/{self.memory_limit} memories, "
                    f"{fallback_size_mb:.1f}MB cache, stressed: {is_stressed}"
                )

                return self.stats

            except Exception as e:
                infra_logger.error(f"❌ Failed to check memory usage: {e}")
                return self.stats

    def _get_fallback_cache_size(self, fallback_store) -> float:
        """Get size of fallback cache in MB"""
        try:
            if hasattr(fallback_store, "fallback_db_path"):
                db_path = fallback_store.fallback_db_path
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    return size_bytes / (1024 * 1024)  # Convert to MB
            return 0.0
        except Exception as e:
            infra_logger.debug(f"Could not get fallback cache size: {e}")
            return 0.0

    def _should_send_warning(self) -> bool:
        """Check if enough time has passed since last warning"""
        if not self.last_warning_time:
            return True

        time_since_warning = time.time() - self.last_warning_time
        return time_since_warning >= self.warning_interval

    def _send_memory_warning(self, memory_ratio: float, cache_ratio: float):
        """Send memory usage warning"""
        self.last_warning_time = time.time()

        warning_msg = (
            f"⚠️ MEMORY USAGE WARNING: "
            f"RAM: {memory_ratio:.1%} ({self.stats.in_ram_count}/{self.memory_limit}), "
            f"Cache: {cache_ratio:.1%} ({self.stats.fallback_cache_size_mb:.1f}MB/{self.cache_size_limit_mb}MB)"
        )

        if self.stats.backpressure_active:
            warning_msg += " - BACKPRESSURE ACTIVE"

        infra_logger.warning(warning_msg)

    def _trigger_memory_archiving(self, memory_manager):
        """Archive least recent memories to free up space"""
        try:
            if not hasattr(memory_manager, "long_term_memory"):
                return

            memories = memory_manager.long_term_memory
            if (
                len(memories) <= self.memory_limit * 0.8
            ):  # Don't archive if we're close to reasonable levels
                return

            # Sort by timestamp (oldest first) and importance (lowest first)
            memories_to_archive = sorted(
                memories,
                key=lambda m: (m.get("timestamp", ""), m.get("importance", 1.0)),
            )[: self.archive_batch_size]

            archived_count = 0
            for memory in memories_to_archive:
                if self._archive_memory(memory):
                    # Remove from in-memory storage
                    if memory in memory_manager.long_term_memory:
                        memory_manager.long_term_memory.remove(memory)
                    archived_count += 1

            if archived_count > 0:
                infra_logger.info(
                    f"📁 Archived {archived_count} memories to free up space"
                )
                # Save updated memory state
                if hasattr(memory_manager, "save"):
                    memory_manager.save()

        except Exception as e:
            infra_logger.error(f"❌ Failed to archive memories: {e}")

    def _archive_memory(self, memory: Dict[str, Any]) -> bool:
        """Archive a single memory to SQLite database"""
        try:
            with sqlite3.connect(self.archive_db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO archived_memories 
                    (id, content, timestamp, source, memory_type, importance, tags, metadata, archived_at, archive_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        memory.get("id", ""),
                        memory.get("content", ""),
                        memory.get("timestamp", ""),
                        memory.get("source", ""),
                        memory.get("memory_type", ""),
                        memory.get("importance", 0.0),
                        str(memory.get("tags", [])),
                        str(memory.get("metadata", {})),
                        datetime.now(timezone.utc).isoformat(),
                        "resource_pressure",
                    ),
                )
                conn.commit()
            return True

        except Exception as e:
            infra_logger.error(
                f"❌ Failed to archive memory {memory.get('id', 'unknown')}: {e}"
            )
            return False

    def is_memory_stressed(self) -> bool:
        """Check if memory system is currently under stress"""
        return self.stats.is_stressed

    def is_backpressure_active(self) -> bool:
        """Check if backpressure is currently active"""
        return self.stats.backpressure_active

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current memory usage statistics"""
        with self.lock:
            return {
                "in_ram_count": self.stats.in_ram_count,
                "memory_limit": self.memory_limit,
                "memory_usage_pct": (
                    round((self.stats.in_ram_count / self.memory_limit) * 100, 1)
                    if self.memory_limit > 0
                    else 0
                ),
                "fallback_cache_size_mb": self.stats.fallback_cache_size_mb,
                "cache_limit_mb": self.cache_size_limit_mb,
                "cache_usage_pct": (
                    round(
                        (self.stats.fallback_cache_size_mb / self.cache_size_limit_mb)
                        * 100,
                        1,
                    )
                    if self.cache_size_limit_mb > 0
                    else 0
                ),
                "is_stressed": self.stats.is_stressed,
                "backpressure_active": self.stats.backpressure_active,
                "last_update": (
                    self.stats.last_update.isoformat()
                    if self.stats.last_update
                    else None
                ),
                "warning_threshold": self.warning_threshold,
                "backpressure_threshold": self.backpressure_threshold,
                "archive_threshold": self.archive_threshold,
            }

    def enforce_limits(self, memory_manager) -> bool:
        """
        Enforce memory limits and apply backpressure if needed.

        Args:
            memory_manager: The Memory instance to check

        Returns:
            True if operation should proceed, False if backpressure should be applied

        Raises:
            MemoryOverloadException: If memory is severely overloaded
        """
        stats = self.check_memory_usage(memory_manager)

        # Check for severe overload (hard limit)
        if stats.in_ram_count > self.memory_limit * 1.1:  # 110% of limit
            raise MemoryOverloadException(
                f"Memory severely overloaded: {stats.in_ram_count}/{self.memory_limit} memories. "
                "Cannot store new memories until space is freed."
            )

        # Apply soft backpressure
        if stats.backpressure_active:
            infra_logger.warning(
                f"🛡️ Memory backpressure active: {stats.in_ram_count}/{self.memory_limit} memories, "
                f"{stats.fallback_cache_size_mb:.1f}MB cache"
            )
            # Don't block, but signal that backpressure is active
            return False

        return True

    def start_monitoring(self, memory_manager):
        """Start background memory monitoring"""
        if self.monitoring:
            infra_logger.warning("🛡️ Memory monitoring already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, args=(memory_manager,), daemon=True
        )
        self.monitor_thread.start()
        infra_logger.info(
            f"🛡️ Started memory usage monitoring (interval: {self.check_interval}s)"
        )

    def stop_monitoring(self):
        """Stop background memory monitoring"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        infra_logger.info("🛡️ Stopped memory usage monitoring")

    def _monitoring_loop(self, memory_manager):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                self.check_memory_usage(memory_manager)
                time.sleep(self.check_interval)
            except Exception as e:
                infra_logger.error(f"❌ Memory monitoring error: {e}")
                time.sleep(self.check_interval)

    def get_archived_memories(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve archived memories from database"""
        try:
            with sqlite3.connect(self.archive_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM archived_memories 
                    ORDER BY archived_at DESC 
                    LIMIT ?
                """,
                    (limit,),
                )

                memories = []
                for row in cursor.fetchall():
                    memory = dict(row)
                    # Parse JSON fields
                    try:
                        memory["tags"] = eval(memory["tags"]) if memory["tags"] else []
                        memory["metadata"] = (
                            eval(memory["metadata"]) if memory["metadata"] else {}
                        )
                    except:
                        pass
                    memories.append(memory)

                return memories

        except Exception as e:
            infra_logger.error(f"❌ Failed to retrieve archived memories: {e}")
            return []


# Integration functions for existing MemoryManager


def create_memory_guard(memory_manager, **kwargs) -> MemoryResourceGuard:
    """
    Create and attach a memory resource guard to a MemoryManager instance.

    Args:
        memory_manager: The Memory instance to protect
        **kwargs: Configuration options for the guard

    Returns:
        MemoryResourceGuard instance
    """
    guard = MemoryResourceGuard(**kwargs)

    # Attach guard to memory manager
    memory_manager._resource_guard = guard

    # Start monitoring
    guard.start_monitoring(memory_manager)

    return guard


def check_memory_limits(memory_manager) -> bool:
    """
    Check if memory manager is within safe limits.

    Args:
        memory_manager: The Memory instance to check

    Returns:
        True if within limits, False if backpressure should be applied

    Raises:
        MemoryOverloadException: If severely overloaded
    """
    if not hasattr(memory_manager, "_resource_guard"):
        # Create guard if it doesn't exist
        create_memory_guard(memory_manager)

    return memory_manager._resource_guard.enforce_limits(memory_manager)


def get_memory_usage_stats(memory_manager) -> Dict[str, Any]:
    """Get current memory usage statistics"""
    if not hasattr(memory_manager, "_resource_guard"):
        create_memory_guard(memory_manager)

    return memory_manager._resource_guard.get_usage_stats()


def is_memory_stressed(memory_manager) -> bool:
    """Check if memory system is under stress"""
    if not hasattr(memory_manager, "_resource_guard"):
        create_memory_guard(memory_manager)

    return memory_manager._resource_guard.is_memory_stressed()
