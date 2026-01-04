"""
Theory of Mind Models

This module defines the core data structures for representing and tracking
other agents' mental states without interfering with Axiom's own beliefs.

All agent models are contained simulations - they do not affect Axiom's
core belief state or memory system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


@dataclass
class AgentModel:
    """
    Represents a simulated agent's mental state for Theory of Mind reasoning.

    This is a contained simulation that tracks beliefs, goals, and traits
    of other agents without affecting Axiom's own cognitive state.
    """

    agent_id: str
    name: str
    traits: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    beliefs: Dict[str, str] = field(
        default_factory=dict
    )  # {belief_topic: belief_content}
    memory_refs: List[str] = field(default_factory=list)  # UUIDs of associated memories
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Ensure agent_id is set and validate basic structure."""
        if not self.agent_id:
            self.agent_id = str(uuid4())

        # Ensure all collections are proper types
        if not isinstance(self.traits, list):
            self.traits = list(self.traits) if self.traits else []
        if not isinstance(self.goals, list):
            self.goals = list(self.goals) if self.goals else []
        if not isinstance(self.beliefs, dict):
            self.beliefs = dict(self.beliefs) if self.beliefs else {}
        if not isinstance(self.memory_refs, list):
            self.memory_refs = list(self.memory_refs) if self.memory_refs else []


@dataclass
class AgentToneProfile:
    """
    Stores learned tone preferences for an agent based on empathy alignment history.

    This enables the empathic learning loop to adapt tone recommendations over time
    based on successful emotional state and intent mappings.
    """

    agent_id: str
    preferred_tones: Dict[str, str] = field(
        default_factory=dict
    )  # {emotion/intent: "tone, style"}
    alignment_history: List[Dict[str, any]] = field(
        default_factory=list
    )  # Recent alignment scores
    entry_count: int = 0  # Total number of alignment entries processed
    confidence_threshold: float = 0.8  # Minimum score to consider for learning
    decay_factor: float = 0.95  # Factor for forgetting old patterns over time
    last_updated: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_alignment_entry(
        self,
        emotion: str,
        intent: str,
        tone_used: str,
        alignment_score: float,
        context: str = "",
    ) -> None:
        """Add a new alignment score to the learning history."""
        if alignment_score >= self.confidence_threshold:
            # Create key for emotion or intent
            emotion_key = f"emotion_{emotion}" if emotion else None
            intent_key = f"intent_{intent}" if intent else None

            # Store high-confidence examples
            entry = {
                "emotion": emotion,
                "intent": intent,
                "tone_used": tone_used,
                "alignment_score": alignment_score,
                "context_summary": context[:100] if context else "",
                "timestamp": datetime.utcnow().isoformat(),
            }

            self.alignment_history.append(entry)

            # Update preferred tones based on successful mappings
            if emotion_key and alignment_score > 0.85:
                self._update_preferred_tone(emotion_key, tone_used, alignment_score)
            if intent_key and alignment_score > 0.85:
                self._update_preferred_tone(intent_key, tone_used, alignment_score)

            # Apply decay to old entries and maintain history size
            self._apply_decay()

            self.entry_count += 1
            self.last_updated = datetime.utcnow()

    def _update_preferred_tone(self, key: str, tone: str, score: float) -> None:
        """Update preferred tone mapping with weighted averaging."""
        if key not in self.preferred_tones:
            self.preferred_tones[key] = tone
        else:
            # Simple replacement for now - could implement weighted averaging
            # if new score is significantly higher
            current_score = self._estimate_current_tone_score(key)
            if score > current_score + 0.1:  # Significant improvement
                self.preferred_tones[key] = tone

    def _estimate_current_tone_score(self, key: str) -> float:
        """Estimate the average score for the current preferred tone."""
        relevant_entries = [
            entry
            for entry in self.alignment_history[-10:]  # Last 10 entries
            if (
                key.startswith("emotion_")
                and entry.get("emotion") == key.replace("emotion_", "")
            )
            or (
                key.startswith("intent_")
                and entry.get("intent") == key.replace("intent_", "")
            )
        ]
        if relevant_entries:
            return sum(entry["alignment_score"] for entry in relevant_entries) / len(
                relevant_entries
            )
        return 0.5  # Default neutral score

    def _apply_decay(self) -> None:
        """Apply decay factor and limit history size to prevent memory bloat."""
        # Keep only last 20 entries to prevent unlimited growth
        if len(self.alignment_history) > 20:
            self.alignment_history = self.alignment_history[-20:]

    def get_preferred_tone(
        self, emotion: str = None, intent: str = None
    ) -> Optional[str]:
        """Get preferred tone for given emotion or intent."""
        if emotion:
            emotion_key = f"emotion_{emotion}"
            if emotion_key in self.preferred_tones:
                return self.preferred_tones[emotion_key]

        if intent:
            intent_key = f"intent_{intent}"
            if intent_key in self.preferred_tones:
                return self.preferred_tones[intent_key]

        return None

    def reset(self) -> None:
        """Reset the tone profile for debugging or manual override."""
        self.preferred_tones.clear()
        self.alignment_history.clear()
        self.entry_count = 0
        self.last_updated = datetime.utcnow()


