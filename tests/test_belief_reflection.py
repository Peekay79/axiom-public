#!/usr/bin/env python3
"""
test_belief_reflection.py - Unit tests for belief metabolism system

Tests cover:
- Candidate detection precision (positive/negative phrases)
- Stable ID reproducibility
- Shadow mode behavior
- Deduplication logic
- Core utility functions
"""

import json
import os

# Import modules under test
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, "/workspace")
from memory.belief_reflection import BeliefReflectionSession, acquire_lock, release_lock
from memory.belief_utils import (
    build_belief,
    is_belief_candidate,
    jsonlog,
    normalize_text,
    score_belief_strength,
    stable_belief_id,
)


class TestBeliefUtils(unittest.TestCase):
    """Test belief utility functions."""

    def test_normalize_text(self):
        """Test text normalization."""
        # Basic normalization
        self.assertEqual(normalize_text("  Hello   World  "), "hello world")

        # Empty input
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")

        # Complex whitespace
        self.assertEqual(
            normalize_text("I  believe\n\tthat   this\r\n  is true"),
            "i believe that this is true",
        )

    def test_is_belief_candidate_positive_cases(self):
        """Test belief candidate detection for positive cases."""
        positive_memories = [
            {
                "id": "test1",
                "content": "I believe that artificial intelligence will transform society in profound ways.",
                "memoryType": "semantic",
            },
            {
                "id": "test2",
                "content": "My belief is that humans are fundamentally good and capable of positive change.",
                "tags": ["belief", "philosophy"],
            },
            {
                "id": "test3",
                "content": "I think that the most important quality in a person is their capacity for empathy and understanding.",
                "memoryType": "semantic",
            },
            {
                "id": "test4",
                "content": "I am convinced that technology should serve humanity rather than the other way around.",
                "importance": 0.8,
            },
        ]

        for memory in positive_memories:
            with self.subTest(memory=memory["id"]):
                self.assertTrue(is_belief_candidate(memory))

    def test_is_belief_candidate_negative_cases(self):
        """Test belief candidate detection for negative cases."""
        negative_memories = [
            # Too short
            {"id": "short", "content": "I believe.", "memoryType": "semantic"},
            # Questions
            {
                "id": "question",
                "content": "Do you think that AI will replace human jobs?",
                "memoryType": "semantic",
            },
            # Uncertainty stopwords
            {
                "id": "uncertain",
                "content": "I believe maybe that technology might be good but I'm unsure about it.",
                "memoryType": "semantic",
            },
            # Simulation tags
            {
                "id": "simulation",
                "content": "I believe that empathy is important in human relationships.",
                "tags": ["#simulation", "belief"],
            },
            # Fallback type
            {
                "id": "fallback",
                "content": "I think that this is a strong belief statement.",
                "memoryType": "fallback",
            },
            # No required phrases
            {
                "id": "no_phrases",
                "content": "This is a statement about the world without belief indicators.",
                "memoryType": "semantic",
            },
            # Procedural content
            {
                "id": "procedural",
                "content": "I believe the first step is to gather requirements, then analyze the data.",
                "memoryType": "procedural",
            },
        ]

        for memory in negative_memories:
            with self.subTest(memory=memory["id"]):
                self.assertFalse(is_belief_candidate(memory))

    def test_score_belief_strength(self):
        """Test belief strength scoring."""
        # High confidence belief
        high_conf_memory = {
            "id": "high",
            "content": "I believe absolutely that compassion is the most important human virtue and I am certain this belief guides my interactions.",
            "memoryType": "semantic",
            "importance": 0.9,
            "tags": ["belief", "philosophy"],
        }

        score = score_belief_strength(high_conf_memory)
        self.assertGreater(score, 0.7)

        # Medium confidence belief
        med_conf_memory = {
            "id": "medium",
            "content": "I believe that technology should be designed with human values in mind.",
            "memoryType": "semantic",
            "importance": 0.5,
        }

        score = score_belief_strength(med_conf_memory)
        self.assertGreater(score, 0.4)
        self.assertLess(score, 0.8)

        # Non-candidate should score 0
        non_candidate = {
            "id": "non",
            "content": "What do you think about this topic?",
            "memoryType": "semantic",
        }

        score = score_belief_strength(non_candidate)
        self.assertEqual(score, 0.0)

    def test_stable_belief_id_reproducibility(self):
        """Test that stable IDs are reproducible."""
        memory = {
            "id": "test_memory_123",
            "content": "I believe in the power of human creativity",
        }

        belief_text = "i believe in the power of human creativity"

        # Generate ID multiple times
        id1 = stable_belief_id(memory, belief_text)
        id2 = stable_belief_id(memory, belief_text)
        id3 = stable_belief_id(memory, belief_text)

        # Should be identical
        self.assertEqual(id1, id2)
        self.assertEqual(id2, id3)

        # Should be different for different content
        different_memory = {
            "id": "different_memory_456",
            "content": "Different content",
        }

        id4 = stable_belief_id(different_memory, "different content")
        self.assertNotEqual(id1, id4)

        # Should be SHA1 hash (40 characters)
        self.assertEqual(len(id1), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in id1))

    def test_build_belief(self):
        """Test belief object construction."""
        memory = {
            "id": "source_memory_123",
            "uuid": "uuid_456",
            "content": "I believe that kindness is the most important human quality.",
            "memoryType": "semantic",
            "importance": 0.8,
            "tags": ["belief", "values"],
        }

        belief = build_belief(memory)

        # Check required fields
        self.assertEqual(belief["content"], memory["content"])
        self.assertEqual(belief["source"], "belief_metabolism")
        self.assertEqual(belief["source_memory_id"], "source_memory_123")
        self.assertEqual(belief["source_memory_uuid"], "uuid_456")
        self.assertIn("auto-extracted", belief["tags"])
        self.assertIn("belief_v1", belief["tags"])
        self.assertIn("belief", belief["tags"])
        self.assertIn("values", belief["tags"])

        # Check metadata
        self.assertEqual(belief["metadata"]["extraction_method"], "belief_metabolism")
        self.assertEqual(belief["metadata"]["source_memory_type"], "semantic")

        # Check timestamps
        self.assertIn("created_at", belief)
        self.assertIn("extraction_timestamp", belief["metadata"])

    def test_jsonlog(self):
        """Test JSON logging functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Patch the logs directory
            with (
                patch("memory.belief_utils.os.makedirs"),
                patch(
                    "memory.belief_utils.os.path.join",
                    return_value=f"{temp_dir}/test.jsonl",
                ),
            ):

                record = {"decision": "accept", "belief_id": "test123", "score": 0.85}

                jsonlog(record)

                # Read back the log
                with open(f"{temp_dir}/test.jsonl", "r") as f:
                    logged = json.loads(f.readline())

                self.assertEqual(logged["decision"], "accept")
                self.assertEqual(logged["belief_id"], "test123")
                self.assertEqual(logged["score"], 0.85)
                self.assertIn("timestamp", logged)


class TestBeliefReflectionSession(unittest.TestCase):
    """Test belief reflection session functionality."""

    def setUp(self):
        """Set up test environment."""
        self.session = BeliefReflectionSession(dry_run=True, limit=10)

    def test_health_check_success(self):
        """Test successful health checks."""
        mock_session = MagicMock()
        self.session.session = mock_session

        # Mock successful responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        result = self.session.health_check()
        self.assertTrue(result)

        # Verify both endpoints were checked
        self.assertEqual(mock_session.get.call_count, 2)

    def test_health_check_failure(self):
        """Test health check failure."""
        mock_session = MagicMock()
        self.session.session = mock_session

        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.get.return_value = mock_response

        result = self.session.health_check()
        self.assertFalse(result)

    def test_belief_exists_check(self):
        """Test belief existence checking."""
        with patch.object(self.session, "session") as mock_session:
            # Test existing belief (200 response)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.head.return_value = mock_response

            exists = self.session._belief_exists("test_belief_id")
            self.assertTrue(exists)

            # Test non-existing belief (404 response)
            mock_response.status_code = 404
            mock_session.head.return_value = mock_response

            exists = self.session._belief_exists("nonexistent_id")
            self.assertFalse(exists)

    def test_shadow_mode_no_ingestion(self):
        """Test that shadow mode doesn't actually ingest beliefs."""
        beliefs = [
            {"id": "test_belief_1", "content": "Test belief content", "confidence": 0.8}
        ]

        with patch("memory.belief_reflection.jsonlog") as mock_jsonlog:
            self.session.ingest_beliefs(beliefs)

            # Should have logged shadow ingest
            mock_jsonlog.assert_called()
            call_args = mock_jsonlog.call_args[0][0]
            self.assertEqual(call_args["action"], "shadow_ingest")
            self.assertEqual(call_args["belief_id"], "test_belief_1")

    def test_extract_beliefs_deduplication(self):
        """Test that existing beliefs are properly deduplicated."""
        memories = [
            {
                "id": "mem1",
                "content": "I believe that testing is important for software quality.",
                "memoryType": "semantic",
            }
        ]

        with patch.object(self.session, "_belief_exists", return_value=True):
            beliefs = self.session.extract_beliefs(memories)

            # Should be empty due to deduplication
            self.assertEqual(len(beliefs), 0)
            self.assertEqual(self.session.stats["beliefs_deduped"], 1)


