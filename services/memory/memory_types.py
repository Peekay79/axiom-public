#!/usr/bin/env python3
"""
memory_types.py - Hierarchical Memory Type Classification for Axiom

This module defines the four-layer hierarchical memory system:
- short_term: Recent working memory, context window, RAM-like memory
- episodic: Specific experiences or interactions, typically journaled
- semantic: Abstract knowledge or generalised beliefs not tied to a single moment
- procedural: Action sequences, skills, and goal-related patterns

Each memory type has specific storage characteristics and retrieval patterns.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("memory_types")


class MemoryType(Enum):
    """Hierarchical memory type classification"""

    SHORT_TERM = "short_term"  # Recent working memory, context window, RAM-like memory
    EPISODIC = "episodic"  # Specific experiences or interactions, typically journaled
    SEMANTIC = "semantic"  # Abstract knowledge or generalised beliefs not tied to a single moment
    PROCEDURAL = "procedural"  # Action sequences, skills, and goal-related patterns
    SIMULATION = "simulation"  # Simulated content from Wonder Engine, ToM, Empathy - NEVER becomes belief
    FALLBACK = "fallback"  # Temporary fallback memories when Qdrant is unavailable - NEVER becomes belief


class MemoryTypeInferrer:
    """Infers memory type based on content, source, and context"""

    def __init__(self):
        self.short_term_indicators = [
            r"\bcurrent\b",
            r"\bright now\b",
            r"\bthis moment\b",
            r"\bcurrently\b",
            r"\btoday\b",
            r"\bjust now\b",
            r"\brecent\b",
            r"\blatest\b",
        ]

        self.episodic_indicators = [
            r"\byesterday\b",
            r"\blast week\b",
            r"\bremember when\b",
            r"\bI experienced\b",
            r"\bhappened to me\b",
            r"\bI went through\b",
            r"\bback then\b",
            r"\bonce upon\b",
            r"\bI recall\b",
            r"\bI witnessed\b",
            r"\bI did\b",
            r"\bI saw\b",
            r"\bI met\b",
        ]

        self.semantic_indicators = [
            r"\bI believe\b",
            r"\bI think\b",
            r"\bin general\b",
            r"\balways\b",
            r"\bnever\b",
            r"\busually\b",
            r"\btypically\b",
            r"\bpeople tend to\b",
            r"\baccording to\b",
            r"\bresearch shows\b",
            r"\bstudies indicate\b",
            r"\bfact\b",
            r"\btruth\b",
            r"\bprinciple\b",
            r"\bconcept\b",
            r"\btheory\b",
            r"\bphilosophy\b",
        ]

        self.procedural_indicators = [
            r"\bhow to\b",
            r"\bstep by step\b",
            r"\bprocess\b",
            r"\bmethod\b",
            r"\bprocedure\b",
            r"\bworkflow\b",
            r"\bstrategy\b",
            r"\bapproach\b",
            r"\btechnique\b",
            r"\bskill\b",
            r"\bI need to\b",
            r"\bI should\b",
            r"\bI must\b",
            r"\bgoal\b",
            r"\bplan\b",
            r"\baction\b",
            r"\btask\b",
            r"\bsequence\b",
            r"\broutine\b",
        ]

    def infer_memory_type(
        self,
        content: str,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MemoryType:
        """
        Infer memory type based on content, source, and context.

        Args:
            content: The memory content text
            source: Source of the memory (e.g., "journal", "goal_engine", "belief_system")
            tags: Existing tags that might indicate memory type
            context: Additional context information

        Returns:
            MemoryType: The inferred memory type
        """
        if not content:
            return MemoryType.SHORT_TERM

        content_lower = content.lower()

        # Check context metadata for explicit simulation markers
        if context and context.get("memoryType") == "simulation":
            return MemoryType.SIMULATION

        # Check tags first for explicit classification
        if tags:
            tags_lower = [tag.lower() for tag in tags]
            # SIMULATION must be checked first to prevent belief contamination
            if any(
                tag
                in [
                    "simulation",
                    "#simulation",
                    "#simulated_output",
                    "#perspective_sim",
                    "#empathy_inference",
                ]
                for tag in tags_lower
            ):
                return MemoryType.SIMULATION
            if any(
                tag in ["belief", "knowledge", "fact", "principle", "theory"]
                for tag in tags_lower
            ):
                return MemoryType.SEMANTIC
            if any(
                tag in ["goal", "plan", "procedure", "skill", "method"]
                for tag in tags_lower
            ):
                return MemoryType.PROCEDURAL
            if any(
                tag in ["experience", "event", "memory", "story"] for tag in tags_lower
            ):
                return MemoryType.EPISODIC
            if any(tag in ["current", "temp", "working"] for tag in tags_lower):
                return MemoryType.SHORT_TERM

        # Check source for hints
        if source:
            source_lower = (source or "unknown").lower()
            if "journal" in source_lower:
                return MemoryType.EPISODIC
            if "goal" in source_lower or "plan" in source_lower:
                return MemoryType.PROCEDURAL
            if "belief" in source_lower or "knowledge" in source_lower:
                return MemoryType.SEMANTIC

        # Score content against each memory type
        scores = {
            MemoryType.SHORT_TERM: self._score_indicators(
                content_lower, self.short_term_indicators
            ),
            MemoryType.EPISODIC: self._score_indicators(
                content_lower, self.episodic_indicators
            ),
            MemoryType.SEMANTIC: self._score_indicators(
                content_lower, self.semantic_indicators
            ),
            MemoryType.PROCEDURAL: self._score_indicators(
                content_lower, self.procedural_indicators
            ),
        }

        # Add context-based scoring
        if context:
            self._add_context_scoring(scores, context)

        # Find the highest scoring type
        max_score = max(scores.values())
        if max_score > 0:
            for memory_type, score in scores.items():
                if score == max_score:
                    logger.debug(
                        f"Inferred memory type: {memory_type.value} (score: {score:.2f})"
                    )
                    return memory_type

        # Default to short_term if no clear indicators
        logger.debug("No clear memory type indicators found, defaulting to short_term")
        return MemoryType.SHORT_TERM

    def _score_indicators(self, content: str, indicators: List[str]) -> float:
        """Score content against a list of regex indicators"""
        score = 0.0
        for indicator in indicators:
            matches = len(re.findall(indicator, content))
            score += matches * 0.5  # Each match adds 0.5 to the score
        return score

    def _add_context_scoring(
        self, scores: Dict[MemoryType, float], context: Dict[str, Any]
    ):
        """Add context-based scoring adjustments"""
        # Time-based context
        if "timestamp" in context:
            try:
                timestamp = datetime.fromisoformat(context["timestamp"])
                age_minutes = (
                    datetime.now(timezone.utc) - timestamp
                ).total_seconds() / 60

                # Recent memories (< 30 minutes) favor short_term
                if age_minutes < 30:
                    scores[MemoryType.SHORT_TERM] += 1.0
                # Memories 30min - 24h favor episodic
                elif age_minutes < 1440:  # 24 hours
                    scores[MemoryType.EPISODIC] += 0.5
            except (ValueError, TypeError):
                pass

        # Speaker context
        if "speaker" in context:
            speaker = context["speaker"].lower()
            if speaker == "system":
                scores[MemoryType.PROCEDURAL] += 0.3
            elif speaker == "axiom":
                scores[MemoryType.SEMANTIC] += 0.3

        # Type context from legacy fields
        if "type" in context:
            type_value = (context["type"] or "external_import").lower()
            if type_value == "belief":
                scores[MemoryType.SEMANTIC] += 1.0
            elif type_value == "goal":
                scores[MemoryType.PROCEDURAL] += 1.0
            elif type_value == "event":
                scores[MemoryType.EPISODIC] += 1.0
            elif type_value == "dialogue":
                scores[MemoryType.SHORT_TERM] += 0.5


class MemoryTypeManager:
    """Manages memory type classifications and provides utility functions"""

    def __init__(self):
        self.inferrer = MemoryTypeInferrer()

    def get_storage_characteristics(self, memory_type: MemoryType) -> Dict[str, Any]:
        """Get storage characteristics for a memory type"""
        characteristics = {
            MemoryType.SHORT_TERM: {
                "storage_layer": "in_memory",
                "retention_policy": "aggressive_decay",
                "max_retention_days": 1,
                "priority_multiplier": 1.0,
                "vector_index": "short_term_index",
                "decay_rate": 0.1,
            },
            MemoryType.EPISODIC: {
                "storage_layer": "vector_db",
                "retention_policy": "timestamped_logs",
                "max_retention_days": 365,
                "priority_multiplier": 1.2,
                "vector_index": "episodic_index",
                "decay_rate": 0.01,
            },
            MemoryType.SEMANTIC: {
                "storage_layer": "belief_system",
                "retention_policy": "belief_promotion",
                "max_retention_days": None,  # Permanent
                "priority_multiplier": 1.5,
                "vector_index": "semantic_index",
                "decay_rate": 0.005,
            },
            MemoryType.PROCEDURAL: {
                "storage_layer": "goal_engine",
                "retention_policy": "skill_retention",
                "max_retention_days": 180,
                "priority_multiplier": 1.3,
                "vector_index": "procedural_index",
                "decay_rate": 0.02,
            },
            MemoryType.SIMULATION: {
                "storage_layer": "simulation_vault",
                "retention_policy": "isolated_containment",
                "max_retention_days": 7,  # Short retention for auditing only
                "priority_multiplier": 0.1,  # Very low priority
                "vector_index": "simulation_index",
                "decay_rate": 0.5,  # Rapid decay
                "containment": True,  # Special flag - NEVER promote to beliefs
                "audit_only": True,
            },
            MemoryType.FALLBACK: {
                "storage_layer": "fallback_cache",
                "retention_policy": "temporary_cache",
                "max_retention_days": 1,  # Very short retention - for automatic flush only
                "priority_multiplier": 0.0,  # Lowest priority
                "vector_index": "fallback_index",
                "decay_rate": 1.0,  # Immediate decay
                "containment": True,  # Special flag - NEVER promote to beliefs
                "temporary": True,  # Auto-flush when Qdrant available
                "fallback_mode": True,
            },
        }
        return characteristics.get(memory_type, characteristics[MemoryType.SHORT_TERM])

    def get_retrieval_priorities(self, query_context: str) -> Dict[MemoryType, float]:
        """Get retrieval priorities for different memory types based on query context"""
        context_lower = query_context.lower()

        # Default priorities
        priorities = {
            MemoryType.SHORT_TERM: 0.8,
            MemoryType.EPISODIC: 0.6,
            MemoryType.SEMANTIC: 0.7,
            MemoryType.PROCEDURAL: 0.5,
            MemoryType.SIMULATION: 0.0,  # Never retrieve for normal operations
            MemoryType.FALLBACK: 0.0,  # Never retrieve for normal operations
        }

        # Adjust based on query context
        if any(
            word in context_lower
            for word in ["remember", "recall", "happened", "experience"]
        ):
            priorities[MemoryType.EPISODIC] = 1.0

        if any(
            word in context_lower
            for word in ["believe", "think", "knowledge", "fact", "true"]
        ):
            priorities[MemoryType.SEMANTIC] = 1.0

        if any(
            word in context_lower
            for word in ["how", "do", "achieve", "goal", "plan", "method"]
        ):
            priorities[MemoryType.PROCEDURAL] = 1.0

        if any(
            word in context_lower for word in ["current", "now", "recent", "latest"]
        ):
            priorities[MemoryType.SHORT_TERM] = 1.0

        return priorities

    def should_promote_memory(
        self, memory_entry: Dict[str, Any]
    ) -> Optional[MemoryType]:
        """Determine if a memory should be promoted to a different type"""
        current_type = MemoryType(memory_entry.get("memory_type", "short_term"))

        # Promotion rules
        if current_type == MemoryType.SHORT_TERM:
            # Promote to episodic if it's a significant experience
            if memory_entry.get("importance", 0) > 0.7:
                return MemoryType.EPISODIC

        elif current_type == MemoryType.EPISODIC:
            # Promote to semantic if it contains generalizable knowledge
            content = memory_entry.get("content", "").lower()
            if any(
                word in content
                for word in ["always", "never", "usually", "generally", "principle"]
            ):
                return MemoryType.SEMANTIC

        elif current_type == MemoryType.PROCEDURAL:
            # Promote to semantic if it becomes a general belief
            tags = memory_entry.get("tags", [])
            if "belief" in tags or "principle" in tags:
                return MemoryType.SEMANTIC

        return None

    def get_default_importance(self, memory_type: MemoryType) -> float:
        """Get default importance score for a memory type"""
        defaults = {
            MemoryType.SHORT_TERM: 0.3,
            MemoryType.EPISODIC: 0.6,
            MemoryType.SEMANTIC: 0.8,
            MemoryType.PROCEDURAL: 0.7,
            MemoryType.SIMULATION: 0.1,  # Very low importance
            MemoryType.FALLBACK: 0.0,  # Zero importance
        }
        return defaults.get(memory_type, 0.5)


# Global instance for use across the system
memory_type_manager = MemoryTypeManager()


def infer_memory_type(
    content: str,
    source: Optional[str] = None,
    tags: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> MemoryType:
    """Convenience function for memory type inference"""
    return memory_type_manager.inferrer.infer_memory_type(
        content, source, tags, context
    )


def get_storage_characteristics(memory_type: MemoryType) -> Dict[str, Any]:
    """Convenience function for getting storage characteristics"""
    return memory_type_manager.get_storage_characteristics(memory_type)


def get_retrieval_priorities(query_context: str) -> Dict[MemoryType, float]:
    """Convenience function for getting retrieval priorities"""
    return memory_type_manager.get_retrieval_priorities(query_context)
