#!/usr/bin/env python3
"""
belief_utils.py - Utility functions for belief detection and processing

This module provides core utilities for the Belief Metabolism system:
- Text normalization and candidate detection
- Belief strength scoring
- Belief object construction
- Stable ID generation
- JSON logging utilities

All functions are designed to be conservative and precision-biased.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Optional dotenv import
try:
    from dotenv import load_dotenv

    load_dotenv(".env.vector", override=False)
    load_dotenv(".env", override=False)
except ImportError:
    # Gracefully handle missing dotenv
    pass

# Configuration defaults
BELIEF_MIN_SCORE = float(os.getenv("BELIEF_MIN_SCORE", "0.7"))
BELIEF_REQUIRED_PHRASES = (
    os.getenv("BELIEF_REQUIRED_PHRASES", "").split(",")
    if os.getenv("BELIEF_REQUIRED_PHRASES")
    else [
        "I believe",
        "I think",
        "My belief",
        "I am convinced",
        "I hold that",
        "In my opinion",
        "I feel that",
        "I maintain",
        "My view is",
        "I consider",
    ]
)
BELIEF_STOPWORDS = (
    os.getenv("BELIEF_STOPWORDS", "").split(",")
    if os.getenv("BELIEF_STOPWORDS")
    else [
        "maybe",
        "perhaps",
        "might",
        "could be",
        "possibly",
        "unsure",
        "confused",
        "don't know",
        "uncertain",
        "unclear",
        "doubt",
        "question",
        "wonder",
    ]
)

# Clean up configuration lists
BELIEF_REQUIRED_PHRASES = [
    phrase.strip() for phrase in BELIEF_REQUIRED_PHRASES if phrase.strip()
]
BELIEF_STOPWORDS = [word.strip() for word in BELIEF_STOPWORDS if word.strip()]

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text by stripping whitespace, collapsing multiple spaces, and converting to lowercase.

    Args:
        text: Input text to normalize

    Returns:
        Normalized text string
    """
    if not text:
        return ""

    # Strip and collapse whitespace
    normalized = re.sub(r"\s+", " ", text.strip())

    # Convert to lowercase
    return normalized.lower()


def is_belief_candidate(memory: Dict[str, Any]) -> bool:
    """
    Determine if a memory is a candidate for belief extraction.
    Uses a precision-biased approach: must contain required phrases AND pass checks.

    Args:
        memory: Memory object with 'content' and optional metadata

    Returns:
        True if memory is a belief candidate, False otherwise
    """
    if not memory or not isinstance(memory, dict):
        return False

    content = memory.get("content", "")
    if not content or not isinstance(content, str):
        return False

    # Minimum length check (avoid trivial statements)
    if len(content.strip()) < 20:
        return False

    # Check for simulation or fallback tags (these should never become beliefs)
    tags = memory.get("tags", [])
    if isinstance(tags, list):
        tags_lower = [tag.lower() for tag in tags]
        excluded_tags = [
            "simulation",
            "#simulation",
            "#simulated_output",
            "#perspective_sim",
            "#empathy_inference",
            "fallback",
        ]
        if any(tag in excluded_tags for tag in tags_lower):
            return False

    # Check memory type (simulation/fallback types are excluded)
    memory_type = memory.get("memoryType", "").lower()
    if memory_type in ["simulation", "fallback"]:
        return False

    content_lower = content.lower()

    # Must contain at least one required phrase (precision requirement)
    if not any(phrase.lower() in content_lower for phrase in BELIEF_REQUIRED_PHRASES):
        return False

    # Must not contain stopwords that indicate uncertainty
    if any(stopword.lower() in content_lower for stopword in BELIEF_STOPWORDS):
        return False

    # Signal quality checks
    # Avoid content that looks like questions
    if content.strip().endswith("?") or content_lower.startswith(
        ("what", "why", "how", "when", "where", "who")
    ):
        return False

    # Avoid obviously procedural content
    procedural_indicators = [
        "step 1",
        "first,",
        "then,",
        "next,",
        "finally,",
        "todo:",
        "task:",
        "first step",
        "step is to",
    ]
    if any(indicator in content_lower for indicator in procedural_indicators):
        return False

    return True


