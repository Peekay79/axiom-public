"""
Empathic Learning Loop Module

This module handles the adaptive learning of tone preferences based on
empathy alignment feedback. It manages agent tone profiles and provides
functions for updating and retrieving learned preferences.

All operations maintain containment and use simulation-only memory types.
"""

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .models import AgentToneProfile, EmotionalState, EmpathyAlignment, IntentionModel

# Set up logging
logger = logging.getLogger(__name__)

# Global tone profile storage (in-memory for simulation)
_tone_profiles: Dict[str, AgentToneProfile] = {}

# Configuration
ENABLE_EMPATHIC_LEARNING = (
    os.getenv("ENABLE_EMPATHIC_LEARNING", "true").lower() == "true"
)
MAX_PROFILES = int(os.getenv("MAX_TONE_PROFILES", "50"))  # Prevent memory bloat
ALIGNMENT_CONFIDENCE_THRESHOLD = float(
    os.getenv("ALIGNMENT_CONFIDENCE_THRESHOLD", "0.8")
)


def is_learning_enabled() -> bool:
    """Check if empathic learning is enabled."""
    return ENABLE_EMPATHIC_LEARNING


def get_or_create_tone_profile(agent_id: str) -> AgentToneProfile:
    """
    Get existing tone profile for agent or create a new one.

    Args:
        agent_id: Identifier for the agent

    Returns:
        AgentToneProfile instance
    """
    if not is_learning_enabled():
        # Return empty profile if learning is disabled
        return AgentToneProfile(agent_id=agent_id)

    if agent_id not in _tone_profiles:
        # Check if we're at the profile limit
        if len(_tone_profiles) >= MAX_PROFILES:
            # Remove oldest profile to make space
            oldest_agent = min(
                _tone_profiles.keys(), key=lambda x: _tone_profiles[x].last_updated
            )
            logger.info(
                f"[EmpathicLearning] Removing oldest tone profile: {oldest_agent}"
            )
            del _tone_profiles[oldest_agent]

        # Create new profile
        _tone_profiles[agent_id] = AgentToneProfile(
            agent_id=agent_id, confidence_threshold=ALIGNMENT_CONFIDENCE_THRESHOLD
        )
        logger.debug(
            f"[EmpathicLearning] Created new tone profile for agent: {agent_id}"
        )

    return _tone_profiles[agent_id]


def update_tone_profile(
    agent_id: str,
    emotion: str,
    intent: str,
    response_tone: str,
    alignment_score: float,
    context: str = "",
) -> None:
    """
    Update agent's tone profile with new alignment data.

    Args:
        agent_id: Identifier for the agent
        emotion: Detected emotion (e.g., 'anxious', 'frustrated')
        intent: Detected intent (e.g., 'avoid blame', 'gain influence')
        response_tone: Tone used in the response
        alignment_score: Alignment score (0.0 to 1.0)
        context: Context summary for the interaction
    """
    if not is_learning_enabled():
        logger.debug(
            "[EmpathicLearning] Learning disabled, skipping tone profile update"
        )
        return

    if alignment_score < ALIGNMENT_CONFIDENCE_THRESHOLD:
        logger.debug(
            f"[EmpathicLearning] Score {alignment_score:.2f} below threshold {ALIGNMENT_CONFIDENCE_THRESHOLD}, skipping"
        )
        return

    profile = get_or_create_tone_profile(agent_id)
    profile.add_alignment_entry(
        emotion, intent, response_tone, alignment_score, context
    )

    logger.info(
        f"[EmpathicLearning] Updated tone profile for {agent_id}: "
        f"emotion={emotion}, intent={intent}, score={alignment_score:.2f}"
    )


def get_preferred_tone(
    agent_id: str, emotion: str = None, intent: str = None
) -> Optional[str]:
    """
    Get preferred tone for agent based on learned preferences.

    Args:
        agent_id: Identifier for the agent
        emotion: Current emotion to match
        intent: Current intent to match

    Returns:
        Preferred tone string if found, None otherwise
    """
    if not is_learning_enabled():
        return None

    if agent_id not in _tone_profiles:
        return None

    profile = _tone_profiles[agent_id]
    return profile.get_preferred_tone(emotion, intent)


