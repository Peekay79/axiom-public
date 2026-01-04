"""
Minimal junk detection module for memory pod isolation.
Contains only the essential junk detection functionality without external dependencies.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


def is_likely_junk(memory: str) -> bool:
    """
    Detect low-quality "junk" memories that should be auto-tagged as tier_5.

    Returns True if the memory is likely junk based on:
    - Message is fewer than 8 words
    - Contains only common filler phrases

    Args:
        memory: The memory content string to analyze

    Returns:
        bool: True if the memory is likely junk, False otherwise
    """
    if not memory or not isinstance(memory, str):
        return True

    # Clean and normalize the memory text
    cleaned_memory = memory.strip().lower()

    if not cleaned_memory:
        return True

    # Check word count - fewer than 8 words is likely junk
    word_count = len(cleaned_memory.split())
    if word_count < 8:
        # Additional check for very short messages - allow some short but meaningful content
        meaningful_short_patterns = [
            # Questions
            r"\?",
            # Commands or requests
            r"\b(please|can|could|would|will|do|get|make|help|show|tell|explain)\b",
            # Specific information
            r"\b(yes|no|maybe|sure|exactly|definitely|absolutely|never|always)\b.*\w+",
            # URLs, emails, technical terms
            r"@|\.com|\.org|http|www|\w+\.\w+",
            # Numbers with context
            r"\d+.*\w+|\w+.*\d+",
        ]

        # If it's very short but has meaningful patterns, don't mark as junk
        if any(
            re.search(pattern, cleaned_memory) for pattern in meaningful_short_patterns
        ):
            logger.debug(
                f"[JunkDetection] Short content has meaningful patterns, not marking as junk: '{memory[:50]}...'"
            )
            return False

        logger.debug(
            f"[JunkDetection] Content too short ({word_count} words): '{memory[:50]}...'"
        )
        return True

    # Define common filler phrases and low-value patterns
    filler_patterns = [
        # Simple acknowledgments
        r"^(ok|okay|k)\.?$",
        r"^(thanks?|thx|ty)\.?$",
        r"^(cool|nice|good)\.?$",
        r"^(yeah|yep|yes|yup|uh-huh)\.?$",
        r"^(nah|nope|no)\.?$",
        # Laughter and reactions
        r"^(lol|lmao|haha|hehe|rofl)\.?$",
        r"^(wow|omg|wtf|damn)\.?$",
        r"^(hmm|uh|um|er)\.?$",
        # Greetings without substance
        r"^(hi|hello|hey|sup)\.?$",
        r"^(bye|goodbye|cya|see ya|ttyl)\.?$",
        # Meta commentary about the chat/conversation
        r"^\w*typing\w*$",
        r"^\w*discord\w*$",
        r"^\w*chat\w*$",
        r"^\w*message\w*$",
        # Very simple responses
        r"^(same|true|right|exactly)\.?$",
        r"^(idk|dunno|who knows)\.?$",
        r"^(whatever|meh)\.?$",
    ]

    # Check if the entire cleaned memory matches any filler pattern
    for pattern in filler_patterns:
        if re.match(pattern, cleaned_memory):
            logger.debug(
                f"[JunkDetection] Content matches filler pattern '{pattern}': '{memory[:50]}...'"
            )
            return True

    # Check for content that's mostly filler words
    filler_words = {
        "um",
        "uh",
        "like",
        "you",
        "know",
        "basically",
        "actually",
        "just",
        "really",
        "kinda",
        "sorta",
    }
    words = cleaned_memory.split()
    filler_ratio = sum(1 for word in words if word.strip(".,!?") in filler_words) / len(
        words
    )

    if filler_ratio > 0.6:  # More than 60% filler words
        logger.debug(
            f"[JunkDetection] Content is {filler_ratio:.1%} filler words: '{memory[:50]}...'"
        )
        return True

    # Check for repetitive content (same word repeated)
    unique_words = set(words)
    if len(words) > 3 and len(unique_words) == 1:
        logger.debug(
            f"[JunkDetection] Content is repetitive (same word repeated): '{memory[:50]}...'"
        )
        return True

    logger.debug(f"[JunkDetection] Content passed junk detection: '{memory[:50]}...'")
    return False


def process_junk_memory(memory_content: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a memory entry and apply junk detection tagging.

    Args:
        memory_content: The memory content to check
        entry: The memory entry dictionary to modify

    Returns:
        Dict[str, Any]: The modified memory entry with junk tagging if applicable
    """
    if is_likely_junk(memory_content):
        # Mark as low-quality tier
        entry["quality_tier"] = "tier_5"

        # Add junk and auto_tagged tags
        existing_tags = entry.get("tags", [])
        junk_tags = ["junk", "auto_tagged"]

        # Merge tags, avoiding duplicates
        for tag in junk_tags:
            if tag not in existing_tags:
                existing_tags.append(tag)

        entry["tags"] = existing_tags

        # Log the junk detection
        preview = (
            memory_content[:100] + "..."
            if len(memory_content) > 100
            else memory_content
        )
        logger.info(f"🗑️ Discardable memory detected: '{preview}' – tagged as junk")

        # Add metadata about the junk detection
        entry["junk_detected"] = True
        entry["junk_detection_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Optionally lower the importance score for junk memories
        if "importance" in entry:
            entry["importance"] = min(
                entry["importance"], 0.1
            )  # Cap importance at very low level
        else:
            entry["importance"] = 0.05  # Set very low importance for junk

        # Simple log event without external dependencies
        logger.info(
            f"Junk detection: Memory tagged as junk: quality_tier=tier_5, tags={junk_tags}"
        )

    return entry
