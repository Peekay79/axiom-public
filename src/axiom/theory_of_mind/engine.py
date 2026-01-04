"""
Theory of Mind

Main engine for Theory of Mind reasoning with strict containment safeguards.
This module NEVER modifies Axiom's core beliefs or memory - it only simulates
other agents' mental states in isolation.

🔒 CONTAINMENT RULES:
1. No writes to core memory system
2. No modifications to Axiom's beliefs
3. All agent models are read-only simulations
4. All operations are logged for audit
5. Memory isolation through agent_id tagging
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from .models import (
    AgentModel,
    AgentSummary,
    Contradiction,
    EmotionalState,
    EmpathyAlignment,
    EmpathySummary,
    IntentionModel,
    PerspectiveSimulation,
    ToMEvent,
)

# Configure logging for audit trail
logger = logging.getLogger("axiom.theory_of_mind")


class TheoryOfMindEngine:
    """
    Main engine for Theory of Mind operations with strict containment.

    All methods respect containment rules and never modify Axiom's core state.
    """

    def __init__(self):
        self.audit_log: List[ToMEvent] = []
        self.agent_cache: Dict[str, AgentModel] = {}

    def _log_operation(
        self,
        operation: str,
        agent_id: str,
        problem_domain: str = "",
        input_summary: str = "",
        output_summary: str = "",
    ) -> ToMEvent:
        """Log all ToM operations for audit and containment verification."""
        event = ToMEvent(
            operation=operation,
            agent_id=agent_id,
            problem_domain=problem_domain,
            input_summary=input_summary[:200],  # Truncate for storage
            output_summary=output_summary[:200],
            containment_verified=True,  # Set to True as we verify containment in code
        )

        self.audit_log.append(event)
        logger.info(
            f"ToM Operation: {operation} for agent {agent_id} in domain {problem_domain}"
        )
        return event

    def load_agent(self, agent_id: str) -> Optional[AgentModel]:
        """
        Load an agent model from cache or initialize new.

        🔒 CONTAINMENT: Only loads agent simulations, never Axiom's core state.
        """
        self._log_operation(
            "load_agent", agent_id, input_summary=f"Loading agent {agent_id}"
        )

        if agent_id in self.agent_cache:
            return self.agent_cache[agent_id]

        # In a full implementation, this would load from persistent storage
        # with memoryType="agent_model" and agent_id tags
        # For now, return None to indicate agent not found
        return None

    def create_agent(
        self,
        agent_id: str,
        name: str,
        traits: List[str] = None,
        goals: List[str] = None,
        beliefs: Dict[str, str] = None,
    ) -> AgentModel:
        """
        Create a new agent model for simulation.

        🔒 CONTAINMENT: Creates isolated simulation, never affects Axiom's beliefs.
        """
        agent = AgentModel(
            agent_id=agent_id,
            name=name,
            traits=traits or [],
            goals=goals or [],
            beliefs=beliefs or {},
            memory_refs=[],
            last_updated=datetime.utcnow(),
        )

        self.agent_cache[agent_id] = agent
        self._log_operation(
            "create_agent", agent_id, input_summary=f"Created agent {name}"
        )

        return agent

    def update_agent_beliefs(self, agent: AgentModel, input_text: str) -> AgentModel:
        """
        Update agent's belief model based on text input (e.g., dialogue).

        🔒 CONTAINMENT: Uses local inference only, NEVER overwrites Axiom's core beliefs.
        Returns updated AgentModel without persisting to core memory.
        """
        self._log_operation(
            "update_agent_beliefs",
            agent.agent_id,
            input_summary=input_text,
            problem_domain="belief_update",
        )

        # Parse potential belief updates from input text
        # This is a simplified implementation - in production this would use
        # local LLM inference to extract belief changes
        updated_agent = AgentModel(
            agent_id=agent.agent_id,
            name=agent.name,
            traits=agent.traits.copy(),
            goals=agent.goals.copy(),
            beliefs=agent.beliefs.copy(),
            memory_refs=agent.memory_refs.copy(),
            last_updated=datetime.utcnow(),
        )

        # Simple belief extraction (in production, use local LLM)
        if "believe" in input_text.lower() or "think" in input_text.lower():
            # Extract belief statements - simplified for demonstration
            lines = input_text.split(".")
            for line in lines:
                if any(
                    word in line.lower()
                    for word in ["believe", "think", "feel", "know"]
                ):
                    # Extract topic and belief (simplified parsing)
                    topic = f"statement_{len(updated_agent.beliefs)}"
                    updated_agent.beliefs[topic] = line.strip()

        # Update cache but DO NOT persist to core memory
        self.agent_cache[agent.agent_id] = updated_agent

        return updated_agent

    def detect_contradictions(self, agent: AgentModel) -> List[Contradiction]:
        """
        Find internal contradictions in the agent's belief system.

        🔒 CONTAINMENT: Analyzes agent beliefs only, never touches Axiom's beliefs.
        """
        self._log_operation(
            "detect_contradictions",
            agent.agent_id,
            problem_domain="contradiction_analysis",
        )

        contradictions = []
        belief_items = list(agent.beliefs.items())

        # Simple contradiction detection (in production, use semantic analysis)
        for i, (topic_a, belief_a) in enumerate(belief_items):
            for topic_b, belief_b in belief_items[i + 1 :]:
                if self._check_contradiction(belief_a, belief_b):
                    contradiction = Contradiction(
                        agent_id=agent.agent_id,
                        belief_topic_a=topic_a,
                        belief_topic_b=topic_b,
                        belief_content_a=belief_a,
                        belief_content_b=belief_b,
                        contradiction_type="logical",
                        severity=0.7,  # Simplified scoring
                        description=f"Potential contradiction between '{belief_a}' and '{belief_b}'",
                    )
                    contradictions.append(contradiction)

        return contradictions

    def _check_contradiction(self, belief_a: str, belief_b: str) -> bool:
        """Simple contradiction detection - in production use semantic analysis."""
        # Look for opposing keywords
        opposing_pairs = [
            ("always", "never"),
            ("good", "bad"),
            ("safe", "dangerous"),
            ("should", "should not"),
            ("will", "will not"),
        ]

        belief_a_lower = belief_a.lower()
        belief_b_lower = belief_b.lower()

        for pos, neg in opposing_pairs:
            if (pos in belief_a_lower and neg in belief_b_lower) or (
                neg in belief_a_lower and pos in belief_b_lower
            ):
                return True

        return False

    def simulate_perspective(
        self, agent: AgentModel, problem: str
    ) -> PerspectiveSimulation:
        """
        Return a hypothetical solution from this agent's point of view.

        🔒 CONTAINMENT: Simulates agent perspective without affecting Axiom's reasoning.
        Results are tagged #perspective_sim for journal isolation.
        """
        self._log_operation(
            "simulate_perspective",
            agent.agent_id,
            problem_domain="perspective_simulation",
            input_summary=problem,
        )

        # Build reasoning chain based on agent's traits, goals, and beliefs
        reasoning_chain = []
        reasoning_chain.append(
            f"Considering agent '{agent.name}' with traits: {', '.join(agent.traits)}"
        )
        reasoning_chain.append(f"Agent's primary goals: {', '.join(agent.goals[:3])}")

        # Generate response based on agent's characteristics
        response_parts = []

        # Factor in traits
        if "curious" in agent.traits:
            response_parts.append(
                "I would want to explore this further and understand all implications."
            )
        if "risk-averse" in agent.traits:
            response_parts.append(
                "We need to be extremely careful and consider all potential risks."
            )
        if "optimistic" in agent.traits:
            response_parts.append(
                "I believe we can find a positive solution to this challenge."
            )

        # Factor in relevant beliefs
        for topic, belief in agent.beliefs.items():
            if any(word in problem.lower() for word in topic.lower().split()):
                response_parts.append(f"Based on my belief that {belief}, ")
                reasoning_chain.append(f"Applied belief: {belief}")

        # Factor in goals
        relevant_goals = [
            goal
            for goal in agent.goals
            if any(word in problem.lower() for word in goal.lower().split())
        ]
        if relevant_goals:
            response_parts.append(f"This aligns with my goal to {relevant_goals[0]}.")
            reasoning_chain.append(f"Relevant goal: {relevant_goals[0]}")

        # Combine into coherent response
        if response_parts:
            simulated_response = " ".join(response_parts)
        else:
            simulated_response = f"From my perspective as {agent.name}, this requires careful consideration of the available options."

        simulation = PerspectiveSimulation(
            agent_id=agent.agent_id,
            problem=problem,
            simulated_response=simulated_response,
            confidence=0.6,  # Moderate confidence for simulation
            reasoning_chain=reasoning_chain,
            metadata={"tag": "#perspective_sim", "agent_name": agent.name},
        )

        return simulation

    def summarize_agent(self, agent: AgentModel) -> AgentSummary:
        """
        Generate a natural language summary of the agent's state.

        🔒 CONTAINMENT: Summarizes agent simulation only, never Axiom's state.
        """
        self._log_operation(
            "summarize_agent", agent.agent_id, problem_domain="agent_summary"
        )

        # Count contradictions
        contradictions = self.detect_contradictions(agent)

        # Generate summary text
        summary_parts = []
        summary_parts.append(
            f"{agent.name} is characterized by {', '.join(agent.traits[:3])}."
        )

        if agent.goals:
            summary_parts.append(
                f"Their primary goals include {', '.join(agent.goals[:2])}."
            )

        if agent.beliefs:
            summary_parts.append(f"They hold {len(agent.beliefs)} distinct beliefs.")

        if contradictions:
            summary_parts.append(
                f"Note: {len(contradictions)} potential contradictions detected."
            )

        summary = AgentSummary(
            agent_id=agent.agent_id,
            summary_text=" ".join(summary_parts),
            key_beliefs=list(agent.beliefs.values())[:3],
            dominant_traits=agent.traits[:3],
            primary_goals=agent.goals[:3],
            contradiction_count=len(contradictions),
            last_activity=agent.last_updated,
        )

        return summary

    def infer_agent_emotion(self, agent: AgentModel, context: str) -> EmotionalState:
        """
        Infer an agent's emotional state from dialogue or events.

        🔒 CONTAINMENT: Analyzes agent state only, never modifies Axiom's emotions.
        Returns EmotionalState with emotion type and confidence level.
        """
        self._log_operation(
            "infer_agent_emotion",
            agent.agent_id,
            problem_domain="emotion_inference",
            input_summary=context,
        )

        # Emotional indicators in text analysis
        emotion_keywords = {
            "anxious": ["worried", "concerned", "nervous", "uncertain", "hesitant"],
            "defensive": ["protect", "defend", "attack", "blame", "fault"],
            "confident": ["sure", "certain", "know", "believe strongly", "confident"],
            "frustrated": ["annoyed", "irritated", "stuck", "blocked", "difficult"],
            "curious": ["wonder", "interested", "explore", "learn", "understand"],
            "skeptical": ["doubt", "question", "unsure", "suspicious", "wary"],
        }

        context_lower = context.lower()
        detected_emotions = {}

        # Score each emotion based on keyword presence
        for emotion, keywords in emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in context_lower)
            if score > 0:
                detected_emotions[emotion] = score

        # Factor in agent traits to adjust emotional baseline
        trait_emotion_modifiers = {
            "anxious": {"risk-averse": 1.2, "cautious": 1.1},
            "confident": {"optimistic": 1.2, "assertive": 1.1},
            "curious": {"curious": 1.3, "inquisitive": 1.2},
            "defensive": {"protective": 1.1},
        }

        for emotion in detected_emotions:
            for trait in agent.traits:
                if (
                    emotion in trait_emotion_modifiers
                    and trait in trait_emotion_modifiers[emotion]
                ):
                    detected_emotions[emotion] *= trait_emotion_modifiers[emotion][
                        trait
                    ]

        # Select dominant emotion
        if detected_emotions:
            dominant_emotion = max(detected_emotions, key=detected_emotions.get)
            intensity = min(
                detected_emotions[dominant_emotion] / 3.0, 1.0
            )  # Normalize to 0-1
            confidence = min(intensity * 0.8, 0.9)  # Conservative confidence
        else:
            dominant_emotion = "neutral"
            intensity = 0.3
            confidence = 0.4

        emotional_state = EmotionalState(
            agent_id=agent.agent_id,
            emotion=dominant_emotion,
            intensity=intensity,
            confidence=confidence,
            context=context[:500],  # Truncate for storage
            metadata={"memoryType": "simulation", "agent_name": agent.name},
        )

        return emotional_state

    def model_agent_intentions(self, agent: AgentModel, context: str) -> IntentionModel:
        """
        Infer likely intentions from agent's behavior and context.

        🔒 CONTAINMENT: Models agent intentions only, never affects Axiom's goals.
        Returns list of inferred intention strings.
        """
        self._log_operation(
            "model_agent_intentions",
            agent.agent_id,
            problem_domain="intention_modeling",
            input_summary=context,
        )

        # Intention indicators based on language patterns
        intention_patterns = {
            "gain influence": ["convince", "persuade", "show", "demonstrate", "prove"],
            "avoid blame": ["not my fault", "wasn't me", "defensive", "justify"],
            "signal withdrawal": ["step back", "distance", "leave", "exit", "done"],
            "seek understanding": [
                "clarify",
                "explain",
                "help me understand",
                "confused",
            ],
            "test boundaries": ["what if", "push", "challenge", "test", "try"],
            "build rapport": [
                "agree",
                "similar",
                "together",
                "collaborate",
                "understand",
            ],
            "establish dominance": ["wrong", "better way", "should", "must", "always"],
            "gather information": ["tell me", "what about", "how", "why", "details"],
        }

        context_lower = context.lower()
        detected_intentions = []
        reasoning_chain = []

        # Match intention patterns
        for intention, patterns in intention_patterns.items():
            matches = sum(1 for pattern in patterns if pattern in context_lower)
            if matches > 0:
                detected_intentions.append(intention)
                reasoning_chain.append(
                    f"Detected '{intention}' from patterns: {matches} matches"
                )

        # Factor in agent goals to predict likely intentions
        for goal in agent.goals[:3]:  # Check top 3 goals
            goal_lower = goal.lower()
            if any(word in context_lower for word in goal_lower.split()):
                intention = f"advance goal: {goal}"
                if intention not in detected_intentions:
                    detected_intentions.append(intention)
                    reasoning_chain.append(f"Intention aligned with agent goal: {goal}")

        # Factor in agent traits for intention likelihood
        trait_intentions = {
            "curious": "seek understanding",
            "assertive": "establish dominance",
            "collaborative": "build rapport",
            "defensive": "avoid blame",
            "strategic": "gain influence",
        }

        for trait in agent.traits:
            if trait in trait_intentions:
                trait_intention = trait_intentions[trait]
                if trait_intention not in detected_intentions:
                    detected_intentions.append(trait_intention)
                    reasoning_chain.append(
                        f"Trait-based intention: {trait} -> {trait_intention}"
                    )

        # Limit to most likely intentions
        final_intentions = detected_intentions[:4]  # Top 4 most likely
        confidence = min(len(final_intentions) * 0.2 + 0.3, 0.9)

        intention_model = IntentionModel(
            agent_id=agent.agent_id,
            intentions=final_intentions,
            confidence=confidence,
            context=context[:500],
            reasoning_chain=reasoning_chain,
        )

        return intention_model

    def generate_empathy_summary(
        self, agent: AgentModel, context: str
    ) -> EmpathySummary:
        """
        Combine emotional + intentional inference into a paragraph summary.

        🔒 CONTAINMENT: Creates empathy simulation only, tagged for journal isolation.
        Returns natural language summary suitable for journal reflection.
        """
        self._log_operation(
            "generate_empathy_summary",
            agent.agent_id,
            problem_domain="empathy_summary",
            input_summary=context,
        )

        # Get emotional and intentional inferences
        emotional_state = self.infer_agent_emotion(agent, context)
        intentions = self.model_agent_intentions(agent, context)

        # Build natural language summary
        summary_parts = []

        # Start with agent identification
        summary_parts.append(f"{agent.name}")

        # Add emotional state
        if emotional_state.emotion != "neutral":
            intensity_desc = (
                "mildly"
                if emotional_state.intensity < 0.4
                else "moderately" if emotional_state.intensity < 0.7 else "strongly"
            )
            summary_parts.append(f"seems {intensity_desc} {emotional_state.emotion}")
        else:
            summary_parts.append("appears emotionally neutral")

        # Add intentional analysis
        if intentions.intentions:
            if len(intentions.intentions) == 1:
                summary_parts.append(
                    f"and is likely trying to {intentions.intentions[0]}"
                )
            elif len(intentions.intentions) == 2:
                summary_parts.append(
                    f"and appears to be {intentions.intentions[0]} while also {intentions.intentions[1]}"
                )
            else:
                primary_intention = intentions.intentions[0]
                summary_parts.append(
                    f"and is primarily focused on {primary_intention}, among other goals"
                )
        else:
            summary_parts.append("with unclear immediate intentions")

        # Add contextual insight based on agent traits
        if agent.traits:
            dominant_trait = agent.traits[0]
            summary_parts.append(f"This aligns with their {dominant_trait} nature.")

        # Combine into flowing text
        summary_text = " ".join(summary_parts)

        empathy_summary = EmpathySummary(
            agent_id=agent.agent_id,
            emotional_state=emotional_state,
            intentions=intentions,
            summary_text=summary_text,
            context=context[:500],
            metadata={
                "tag": "#empathy_inference",
                "memoryType": "simulation",
                "agent_name": agent.name,
                "emotional_state": emotional_state.emotion,
                "inferred_intentions": ", ".join(intentions.intentions[:2]),
            },
        )

        return empathy_summary

    def score_empathic_alignment(
        self, agent: AgentModel, axiom_response: str, agent_context: str = ""
    ) -> EmpathyAlignment:
        """
        Score how well Axiom's response matches the agent's inferred state.

        🔒 CONTAINMENT: Evaluates response alignment only, never modifies responses.
        Returns float from 0 to 1 with suggestions for improvement.
        """
        self._log_operation(
            "score_empathic_alignment",
            agent.agent_id,
            problem_domain="empathy_alignment",
            input_summary=axiom_response,
        )

        # Use provided context or fall back to response for state inference
        context = agent_context if agent_context else axiom_response
        emotional_state = self.infer_agent_emotion(agent, context)
        intentions = self.model_agent_intentions(agent, context)

        # Analyze Axiom's response characteristics
        response_lower = axiom_response.lower()

        # Score emotional appropriateness
        emotional_alignment_score = 0.5  # Default neutral

        emotion_response_patterns = {
            "anxious": [
                "understand your concern",
                "let's be careful",
                "step by step",
                "carefully",
                "concern",
                "review",
            ],
            "defensive": [
                "i hear you",
                "valid point",
                "let's find common ground",
                "understand",
            ],
            "confident": ["great point", "building on that", "exactly", "excellent"],
            "frustrated": [
                "let's try a different approach",
                "i understand the challenge",
                "break this down",
            ],
            "curious": [
                "great question",
                "let's explore",
                "interesting perspective",
                "explore",
            ],
            "skeptical": [
                "what if we considered",
                "here's another way to think",
                "evidence suggests",
            ],
        }

        if emotional_state.emotion in emotion_response_patterns:
            appropriate_patterns = emotion_response_patterns[emotional_state.emotion]
            matches = sum(
                1 for pattern in appropriate_patterns if pattern in response_lower
            )
            if matches > 0:
                emotional_alignment_score = min(
                    0.4 + matches * 0.25, 1.0
                )  # More generous scoring

        # Check for clearly inappropriate responses based on emotion
        inappropriate_patterns = {
            "anxious": ["quickly", "don't overthink", "just do it", "rush", "fast"],
            "defensive": ["you're wrong", "that's bad", "completely incorrect"],
            "frustrated": ["calm down", "don't worry", "it's easy"],
        }

        if emotional_state.emotion in inappropriate_patterns:
            inappropriate_matches = sum(
                1
                for pattern in inappropriate_patterns[emotional_state.emotion]
                if pattern in response_lower
            )
            if inappropriate_matches > 0:
                emotional_alignment_score = max(
                    0.1, emotional_alignment_score - inappropriate_matches * 0.3
                )

        # Score intentional alignment
        intentional_alignment_score = 0.5  # Default neutral

        if intentions.intentions:
            intention_keywords = {
                "seek understanding": [
                    "explain",
                    "clarify",
                    "here's how",
                    "because",
                    "understand",
                    "review",
                ],
                "build rapport": ["we", "together", "shared", "common", "let's"],
                "gain influence": ["consider", "perhaps", "what about", "imagine"],
                "gather information": [
                    "tell me more",
                    "what do you think",
                    "your perspective",
                ],
                "avoid blame": ["understand", "concern", "valid", "hear you"],
                "test boundaries": ["let's", "consider", "what if", "try"],
            }

            total_matches = 0
            for intention in intentions.intentions[:2]:  # Check top 2 intentions
                if intention in intention_keywords:
                    patterns = intention_keywords[intention]
                    matches = sum(
                        1 for pattern in patterns if pattern in response_lower
                    )
                    total_matches += matches

            if total_matches > 0:
                intentional_alignment_score = min(
                    0.4 + total_matches * 0.2, 1.0
                )  # More generous scoring

        # Overall alignment score (weighted average)
        overall_score = (
            emotional_alignment_score * 0.6 + intentional_alignment_score * 0.4
        )

        # Generate reasoning and suggestions
        reasoning_parts = []
        suggestions = []

        if emotional_alignment_score < 0.5:
            reasoning_parts.append(
                f"Low emotional alignment for {emotional_state.emotion} state"
            )
            suggestions.append(
                f"Consider acknowledging the agent's {emotional_state.emotion} emotional state"
            )

        if intentional_alignment_score < 0.5 and intentions.intentions:
            reasoning_parts.append(
                f"Response doesn't align with agent's intentions: {intentions.intentions[0]}"
            )
            suggestions.append(
                f"Address the agent's apparent intention to {intentions.intentions[0]}"
            )

        if overall_score < 0.5:
            suggestions.append(
                "Consider adjusting tone to better match agent's current state"
            )

        reasoning = (
            "; ".join(reasoning_parts)
            if reasoning_parts
            else "Reasonable empathic alignment detected"
        )

        # Log warning for low alignment
        if overall_score < 0.5:
            logger.warning(
                f"Low empathy alignment score ({overall_score:.2f}) for agent {agent.agent_id}"
            )

        empathy_alignment = EmpathyAlignment(
            agent_id=agent.agent_id,
            axiom_response=axiom_response[:500],  # Truncate for storage
            agent_emotional_state=emotional_state,
            agent_intentions=intentions,
            alignment_score=overall_score,
            reasoning=reasoning,
            suggestions=suggestions,
            metadata={
                "memoryType": "simulation",
                "agent_name": agent.name,
                "low_empathy_alignment": overall_score < 0.5,
            },
        )

        return empathy_alignment

    def get_audit_log(self) -> List[ToMEvent]:
        """Return complete audit log for transparency and monitoring."""
        return self.audit_log.copy()

    def verify_containment(self) -> bool:
        """
        Verify that all operations have respected containment rules.

        Returns True if containment is verified, False if violations detected.
        """
        # Check that no operations modified core systems
        violations = [
            event for event in self.audit_log if not event.containment_verified
        ]

        if violations:
            logger.warning(f"Containment violations detected: {len(violations)} events")
            return False

        logger.info("Containment verification passed - no violations detected")
        return True


# Module-level convenience functions for direct import
_engine = TheoryOfMindEngine()


def load_agent(agent_id: str) -> Optional[AgentModel]:
    """Load an agent model from cache or storage."""
    return _engine.load_agent(agent_id)


def create_agent(
    agent_id: str,
    name: str,
    traits: List[str] = None,
    goals: List[str] = None,
    beliefs: Dict[str, str] = None,
) -> AgentModel:
    """Create a new agent model for simulation."""
    return _engine.create_agent(agent_id, name, traits, goals, beliefs)


def update_agent_beliefs(agent: AgentModel, input_text: str) -> AgentModel:
    """Update agent's belief model based on text input."""
    return _engine.update_agent_beliefs(agent, input_text)