class TestLockingMechanism(unittest.TestCase):
    """Test the locking mechanism for concurrent runs."""

    def setUp(self):
        """Set up test environment."""
        # Use temporary lock file for testing
        self.temp_lock = tempfile.NamedTemporaryFile(delete=False)
        self.temp_lock.close()

        # Patch the LOCK_FILE constant
        self.lock_patcher = patch(
            "memory.belief_reflection.LOCK_FILE", self.temp_lock.name
        )
        self.lock_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.lock_patcher.stop()
        try:
            os.unlink(self.temp_lock.name)
        except OSError:
            pass

    def test_acquire_release_lock(self):
        """Test lock acquisition and release."""
        # Import inside test to respect patching
        from memory.belief_reflection import acquire_lock, release_lock

        # Should be able to acquire lock
        self.assertTrue(acquire_lock())

        # Should not be able to acquire again
        self.assertFalse(acquire_lock())

        # After release, should be able to acquire again
        release_lock()
        self.assertTrue(acquire_lock())

        # Clean up
        release_lock()

    def test_stale_lock_removal(self):
        """Test that stale locks are properly removed."""
        # Create a stale lock file
        with open(self.temp_lock.name, "w") as f:
            f.write("pid:999\nstarted:2020-01-01T00:00:00Z\n")

        # Set old modification time (way older than max runtime)
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(self.temp_lock.name, (old_time, old_time))

        # Should be able to acquire (stale lock removed)
        self.assertTrue(acquire_lock())

        # Clean up
        release_lock()


class TestConfigurationBehavior(unittest.TestCase):
    """Test configuration-driven behavior."""

    def test_disabled_extraction(self):
        """Test that disabled extraction returns appropriate status."""
        with patch.dict(os.environ, {"BELIEF_EXTRACT_ENABLED": "false"}):
            from memory.belief_reflection import run_once

            result = run_once(dry_run=False)
            self.assertEqual(result["status"], "disabled")

    def test_required_phrases_configuration(self):
        """Test that required phrases can be configured."""
        custom_phrases = "I am certain,My conviction is"

        with patch.dict(os.environ, {"BELIEF_REQUIRED_PHRASES": custom_phrases}):
            # Reload the module to pick up new config
            import importlib

            from memory import belief_utils

            importlib.reload(belief_utils)

            memory = {
                "id": "test",
                "content": "My conviction is that this should be detected as a belief candidate.",
                "memoryType": "semantic",
            }

            self.assertTrue(belief_utils.is_belief_candidate(memory))


if __name__ == "__main__":
    # Ensure logs directory exists for tests
    os.makedirs("/workspace/logs", exist_ok=True)

    unittest.main(verbosity=2)
