#!/usr/bin/env python3
"""
Unit tests for reflection prompt injection in journal engine.
Tests that diagnostic reflection prompts are properly integrated into journal entries.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from journal_engine import generate_journal_entry


class TestJournalReflectionPrompts(unittest.TestCase):
    """Test reflection prompt injection into journal entries."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test logs
        self.test_dir = tempfile.mkdtemp()
        self.original_log_dir = os.environ.get("LOG_DIR")
        os.environ["LOG_DIR"] = self.test_dir

        # Enable reflection prompts for testing
        self.original_enable_prompts = os.environ.get("ENABLE_REFLECTION_PROMPTS")
        os.environ["ENABLE_REFLECTION_PROMPTS"] = "1"

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        if self.original_log_dir:
            os.environ["LOG_DIR"] = self.original_log_dir
        elif "LOG_DIR" in os.environ:
            del os.environ["LOG_DIR"]

        if self.original_enable_prompts:
            os.environ["ENABLE_REFLECTION_PROMPTS"] = self.original_enable_prompts
        elif "ENABLE_REFLECTION_PROMPTS" in os.environ:
            del os.environ["ENABLE_REFLECTION_PROMPTS"]

        # Clean up temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("journal_engine.get_reflection_prompts")
    @patch("journal_engine.JournalMemoryAdapter")
    @patch("journal_engine._llm_reflection")
    @patch("journal_engine.Memory")
    @patch("journal_engine.log")
    async def test_reflection_prompts_injected_when_available(
        self,
        mock_log,
        mock_memory,
        mock_llm_reflection,
        mock_memory_adapter,
        mock_get_reflection_prompts,
    ):
        """Test that reflection prompts are injected when available."""

        # Mock reflection prompts
        test_prompts = [
            "What patterns do I notice in my recent cognitive processes?",
            "Are there any beliefs that seem inconsistent?",
            "What goals deserve more attention?",
        ]
        mock_get_reflection_prompts.return_value = test_prompts

        # Mock memory adapter
        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.get_recent.return_value = [
            {
                "id": "test1",
                "content": "Test memory 1",
                "timestamp": "2025-01-01T10:00:00Z",
            },
            {
                "id": "test2",
                "content": "Test memory 2",
                "timestamp": "2025-01-01T11:00:00Z",
            },
        ]
        mock_memory_adapter.return_value = mock_adapter_instance

        # Mock LLM response
        mock_llm_reflection.return_value = (
            "This is a test journal entry reflecting on recent experiences."
        )

        # Mock memory storage
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance

        # Call the function
        result = await generate_journal_entry(triggered_by="test")

        # Verify the function was called and prompts were requested
        mock_get_reflection_prompts.assert_called_once()

        # Verify logging occurred
        mock_log.info.assert_any_call("🪞 Injected 3 reflection prompts into journal.")

        # Check that the result indicates success
        self.assertEqual(result["status"], "success")

        # Verify that the journal entry contains the prompts
        journal_entry = result["entry"]
        journal_content = journal_entry["content"]

        self.assertIn("🪞 **Self-Reflection Prompts**", journal_content)
        self.assertIn(
            "1. What patterns do I notice in my recent cognitive processes?",
            journal_content,
        )
        self.assertIn(
            "2. Are there any beliefs that seem inconsistent?", journal_content
        )
        self.assertIn("3. What goals deserve more attention?", journal_content)

    @patch("journal_engine.get_reflection_prompts")
    @patch("journal_engine.JournalMemoryAdapter")
    @patch("journal_engine._llm_reflection")
    @patch("journal_engine.Memory")
    @patch("journal_engine.log")
    async def test_reflection_prompts_skipped_when_unavailable(
        self,
        mock_log,
        mock_memory,
        mock_llm_reflection,
        mock_memory_adapter,
        mock_get_reflection_prompts,
    ):
        """Test that journal works normally when no reflection prompts are available."""

        # Mock no reflection prompts
        mock_get_reflection_prompts.return_value = None

        # Mock memory adapter
        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.get_recent.return_value = [
            {
                "id": "test1",
                "content": "Test memory 1",
                "timestamp": "2025-01-01T10:00:00Z",
            }
        ]
        mock_memory_adapter.return_value = mock_adapter_instance

        # Mock LLM response
        test_journal_content = (
            "This is a test journal entry reflecting on recent experiences."
        )
        mock_llm_reflection.return_value = test_journal_content

        # Mock memory storage
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance

        # Call the function
        result = await generate_journal_entry(triggered_by="test")

        # Verify the function was called and prompts were requested
        mock_get_reflection_prompts.assert_called_once()

        # Verify no injection logging occurred
        mock_log.info.assert_not_called_with(
            "🪞 Injected reflection prompts into journal."
        )

        # Check that the result indicates success
        self.assertEqual(result["status"], "success")

        # Verify that the journal entry does NOT contain prompts
        journal_entry = result["entry"]
        journal_content = journal_entry["content"]

        self.assertNotIn("🪞 **Self-Reflection Prompts**", journal_content)
        self.assertIn(test_journal_content, journal_content)

    @patch("journal_engine.get_reflection_prompts")
    @patch("journal_engine.JournalMemoryAdapter")
    @patch("journal_engine._llm_reflection")
    @patch("journal_engine.Memory")
    async def test_reflection_prompts_limited_to_three(
        self,
        mock_memory,
        mock_llm_reflection,
        mock_memory_adapter,
        mock_get_reflection_prompts,
    ):
        """Test that only first 3 reflection prompts are included."""

        # Mock many reflection prompts
        test_prompts = [
            "Prompt 1",
            "Prompt 2",
            "Prompt 3",
            "Prompt 4",
            "Prompt 5",
            "Prompt 6",
        ]
        mock_get_reflection_prompts.return_value = test_prompts

        # Mock memory adapter
        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.get_recent.return_value = [
            {
                "id": "test1",
                "content": "Test memory 1",
                "timestamp": "2025-01-01T10:00:00Z",
            }
        ]
        mock_memory_adapter.return_value = mock_adapter_instance

        # Mock LLM response
        mock_llm_reflection.return_value = "Test journal entry."

        # Mock memory storage
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance

        # Call the function
        result = await generate_journal_entry(triggered_by="test")

        # Check that the result indicates success
        self.assertEqual(result["status"], "success")

        # Verify that only 3 prompts are included
        journal_entry = result["entry"]
        journal_content = journal_entry["content"]

        self.assertIn("1. Prompt 1", journal_content)
        self.assertIn("2. Prompt 2", journal_content)
        self.assertIn("3. Prompt 3", journal_content)
        self.assertNotIn("4. Prompt 4", journal_content)
        self.assertNotIn("Prompt 4", journal_content)

    @patch("journal_engine.JournalMemoryAdapter")
    @patch("journal_engine._llm_reflection")
    @patch("journal_engine.Memory")
    async def test_reflection_prompts_disabled_by_config(
        self, mock_memory, mock_llm_reflection, mock_memory_adapter
    ):
        """Test that reflection prompts can be disabled via configuration."""

        # Disable reflection prompts
        os.environ["ENABLE_REFLECTION_PROMPTS"] = "0"

        # Need to reimport to pick up new environment variable
        import importlib

        import journal_engine

        importlib.reload(journal_engine)

        # Mock memory adapter
        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.get_recent.return_value = [
            {
                "id": "test1",
                "content": "Test memory 1",
                "timestamp": "2025-01-01T10:00:00Z",
            }
        ]
        mock_memory_adapter.return_value = mock_adapter_instance

        # Mock LLM response
        test_journal_content = "This is a test journal entry."
        mock_llm_reflection.return_value = test_journal_content

        # Mock memory storage
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance

        # Call the function
        result = await journal_engine.generate_journal_entry(triggered_by="test")

        # Check that the result indicates success
        self.assertEqual(result["status"], "success")

        # Verify that the journal entry does NOT contain prompts
        journal_entry = result["entry"]
        journal_content = journal_entry["content"]

        self.assertNotIn("🪞 **Self-Reflection Prompts**", journal_content)
        self.assertIn(test_journal_content, journal_content)


def run_async_test(test_func):
    """Helper to run async test functions."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_func())
    finally:
        loop.close()


if __name__ == "__main__":
    # Run async tests
    test_case = TestJournalReflectionPrompts()
    test_case.setUp()

    try:
        print("Running test_reflection_prompts_injected_when_available...")
        run_async_test(test_case.test_reflection_prompts_injected_when_available)
        print("✅ PASSED")

        print("Running test_reflection_prompts_skipped_when_unavailable...")
        run_async_test(test_case.test_reflection_prompts_skipped_when_unavailable)
        print("✅ PASSED")

        print("Running test_reflection_prompts_limited_to_three...")
        run_async_test(test_case.test_reflection_prompts_limited_to_three)
        print("✅ PASSED")

        print("Running test_reflection_prompts_disabled_by_config...")
        run_async_test(test_case.test_reflection_prompts_disabled_by_config)
        print("✅ PASSED")

        print("\n🎉 All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        test_case.tearDown()
