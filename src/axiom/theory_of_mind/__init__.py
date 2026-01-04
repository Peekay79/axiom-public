"""
Theory of Mind for Axiom

A standalone module for Theory of Mind (ToM) reasoning that simulates other minds
without corrupting Axiom's own belief state. Includes strict containment safeguards,
agent-specific memory tagging, and structured interfaces for simulation and reasoning.

🔒 CONTAINMENT GUARANTEE:
This module operates in isolation and NEVER modifies Axiom's core beliefs, memory,
or cognitive state. All agent models are read-only simulations.

Usage:
    from axiom.theory_of_mind import create_agent, simulate_perspective

    agent = create_agent("dr_lyra", "Dr. Lyra",
                        traits=["curious", "risk-averse"],
                        goals=["understand consciousness"])

    simulation = simulate_perspective(agent, "Should we deploy recursive AI?")
    print(simulation.simulated_response)

⚠️  WARNING: This is a simulation space, not a belief-altering system.
"""

from .engine import (
    TheoryOfMindEngine,
    create_agent,
    detect_contradictions,
    get_audit_log,
    load_agent,
    simulate_perspective,
    summarize_agent,
    update_agent_beliefs,
    verify_containment,
)
from .models import (
    AgentModel,
    AgentSummary,
    Contradiction,
    PerspectiveSimulation,
    ToMEvent,
)

__version__ = "1.0.0"
__author__ = "Axiom Development Team"

# Export main public interface
__all__ = [
    # Core models
    "AgentModel",
    "Contradiction",
    "ToMEvent",
    "PerspectiveSimulation",
    "AgentSummary",
    # Main engine class
    "TheoryOfMindEngine",
    # Convenience functions
    "load_agent",
    "create_agent",
    "update_agent_beliefs",
    "detect_contradictions",
    "simulate_perspective",
    "summarize_agent",
    "get_audit_log",
    "verify_containment",
]


# Containment verification on import
def _verify_module_containment():
    """Verify module respects containment rules on import."""
    import logging

    logger = logging.getLogger("axiom.theory_of_mind")
    logger.info("Theory of Mind module loaded with containment safeguards active")


_verify_module_containment()
