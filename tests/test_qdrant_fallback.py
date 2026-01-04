#!/usr/bin/env python3
"""
test_qdrant_fallback.py - Comprehensive tests for Qdrant fallback system

Tests the memory manager's ability to:
1. Detect Qdrant failures and enter fallback mode
2. Store memories in fallback cache when Qdrant is unavailable
3. Automatically resync when Qdrant becomes available again
4. Maintain operational continuity during outages
5. Prevent beliefs from forming from fallback-only data
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the modules we're testing
from pods.memory.memory_manager import FallbackMemoryStore, Memory
from pods.memory.memory_types import MemoryType


class TestQdrantFallback(unittest.TestCase):
    """Test suite for Qdrant fallback functionality"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.original_memory_file = os.environ.get("MEMORY_FILE")
        self.test_memory_file = os.path.join(self.test_dir, "test_memory.json")
        self.test_fallback_db = os.path.join(self.test_dir, "test_fallback.db")

        # Set environment variables for testing
        os.environ["MEMORY_FILE"] = self.test_memory_file
        os.environ["USE_QDRANT_BACKEND"] = "true"
        os.environ["LOG_LEVEL"] = "DEBUG"

    def tearDown(self):
        """Clean up test environment"""
        # Restore original environment
        if self.original_memory_file:
            os.environ["MEMORY_FILE"] = self.original_memory_file
        else:
            os.environ.pop("MEMORY_FILE", None)

        # Clean up test directory
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_fallback_store_initialization(self):
        """Test that FallbackMemoryStore initializes correctly"""
        store = FallbackMemoryStore(db_path=self.test_fallback_db)

        self.assertFalse(store.is_fallback_mode)
        self.assertIsNone(store.fallback_start_time)
        self.assertEqual(len(store.fallback_memories), 0)

        # Check that SQLite database was created
        self.assertTrue(os.path.exists(self.test_fallback_db))

        # Verify database schema
        with sqlite3.connect(self.test_fallback_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='fallback_memories'"
            )
            self.assertIsNotNone(cursor.fetchone())

    def test_enter_exit_fallback_mode(self):
        """Test entering and exiting fallback mode"""
        store = FallbackMemoryStore(db_path=self.test_fallback_db)

        # Enter fallback mode
        store.enter_fallback_mode("Test reason")
        self.assertTrue(store.is_fallback_mode)
        self.assertIsNotNone(store.fallback_start_time)

        # Get duration
        duration = store.get_fallback_duration()
        self.assertIsNotNone(duration)
        self.assertGreater(duration.total_seconds(), 0)

        # Exit fallback mode
        store.exit_fallback_mode("Test recovery")
        self.assertFalse(store.is_fallback_mode)
        self.assertIsNone(store.fallback_start_time)
        self.assertIsNone(store.get_fallback_duration())

    def test_store_fallback_memory(self):
        """Test storing memories in fallback mode"""
        store = FallbackMemoryStore(db_path=self.test_fallback_db)
        store.enter_fallback_mode("Test outage")

        # Create test memory
        test_memory = {
            "content": "Test memory content",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "test",
            "memory_type": "semantic",
            "confidence": 0.8,
        }

        # Store in fallback
        memory_id = store.store_fallback_memory(test_memory)
        self.assertIsNotNone(memory_id)

        # Verify memory was stored
        fallback_memories = store.get_fallback_memories()
        self.assertEqual(len(fallback_memories), 1)

        stored_memory = fallback_memories[0]
        self.assertEqual(stored_memory["content"], test_memory["content"])
        self.assertEqual(stored_memory["memory_type"], "fallback")
        self.assertEqual(stored_memory["confidence"], 0.0)
        self.assertTrue(stored_memory["metadata"]["fallback"])

        # Verify persistence to SQLite
        with sqlite3.connect(self.test_fallback_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM fallback_memories")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)

    def test_qdrant_failure_detection(self):
        """Test detection of various Qdrant failure scenarios"""
        with patch("pods.memory.memory_manager.QDRANT_BACKEND_AVAILABLE", True):
            with patch(
                "pods.memory.memory_manager.MemoryBackendFactory"
            ) as mock_factory:
                # Mock a connection error during initialization
                mock_factory.create_backend.side_effect = ConnectionError(
                    "Connection refused"
                )

                memory = Memory()

                # Should be in fallback mode due to initialization failure
                self.assertTrue(memory.is_fallback_mode())

    def test_memory_storage_with_qdrant_failure(self):
        """Test memory storage when Qdrant fails"""
        with patch("pods.memory.memory_manager.QDRANT_BACKEND_AVAILABLE", True):
            with patch(
                "pods.memory.memory_manager.MemoryBackendFactory"
            ) as mock_factory:
                # Create mock backend that fails on store_memory
                mock_backend = Mock()
                mock_backend.health_check.return_value = True
                mock_backend.initialize.return_value = True
                mock_backend.store_memory.side_effect = ConnectionError(
                    "Qdrant unavailable"
                )

                mock_factory.create_backend.return_value = mock_backend

                memory = Memory()

                # Should not be in fallback mode initially
                self.assertFalse(memory.is_fallback_mode())

                # Store a memory - this should trigger fallback mode
                test_memory = {
                    "content": "Test memory during outage",
                    "source": "test",
                    "type": "memory",
                }

                memory_id = memory.store(test_memory)

                # Should now be in fallback mode
                self.assertTrue(memory.is_fallback_mode())

                # Should have fallback memory stored
                fallback_memories = memory.fallback_store.get_fallback_memories()
                self.assertGreater(len(fallback_memories), 0)

    def test_automatic_resync_on_recovery(self):
        """Test automatic resync when Qdrant becomes available again"""
        with patch("pods.memory.memory_manager.QDRANT_BACKEND_AVAILABLE", True):
            with patch(
                "pods.memory.memory_manager.MemoryBackendFactory"
            ) as mock_factory:
                # Create mock backend
                mock_backend = Mock()
                mock_backend.health_check.return_value = True
                mock_backend.initialize.return_value = True
                mock_backend.store_memory.return_value = "test-id-123"

                mock_factory.create_backend.return_value = mock_backend

                memory = Memory()

                # Manually enter fallback mode and store some memories
                memory.fallback_store.enter_fallback_mode("Test outage")

                test_memories = [
                    {"content": "Memory 1", "source": "test", "type": "memory"},
                    {"content": "Memory 2", "source": "test", "type": "memory"},
                    {"content": "Memory 3", "source": "test", "type": "memory"},
                ]

                for mem in test_memories:
                    memory.fallback_store.store_fallback_memory(mem)

                # Verify fallback memories exist
                self.assertEqual(len(memory.fallback_store.get_fallback_memories()), 3)

                # Simulate Qdrant recovery by attempting sync
                memory.memory_backend = mock_backend  # Restore backend
                memory._attempt_fallback_sync()

                # Should have exited fallback mode and cleared cache
                self.assertFalse(memory.is_fallback_mode())
                self.assertEqual(len(memory.fallback_store.get_fallback_memories()), 0)

                # Verify store_memory was called for each fallback memory
                self.assertEqual(mock_backend.store_memory.call_count, 3)

    def test_fallback_memory_metadata(self):
        """Test that fallback memories have correct metadata"""
        store = FallbackMemoryStore(db_path=self.test_fallback_db)
        store.enter_fallback_mode("Test outage")

        original_memory = {
            "content": "Original memory",
            "memory_type": "semantic",
            "confidence": 0.9,
            "source": "test",
        }

        memory_id = store.store_fallback_memory(original_memory)
        fallback_memories = store.get_fallback_memories()
        stored_memory = fallback_memories[0]

        # Verify fallback metadata
        self.assertEqual(stored_memory["memory_type"], "fallback")
        self.assertEqual(stored_memory["confidence"], 0.0)
        self.assertTrue(stored_memory["metadata"]["fallback"])
        self.assertIn("fallback_timestamp", stored_memory["metadata"])

        # Original information should be preserved in metadata
        # (This would be added by _store_in_fallback method)

    def test_long_fallback_mode_warning(self):
        """Test warning for extended fallback mode"""
        store = FallbackMemoryStore(db_path=self.test_fallback_db)

        # Set fallback start time to 15 minutes ago
        store.is_fallback_mode = True
        store.fallback_start_time = datetime.now(timezone.utc) - timedelta(minutes=15)

        # Should trigger warning for threshold > 10 minutes
        is_long_fallback = store.check_long_fallback_mode(threshold_minutes=10)
        self.assertTrue(is_long_fallback)

        # Should not trigger warning for threshold > 20 minutes
        is_long_fallback = store.check_long_fallback_mode(threshold_minutes=20)
        self.assertFalse(is_long_fallback)

    def test_fallback_memory_type_properties(self):
        """Test that FALLBACK memory type has correct properties"""
        from pods.memory.memory_types import MemoryType, get_storage_characteristics

        # Test that FALLBACK type exists
        self.assertTrue(hasattr(MemoryType, "FALLBACK"))

        # Test storage characteristics
        characteristics = get_storage_characteristics(MemoryType.FALLBACK)

        self.assertEqual(characteristics["storage_layer"], "fallback_cache")
        self.assertEqual(characteristics["priority_multiplier"], 0.0)
        self.assertTrue(characteristics["containment"])
        self.assertTrue(characteristics["temporary"])
        self.assertTrue(characteristics["fallback_mode"])

    def test_fallback_memories_not_used_for_beliefs(self):
        """Test that fallback memories cannot be promoted to beliefs"""
        # This test ensures the safety constraint that fallback memories
        # should never be used to form beliefs

        store = FallbackMemoryStore(db_path=self.test_fallback_db)
        store.enter_fallback_mode("Test outage")

        # Store a memory that might normally become a belief
        belief_like_memory = {
            "content": "I believe this is an important principle",
            "type": "belief",
            "confidence": 0.9,
            "source": "reasoning",
        }

        memory_id = store.store_fallback_memory(belief_like_memory)
        fallback_memories = store.get_fallback_memories()
        stored_memory = fallback_memories[0]

        # Even though original was marked as belief, stored version should be fallback
        self.assertEqual(stored_memory["memory_type"], "fallback")
        self.assertEqual(stored_memory["confidence"], 0.0)
        self.assertTrue(stored_memory["metadata"]["fallback"])

    def test_concurrent_fallback_operations(self):
        """Test thread safety of fallback operations"""
        store = FallbackMemoryStore(db_path=self.test_fallback_db)
        store.enter_fallback_mode("Concurrent test")

        def store_memory_worker(worker_id):
            for i in range(5):
                memory = {
                    "content": f"Worker {worker_id} memory {i}",
                    "source": f"worker_{worker_id}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                store.store_fallback_memory(memory)

        # Start multiple threads storing memories concurrently
        threads = []
        for worker_id in range(3):
            thread = threading.Thread(target=store_memory_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have 15 memories total (3 workers × 5 memories each)
        fallback_memories = store.get_fallback_memories()
        self.assertEqual(len(fallback_memories), 15)

        # Verify database consistency
        with sqlite3.connect(self.test_fallback_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM fallback_memories")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 15)

    def test_fallback_persistence_across_restarts(self):
        """Test that fallback memories persist across application restarts"""
        # Create and populate fallback store
        store1 = FallbackMemoryStore(db_path=self.test_fallback_db)
        store1.enter_fallback_mode("Test persistence")

        test_memory = {"content": "Persistent memory", "source": "persistence_test"}

        memory_id = store1.store_fallback_memory(test_memory)

        # Simulate application restart by creating new store instance
        store2 = FallbackMemoryStore(db_path=self.test_fallback_db)

        # Should load the previously stored memory
        fallback_memories = store2.get_fallback_memories()
        self.assertEqual(len(fallback_memories), 1)
        self.assertEqual(fallback_memories[0]["content"], "Persistent memory")

    def test_partial_sync_failure_handling(self):
        """Test handling of partial sync failures"""
        with patch("pods.memory.memory_manager.QDRANT_BACKEND_AVAILABLE", True):
            with patch(
                "pods.memory.memory_manager.MemoryBackendFactory"
            ) as mock_factory:
                # Create mock backend that fails on some operations
                mock_backend = Mock()
                mock_backend.health_check.return_value = True
                mock_backend.initialize.return_value = True

                # Make it fail on second memory
                def failing_store_memory(memory):
                    if "Memory 2" in memory.get("content", ""):
                        raise ConnectionError("Partial failure")
                    return "success-id"

                mock_backend.store_memory.side_effect = failing_store_memory
                mock_factory.create_backend.return_value = mock_backend

                memory = Memory()

                # Store test memories in fallback
                memory.fallback_store.enter_fallback_mode("Test partial sync")
                memory.fallback_store.store_fallback_memory(
                    {"content": "Memory 1", "source": "test"}
                )
                memory.fallback_store.store_fallback_memory(
                    {"content": "Memory 2", "source": "test"}
                )
                memory.fallback_store.store_fallback_memory(
                    {"content": "Memory 3", "source": "test"}
                )

                # Attempt sync
                memory.memory_backend = mock_backend
                memory._attempt_fallback_sync()

                # Should still have the failed memory in fallback cache
                remaining_memories = memory.fallback_store.get_fallback_memories()
                self.assertGreater(len(remaining_memories), 0)

                # Should still be in fallback mode due to partial failure
                self.assertTrue(memory.is_fallback_mode())


class TestFallbackSafetyConstraints(unittest.TestCase):
    """Test suite for fallback system safety constraints"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_fallback_db = os.path.join(self.test_dir, "test_fallback.db")

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_fallback_memories_zero_confidence(self):
        """Test that all fallback memories have zero confidence"""
        store = FallbackMemoryStore(db_path=self.test_fallback_db)
        store.enter_fallback_mode("Safety test")

        # Store memory with high confidence
        high_confidence_memory = {
            "content": "High confidence memory",
            "confidence": 0.95,
            "importance": 0.8,
        }

        memory_id = store.store_fallback_memory(high_confidence_memory)
        fallback_memories = store.get_fallback_memories()
        stored_memory = fallback_memories[0]

        # Should be forced to zero confidence
        self.assertEqual(stored_memory["confidence"], 0.0)

    def test_fallback_memory_containment(self):
        """Test that fallback memories are properly contained"""
        from pods.memory.memory_types import MemoryType, get_storage_characteristics

        characteristics = get_storage_characteristics(MemoryType.FALLBACK)

        # Should be marked for containment
        self.assertTrue(characteristics.get("containment", False))

        # Should not be used for belief formation
        self.assertEqual(characteristics.get("priority_multiplier", 1.0), 0.0)

    def test_fallback_memories_not_in_normal_retrieval(self):
        """Test that fallback memories don't appear in normal retrieval operations"""
        from pods.memory.memory_types import MemoryType, get_retrieval_priorities

        # Fallback memories should have zero retrieval priority
        priorities = get_retrieval_priorities("test query")
        self.assertEqual(priorities[MemoryType.FALLBACK], 0.0)


if __name__ == "__main__":
    # Create data directory if it doesn't exist
    os.makedirs("data/logs", exist_ok=True)

    # Run tests
    unittest.main(verbosity=2)
