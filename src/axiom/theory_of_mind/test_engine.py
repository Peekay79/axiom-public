"""
Integration Tests for Theory of Mind

Tests all core functionality while verifying containment safeguards.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add the axiom directory to the path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from axiom.theory_of_mind.engine import (
    create_agent,
    detect_contradictions,
    generate_empathy_summary,
    get_audit_log,
    infer_agent_emotion,
    model_agent_intentions,
    score_empathic_alignment,
    simulate_perspective,
    summarize_agent,
    update_agent_beliefs,
    verify_containment,
)
from axiom.theory_of_mind.models import AgentModel


def test_simulate_agent_perspective():
    """Test perspective simulation as specified in the prompt."""
    print("🧪 Testing simulate_agent_perspective...")

    agent = AgentModel(
        agent_id="alpha",
        name="Dr. Lyra",
        traits=["curious", "risk-averse"],
        goals=["understand consciousness"],
        beliefs={"AI safety": "must include emotional modeling"},
        memory_refs=[],
        last_updated=datetime.utcnow(),
    )

    response = simulate_perspective(agent, "Should we deploy recursive AI?")
    print(f"Agent: {agent.name}")
    print(f"Problem: Should we deploy recursive AI?")
    print(f"Response: {response.simulated_response}")
    print(f"Confidence: {response.confidence}")
    print(f"Reasoning chain: {response.reasoning_chain}")
    print("✅ Perspective simulation test passed\n")

    return response


def test_agent_creation_and_management():
    """Test creating and managing agent models."""
    print("🧪 Testing agent creation and management...")

    # Create agent using convenience function
    agent = create_agent(
        agent_id="test_agent",
        name="Test Agent",
        traits=["analytical", "cautious"],
        goals=["solve problems", "avoid mistakes"],
        beliefs={"testing": "is essential for reliable systems"},
    )

    assert agent.agent_id == "test_agent"
    assert agent.name == "Test Agent"
    assert "analytical" in agent.traits
    assert "solve problems" in agent.goals
    assert agent.beliefs["testing"] == "is essential for reliable systems"

    print(f"Created agent: {agent.name}")
    print(f"Traits: {agent.traits}")
    print(f"Goals: {agent.goals}")
    print("✅ Agent creation test passed\n")

    return agent


def test_belief_updates():
    """Test updating agent beliefs without affecting core system."""
    print("🧪 Testing belief updates...")

    agent = create_agent("belief_test", "Belief Tester")

    # Update beliefs with new input
    input_text = "I believe that artificial intelligence should be developed carefully. I think we need robust testing."
    updated_agent = update_agent_beliefs(agent, input_text)

    assert len(updated_agent.beliefs) > 0
    assert updated_agent.last_updated > agent.last_updated
    print(f"Original beliefs: {len(agent.beliefs)}")
    print(f"Updated beliefs: {len(updated_agent.beliefs)}")
    print(f"New beliefs: {updated_agent.beliefs}")
    print("✅ Belief update test passed\n")

    return updated_agent


def test_contradiction_detection():
    """Test detecting contradictions in agent beliefs."""
    print("🧪 Testing contradiction detection...")

    # Create agent with contradictory beliefs
    agent = create_agent(
        "contradiction_test",
        "Contradiction Tester",
        beliefs={
            "safety_positive": "AI is always safe when properly designed",
            "safety_negative": "AI systems are never completely safe",
            "speed_good": "Fast deployment is good for innovation",
            "speed_bad": "Fast deployment is dangerous for safety",
        },
    )

    contradictions = detect_contradictions(agent)

    print(f"Agent beliefs: {agent.beliefs}")
    print(f"Detected contradictions: {len(contradictions)}")
    for contradiction in contradictions:
        print(f"  - {contradiction.description}")

    assert len(contradictions) > 0
    print("✅ Contradiction detection test passed\n")

    return contradictions


def test_agent_summarization():
    """Test generating agent summaries."""
    print("🧪 Testing agent summarization...")

    agent = create_agent(
        "summary_test",
        "Summary Tester",
        traits=["thoughtful", "systematic", "collaborative"],
        goals=["understand complex systems", "help others learn"],
        beliefs={
            "learning": "is a lifelong process",
            "collaboration": "leads to better outcomes",
            "patience": "is essential for deep understanding",
        },
    )

    summary = summarize_agent(agent)

    print(f"Agent Summary: {summary.summary_text}")
    print(f"Key beliefs: {summary.key_beliefs}")
    print(f"Dominant traits: {summary.dominant_traits}")
    print(f"Primary goals: {summary.primary_goals}")
    print(f"Contradiction count: {summary.contradiction_count}")

    assert summary.agent_id == agent.agent_id
    assert len(summary.key_beliefs) > 0
    print("✅ Agent summarization test passed\n")

    return summary


def test_containment_verification():
    """Test that containment safeguards are working."""
    print("🧪 Testing containment verification...")

    # Run some operations
    agent = create_agent("containment_test", "Containment Tester")
    simulate_perspective(agent, "Test problem")
    update_agent_beliefs(agent, "Test belief update")

    # Verify containment
    containment_ok = verify_containment()
    audit_log = get_audit_log()

    print(f"Containment verified: {containment_ok}")
    print(f"Audit log entries: {len(audit_log)}")
    for entry in audit_log[-3:]:  # Show last 3 entries
        print(f"  - {entry.operation} for {entry.agent_id} at {entry.timestamp}")

    assert containment_ok is True
    assert len(audit_log) > 0
    print("✅ Containment verification test passed\n")


def test_perspective_simulation_complex():
    """Test perspective simulation with complex scenarios."""
    print("🧪 Testing complex perspective simulation...")

    # Create an agent with complex characteristics
    agent = create_agent(
        "complex_test",
        "Complex Thinker",
        traits=["curious", "risk-averse", "optimistic"],
        goals=["understand consciousness", "ensure safety", "promote learning"],
        beliefs={
            "consciousness": "may emerge from complex information processing",
            "safety": "requires careful validation and testing",
            "learning": "happens through exploration and reflection",
        },
    )

    problems = [
        "How should we approach consciousness research?",
        "What safety measures are needed for AI development?",
        "How can we balance innovation with caution?",
    ]

    for problem in problems:
        simulation = simulate_perspective(agent, problem)
        print(f"Problem: {problem}")
        print(f"Response: {simulation.simulated_response}")
        print(f"Metadata: {simulation.metadata}")
        print("---")

    print("✅ Complex perspective simulation test passed\n")


def test_emotion_inference():
    """Test inferring agent emotional states."""
    print("🧪 Testing emotion inference...")

    agent = create_agent(
        "emotion_test",
        "Emotional Agent",
        traits=["anxious", "curious"],
        goals=["understand complex systems"],
    )

    test_contexts = [
        "I'm really worried about this approach. Are we sure it's safe?",
        "This is fascinating! I'd love to explore this further.",
        "I'm frustrated that we keep hitting these roadblocks.",
        "I feel confident that this is the right direction.",
    ]

    for context in test_contexts:
        emotional_state = infer_agent_emotion(agent, context)
        print(f"Context: {context[:50]}...")
        print(
            f"Emotion: {emotional_state.emotion} (intensity: {emotional_state.intensity:.2f}, confidence: {emotional_state.confidence:.2f})"
        )

        # Verify structure
        assert emotional_state.agent_id == agent.agent_id
        assert emotional_state.emotion in [
            "anxious",
            "curious",
            "frustrated",
            "confident",
            "neutral",
        ]
        assert 0 <= emotional_state.intensity <= 1
        assert 0 <= emotional_state.confidence <= 1
        assert emotional_state.metadata["memoryType"] == "simulation"
        print("---")

    print("✅ Emotion inference test passed\n")


def test_intention_modeling():
    """Test modeling agent intentions."""
    print("🧪 Testing intention modeling...")

    agent = create_agent(
        "intention_test",
        "Strategic Agent",
        traits=["strategic", "collaborative"],
        goals=["gain influence", "build partnerships"],
    )

    test_contexts = [
        "Let me convince you that this approach is better.",
        "I think we should work together to solve this challenge.",
        "What if we tried a completely different strategy?",
        "I need to understand how this system works before proceeding.",
    ]

    for context in test_contexts:
        intentions = model_agent_intentions(agent, context)
        print(f"Context: {context[:50]}...")
        print(f"Intentions: {intentions.intentions}")
        print(f"Confidence: {intentions.confidence:.2f}")
        print(f"Reasoning: {intentions.reasoning_chain}")

        # Verify structure
        assert intentions.agent_id == agent.agent_id
        assert isinstance(intentions.intentions, list)
        assert 0 <= intentions.confidence <= 1
        print("---")

    print("✅ Intention modeling test passed\n")


def test_empathy_summary_generation():
    """Test generating empathy summaries."""
    print("🧪 Testing empathy summary generation...")

    agent = create_agent(
        "empathy_test",
        "Alice",
        traits=["defensive", "analytical"],
        goals=["protect reputation", "prove competence"],
        beliefs={"trust": "must be earned through demonstrated competence"},
    )

    context = "I'm concerned that you're questioning my expertise on this matter. I've been working in this field for years."

    empathy_summary = generate_empathy_summary(agent, context)

    print(f"Agent: {agent.name}")
    print(f"Context: {context}")
    print(f"Empathy Summary: {empathy_summary.summary_text}")
    print(
        f"Emotional State: {empathy_summary.emotional_state.emotion} ({empathy_summary.emotional_state.intensity:.2f})"
    )
    print(f"Intentions: {empathy_summary.intentions.intentions}")
    print(f"Metadata: {empathy_summary.metadata}")

    # Verify structure and tagging
    assert empathy_summary.agent_id == agent.agent_id
    assert empathy_summary.metadata["tag"] == "#empathy_inference"
    assert empathy_summary.metadata["memoryType"] == "simulation"
    assert empathy_summary.metadata["agent_name"] == "Alice"
    assert "Alice" in empathy_summary.summary_text
    assert len(empathy_summary.summary_text) > 20  # Reasonable length

    print("✅ Empathy summary generation test passed\n")


def test_empathic_alignment_scoring():
    """Test scoring empathic alignment of responses."""
    print("🧪 Testing empathic alignment scoring...")

    agent = create_agent(
        "alignment_test",
        "Bob",
        traits=["anxious", "detail-oriented"],
        goals=["ensure safety", "avoid mistakes"],
    )

    # Test good and poor alignment responses
    test_cases = [
        {
            "agent_context": "I'm really worried about this approach. Are we sure it's safe? I keep thinking we might miss something important.",
            "response": "I understand your concern about safety. Let's carefully review each step to make sure we haven't missed anything.",
            "expected_score_range": (0.6, 1.0),
            "description": "Good empathic alignment",
        },
        {
            "agent_context": "I'm really worried about this approach. Are we sure it's safe? I keep thinking we might miss something important.",
            "response": "Just go ahead and do it quickly. Don't overthink it.",
            "expected_score_range": (0.0, 0.4),
            "description": "Poor empathic alignment",
        },
    ]

    for test_case in test_cases:
        alignment = score_empathic_alignment(
            agent, test_case["response"], test_case["agent_context"]
        )

        print(f"Agent Context: {test_case['agent_context'][:50]}...")
        print(f"Response: {test_case['response'][:50]}...")
        print(f"Alignment Score: {alignment.alignment_score:.2f}")
        print(f"Reasoning: {alignment.reasoning}")
        print(f"Suggestions: {alignment.suggestions}")
        print(
            f"Low Alignment Warning: {alignment.metadata.get('low_empathy_alignment', False)}"
        )

        # Verify score is in expected range
        min_score, max_score = test_case["expected_score_range"]
        assert (
            min_score <= alignment.alignment_score <= max_score
        ), f"Score {alignment.alignment_score} not in range {test_case['expected_score_range']} for {test_case['description']}"

        # Verify structure
        assert alignment.agent_id == agent.agent_id
        assert alignment.metadata["memoryType"] == "simulation"
        assert 0 <= alignment.alignment_score <= 1
        print("---")

    print("✅ Empathic alignment scoring test passed\n")


def test_empathy_containment_safeguards():
    """Test that empathy functions respect containment rules."""
    print("🧪 Testing empathy containment safeguards...")

    agent = create_agent("containment_empathy_test", "Containment Tester")
    context = "I'm testing the empathy system containment."

    # Run empathy operations
    emotion = infer_agent_emotion(agent, context)
    intentions = model_agent_intentions(agent, context)
    empathy_summary = generate_empathy_summary(agent, context)
    alignment = score_empathic_alignment(
        agent, "Test response for containment.", context
    )

    # Verify all results are properly tagged as simulations
    assert emotion.metadata["memoryType"] == "simulation"
    assert empathy_summary.metadata["memoryType"] == "simulation"
    assert empathy_summary.metadata["tag"] == "#empathy_inference"
    assert alignment.metadata["memoryType"] == "simulation"

    # Verify containment is still intact
    containment_ok = verify_containment()
    assert containment_ok, "Containment violated by empathy operations"

    # Verify audit log shows empathy operations
    audit_log = get_audit_log()
    empathy_operations = [
        event
        for event in audit_log
        if event.problem_domain
        in [
            "emotion_inference",
            "intention_modeling",
            "empathy_summary",
            "empathy_alignment",
        ]
    ]
    assert len(empathy_operations) >= 4, "Empathy operations not properly logged"

    print(f"Empathy operations logged: {len(empathy_operations)}")
    print(f"Containment verified: {containment_ok}")

    for operation in empathy_operations[-4:]:
        print(f"  - {operation.operation} in {operation.problem_domain}")
        assert (
            operation.containment_verified
        ), f"Containment not verified for {operation.operation}"

    print("✅ Empathy containment safeguards test passed\n")


def test_empathy_integration_comprehensive():
    """Comprehensive test of empathy features working together."""
    print("🧪 Testing comprehensive empathy integration...")

    # Create a complex agent scenario
    agent = create_agent(
        "comprehensive_test",
        "Dr. Sarah Chen",
        traits=["perfectionist", "collaborative", "analytical"],
        goals=[
            "maintain high standards",
            "build team consensus",
            "deliver quality results",
        ],
        beliefs={
            "quality": "should never be compromised for speed",
            "teamwork": "produces better outcomes than individual work",
            "expertise": "should be respected and leveraged properly",
        },
    )

    # Simulate a workplace scenario
    contexts = [
        "I'm concerned that we're rushing this project and might miss critical issues.",
        "Let's make sure everyone on the team understands the requirements before we proceed.",
        "I think my experience with similar projects could be valuable here.",
    ]

    responses = [
        "You're right to be concerned. Let's take the time needed to do this properly.",
        "Great idea. Should we schedule a team meeting to align everyone?",
        "I'd appreciate your insights. Can you share what worked well in your previous projects?",
    ]

    print(f"Agent Profile: {agent.name}")
    print(f"Traits: {agent.traits}")
    print(f"Goals: {agent.goals}")
    print()

    for i, (context, response) in enumerate(zip(contexts, responses)):
        print(f"--- Scenario {i+1} ---")
        print(f"Agent Context: {context}")
        print(f"Axiom Response: {response}")

        # Generate comprehensive empathy analysis
        empathy_summary = generate_empathy_summary(agent, context)
        alignment = score_empathic_alignment(agent, response)

        print(f"Empathy Analysis: {empathy_summary.summary_text}")
        print(f"Alignment Score: {alignment.alignment_score:.2f}")
        if alignment.suggestions:
            print(f"Suggestions: {', '.join(alignment.suggestions)}")
        print()

    # Verify all operations maintained containment
    containment_ok = verify_containment()
    assert containment_ok, "Containment violated during comprehensive test"

    print("✅ Comprehensive empathy integration test passed\n")


def run_all_tests():
    """Run all integration tests."""
    print("🚀 Starting Theory of Mind Engine Integration Tests")
    print("=" * 60)

    try:
        # Run all tests
        test_simulate_agent_perspective()
        test_agent_creation_and_management()
        test_belief_updates()
        test_contradiction_detection()
        test_agent_summarization()
        test_containment_verification()
        test_perspective_simulation_complex()
        test_emotion_inference()
        test_intention_modeling()
        test_empathy_summary_generation()
        test_empathic_alignment_scoring()
        test_empathy_containment_safeguards()
        test_empathy_integration_comprehensive()

        print("🎉 All integration tests passed successfully!")
        print("✅ Theory of Mind module is ready for integration")

        # Final containment check
        final_containment = verify_containment()
        if final_containment:
            print(
                "🔒 Containment safeguards verified - no core system modifications detected"
            )
        else:
            print("⚠️  CONTAINMENT VIOLATION DETECTED - Review audit log")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
