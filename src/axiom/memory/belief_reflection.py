#!/usr/bin/env python3
"""
belief_reflection.py - Belief Metabolism reflection and extraction pipeline

This module implements the main belief extraction pipeline:
- Memory sampling from the pod API
- Belief candidate detection and scoring
- Deduplication against existing beliefs
- Shadow mode and actual ingestion
- Comprehensive logging and error handling

The system is designed to be safe by default with shadow mode enabled.
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Optional imports with graceful fallbacks
try:
    from urllib.parse import urljoin

    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

    # Provide minimal fallbacks
    def urljoin(base, url):
        return f"{base.rstrip('/')}/{url.lstrip('/')}"


try:
    from dotenv import load_dotenv

    load_dotenv(".env.vector", override=False)
    load_dotenv(".env", override=False)
except ImportError:
    pass

# Import our belief utilities
from .belief_utils import (
    BELIEF_MIN_SCORE,
    build_belief,
    is_belief_candidate,
    jsonlog,
    score_belief_strength,
    stable_belief_id,
)

# Configuration (public-safe defaults)
# NOTE: Production deployments should set these explicitly via environment variables.
MEMORY_POD_URL = os.getenv("MEMORY_POD_URL", "http://localhost:8002")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# Feature flags
BELIEF_EXTRACT_ENABLED = os.getenv("BELIEF_EXTRACT_ENABLED", "false").lower() == "true"
BELIEF_EXTRACT_SHADOW = os.getenv("BELIEF_EXTRACT_SHADOW", "true").lower() == "true"
BELIEF_SAMPLING_ON_BOOT = (
    os.getenv("BELIEF_SAMPLING_ON_BOOT", "false").lower() == "true"
)
BELIEF_SAMPLING_IDLE = os.getenv("BELIEF_SAMPLING_IDLE", "false").lower() == "true"

# Pipeline parameters
BELIEF_SAMPLE_SIZE = int(os.getenv("BELIEF_SAMPLE_SIZE", "100"))
BELIEF_BATCH_SIZE = int(os.getenv("BELIEF_BATCH_SIZE", "50"))
BELIEF_MAX_RUNTIME_SEC = int(os.getenv("BELIEF_MAX_RUNTIME_SEC", "60"))
BELIEF_BOOT_DELAY_SEC = int(os.getenv("BELIEF_BOOT_DELAY_SEC", "7"))

# Lock file for single-host concurrency control
LOCK_FILE = "/tmp/belief_reflection.lock"

logger = logging.getLogger(__name__)


class BeliefReflectionError(Exception):
    """Base exception for belief reflection operations."""

    pass


class BeliefReflectionSession:
    """
    Manages a belief reflection session with health checks, sampling, and extraction.
    """

    def __init__(self, dry_run: bool = False, limit: Optional[int] = None):
        self.dry_run = dry_run
        self.limit = limit or BELIEF_SAMPLE_SIZE
        self.session = None  # Initialize later to allow testing
        self.stats = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "memories_sampled": 0,
            "candidates_found": 0,
            "beliefs_accepted": 0,
            "beliefs_deduped": 0,
            "beliefs_posted": 0,
            "errors": 0,
            "total_runtime_ms": 0,
        }

    def _create_session(self):
        """Create a requests session with timeouts and retries."""
        if not _REQUESTS_AVAILABLE:
            raise BeliefReflectionError("requests library not available")

        session = requests.Session()

        # Configure retries with exponential backoff
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set timeouts (connect, read)
        session.timeout = (3, 20)

        return session

    def _ensure_session(self):
        """Ensure session is initialized."""
        if self.session is None:
            self.session = self._create_session()

    def health_check(self) -> bool:
        """
        Perform health checks on required services.

        Returns:
            True if all services are healthy, False otherwise
        """
        try:
            self._ensure_session()
            # Check Memory Pod
            memory_health_url = urljoin(MEMORY_POD_URL, "/health")
            resp = self.session.get(memory_health_url, timeout=(3, 10))
            if resp.status_code != 200:
                logger.error(f"Memory pod health check failed: {resp.status_code}")
                return False

            # Check Qdrant
            qdrant_collections_url = urljoin(QDRANT_URL, "/collections")
            resp = self.session.get(qdrant_collections_url, timeout=(3, 10))
            if resp.status_code != 200:
                logger.error(f"Qdrant health check failed: {resp.status_code}")
                return False

            logger.info("Health checks passed")
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def sample_memories(self) -> List[Dict[str, Any]]:
        """
        Sample memories from the memory pod API using paged access.

        Returns:
            List of sampled memory objects
        """
        memories = []
        page_size = min(50, self.limit)  # Reasonable page size
        total_fetched = 0

        try:
            self._ensure_session()
            # Use paged API if available, otherwise implement fallback
            memories_url = urljoin(MEMORY_POD_URL, "/memories")

            page = 0
            while total_fetched < self.limit:
                remaining = self.limit - total_fetched
                current_page_size = min(page_size, remaining)

                params = {
                    "page": page,
                    "limit": current_page_size,
                    "include_content": "true",
                }

                resp = self.session.get(memories_url, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        f"Failed to fetch memories page {page}: {resp.status_code}"
                    )
                    break

                data = resp.json()
                page_memories = data.get("memories", [])

                if not page_memories:
                    logger.info(f"No more memories available at page {page}")
                    break

                memories.extend(page_memories)
                total_fetched += len(page_memories)

                logger.debug(f"Fetched page {page}: {len(page_memories)} memories")
                page += 1

                # Avoid infinite loops
                if page > 100:
                    logger.warning("Too many pages, stopping sampling")
                    break

            # Implement reservoir sampling if we got more than needed
            if len(memories) > self.limit:
                import random

                memories = random.sample(memories, self.limit)

            self.stats["memories_sampled"] = len(memories)
            logger.info(f"Sampled {len(memories)} memories")

            return memories

        except Exception as e:
            logger.error(f"Memory sampling failed: {e}")
            self.stats["errors"] += 1
            return []

    def extract_beliefs(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract belief candidates from sampled memories.

        Args:
            memories: List of memory objects

        Returns:
            List of extracted belief objects
        """
        beliefs = []

        for memory in memories:
            start_time = time.time()

            try:
                # Check if memory is a belief candidate
                if not is_belief_candidate(memory):
                    reason = "not_belief_candidate"
                    jsonlog(
                        {
                            "decision": "skip",
                            "reason": reason,
                            "score": 0.0,
                            "id": memory.get("id", "unknown"),
                            "source_memory": memory.get("id", "unknown"),
                            "elapsed_ms": int((time.time() - start_time) * 1000),
                        }
                    )
                    continue

                self.stats["candidates_found"] += 1

                # Score belief strength
                score = score_belief_strength(memory)

                if score < BELIEF_MIN_SCORE:
                    reason = f"score_too_low_{score:.2f}"
                    jsonlog(
                        {
                            "decision": "skip",
                            "reason": reason,
                            "score": score,
                            "id": memory.get("id", "unknown"),
                            "source_memory": memory.get("id", "unknown"),
                            "elapsed_ms": int((time.time() - start_time) * 1000),
                        }
                    )
                    continue

                # Build belief object
                belief = build_belief(memory)
                belief_text = belief.get("belief_text", belief.get("content", ""))
                belief_id = stable_belief_id(memory, belief_text)
                belief["id"] = belief_id

                # Check for deduplication
                if self._belief_exists(belief_id):
                    self.stats["beliefs_deduped"] += 1
                    reason = "already_exists"
                    jsonlog(
                        {
                            "decision": "skip",
                            "reason": reason,
                            "score": score,
                            "id": belief_id,
                            "source_memory": memory.get("id", "unknown"),
                            "elapsed_ms": int((time.time() - start_time) * 1000),
                        }
                    )
                    continue

                beliefs.append(belief)
                self.stats["beliefs_accepted"] += 1

                jsonlog(
                    {
                        "decision": "accept",
                        "reason": "candidate_approved",
                        "score": score,
                        "id": belief_id,
                        "source_memory": memory.get("id", "unknown"),
                        "elapsed_ms": int((time.time() - start_time) * 1000),
                    }
                )

            except Exception as e:
                logger.error(
                    f"Error processing memory {memory.get('id', 'unknown')}: {e}"
                )
                self.stats["errors"] += 1
                jsonlog(
                    {
                        "decision": "error",
                        "reason": str(e),
                        "score": 0.0,
                        "id": memory.get("id", "unknown"),
                        "source_memory": memory.get("id", "unknown"),
                        "elapsed_ms": int((time.time() - start_time) * 1000),
                    }
                )

        logger.info(f"Extracted {len(beliefs)} beliefs from {len(memories)} memories")
        return beliefs

    def _belief_exists(self, belief_id: str) -> bool:
        """
        Check if a belief with the given ID already exists.

        Args:
            belief_id: Stable belief ID to check

        Returns:
            True if belief exists, False otherwise
        """
        try:
            self._ensure_session()
            # Try lightweight HEAD request first if API supports it
            belief_url = urljoin(MEMORY_POD_URL, f"/beliefs/{belief_id}")
            resp = self.session.head(belief_url, timeout=(3, 10))

            if resp.status_code == 200:
                return True
            elif resp.status_code == 404:
                return False
            else:
                # Fallback to GET if HEAD not supported
                resp = self.session.get(belief_url, timeout=(3, 10))
                return resp.status_code == 200

        except Exception as e:
            logger.warning(f"Could not check belief existence for {belief_id}: {e}")
            # Conservative approach: assume it doesn't exist to avoid blocking
            return False

    def ingest_beliefs(self, beliefs: List[Dict[str, Any]]) -> None:
        """
        Ingest beliefs using the existing belief ingestion route.

        Args:
            beliefs: List of belief objects to ingest
        """
        if not beliefs:
            return

        if BELIEF_EXTRACT_SHADOW or self.dry_run:
            logger.info(f"Shadow mode: would ingest {len(beliefs)} beliefs")
            for belief in beliefs:
                jsonlog(
                    {
                        "action": "shadow_ingest",
                        "belief_id": belief.get("id", "unknown"),
                        "confidence": belief.get("confidence", 0.0),
                        "content_preview": belief.get("content", "")[:100] + "...",
                    }
                )
            return

        # Batch the beliefs for ingestion
        batch_size = BELIEF_BATCH_SIZE
        for i in range(0, len(beliefs), batch_size):
            batch = beliefs[i : i + batch_size]

            try:
                self._ensure_session()
                # Use existing belief ingestion endpoint
                ingest_url = urljoin(MEMORY_POD_URL, "/beliefs")

                # Post as batch
                resp = self.session.post(
                    ingest_url,
                    json={"beliefs": batch},
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code in [200, 201]:
                    self.stats["beliefs_posted"] += len(batch)
                    logger.info(f"Successfully ingested batch of {len(batch)} beliefs")

                    for belief in batch:
                        jsonlog(
                            {
                                "action": "ingest_success",
                                "belief_id": belief.get("id", "unknown"),
                                "confidence": belief.get("confidence", 0.0),
                            }
                        )
                else:
                    logger.error(
                        f"Failed to ingest belief batch: {resp.status_code} - {resp.text}"
                    )
                    self.stats["errors"] += 1

            except Exception as e:
                logger.error(f"Error ingesting belief batch: {e}")
                self.stats["errors"] += 1
                time.sleep(1)  # Brief backoff on error

    def run_extraction_pipeline(self) -> Dict[str, Any]:
        """
        Run the complete belief extraction pipeline.

        Returns:
            Statistics dictionary with results
        """
        start_time = time.time()

        try:
            logger.info(
                f"Starting belief reflection session (dry_run={self.dry_run}, limit={self.limit})"
            )

            # Health checks
            if not self.health_check():
                raise BeliefReflectionError("Health checks failed")

            # Sample memories
            memories = self.sample_memories()
            if not memories:
                logger.warning("No memories sampled, ending session")
                return self.stats

            # Extract beliefs
            beliefs = self.extract_beliefs(memories)

            # Ingest beliefs
            if beliefs:
                self.ingest_beliefs(beliefs)

            # Update final stats
            self.stats["total_runtime_ms"] = int((time.time() - start_time) * 1000)
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(f"Belief reflection session completed: {self.stats}")

            return self.stats

        except Exception as e:
            logger.error(f"Belief reflection session failed: {e}")
            self.stats["errors"] += 1
            self.stats["error_message"] = str(e)
            self.stats["total_runtime_ms"] = int((time.time() - start_time) * 1000)
            raise


def acquire_lock() -> bool:
    """
    Acquire single-host lock to prevent concurrent runs.

    Returns:
        True if lock acquired, False if already locked
    """
    try:
        if os.path.exists(LOCK_FILE):
            # Check if lock is stale (older than max runtime + buffer)
            lock_age = time.time() - os.path.getmtime(LOCK_FILE)
            if lock_age > (BELIEF_MAX_RUNTIME_SEC + 60):
                logger.warning(f"Removing stale lock file (age: {lock_age}s)")
                os.remove(LOCK_FILE)
            else:
                return False

        # Create lock file
        with open(LOCK_FILE, "w") as f:
            f.write(
                f"pid:{os.getpid()}\nstarted:{datetime.now(timezone.utc).isoformat()}\n"
            )

        return True

    except Exception as e:
        logger.error(f"Failed to acquire lock: {e}")
        return False


def release_lock() -> None:
    """Release the lock file."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        logger.warning(f"Failed to release lock: {e}")


def run_once(dry_run: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Run belief reflection once with proper locking and timeout.

    Args:
        dry_run: If True, don't actually ingest beliefs
        limit: Optional limit on number of memories to sample

    Returns:
        Statistics dictionary
    """
    if not BELIEF_EXTRACT_ENABLED and not dry_run:
        logger.info("Belief extraction disabled by config")
        return {"status": "disabled"}

    # Acquire lock
    if not acquire_lock():
        logger.warning("Another belief reflection process is running")
        return {"status": "locked"}

    try:
        # Set up timeout guard
        def timeout_handler(signum, frame):
            raise TimeoutError(
                f"Belief reflection exceeded {BELIEF_MAX_RUNTIME_SEC}s limit"
            )

        import signal

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(BELIEF_MAX_RUNTIME_SEC)

        # Run the extraction pipeline
        session = BeliefReflectionSession(dry_run=dry_run, limit=limit)
        stats = session.run_extraction_pipeline()

        # Clear timeout
        signal.alarm(0)

        return stats

    except Exception as e:
        logger.error(f"Belief reflection failed: {e}")
        return {"status": "error", "error": str(e)}

    finally:
        release_lock()


def setup_logging():
    """Setup logging with rotating file handler."""
    # Default to a local relative directory for public-safe dev usage.
    logs_dir = os.getenv("AXIOM_LOGS_DIR", "./logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Configure main logger
    logger = logging.getLogger(__name__)

    if not logger.handlers:
        # Rotating file handler
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, "belief_reflection.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Also add console handler for dry-run mode
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Set level
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

    return logger


def main():
    """Command-line interface for belief reflection."""
    parser = argparse.ArgumentParser(
        description="Belief Metabolism Reflection Pipeline"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually ingest beliefs"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Limit number of memories to sample (default: 30)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Setup logging
    setup_logging()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run the pipeline
    stats = run_once(dry_run=args.dry_run, limit=args.limit)

    # Print results with formatting
    print("=" * 60)
    print("BELIEF METABOLISM DRY-RUN RESULTS")
    print("=" * 60)
    print(json.dumps(stats, indent=2))
    print("=" * 60)

    # Print summary
    if stats.get("status") not in ["error", "disabled", "locked"]:
        print(f"Memories sampled: {stats.get('memories_sampled', 0)}")
        print(f"Candidates found: {stats.get('candidates_found', 0)}")
        print(f"Beliefs accepted: {stats.get('beliefs_accepted', 0)}")
        print(f"Beliefs deduped: {stats.get('beliefs_deduped', 0)}")
        if args.dry_run:
            print(f"Would have posted: {stats.get('beliefs_accepted', 0)} beliefs")
        else:
            print(f"Beliefs posted: {stats.get('beliefs_posted', 0)}")
        print(f"Errors: {stats.get('errors', 0)}")
        print(f"Runtime: {stats.get('total_runtime_ms', 0)}ms")

    print("=" * 60)

    # Exit with appropriate code
    if stats.get("status") == "error":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
