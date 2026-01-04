"""
Tests for the Empathic Learning Loop System

This test suite validates the empathy alignment scoring, tone learning,
and adaptive prompt building functionality.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

from axiom.theory_of_mind.learning_loop import (
    cleanup_old_profiles,
    get_or_create_tone_profile,
    get_preferred_tone,
    get_tone_profile_summary,
    is_learning_enabled,
    reset_tone_profile,
    score_empathic_alignment,
    update_tone_profile,
)

# Import the modules under test
from axiom.theory_of_mind.models import (
    AgentToneProfile,
    EmotionalState,
    EmpathyAlignment,
    IntentionModel,
)


class TestAgentToneProfile:
    """Test the AgentToneProfile model and its methods."""

    def test_create_tone_profile(self):
        """Test creating a new tone profile."""
        profile = AgentToneProfile(agent_id="ExamplePerson")

        assert profile.agent_id == "ExamplePerson"
        assert profile.preferred_tones == {}
        assert profile.alignment_history == []
        assert profile.entry_count == 0
        assert profile.confidence_threshold == 0.8

    def test_add_alignment_entry_above_threshold(self):
        """Test adding alignment entry above confidence threshold."""
        profile = AgentToneProfile(agent_id="ExamplePerson")

        profile.add_alignment_entry(
            emotion="anxious",
            intent="avoid blame",
            tone_used="reassuring and clear",
            alignment_score=0.85,
            context="User seems worried about system behavior",
        )

        assert profile.entry_count == 1
        assert len(profile.alignment_history) == 1
        assert "emotion_anxious" in profile.preferred_tones
        assert profile.preferred_tones["emotion_anxious"] == "reassuring and clear"

    def test_add_alignment_entry_below_threshold(self):
        """Test adding alignment entry below confidence threshold."""
        profile = AgentToneProfile(agent_id="ExamplePerson")

        profile.add_alignment_entry(
            emotion="anxious",
            intent="avoid blame",
            tone_used="reassuring and clear",
            alignment_score=0.75,  # Below default threshold of 0.8
            context="User seems worried",
        )

        assert profile.entry_count == 0
        assert len(profile.alignment_history) == 0
        assert "emotion_anxious" not in profile.preferred_tones

    def test_get_preferred_tone(self):
        """Test retrieving preferred tone for emotion/intent."""
        profile = AgentToneProfile(agent_id="ExamplePerson")

        # Add a high-scoring entry
        profile.add_alignment_entry(
            "frustrated", "get help", "patient and humorous", 0.9
        )

        # Test emotion-based lookup
        tone = profile.get_preferred_tone(emotion="frustrated")
        assert tone == "patient and humorous"

        # Test intent-based lookup
        tone = profile.get_preferred_tone(intent="get help")
        assert tone == "patient and humorous"

        # Test non-existent tone
        tone = profile.get_preferred_tone(emotion="happy")
        assert tone is None


class TestLearningLoop:
    """Test the learning loop functionality."""

    def setup_method(self):
        """Reset learning loop state before each test."""
        from axiom.theory_of_mind.learning_loop import _tone_profiles

        _tone_profiles.clear()

    @patch("axiom.theory_of_mind.learning_loop.is_learning_enabled", return_value=True)
    def test_get_or_create_tone_profile(self, mock_enabled):
        """Test getting or creating tone profiles."""
        # First call should create new profile
        profile1 = get_or_create_tone_profile("ExamplePerson")
        assert profile1.agent_id == "ExamplePerson"

        # Second call should return same profile
        profile2 = get_or_create_tone_profile("ExamplePerson")
        assert profile1 is profile2

    @patch("axiom.theory_of_mind.learning_loop.is_learning_enabled", return_value=False)
    def test_get_tone_profile_learning_disabled(self, mock_enabled):
        """Test that empty profile is returned when learning is disabled."""
        profile = get_or_create_tone_profile("ExamplePerson")
        assert profile.agent_id == "ExamplePerson"
        # Profile should not be stored in global state when learning is disabled

    @patch("axiom.theory_of_mind.learning_loop.is_learning_enabled", return_value=True)
    def test_update_tone_profile(self, mock_enabled):
        """Test updating tone profile with new alignment data."""
        update_tone_profile(
            agent_id="ExamplePerson",
            emotion="anxious",
            intent="avoid blame",
            response_tone="reassuring and clear",
            alignment_score=0.85,
            context="User worried about AI behavior",
        )

        profile = get_or_create_tone_profile("ExamplePerson")
        assert profile.entry_count == 1
        assert "emotion_anxious" in profile.preferred_tones


class TestEmpathyAlignmentScoring:
    """Test the empathy alignment scoring system."""

    def create_mock_emotional_state(
        self, emotion: str = "anxious", confidence: float = 0.8
    ):
        """Create a mock emotional state for testing."""
        return EmotionalState(
            agent_id="ExamplePerson",
            emotion=emotion,
            confidence=confidence,
            context="Test context",
        )

    def create_mock_intentions(self, intentions: list = None, confidence: float = 0.7):
        """Create mock intentions for testing."""
        if intentions is None:
            intentions = ["avoid blame", "get help"]
        return IntentionModel(
            agent_id="ExamplePerson",
            intentions=intentions,
            confidence=confidence,
            context="Test context",
        )

    def test_score_empathic_alignment_with_emotional_state(self):
        """Test scoring with emotional state provided."""
        emotional_state = self.create_mock_emotional_state("anxious")

        # Test response with anxious-appropriate tone
        good_response = "I understand your concern. Let me walk you through this step by step to make it clear and reassuring."

        alignment = score_empathic_alignment(
            agent_id="ExamplePerson",
            response=good_response,
            context="User asking about AI safety",
            emotional_state=emotional_state,
        )

        assert 0.0 <= alignment.alignment_score <= 1.0
        assert alignment.agent_id == "ExamplePerson"
        assert alignment.agent_emotional_state == emotional_state
        assert "anxious" in alignment.reasoning.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
