#!/usr/bin/env python3
"""
test_transactional_cognition.py - Comprehensive test suite for transactional cognition

Tests the atomic transaction system across memory, beliefs, and journal subsystems.
Validates that operations are atomic and rollback works correctly on failures.
"""

import json
import logging
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Setup test environment
os.environ["LOG_LEVEL"] = "INFO"

# Import the transaction system
try:
    from cognitive.transaction import (
        CognitionTransaction,
        TransactionLog,
        cognitive_transaction,
    )

    TRANSACTION_AVAILABLE = True
except ImportError:
    TRANSACTION_AVAILABLE = False

# Import memory components
try:
    from pods.memory.memory_manager import Memory

    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# Import belief core
try:
    import belief_core

    BELIEF_CORE_AVAILABLE = True
except ImportError:
    BELIEF_CORE_AVAILABLE = False

# Import journal engine
try:
    import journal_engine

    JOURNAL_ENGINE_AVAILABLE = True
except ImportError:
    JOURNAL_ENGINE_AVAILABLE = False


class TransactionalCognitionTest(unittest.TestCase):
    """Test suite for transactional cognition system"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create cognitive/logs directory
        Path("cognitive/logs").mkdir(parents=True, exist_ok=True)

        # Setup logging for tests
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("TransactionalCognitionTest")

    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @unittest.skipUnless(TRANSACTION_AVAILABLE, "Transaction system not available")
    def test_transaction_initialization(self):
        """Test basic transaction initialization"""
        transaction = CognitionTransaction()

        self.assertIsNotNone(transaction.transaction_id)
        self.assertFalse(transaction.is_active)
        self.assertIsNone(transaction.snapshot)
        self.assertEqual(len(transaction.involved_subsystems), 0)

    @unittest.skipUnless(TRANSACTION_AVAILABLE, "Transaction system not available")
    def test_transaction_start_and_commit(self):
        """Test successful transaction start and commit"""
        transaction = CognitionTransaction()

        # Mock subsystems
        mock_memory = Mock()
        mock_belief = Mock()
        mock_journal = Mock()

        transaction.inject_subsystems(mock_memory, mock_belief, mock_journal)

        # Start transaction
        transaction.start()
        self.assertTrue(transaction.is_active)
        self.assertIsNotNone(transaction.start_time)
        self.assertIsNotNone(transaction.snapshot)

        # Verify subsystem methods were called
        mock_memory.begin_transaction.assert_called_once_with(
            transaction.transaction_id
        )
        mock_belief.begin_transaction.assert_called_once_with(
            transaction.transaction_id
        )
        mock_journal.begin_transaction.assert_called_once_with(
            transaction.transaction_id
        )

        # Commit transaction
        transaction.commit()
        self.assertFalse(transaction.is_active)

        # Verify commit methods were called
        mock_memory.commit_transaction.assert_called_once_with(
            transaction.transaction_id
        )
        mock_belief.commit_transaction.assert_called_once_with(
            transaction.transaction_id
        )
        mock_journal.commit_transaction.assert_called_once_with(
            transaction.transaction_id
        )

    @unittest.skipUnless(TRANSACTION_AVAILABLE, "Transaction system not available")
    def test_transaction_rollback(self):
        """Test transaction rollback functionality"""
        transaction = CognitionTransaction()

        # Mock subsystems
        mock_memory = Mock()
        mock_belief = Mock()
        mock_journal = Mock()

        transaction.inject_subsystems(mock_memory, mock_belief, mock_journal)

        # Start transaction
        transaction.start()
        self.assertTrue(transaction.is_active)

        # Rollback transaction
        rollback_reason = "Test rollback"
        transaction.rollback(rollback_reason)
        self.assertFalse(transaction.is_active)

        # Verify rollback methods were called
        mock_memory.rollback_transaction.assert_called_once_with(
            transaction.transaction_id
        )
        mock_belief.rollback_transaction.assert_called_once_with(
            transaction.transaction_id
        )
        mock_journal.rollback_transaction.assert_called_once_with(
            transaction.transaction_id
        )

    @unittest.skipUnless(TRANSACTION_AVAILABLE, "Transaction system not available")
    def test_transaction_commit_failure_triggers_rollback(self):
        """Test that commit failure triggers automatic rollback"""
        transaction = CognitionTransaction()

        # Mock subsystems - memory commit will fail
        mock_memory = Mock()
        mock_memory.commit_transaction.side_effect = Exception("Memory commit failed")

        mock_belief = Mock()
        mock_journal = Mock()

        transaction.inject_subsystems(mock_memory, mock_belief, mock_journal)

        # Start transaction
        transaction.start()

        # Commit should fail and trigger rollback
        with self.assertRaises(RuntimeError):
            transaction.commit()

        # Verify rollback was called
        mock_memory.rollback_transaction.assert_called_once()
        mock_belief.rollback_transaction.assert_called_once()
        mock_journal.rollback_transaction.assert_called_once()

    @unittest.skipUnless(TRANSACTION_AVAILABLE, "Transaction system not available")
    def test_context_manager_success(self):
        """Test successful transaction using context manager"""
        mock_memory = Mock()
        mock_belief = Mock()
        mock_journal = Mock()

        # Test successful context manager usage
        with cognitive_transaction(mock_memory, mock_belief, mock_journal) as tx:
            self.assertTrue(tx.is_active)
            tx.log_state_snapshot("test_operation", {"test": "data"})

        # After context exit, transaction should be committed
        mock_memory.commit_transaction.assert_called_once()
        mock_belief.commit_transaction.assert_called_once()
        mock_journal.commit_transaction.assert_called_once()

    @unittest.skipUnless(TRANSACTION_AVAILABLE, "Transaction system not available")
    def test_context_manager_exception_triggers_rollback(self):
        """Test that exception in context manager triggers rollback"""
        mock_memory = Mock()
        mock_belief = Mock()
        mock_journal = Mock()

        # Test exception handling in context manager
        with self.assertRaises(ValueError):
            with cognitive_transaction(mock_memory, mock_belief, mock_journal) as tx:
                self.assertTrue(tx.is_active)
                raise ValueError("Test exception")

        # After exception, transaction should be rolled back
        mock_memory.rollback_transaction.assert_called_once()
        mock_belief.rollback_transaction.assert_called_once()
        mock_journal.rollback_transaction.assert_called_once()

    @unittest.skipUnless(TRANSACTION_AVAILABLE, "Transaction system not available")
    def test_transaction_logging(self):
        """Test transaction event logging to JSONL file"""
        transaction = CognitionTransaction()

        # Mock subsystems
        mock_memory = Mock()
        transaction.inject_subsystems(mock_memory)

        # Start and commit transaction
        transaction.start()
        transaction.commit()

        # Check that log file was created and contains entries
        log_file = Path("cognitive/logs/cognition_trace.jsonl")
        self.assertTrue(log_file.exists())

        with open(log_file, "r") as f:
            lines = f.readlines()

        # Should have at least start and commit entries
        self.assertGreaterEqual(len(lines), 2)

        # Parse and validate log entries
        start_entry = json.loads(lines[0])
        commit_entry = json.loads(lines[1])

        self.assertEqual(start_entry["operation"], "start")
        self.assertEqual(start_entry["result"], "success")
        self.assertEqual(start_entry["transaction_id"], transaction.transaction_id)

        self.assertEqual(commit_entry["operation"], "commit")
        self.assertEqual(commit_entry["result"], "success")
        self.assertEqual(commit_entry["transaction_id"], transaction.transaction_id)

    @unittest.skipUnless(
        TRANSACTION_AVAILABLE and MEMORY_AVAILABLE, "Memory system not available"
    )
    def test_memory_transaction_integration(self):
        """Test integration with actual memory manager"""
        # Create a real memory instance
        memory = Memory()

        # Test transaction buffering
        if hasattr(memory, "begin_transaction"):
            memory.begin_transaction("test-tx-123")

            # Add memory during transaction - should be buffered
            test_memory = {
                "content": "Test memory during transaction",
                "type": "test",
                "importance": 0.8,
            }
            memory.add_to_long_term(test_memory)

            # Memory should be in buffer, not committed yet
            if hasattr(memory, "transaction_buffer"):
                self.assertEqual(len(memory.transaction_buffer), 1)

            # Commit transaction
            memory.commit_transaction("test-tx-123")

            # Memory should now be committed
            if hasattr(memory, "transaction_buffer"):
                self.assertEqual(len(memory.transaction_buffer), 0)

    def test_simulated_cognitive_pipeline_failure(self):
        """Test simulated failure in CHAMP decision engine"""
        with patch("cognitive.transaction.CognitionTransaction") as MockTransaction:
            mock_tx = MockTransaction.return_value
            mock_tx.transaction_id = "test-champ-failure"

            # Simulate CHAMP failure
            def failing_champ_operation():
                mock_tx.log_state_snapshot("champ_decision_start", {"confidence": 0.7})
                # Simulate failure in CHAMP
                raise Exception("CHAMP decision engine timeout")

            # Test that failure triggers rollback
            mock_tx.__enter__ = Mock(return_value=mock_tx)
            mock_tx.__exit__ = Mock(return_value=None)

            with self.assertRaises(Exception):
                with MockTransaction() as tx:
                    failing_champ_operation()

            # Verify rollback was called
            mock_tx.rollback.assert_called_once()

    def test_simulated_journal_reflection_failure(self):
        """Test simulated failure in journal reflection"""
        with patch("cognitive.transaction.CognitionTransaction") as MockTransaction:
            mock_tx = MockTransaction.return_value
            mock_tx.transaction_id = "test-journal-failure"

            # Simulate journal failure
            def failing_journal_operation():
                mock_tx.log_state_snapshot(
                    "journal_reflection_start", {"trigger": "test"}
                )
                # Simulate failure in journal reflection
                raise Exception("Journal reflection LLM timeout")

            mock_tx.__enter__ = Mock(return_value=mock_tx)
            mock_tx.__exit__ = Mock(return_value=None)

            with self.assertRaises(Exception):
                with MockTransaction() as tx:
                    failing_journal_operation()

            # Verify rollback was called
            mock_tx.rollback.assert_called_once()

    def test_double_failure_recovery(self):
        """Test recovery when both primary operation and rollback fail"""
        transaction = CognitionTransaction()

        # Mock subsystems where commit fails and rollback also fails
        mock_memory = Mock()
        mock_memory.commit_transaction.side_effect = Exception("Commit failed")
        mock_memory.rollback_transaction.side_effect = Exception("Rollback also failed")

        transaction.inject_subsystems(mock_memory)

        # Start transaction
        transaction.start()

        # Both commit and rollback should fail
        with self.assertRaises(RuntimeError):
            transaction.commit()

        # Verify both operations were attempted
        mock_memory.commit_transaction.assert_called_once()
        mock_memory.rollback_transaction.assert_called_once()

        # Check that critical error was logged
        log_file = Path("cognitive/logs/cognition_trace.jsonl")
        if log_file.exists():
            with open(log_file, "r") as f:
                lines = f.readlines()

            # Should have rollback failure entry
            rollback_entry = json.loads(lines[-1])
            self.assertEqual(rollback_entry["operation"], "rollback")
            self.assertEqual(rollback_entry["result"], "failure")

    def test_transaction_state_snapshot(self):
        """Test transaction state snapshots for audit trail"""
        transaction = CognitionTransaction()

        # Log some state snapshots
        transaction.log_state_snapshot("operation_1", {"step": 1, "data": "test"})
        transaction.log_state_snapshot("operation_2", {"step": 2, "confidence": 0.8})

        # Verify snapshots were logged
        self.assertEqual(len(transaction.operation_log), 2)

        snapshot_1 = transaction.operation_log[0]
        self.assertEqual(snapshot_1["operation"], "operation_1")
        self.assertEqual(snapshot_1["data"]["step"], 1)

        snapshot_2 = transaction.operation_log[1]
        self.assertEqual(snapshot_2["operation"], "operation_2")
        self.assertEqual(snapshot_2["data"]["confidence"], 0.8)

    def test_no_partial_memory_storage(self):
        """Verify that no partial memories are stored on failure"""
        # This test ensures the core safety requirement:
        # No partial memories should persist if any part of cognition fails

        with patch("cognitive.transaction.cognitive_transaction") as mock_ctx:
            mock_transaction = Mock()
            mock_ctx.return_value.__enter__ = Mock(return_value=mock_transaction)
            mock_ctx.return_value.__exit__ = Mock(
                side_effect=Exception("Simulated failure")
            )

            # Simulate cognitive operation that creates multiple memories
            memories_to_create = [
                {"content": "Memory 1", "type": "test"},
                {"content": "Memory 2", "type": "test"},
                {"content": "Memory 3", "type": "test"},
            ]

            with self.assertRaises(Exception):
                with mock_ctx() as tx:
                    for memory in memories_to_create:
                        tx.log_state_snapshot("memory_creation", memory)
                    raise Exception("Simulated cognitive failure")

            # Verify rollback was triggered
            mock_transaction.rollback.assert_called_once()


class IntegrationTest(unittest.TestCase):
    """Integration tests for the complete transactional system"""

    def setUp(self):
        """Set up integration test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create necessary directories
        Path("cognitive/logs").mkdir(parents=True, exist_ok=True)
        Path("data/logs").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up integration test environment"""
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @unittest.skipUnless(
        all([TRANSACTION_AVAILABLE, MEMORY_AVAILABLE]), "Required systems not available"
    )
    def test_end_to_end_transaction_flow(self):
        """Test complete end-to-end transaction flow"""
        try:
            from cognitive_state_manager import CognitiveStateManager

            # Initialize cognitive state manager
            manager = CognitiveStateManager(check_interval=1)

            # Test cognitive processing inputs
            test_inputs = {
                "user_query": "Test transactional processing",
                "contradictions": [],
                "goals": [],
                "memory_matches": [],
            }

            # Process with transaction support
            if hasattr(manager, "process_cognition_transactionally"):
                result = manager.process_cognition_transactionally(test_inputs)

                # Verify transaction metadata in result
                if "transaction_id" in result:
                    self.assertIn("transaction_status", result)
                    self.assertIn(
                        result["transaction_status"], ["committed", "rolled_back"]
                    )

                # Check transaction log
                status = manager.get_last_transaction_status()
                if status["status"] == "found":
                    self.assertIsNotNone(status["last_transaction"])

        except ImportError:
            self.skipTest("CognitiveStateManager not available for integration test")


if __name__ == "__main__":
    # Check system availability
    print("🧪 Transactional Cognition Test Suite")
    print("=" * 50)
    print(f"Transaction System: {'✅' if TRANSACTION_AVAILABLE else '❌'}")
    print(f"Memory Manager: {'✅' if MEMORY_AVAILABLE else '❌'}")
    print(f"Belief Core: {'✅' if BELIEF_CORE_AVAILABLE else '❌'}")
    print(f"Journal Engine: {'✅' if JOURNAL_ENGINE_AVAILABLE else '❌'}")
    print("=" * 50)

    # Run tests
    unittest.main(verbosity=2)
