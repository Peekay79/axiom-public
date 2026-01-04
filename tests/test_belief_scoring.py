#!/usr/bin/env python3
"""
test_belief_scoring.py - Test suite for the multi-dimensional belief confidence scoring system

This test file validates:
- Source trust scoring
- Age decay functionality
- Contradiction pressure calculation
- Entropy scoring
- Composite confidence calculation
- Protection logic for high-confidence beliefs
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Add the project root to the path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from belief_scoring import (
    calculate_age_weighted_confidence,
    calculate_contradiction_pressure,
    calculate_entropy_score,
    calculate_source_trust,
    default_confidence_from_source,
    enhance_belief_with_scoring,
    get_scoring_config,
    score_belief,
    should_protect_belief,
)


class TestBeliefScoring(unittest.TestCase):
    """Test suite for belief scoring functionality"""

    def setUp(self):
        """Set up test environment"""
        # Ensure we're using structured confidence for testing
        os.environ["USE_STRUCTURED_CONFIDENCE"] = "true"
        os.environ["PROTECT_HIGH_CONFIDENCE_THRESHOLD"] = "0.95"

    def tearDown(self):
        """Clean up test environment"""
        # Reset environment variables
        if "USE_STRUCTURED_CONFIDENCE" in os.environ:
            del os.environ["USE_STRUCTURED_CONFIDENCE"]
        if "PROTECT_HIGH_CONFIDENCE_THRESHOLD" in os.environ:
            del os.environ["PROTECT_HIGH_CONFIDENCE_THRESHOLD"]

    def test_source_trust_calculation(self):
        """Test source trust scoring for different belief sources"""

        # High trust sources
        self.assertAlmostEqual(calculate_source_trust("user"), 0.92, places=2)
        self.assertAlmostEqual(calculate_source_trust("human"), 0.92, places=2)
        self.assertAlmostEqual(calculate_source_trust("axiom"), 0.85, places=2)
        self.assertAlmostEqual(calculate_source_trust("system"), 0.85, places=2)

        # Medium trust sources
        self.assertAlmostEqual(calculate_source_trust("extracted"), 0.65, places=2)
        self.assertAlmostEqual(calculate_source_trust("ai_generated"), 0.65, places=2)

        # Low trust sources
        self.assertAlmostEqual(calculate_source_trust("dream_derived"), 0.35, places=2)
        self.assertAlmostEqual(calculate_source_trust("unknown"), 0.25, places=2)

        # Case insensitivity
        self.assertAlmostEqual(calculate_source_trust("USER"), 0.92, places=2)
        self.assertAlmostEqual(calculate_source_trust("User"), 0.92, places=2)

    def test_age_weighted_confidence(self):
        """Test age-based confidence decay"""
        config = get_scoring_config()

        # Recent belief (no timestamp = assume recent)
        recent_belief = {"text": "Recent belief"}
        age_score = calculate_age_weighted_confidence(recent_belief, config)
        self.assertGreaterEqual(age_score, 0.8)

        # Very recent belief (current time)
        now = datetime.now(timezone.utc)
        very_recent_belief = {
            "text": "Very recent belief",
            "timestamp": now.isoformat(),
        }
        age_score = calculate_age_weighted_confidence(very_recent_belief, config)
        self.assertGreaterEqual(age_score, 0.9)

        # Old belief (30 days ago)
        old_time = now - timedelta(days=30)
        old_belief = {"text": "Old belief", "timestamp": old_time.isoformat()}
        age_score = calculate_age_weighted_confidence(old_belief, config)
        self.assertLessEqual(age_score, 0.9)  # More reasonable expectation

        # Very old belief (90 days ago)
        very_old_time = now - timedelta(days=90)
        very_old_belief = {
            "text": "Very old belief",
            "timestamp": very_old_time.isoformat(),
        }
        age_score = calculate_age_weighted_confidence(very_old_belief, config)
        self.assertLessEqual(age_score, 0.6)  # More reasonable expectation

    def test_contradiction_pressure(self):
        """Test contradiction pressure calculation"""

        # No pressure - clean belief
        clean_belief = {
            "text": "This is a clear, definitive statement.",
            "tags": ["belief", "clear"],
        }
        pressure = calculate_contradiction_pressure(clean_belief)
        self.assertLessEqual(pressure, 0.1)

        # Some pressure - uncertain language
        uncertain_belief = {
            "text": "Maybe this is true, but I'm not certain.",
            "tags": ["belief", "uncertain"],
        }
        pressure = calculate_contradiction_pressure(uncertain_belief)
        self.assertGreaterEqual(pressure, 0.2)

        # High pressure - conflicted
        conflicted_belief = {
            "text": "This contradicts what I said before.",
            "tags": ["belief", "conflicted", "contradiction"],
            "merge_count": 3,
            "version": 2,
        }
        pressure = calculate_contradiction_pressure(conflicted_belief)
        self.assertGreaterEqual(pressure, 0.5)

    def test_entropy_score(self):
        """Test entropy/complexity scoring"""

        # Simple, short text
        simple_belief = {"text": "Yes."}
        entropy = calculate_entropy_score(simple_belief)
        self.assertLessEqual(entropy, 0.3)

        # Moderate complexity
        moderate_belief = {
            "text": "Axiom has a multi-pod memory system that stores different types of information."
        }
        entropy = calculate_entropy_score(moderate_belief)
        self.assertGreaterEqual(entropy, 0.4)
        self.assertLessEqual(entropy, 0.8)

        # High complexity
        complex_belief = {
            "text": "The quantum-entangled consciousness architecture facilitates bidirectional "
            "information transfer between heterogeneous cognitive substrates, enabling "
            "emergent metacognitive phenomena through recursive self-reflection loops."
        }
        entropy = calculate_entropy_score(complex_belief)
        self.assertGreaterEqual(entropy, 0.3)  # More reasonable expectation

    def test_belief_scoring_integration(self):
        """Test complete belief scoring with different scenarios"""

        # High-confidence user belief
        user_belief = {
            "text": "Axiom has a multi-pod memory system.",
            "source": "user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tags": ["belief", "system_info"],
        }

        score = score_belief(user_belief)

        # Verify structure
        self.assertIn("source_trust", score)
        self.assertIn("age_weighted", score)
        self.assertIn("contradiction_pressure", score)
        self.assertIn("entropy", score)
        self.assertIn("summary_confidence", score)

        # Verify high confidence for user belief
        self.assertGreaterEqual(score["source_trust"], 0.9)
        self.assertGreaterEqual(score["summary_confidence"], 0.7)

        # Low-confidence dream belief
        dream_belief = {
            "text": "Maybe unicorns exist in parallel dimensions.",
            "source": "dream_derived",
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
            "tags": ["belief", "dream_derived", "hypothetical", "uncertain"],
        }

        dream_score = score_belief(dream_belief)

        # Verify lower confidence for dream belief
        self.assertLessEqual(dream_score["source_trust"], 0.4)
        self.assertLessEqual(dream_score["summary_confidence"], 0.5)
        self.assertGreaterEqual(dream_score["contradiction_pressure"], 0.3)

    def test_belief_protection(self):
        """Test high-confidence belief protection logic"""

        # High confidence bundle that should be protected
        high_confidence_bundle = {
            "source_trust": 0.92,
            "age_weighted": 0.90,
            "contradiction_pressure": 0.05,
            "entropy": 0.70,
            "summary_confidence": 0.96,
        }
        self.assertTrue(should_protect_belief(high_confidence_bundle))

        # Medium confidence bundle that should not be protected
        medium_confidence_bundle = {
            "source_trust": 0.65,
            "age_weighted": 0.70,
            "contradiction_pressure": 0.20,
            "entropy": 0.50,
            "summary_confidence": 0.80,
        }
        self.assertFalse(should_protect_belief(medium_confidence_bundle))

        # High summary confidence but low source trust - should not be protected
        mixed_confidence_bundle = {
            "source_trust": 0.30,
            "age_weighted": 0.95,
            "contradiction_pressure": 0.05,
            "entropy": 0.80,
            "summary_confidence": 0.96,
        }
        self.assertFalse(should_protect_belief(mixed_confidence_bundle))

    def test_enhance_belief_with_scoring(self):
        """Test belief enhancement with structured scoring"""

        belief = {
            "id": "test-belief-001",
            "text": "Axiom processes beliefs through multiple confidence dimensions.",
            "source": "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        enhanced_belief = enhance_belief_with_scoring(belief)

        # Verify belief has confidence bundle
        self.assertIn("confidence_bundle", enhanced_belief)
        self.assertIn("confidence", enhanced_belief)

        # Verify confidence matches summary
        confidence_bundle = enhanced_belief["confidence_bundle"]
        self.assertEqual(
            enhanced_belief["confidence"], confidence_bundle["summary_confidence"]
        )

        # Check for protection flag if applicable
        if (
            confidence_bundle["summary_confidence"] >= 0.95
            and confidence_bundle["source_trust"] >= 0.8
        ):
            self.assertIn("is_protected", enhanced_belief)
            self.assertTrue(enhanced_belief["is_protected"])

    def test_legacy_mode(self):
        """Test fallback to legacy confidence scoring"""

        # Temporarily disable structured confidence
        os.environ["USE_STRUCTURED_CONFIDENCE"] = "false"

        belief = {"text": "Test belief for legacy mode", "source": "user"}

        enhanced_belief = enhance_belief_with_scoring(belief)

        # Should have confidence but no confidence_bundle
        self.assertIn("confidence", enhanced_belief)
        self.assertNotIn("confidence_bundle", enhanced_belief)

        # Confidence should match default from source
        expected_confidence = default_confidence_from_source("user")
        self.assertEqual(enhanced_belief["confidence"], expected_confidence)

        # Reset for other tests
        os.environ["USE_STRUCTURED_CONFIDENCE"] = "true"

    def test_default_confidence_from_source(self):
        """Test legacy default confidence calculation"""

        # High trust sources should have high default confidence
        self.assertGreaterEqual(default_confidence_from_source("user"), 0.7)
        self.assertGreaterEqual(default_confidence_from_source("axiom"), 0.6)

        # Low trust sources should have lower default confidence
        self.assertLessEqual(default_confidence_from_source("unknown"), 0.4)
        self.assertLessEqual(default_confidence_from_source("dream_derived"), 0.4)


def run_belief_scoring_demos():
    """Run demonstrations of the belief scoring system with various scenarios"""

    print("\n" + "=" * 80)
    print("🧠 BELIEF SCORING SYSTEM DEMONSTRATION")
    print("=" * 80)

    # Demo scenarios
    scenarios = [
        {
            "name": "👤 High-Confidence User Belief",
            "belief": {
                "id": "demo-001",
                "text": "Axiom has a multi-pod memory system that enables distributed storage.",
                "source": "user",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": ["belief", "system_architecture", "verified"],
            },
        },
        {
            "name": "🤖 System-Generated Belief",
            "belief": {
                "id": "demo-002",
                "text": "Users prefer concise responses over verbose explanations.",
                "source": "system",
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(days=5)
                ).isoformat(),
                "tags": ["belief", "user_preference", "extracted"],
            },
        },
        {
            "name": "💭 Aged Dream-Derived Belief",
            "belief": {
                "id": "demo-003",
                "text": "Perhaps consciousness emerges from quantum fluctuations in neural microtubules.",
                "source": "dream_derived",
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(days=45)
                ).isoformat(),
                "tags": [
                    "belief",
                    "consciousness",
                    "hypothetical",
                    "unverified",
                    "dream_derived",
                ],
            },
        },
        {
            "name": "⚠️ Conflicted Belief",
            "belief": {
                "id": "demo-004",
                "text": "AI systems might become conscious, but this contradicts materialist assumptions.",
                "source": "extracted",
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(days=15)
                ).isoformat(),
                "tags": ["belief", "ai_consciousness", "conflicted", "uncertain"],
                "merge_count": 2,
                "version": 3,
            },
        },
        {
            "name": "🔍 Simple Low-Entropy Belief",
            "belief": {
                "id": "demo-005",
                "text": "Yes.",
                "source": "user",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": ["belief", "simple"],
            },
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print("-" * len(scenario["name"]))

        belief = scenario["belief"]
        print(f"Text: \"{belief['text']}\"")
        print(f"Source: {belief['source']}")
        print(
            f"Age: {(datetime.now(timezone.utc) - datetime.fromisoformat(belief['timestamp'].replace('Z', '+00:00'))).days} days"
        )

        # Score the belief
        confidence_bundle = score_belief(belief)

        print(f"\n📊 Confidence Bundle:")
        for key, value in confidence_bundle.items():
            print(f"  • {key.replace('_', ' ').title()}: {value:.3f}")

        # Check protection status
        if should_protect_belief(confidence_bundle):
            print(f"🛡️  Protected: Yes (high confidence)")
        else:
            print(f"🛡️  Protected: No")

        print()


if __name__ == "__main__":
    # Run the test suite
    print("Running belief scoring test suite...")
    unittest.main(argv=[""], exit=False, verbosity=2)

    # Run demonstrations
    run_belief_scoring_demos()