@dataclass
class Contradiction:
    """
    Represents a detected contradiction within an agent's belief system.
    """

    contradiction_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    belief_topic_a: str = ""
    belief_topic_b: str = ""
    belief_content_a: str = ""
    belief_content_b: str = ""
    contradiction_type: str = "logical"  # logical, factual, temporal, etc.
    severity: float = 0.0  # 0.0 to 1.0
    detected_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""


@dataclass
class ToMEvent:
    """
    Audit log entry for Theory of Mind operations.

    Ensures transparency and containment by tracking all ToM operations.
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    operation: str = ""  # simulate_perspective, update_beliefs, etc.
    agent_id: str = ""
    problem_domain: str = ""
    input_summary: str = ""
    output_summary: str = ""
    containment_verified: bool = False  # Did this operation respect containment rules?


@dataclass
class PerspectiveSimulation:
    """
    Result of simulating an agent's perspective on a problem.

    Contains the simulated response and metadata about the simulation.
    """

    simulation_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    problem: str = ""
    simulated_response: str = ""
    confidence: float = 0.0  # How confident the simulation is
    reasoning_chain: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentSummary:
    """
    Natural language summary of an agent's current state.
    """

    agent_id: str = ""
    summary_text: str = ""
    key_beliefs: List[str] = field(default_factory=list)
    dominant_traits: List[str] = field(default_factory=list)
    primary_goals: List[str] = field(default_factory=list)
    contradiction_count: int = 0
    last_activity: Optional[datetime] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EmotionalState:
    """
    Represents an inferred emotional state of an agent.

    Used by the empathy engine to track emotional patterns and responses.
    """

    emotion_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    emotion: str = ""  # e.g., 'anxious', 'defensive', 'confident', 'frustrated'
    intensity: float = 0.0  # 0.0 to 1.0
    confidence: float = 0.0  # How confident we are in this inference
    context: str = ""  # Context that led to this emotional inference
    detected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class IntentionModel:
    """
    Represents inferred intentions/motivations of an agent.
    """

    intention_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    intentions: List[str] = field(
        default_factory=list
    )  # e.g., ['gain influence', 'avoid blame']
    confidence: float = 0.0  # Overall confidence in intention inference
    context: str = ""  # Context that led to these inferences
    detected_at: datetime = field(default_factory=datetime.utcnow)
    reasoning_chain: List[str] = field(default_factory=list)


@dataclass
class EmpathySummary:
    """
    Combined emotional and intentional summary for journal reflection.
    """

    summary_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    emotional_state: Optional[EmotionalState] = None
    intentions: Optional[IntentionModel] = None
    summary_text: str = ""  # Natural language summary combining emotion + intention
    context: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = field(
        default_factory=lambda: {"tag": "#empathy_inference"}
    )


@dataclass
class EmpathyAlignment:
    """
    Represents how well Axiom's response aligns with an agent's inferred state.
    """

    alignment_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    axiom_response: str = ""
    agent_emotional_state: Optional[EmotionalState] = None
    agent_intentions: Optional[IntentionModel] = None
    alignment_score: float = 0.0  # 0.0 to 1.0
    reasoning: str = ""  # Why this score was assigned
    suggestions: List[str] = field(default_factory=list)  # How to improve alignment
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = field(default_factory=dict)