def score_belief_strength(memory: Dict[str, Any]) -> float:
    """
    Score the strength/confidence of a belief candidate on a 0-1 scale.
    Uses conservative weighting to avoid false positives.

    Args:
        memory: Memory object with content and metadata

    Returns:
        Float score between 0.0 and 1.0
    """
    if not memory or not isinstance(memory, dict):
        return 0.0

    content = memory.get("content", "")
    if not content:
        return 0.0

    content_lower = content.lower()
    score = 0.0

    # Base score for being a valid candidate
    if is_belief_candidate(memory):
        score = 0.3
    else:
        return 0.0

    # Strong confidence indicators
    strong_indicators = [
        "i am certain",
        "i know",
        "i am convinced",
        "without doubt",
        "absolutely",
        "definitely",
        "clearly",
        "obviously",
    ]
    if any(indicator in content_lower for indicator in strong_indicators):
        score += 0.3

    # Medium confidence indicators
    medium_indicators = [
        "i believe",
        "i think",
        "my view",
        "in my opinion",
        "i maintain",
        "i hold that",
    ]
    if any(indicator in content_lower for indicator in medium_indicators):
        score += 0.2

    # Length bonus (longer statements tend to be more substantive)
    content_length = len(content.strip())
    if content_length > 100:
        score += 0.1
    if content_length > 200:
        score += 0.1

    # Importance/priority bonus from metadata
    importance = memory.get("importance", 0.0)
    if isinstance(importance, (int, float)) and importance > 0.5:
        score += 0.1

    # Memory type bonus (semantic memories are more likely to be beliefs)
    memory_type = memory.get("memoryType", "").lower()
    if memory_type == "semantic":
        score += 0.2

    # Tags bonus
    tags = memory.get("tags", [])
    if isinstance(tags, list):
        tags_lower = [tag.lower() for tag in tags]
        belief_tags = ["belief", "philosophy", "principle", "value", "conviction"]
        if any(tag in belief_tags for tag in tags_lower):
            score += 0.15

    # Cap at 1.0
    return min(score, 1.0)


def build_belief(memory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a memory to the repository's belief schema with required tags.

    Args:
        memory: Source memory object

    Returns:
        Belief object following the repo's schema
    """
    if not memory or not isinstance(memory, dict):
        raise ValueError("Invalid memory object provided")

    content = memory.get("content", "")
    if not content:
        raise ValueError("Memory content cannot be empty")

    # Generate stable belief text (normalized)
    belief_text = normalize_text(content)

    # Base belief structure following repo schema
    belief = {
        "content": content,  # Keep original content
        "belief_text": belief_text,  # Normalized version for comparison
        "source": "belief_metabolism",
        "source_memory_id": memory.get("id", ""),
        "source_memory_uuid": memory.get("uuid", memory.get("id", "")),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "confidence": score_belief_strength(memory),
        "importance": memory.get("importance", 0.1),
        "tags": ["auto-extracted", "belief_v1"],
        "metadata": {
            "extraction_method": "belief_metabolism",
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_memory_type": memory.get("memoryType", "unknown"),
            "original_tags": memory.get("tags", []),
        },
    }

    # Add any existing relevant tags from source memory
    source_tags = memory.get("tags", [])
    if isinstance(source_tags, list):
        relevant_tags = [
            tag
            for tag in source_tags
            if tag.lower()
            in [
                "belief",
                "philosophy",
                "principle",
                "value",
                "values",
                "conviction",
                "semantic",
            ]
        ]
        belief["tags"].extend(relevant_tags)

    # Remove duplicates from tags
    belief["tags"] = list(set(belief["tags"]))

    return belief


def stable_belief_id(memory: Dict[str, Any], belief_text: str) -> str:
    """
    Generate a stable, deterministic ID for a belief based on memory ID and belief text.

    Args:
        memory: Source memory object
        belief_text: Normalized belief text

    Returns:
        SHA1 hash string as stable ID
    """
    memory_id = memory.get("id", memory.get("uuid", ""))
    if not memory_id:
        raise ValueError("Memory must have an ID or UUID")

    # Create deterministic string for hashing
    id_string = f"{memory_id}|{normalize_text(belief_text)}"

    # Generate SHA1 hash
    hash_obj = hashlib.sha1(id_string.encode("utf-8"))
    return hash_obj.hexdigest()


def jsonlog(record: Dict[str, Any]) -> None:
    """
    Append a JSON record to the belief reflection outbox log.

    Args:
        record: Dictionary to log as JSON
    """
    if not record or not isinstance(record, dict):
        return

    # Ensure logs directory exists
    logs_dir = "/workspace/logs"
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, "belief_reflection_outbox.jsonl")

    try:
        # Add timestamp if not present
        if "timestamp" not in record:
            record["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Append to JSONL file
        with open(log_file, "a", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")

    except Exception as e:
        logger.error(f"Failed to write to belief reflection log: {e}")


# Module-level logger configuration
def setup_logging():
    """Setup module logging with proper handlers."""
    logger = logging.getLogger(__name__)

    if not logger.handlers:
        # Create logs directory
        os.makedirs("/workspace/logs", exist_ok=True)

        # File handler
        file_handler = logging.FileHandler("/workspace/logs/belief_utils.log")
        file_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Set level
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

    return logger


# Initialize logging
setup_logging()