def score_empathic_alignment(
    agent_id: str,
    response: str,
    context: str,
    emotional_state: Optional[EmotionalState] = None,
    intentions: Optional[IntentionModel] = None,
) -> EmpathyAlignment:
    """
    Score how well a response aligns with the agent's inferred emotional state and intentions.

    This is a simplified scoring algorithm. In a production system, this could be
    enhanced with ML models or more sophisticated analysis.

    Args:
        agent_id: Identifier for the agent
        response: The response text to evaluate
        context: Conversation context
        emotional_state: Inferred emotional state
        intentions: Inferred intentions

    Returns:
        EmpathyAlignment with score and reasoning
    """
    if not emotional_state and not intentions:
        # No emotional context to evaluate against
        return EmpathyAlignment(
            agent_id=agent_id,
            axiom_response=response[:200],  # Truncate for storage
            alignment_score=0.5,
            reasoning="No emotional state or intentions available for alignment evaluation",
            suggestions=["Gather more context about agent's emotional state"],
        )

    score = 0.5  # Start with neutral
    reasoning_parts = []
    suggestions = []

    # Evaluate emotional alignment
    if emotional_state:
        emotion_score = _evaluate_emotional_alignment(response, emotional_state)
        score = (score + emotion_score) / 2
        reasoning_parts.append(
            f"Emotion alignment: {emotion_score:.2f} for {emotional_state.emotion}"
        )

        if emotion_score < 0.7:
            suggestions.append(
                f"Consider more {emotional_state.emotion}-appropriate tone"
            )

    # Evaluate intentional alignment
    if intentions:
        intent_score = _evaluate_intentional_alignment(response, intentions)
        score = (score + intent_score) / 2
        reasoning_parts.append(
            f"Intent alignment: {intent_score:.2f} for {intentions.intentions[:2]}"
        )

        if intent_score < 0.7:
            suggestions.append(
                f"Address agent's intentions: {', '.join(intentions.intentions[:2])}"
            )

    # Adjust score based on response appropriateness
    appropriateness_score = _evaluate_response_appropriateness(response, context)
    score = (score + appropriateness_score) / 2
    reasoning_parts.append(f"Response appropriateness: {appropriateness_score:.2f}")

    return EmpathyAlignment(
        agent_id=agent_id,
        axiom_response=response[:200],  # Truncate for storage
        agent_emotional_state=emotional_state,
        agent_intentions=intentions,
        alignment_score=score,
        reasoning="; ".join(reasoning_parts),
        suggestions=suggestions,
        metadata={"context_length": str(len(context)), "tag": "#empathy_alignment"},
    )


def _evaluate_emotional_alignment(
    response: str, emotional_state: EmotionalState
) -> float:
    """Evaluate how well the response aligns with the detected emotion."""
    emotion = emotional_state.emotion.lower()
    response_lower = response.lower()

    # Simple keyword-based evaluation
    emotion_indicators = {
        "anxious": {
            "positive": [
                "reassuring",
                "clear",
                "step by step",
                "no worry",
                "simple",
                "confident",
            ],
            "negative": ["complicated", "maybe", "uncertain", "confusing"],
        },
        "frustrated": {
            "positive": ["understand", "help", "let me explain", "patient", "humor"],
            "negative": ["just", "simply", "obviously", "should"],
        },
        "curious": {
            "positive": ["explore", "interesting", "let's see", "discover", "learn"],
            "negative": ["boring", "simple", "obvious"],
        },
        "skeptical": {
            "positive": ["evidence", "research", "studies show", "data", "proof"],
            "negative": ["trust me", "believe", "just accept"],
        },
        "defensive": {
            "positive": ["understand", "perspective", "valid point", "respect"],
            "negative": ["wrong", "mistake", "incorrect", "fault"],
        },
    }

    indicators = emotion_indicators.get(emotion, {"positive": [], "negative": []})

    positive_count = sum(1 for word in indicators["positive"] if word in response_lower)
    negative_count = sum(1 for word in indicators["negative"] if word in response_lower)

    # Calculate score based on positive/negative indicators
    total_indicators = len(indicators["positive"]) + len(indicators["negative"])
    if total_indicators == 0:
        return 0.6  # Neutral score for unknown emotions

    positive_ratio = (
        positive_count / len(indicators["positive"]) if indicators["positive"] else 0
    )
    negative_ratio = (
        negative_count / len(indicators["negative"]) if indicators["negative"] else 0
    )

    # Score ranges from 0.2 to 0.9
    score = 0.5 + (positive_ratio * 0.4) - (negative_ratio * 0.3)
    return max(0.2, min(0.9, score))