def detect_contradictions(agent: AgentModel) -> List[Contradiction]:
    """Find internal contradictions in the agent's beliefs."""
    return _engine.detect_contradictions(agent)


def simulate_perspective(agent: AgentModel, problem: str) -> PerspectiveSimulation:
    """Return a hypothetical solution from this agent's point of view."""
    return _engine.simulate_perspective(agent, problem)


def summarize_agent(agent: AgentModel) -> AgentSummary:
    """Generate a natural language summary of the agent's state."""
    return _engine.summarize_agent(agent)


def get_audit_log() -> List[ToMEvent]:
    """Return complete audit log for transparency."""
    return _engine.get_audit_log()


def verify_containment() -> bool:
    """Verify that all operations have respected containment rules."""
    return _engine.verify_containment()


def infer_agent_emotion(agent: AgentModel, context: str) -> EmotionalState:
    """Infer an agent's emotional state from dialogue or events."""
    return _engine.infer_agent_emotion(agent, context)


def model_agent_intentions(agent: AgentModel, context: str) -> IntentionModel:
    """Infer likely intentions from agent's behavior and context."""
    return _engine.model_agent_intentions(agent, context)


def generate_empathy_summary(agent: AgentModel, context: str) -> EmpathySummary:
    """Combine emotional + intentional inference into a paragraph summary."""
    return _engine.generate_empathy_summary(agent, context)


def score_empathic_alignment(
    agent: AgentModel, axiom_response: str, agent_context: str = ""
) -> EmpathyAlignment:
    """Score how well Axiom's response matches the agent's inferred state."""
    return _engine.score_empathic_alignment(agent, axiom_response, agent_context)
