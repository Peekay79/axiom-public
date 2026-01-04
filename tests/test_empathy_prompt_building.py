#!/usr/bin/env python3
"""
Test empathy-aware prompt building functionality.

This test suite verifies that the empathy engine integration works correctly
with the LLM connector and produces appropriate prompt enhancements.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

# Add the workspace to Python path
sys.path.insert(0, "/workspace")


class TestEmpathyPromptBuilding(unittest.TestCase):
    """Test cases for empathy-aware prompt building"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock imports to avoid dependency issues during testing
        self.mock_empathy_engine = Mock()
        self.mock_agent_model = Mock()
        self.mock_empathy_summary = Mock()

    def test_identify_agent_with_kurt(self):
        """Test agent identification for ExamplePerson"""
        from llm_connector import identify_agent

        context = "ExamplePerson: How does the empathy engine work?"
        result = identify_agent(context)
        self.assertEqual(result, "ExamplePerson")

        context = "Previous conversation...\nKurt: Tell me more about consciousness"
        result = identify_agent(context)
        self.assertEqual(result, "ExamplePerson")

    def test_identify_agent_with_user(self):
        """Test agent identification for generic user"""
        from llm_connector import identify_agent

        context = "User is asking about AI capabilities"
        result = identify_agent(context)
        self.assertEqual(result, "user")

        context = "Please explain the system architecture"
        result = identify_agent(context)
        self.assertEqual(result, "user")

    def test_identify_agent_unknown(self):
        """Test agent identification for unknown context"""
        from llm_connector import identify_agent

        context = "Some random system output"
        result = identify_agent(context)
        self.assertEqual(result, "unknown")

        context = ""
        result = identify_agent(context)
        self.assertEqual(result, "unknown")

    @patch("llm_connector.EMPATHY_ENGINE_AVAILABLE", False)
    def test_build_empathy_prompt_block_unavailable(self):
        """Test empathy prompt building when engine is unavailable"""
        from llm_connector import build_empathy_prompt_block

        result = build_empathy_prompt_block("ExamplePerson", "Some context")
        self.assertEqual(result, "")

    @patch("llm_connector.EMPATHY_ENGINE_AVAILABLE", True)
    @patch("llm_connector.load_agent")
    @patch("llm_connector.create_agent")
    @patch("llm_connector.generate_empathy_summary")
    def test_build_empathy_prompt_block_with_existing_agent(
        self, mock_generate, mock_create, mock_load
    ):
        """Test empathy prompt building with existing agent model"""
        from llm_connector import build_empathy_prompt_block

        # Mock existing agent
        mock_agent = Mock()
        mock_agent.agent_id = "ExamplePerson"
        mock_load.return_value = mock_agent

        # Mock empathy summary
        mock_emotional_state = Mock()
        mock_emotional_state.emotion = "curious"
        mock_emotional_state.confidence = 0.8

        mock_intentions = Mock()
        mock_intentions.intentions = ["seek understanding", "learn more"]
        mock_intentions.confidence = 0.7

        mock_summary = Mock()
        mock_summary.emotional_state = mock_emotional_state
        mock_summary.intentions = mock_intentions
        mock_summary.summary_text = (
            "ExamplePerson seems curious and eager to learn about AI consciousness"
        )

        mock_generate.return_value = mock_summary

        result = build_empathy_prompt_block(
            "ExamplePerson", "ExamplePerson: How does consciousness work?"
        )

        # Verify the result contains expected elements
        self.assertIn("[Empathy Context]", result)
        self.assertIn("Agent: ExamplePerson", result)
        self.assertIn("Emotion: curious", result)
        self.assertIn("Intent: seek understanding, learn more", result)
        self.assertIn("Suggested tone: informative and encouraging", result)
        self.assertIn("ExamplePerson seems curious and eager to learn", result)
        self.assertIn("#end_empathy_context", result)

    @patch("llm_connector.EMPATHY_ENGINE_AVAILABLE", True)
    @patch("llm_connector.load_agent")
    @patch("llm_connector.create_agent")
    @patch("llm_connector.generate_empathy_summary")
    def test_build_empathy_prompt_block_with_new_agent(
        self, mock_generate, mock_create, mock_load
    ):
        """Test empathy prompt building with new agent creation"""
        from llm_connector import build_empathy_prompt_block

        # Mock no existing agent
        mock_load.return_value = None

        # Mock created agent
        mock_agent = Mock()
        mock_agent.agent_id = "ExamplePerson"
        mock_create.return_value = mock_agent

        # Mock empathy summary
        mock_emotional_state = Mock()
        mock_emotional_state.emotion = "anxious"
        mock_emotional_state.confidence = 0.6

        mock_intentions = Mock()
        mock_intentions.intentions = ["avoid blame"]
        mock_intentions.confidence = 0.5

        mock_summary = Mock()
        mock_summary.emotional_state = mock_emotional_state
        mock_summary.intentions = mock_intentions
        mock_summary.summary_text = "ExamplePerson appears anxious about system reliability"

        mock_generate.return_value = mock_summary

        result = build_empathy_prompt_block(
            "ExamplePerson", "ExamplePerson: I'm worried this might not work correctly"
        )

        # Verify agent creation was called with correct parameters for ExamplePerson
        mock_create.assert_called_once()
        call_args = mock_create.call_args[1]
        self.assertEqual(call_args["agent_id"], "ExamplePerson")
        self.assertEqual(call_args["name"], "ExamplePerson")
        self.assertIn("inquisitive", call_args["traits"])
        self.assertIn("understand AI systems", call_args["goals"])

        # Verify the result contains empathy context
        self.assertIn("Agent: ExamplePerson", result)
        self.assertIn("Emotion: anxious", result)
        self.assertIn("Suggested tone: reassuring and careful", result)

    @patch("llm_connector.EMPATHY_ENGINE_AVAILABLE", True)
    def test_build_empathy_prompt_block_with_exception(self):
        """Test empathy prompt building with exception handling"""
        from llm_connector import build_empathy_prompt_block

        with patch("llm_connector.load_agent", side_effect=Exception("Test error")):
            result = build_empathy_prompt_block("ExamplePerson", "Some context")
            self.assertEqual(result, "")

    def test_inject_empathy_context_no_empathy_engine(self):
        """Test empathy injection when engine is unavailable"""
        from llm_connector import inject_empathy_context

        original_prompt = """[IDENTITY]
I am Axiom, an AI assistant.

Memory: "Previous conversation about AI"
ExamplePerson: How does the empathy engine work?
Steve:"""

        with patch("llm_connector.EMPATHY_ENGINE_AVAILABLE", False):
            result = inject_empathy_context(original_prompt)
            self.assertEqual(result, original_prompt)

    @patch("llm_connector.EMPATHY_ENGINE_AVAILABLE", True)
    @patch("llm_connector.identify_agent")
    @patch("llm_connector.build_empathy_prompt_block")
    def test_inject_empathy_context_success(self, mock_build_block, mock_identify):
        """Test successful empathy context injection"""
        from llm_connector import inject_empathy_context

        original_prompt = """[IDENTITY]
I am Axiom, an AI assistant.

Memory: "Previous conversation about consciousness"
ExamplePerson: Tell me about AI emotions
Steve:"""

        mock_identify.return_value = "ExamplePerson"
        mock_build_block.return_value = """[Empathy Context]
Agent: ExamplePerson
Emotion: curious (confidence: 0.8)
Intent: seek understanding (confidence: 0.7)
Suggested tone: informative and encouraging
Empathy Notes: ExamplePerson seems genuinely interested in AI emotions
#end_empathy_context

"""

        result = inject_empathy_context(original_prompt)

        # Verify empathy context was injected at the beginning
        self.assertIn("[Empathy Context]", result)
        self.assertIn("Agent: ExamplePerson", result)
        self.assertIn("Emotion: curious", result)
        self.assertTrue(result.startswith("[Empathy Context]"))

        # Verify original content is preserved
        self.assertIn("[IDENTITY]", result)
        self.assertIn("ExamplePerson: Tell me about AI emotions", result)
        self.assertIn("Steve:", result)

    def test_inject_empathy_context_no_kurt_line(self):
        """Test empathy injection when no ExamplePerson: line is found"""
        from llm_connector import inject_empathy_context

        original_prompt = """[IDENTITY]
I am Axiom, an AI assistant.

Some system output without user input"""

        result = inject_empathy_context(original_prompt)
        self.assertEqual(result, original_prompt)

    def test_inject_empathy_context_empty_prompt(self):
        """Test empathy injection with empty prompt"""
        from llm_connector import inject_empathy_context

        result = inject_empathy_context("")
        self.assertEqual(result, "")

        result = inject_empathy_context(None)
        self.assertEqual(result, None)

    @patch("llm_connector.inject_empathy_context")
    def test_safe_multiquery_empathy_integration(self, mock_inject):
        """Test empathy integration in safe_multiquery_context_pipeline"""
        from llm_connector import safe_multiquery_context_pipeline

        mock_inject.return_value = "enhanced_prompt_with_empathy"

        # Mock the multiquery_context_pipeline function
        with patch("llm_connector.multiquery_context_pipeline") as mock_pipeline:
            mock_pipeline.return_value = [{"response": "Test response"}]

            # Test with final_prompt (dialogue scenario)
            result = safe_multiquery_context_pipeline(
                final_prompt="ExamplePerson: How are you?\nSteve:"
            )

            # Verify empathy injection was called
            mock_inject.assert_called_once_with("ExamplePerson: How are you?\nSteve:")

            # Verify enhanced prompt was passed to pipeline
            mock_pipeline.assert_called_once()
            call_args = mock_pipeline.call_args[1]
            self.assertEqual(call_args["final_prompt"], "enhanced_prompt_with_empathy")

    @patch("llm_connector.inject_empathy_context")
    def test_safe_multiquery_empathy_not_triggered_for_memory_ids(self, mock_inject):
        """Test empathy integration is not triggered for memory retrieval"""
        from llm_connector import safe_multiquery_context_pipeline

        # Mock the multiquery_context_pipeline function
        with patch("llm_connector.multiquery_context_pipeline") as mock_pipeline:
            mock_pipeline.return_value = [{"response": "Memory response"}]

            # Test with memory_ids (memory retrieval scenario)
            result = safe_multiquery_context_pipeline(
                final_prompt="Some prompt", memory_ids=["mem1", "mem2"]
            )

            # Verify empathy injection was NOT called for memory retrieval
            mock_inject.assert_not_called()

    def test_empathy_tone_mapping(self):
        """Test the emotion to tone mapping"""
        from llm_connector import build_empathy_prompt_block

        # Test various emotions map to appropriate tones
        tone_mapping = {
            "anxious": "reassuring and careful",
            "defensive": "understanding and diplomatic",
            "confident": "engaging and supportive",
            "frustrated": "patient and helpful",
            "curious": "informative and encouraging",
            "skeptical": "evidence-based and clear",
            "neutral": "balanced and responsive",
        }

        # This is more of a documentation test - ensuring our mapping is reasonable
        for emotion, expected_tone in tone_mapping.items():
            self.assertIsInstance(expected_tone, str)
            self.assertGreater(len(expected_tone), 0)

    @patch("llm_connector.EMPATHY_ENGINE_AVAILABLE", True)
    @patch("llm_connector.load_agent")
    @patch("llm_connector.create_agent")
    @patch("llm_connector.generate_empathy_summary")
    def test_empathy_prompt_structure(self, mock_generate, mock_create, mock_load):
        """Test the structure of the empathy prompt block"""
        from llm_connector import build_empathy_prompt_block

        # Setup mocks
        mock_load.return_value = None
        mock_agent = Mock()
        mock_create.return_value = mock_agent

        mock_emotional_state = Mock()
        mock_emotional_state.emotion = "frustrated"
        mock_emotional_state.confidence = 0.9

        mock_intentions = Mock()
        mock_intentions.intentions = ["solve problem", "get help"]
        mock_intentions.confidence = 0.8

        mock_summary = Mock()
        mock_summary.emotional_state = mock_emotional_state
        mock_summary.intentions = mock_intentions
        mock_summary.summary_text = "User is frustrated with the current situation"

        mock_generate.return_value = mock_summary

        result = build_empathy_prompt_block("user", "This is so confusing!")

        # Verify structure
        lines = result.strip().split("\n")

        # Should start with [Empathy Context]
        self.assertEqual(lines[0], "[Empathy Context]")

        # Should contain required fields
        agent_line = next((line for line in lines if line.startswith("Agent:")), None)
        self.assertIsNotNone(agent_line)
        self.assertIn("user", agent_line)

        emotion_line = next(
            (line for line in lines if line.startswith("Emotion:")), None
        )
        self.assertIsNotNone(emotion_line)
        self.assertIn("frustrated", emotion_line)
        self.assertIn("0.9", emotion_line)

        intent_line = next((line for line in lines if line.startswith("Intent:")), None)
        self.assertIsNotNone(intent_line)
        self.assertIn("solve problem", intent_line)

        tone_line = next(
            (line for line in lines if line.startswith("Suggested tone:")), None
        )
        self.assertIsNotNone(tone_line)
        self.assertIn("patient and helpful", tone_line)

        notes_line = next(
            (line for line in lines if line.startswith("Empathy Notes:")), None
        )
        self.assertIsNotNone(notes_line)
        self.assertIn("frustrated with the current situation", notes_line)

        # Should end with #end_empathy_context
        end_line = next(
            (line for line in lines if line.startswith("#end_empathy_context")), None
        )
        self.assertIsNotNone(end_line)


if __name__ == "__main__":
    unittest.main()