def _evaluate_intentional_alignment(response: str, intentions: IntentionModel) -> float:
    """Evaluate how well the response addresses the agent's intentions."""
    if not intentions.intentions:
        return 0.5

    response_lower = response.lower()

    # Map common intentions to response patterns
    intention_patterns = {
        "avoid blame": ["not your fault", "understand", "happens", "no problem"],
        "gain influence": ["excellent point", "you're right", "great idea", "valuable"],
        "seek information": [
            "here's how",
            "let me explain",
            "the answer",
            "information",
        ],
        "solve problems": ["solution", "fix", "resolve", "approach", "method"],
        "get attention": ["interesting", "important", "noticed", "attention"],
        "understand": ["explain", "clarify", "understand", "meaning", "definition"],
    }

    alignment_scores = []
    for intent in intentions.intentions[:3]:  # Check top 3 intentions
        intent_lower = intent.lower()
        patterns = intention_patterns.get(intent_lower, [])

        if patterns:
            matches = sum(1 for pattern in patterns if pattern in response_lower)
            intent_score = min(0.9, 0.4 + (matches / len(patterns)) * 0.5)
        else:
            intent_score = 0.5  # Neutral for unknown intentions

        alignment_scores.append(intent_score)

    return sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0.5


def _evaluate_response_appropriateness(response: str, context: str) -> float:
    """Evaluate overall appropriateness of the response given context."""
    if len(response.strip()) < 10:
        return 0.3  # Too short

    if len(response) > 2000:
        return 0.7  # Might be too verbose

    # Check for professional tone
    professional_indicators = [
        "understand",
        "help",
        "explain",
        "clarify",
        "information",
    ]
    unprofessional_indicators = ["whatever", "duh", "stupid", "idiot"]

    response_lower = response.lower()
    professional_count = sum(
        1 for word in professional_indicators if word in response_lower
    )
    unprofessional_count = sum(
        1 for word in unprofessional_indicators if word in response_lower
    )

    base_score = 0.7
    base_score += professional_count * 0.05
    base_score -= unprofessional_count * 0.2

    return max(0.2, min(0.9, base_score))


def reset_tone_profile(agent_id: str) -> bool:
    """
    Reset tone profile for an agent (for debugging/manual override).

    Args:
        agent_id: Identifier for the agent

    Returns:
        True if profile was reset, False if not found
    """
    if agent_id in _tone_profiles:
        _tone_profiles[agent_id].reset()
        logger.info(f"[EmpathicLearning] Reset tone profile for agent: {agent_id}")
        return True
    return False


def get_tone_profile_summary(agent_id: str) -> Optional[Dict]:
    """
    Get a summary of the agent's tone profile for debugging/analysis.

    Args:
        agent_id: Identifier for the agent

    Returns:
        Dictionary with profile summary or None if not found
    """
    if agent_id not in _tone_profiles:
        return None

    profile = _tone_profiles[agent_id]
    return {
        "agent_id": agent_id,
        "preferred_tones": profile.preferred_tones.copy(),
        "entry_count": profile.entry_count,
        "last_updated": profile.last_updated.isoformat(),
        "recent_scores": [
            {"score": entry["alignment_score"], "timestamp": entry["timestamp"]}
            for entry in profile.alignment_history[-5:]  # Last 5 scores
        ],
    }


def get_all_profiles_summary() -> Dict[str, Dict]:
    """Get summary of all tone profiles for system analysis."""
    return {
        agent_id: get_tone_profile_summary(agent_id)
        for agent_id in _tone_profiles.keys()
    }


def cleanup_old_profiles(max_age_days: int = 30) -> int:
    """
    Clean up tone profiles that haven't been updated recently.

    Args:
        max_age_days: Maximum age in days before profile is removed

    Returns:
        Number of profiles removed
    """
    if not is_learning_enabled():
        return 0

    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

    old_profiles = [
        agent_id
        for agent_id, profile in _tone_profiles.items()
        if profile.last_updated < cutoff_date
    ]

    for agent_id in old_profiles:
        del _tone_profiles[agent_id]
        logger.info(f"[EmpathicLearning] Cleaned up old tone profile: {agent_id}")

    return len(old_profiles)
