#!/usr/bin/env python3
"""
Unit tests for Theory of Mind integration in journal engine.
Tests that ToM perspective simulation is properly integrated into journal entries.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from journal_engine import (
    generate_journal_entry,
    journal_autonomous_cognition,
    simulate_alternate_perspective,
)


class TestJournalEngineToMIntegration(unittest.TestCase):
    """Test Theory of Mind integration into journal entries."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test logs
        self.test_dir = tempfile.mkdtemp()
        self.original_log_dir = os.environ.get("LOG_DIR")
        os.environ["LOG_DIR"] = self.test_dir

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        if self.original_log_dir:
            os.environ["LOG_DIR"] = self.original_log_dir
        elif "LOG_DIR" in os.environ:
            del os.environ["LOG_DIR"]

        # Clean up temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_journal_with_tom_simulation(self):
        """Test that ToM simulation is triggered with low confidence + ethical context."""
        context = {"confidence": 0.42, "tags": ["#alignment", "#deep_think", "#ethics"]}

        problem_text = "Should we constrain AIs that learn morality independently?"

        result = simulate_alternate_perspective(problem_text, context)

        # Should trigger because confidence < 0.5 and contains ethical tags
        self.assertIsNotNone(
            result,
            "ToM simulation should be triggered with low confidence and ethical tags",
        )
        self.assertIn("Simulated Observer", result)
        self.assertIn("Perspective:", result)
        self.assertIn("Problem:", result)

    def test_tom_simulation_not_triggered_high_confidence(self):
        """Test that ToM simulation is not triggered with high confidence and no trigger tags."""
        context = {"confidence": 0.85, "tags": ["#routine", "#normal"]}

        problem_text = "Today was a normal day with routine interactions."

        result = simulate_alternate_perspective(problem_text, context)

        # Should not trigger because confidence is high and no trigger tags
        self.assertIsNone(
            result,
            "ToM simulation should not be triggered with high confidence and no trigger tags",
        )

    def test_tom_simulation_triggered_by_conflict_tag(self):
        """Test that ToM simulation is triggered by conflict tag regardless of confidence."""
        context = {
            "confidence": 0.75,  # High confidence
            "tags": ["#conflict", "#resolution"],
        }

        problem_text = "There appears to be a conflict between efficiency and safety in this approach."

        result = simulate_alternate_perspective(problem_text, context)

        # Should trigger because of conflict tag even with high confidence
        self.assertIsNotNone(
            result,
            "ToM simulation should be triggered by conflict tag even with high confidence",
        )
        self.assertIn("Simulated Observer", result)

    def test_tom_simulation_triggered_by_dilemma_tag(self):
        """Test that ToM simulation is triggered by dilemma tag."""
        context = {"confidence": 0.65, "tags": ["#dilemma", "#decision"]}

        problem_text = "This presents a difficult dilemma between competing values."

        result = simulate_alternate_perspective(problem_text, context)

        # Should trigger because of dilemma tag
        self.assertIsNotNone(
            result, "ToM simulation should be triggered by dilemma tag"
        )
        self.assertIn("Simulated Observer", result)

    def test_tom_simulation_with_empty_problem(self):
        """Test that ToM simulation gracefully handles empty problem text."""
        context = {"confidence": 0.3, "tags": ["#ethics", "#conflict"]}

        result = simulate_alternate_perspective("", context)

        # Should not trigger with empty problem text
        self.assertIsNone(
            result, "ToM simulation should not trigger with empty problem text"
        )

    def test_tom_simulation_with_none_problem(self):
        """Test that ToM simulation gracefully handles None problem text."""
        context = {"confidence": 0.3, "tags": ["#ethics", "#conflict"]}

        result = simulate_alternate_perspective(None, context)

        # Should not trigger with None problem text
        self.assertIsNone(
            result, "ToM simulation should not trigger with None problem text"
        )

    @patch("journal_engine.TOM_AVAILABLE", False)
    def test_tom_simulation_when_module_unavailable(self):
        """Test that ToM simulation gracefully handles when module is unavailable."""
        context = {"confidence": 0.3, "tags": ["#ethics", "#conflict"]}

        problem_text = "Should we prioritize safety over speed in AI development?"

        result = simulate_alternate_perspective(problem_text, context)

        # Should not trigger when module is unavailable
        self.assertIsNone(
            result, "ToM simulation should not trigger when module is unavailable"
        )

    @patch("journal_engine.simulate_perspective")
    @patch("journal_engine.AgentModel")
    @patch("journal_engine.TOM_AVAILABLE", True)
    def test_tom_simulation_agent_creation(
        self, mock_agent_model, mock_simulate_perspective
    ):
        """Test that ToM simulation creates agent with correct properties."""
        # Mock the simulation response
        mock_simulation = MagicMock()
        mock_simulation.simulated_response = (
            "From my analytical perspective, this requires careful consideration."
        )
        mock_simulation.confidence = 0.7
        mock_simulate_perspective.return_value = mock_simulation

        # Mock agent model
        mock_agent = MagicMock()
        mock_agent_model.return_value = mock_agent

        context = {"confidence": 0.4, "tags": ["#alignment"]}

        problem_text = "How should we handle AI alignment challenges?"

        result = simulate_alternate_perspective(problem_text, context)

        # Verify agent was created with correct properties
        mock_agent_model.assert_called_once()
        agent_call_args = mock_agent_model.call_args[1]

        self.assertEqual(agent_call_args["agent_id"], "simulated_observer")
        self.assertEqual(agent_call_args["name"], "Simulated Observer")
        self.assertIn("analytical", agent_call_args["traits"])
        self.assertIn("cautious", agent_call_args["traits"])
        self.assertIn("curious", agent_call_args["traits"])
        self.assertIn("maximize insight", agent_call_args["goals"])
        self.assertEqual(
            agent_call_args["beliefs"], {}
        )  # Should be empty for fresh perspective

        # Verify simulation was called
        mock_simulate_perspective.assert_called_once_with(mock_agent, problem_text)

        # Verify result contains expected content
        self.assertIsNotNone(result)
        self.assertIn("Simulated Observer", result)
        self.assertIn("From my analytical perspective", result)

    @patch("journal_engine.JournalMemoryAdapter")
    @patch("journal_engine._llm_reflection")
    @patch("journal_engine.Memory")
    @patch("journal_engine.simulate_alternate_perspective")
    @patch("journal_engine.detect_contradictions")
    async def test_journal_entry_includes_tom_simulation(
        self,
        mock_detect_contradictions,
        mock_tom_simulation,
        mock_memory,
        mock_llm_reflection,
        mock_memory_adapter,
    ):
        """Test that journal entry includes ToM simulation when triggered."""

        # Mock ToM simulation
        mock_tom_simulation.return_value = "**Perspective Simulation: Simulated Observer**\nPerspective: This is a complex ethical issue that requires careful analysis."

        # Mock memory adapter
        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.get_recent.return_value = [
            {
                "id": "test1",
                "content": "Test memory with ethical dilemma",
                "timestamp": "2025-01-01T10:00:00Z",
            }
        ]
        mock_memory_adapter.return_value = mock_adapter_instance

        # Mock LLM response
        mock_llm_reflection.return_value = (
            "Today I encountered a challenging ethical dilemma about AI alignment."
        )

        # Mock memory storage
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance

        # Mock contradiction detection
        mock_detect_contradictions.return_value = []

        # Call the function
        result = await generate_journal_entry(triggered_by="test")

        # Verify ToM simulation was called
        mock_tom_simulation.assert_called_once()

        # Check that the result indicates success
        self.assertEqual(result["status"], "success")

        # Verify that the journal entry contains the ToM simulation
        journal_entry = result["entry"]
        journal_content = journal_entry["content"]

        self.assertIn("🧠 **Theory of Mind Simulation**", journal_content)
        self.assertIn("Perspective Simulation: Simulated Observer", journal_content)
        self.assertIn("perspective_sim", journal_entry["tags"])

        # Verify ToM simulation metadata
        self.assertIn("tom_simulation", journal_entry)
        self.assertTrue(journal_entry["tom_simulation"]["triggered"])

    def test_journal_autonomous_cognition_with_tom(self):
        """Test that autonomous cognition journal includes ToM simulation."""

        # Mock cognitive result with contradictions (should trigger ToM)
        mock_result = {
            "structured_result": {
                "original_problem": "How to balance AI safety with innovation speed?",
                "reframes": ["reframe1", "reframe2"],
                "contradictions": [{"description": "Speed vs Safety conflict"}],
                "reasoning_steps": [
                    {"description": "Step 1"},
                    {"description": "Step 2"},
                ],
                "confidence": 0.4,  # Low confidence should trigger ToM
                "session_id": "test_session",
            },
            "summary": "Analyzed the tradeoff between safety and speed in AI development.",
        }

        with (
            patch("journal_engine.Memory") as mock_memory,
            patch("journal_engine.log_reflection_created") as mock_log_reflection,
            patch(
                "journal_engine.simulate_alternate_perspective"
            ) as mock_tom_simulation,
        ):

            # Mock ToM simulation
            mock_tom_simulation.return_value = "**Alternative Perspective**: From a risk-averse viewpoint, safety should always come first."

            # Mock memory storage
            mock_memory_instance = MagicMock()
            mock_memory_instance.add_to_long_term.return_value = {"id": "journal_123"}
            mock_memory.return_value = mock_memory_instance

            # Call the function
            result = journal_autonomous_cognition(mock_result, "high_cognitive_load")

            # Verify ToM simulation was called
            mock_tom_simulation.assert_called_once()

            # Verify success
            self.assertTrue(result["success"])

            # Verify memory was stored with ToM content
            memory_calls = mock_memory_instance.add_to_long_term.call_args_list
            self.assertEqual(len(memory_calls), 1)

            stored_entry = memory_calls[0][0][0]
            self.assertIn(
                "🧠 **Alternative Perspective on Problem**", stored_entry["content"]
            )
            self.assertIn("perspective_sim", stored_entry["tags"])
            self.assertTrue(stored_entry["tom_simulation"]["triggered"])


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
    test_case = TestJournalEngineToMIntegration()
    test_case.setUp()

    try:
        print("Running test_journal_with_tom_simulation...")
        test_case.test_journal_with_tom_simulation()
        print("✅ PASSED")

        print("Running test_tom_simulation_not_triggered_high_confidence...")
        test_case.test_tom_simulation_not_triggered_high_confidence()
        print("✅ PASSED")

        print("Running test_tom_simulation_triggered_by_conflict_tag...")
        test_case.test_tom_simulation_triggered_by_conflict_tag()
        print("✅ PASSED")

        print("Running test_tom_simulation_triggered_by_dilemma_tag...")
        test_case.test_tom_simulation_triggered_by_dilemma_tag()
        print("✅ PASSED")

        print("Running test_tom_simulation_with_empty_problem...")
        test_case.test_tom_simulation_with_empty_problem()
        print("✅ PASSED")

        print("Running test_tom_simulation_with_none_problem...")
        test_case.test_tom_simulation_with_none_problem()
        print("✅ PASSED")

        print("Running test_tom_simulation_when_module_unavailable...")
        test_case.test_tom_simulation_when_module_unavailable()
        print("✅ PASSED")

        print("Running test_tom_simulation_agent_creation...")
        test_case.test_tom_simulation_agent_creation()
        print("✅ PASSED")

        print("Running test_journal_entry_includes_tom_simulation...")
        run_async_test(test_case.test_journal_entry_includes_tom_simulation)
        print("✅ PASSED")

        print("Running test_journal_autonomous_cognition_with_tom...")
        test_case.test_journal_autonomous_cognition_with_tom()
        print("✅ PASSED")

        print("\n🎉 All ToM integration tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        test_case.tearDown()
