from __future__ import annotations

import abc
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple


class BeliefGraphBase(abc.ABC):
    """Abstract interface for a symbolic belief graph backend.

    All implementations must be fail-closed: methods should not raise on common
    errors and instead return conservative defaults.
    """

    @abc.abstractmethod
    def upsert_belief(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        confidence: float = 0.5,
        sources: Optional[Iterable[str]] = None,
    ) -> Optional[str]:
        """Insert or update a belief triple and return its ID (string) on success.

        Implementations may insert a new row each call or update an existing
        record if the same triple exists. Returning None signals failure.
        """

    @abc.abstractmethod
    def get_beliefs(self, subjects: List[str], *, hops: int = 1) -> List[Dict[str, Any]]:
        """Retrieve beliefs relevant to the provided subjects.

        Implementations should return up to ~20 items ordered by confidence and
        recency. Each item should be a dict compatible with memory candidate
        entries, minimally including: {"id","content","type":"belief",
        "confidence","recency","tags":["belief"]}.
        """

    @abc.abstractmethod
    def link_beliefs(self, id1: str, id2: str, relation: str) -> Optional[str]:
        """Create a typed relation between two belief records. Returns relation ID or None."""

    # Phase 4: Graph traversal API (optional for backends)
    def get_related_beliefs(self, subject: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Traverse the belief graph starting from a subject string.

        Default implementation falls back to get_beliefs([subject], hops=depth) if implemented.
        Implementations may override for efficient traversal.
        """
        try:
            return self.get_beliefs([subject], hops=max(1, int(depth)))
        except Exception:
            return []

    # Phase 10: Associative retrieval
    def get_associative_beliefs(self, entity: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Traverse beliefs associated with an entity up to depth.

        Default implementation delegates to get_related_beliefs to preserve
        compatibility for backends that did not specialize associative traversal.
        Implementations should cap results to a small, safe maximum.
        """
        try:
            return self.get_related_beliefs(entity, depth=depth)[:20]
        except Exception:
            return []

    # Phase 13: Causal traversal (optional; default falls back to related)
    def get_causal_beliefs(self, entity: str, *, direction: str = "forward", depth: int = 1) -> List[Dict[str, Any]]:
        """Traverse beliefs along causal relations starting from an entity string.

        direction: "forward" follows causes→effects (cause_of/enables/results_in)
                   "backward" follows effects→causes (effect_of)

        Default implementation uses get_related_beliefs for compatibility.
        Implementations may override to honor relation types and direction.
        """
        try:
            return self.get_related_beliefs(entity, depth=max(1, int(depth)))
        except Exception:
            return []

    # Phase 7/24: Belief state transitions (optional; default no-op)
    def set_belief_state(self, belief_id: str, state: str) -> bool:
        """Set the resolution state for a belief.

        Allowed states include: active | superseded | uncertain | archived | retired

        Default implementation returns False (not supported). Implementations must fail-closed.
        """
        try:
            _ = (belief_id or "").strip()
            _ = (state or "").strip().lower()
            return False
        except Exception:
            return False

    # Phase 14: Counterfactual simulation (optional; default returns empty)
    def simulate_counterfactual(
        self,
        node: str,
        remove_edge: Tuple[str, str, str] | None = None,
    ) -> List[Dict[str, Any]]:
        """Simulate counterfactual effects when a cause is negated.

        remove_edge: optional tuple (subject, relation, object) to virtually remove.
        Returns a list of plausible alternative effects/outcomes as dicts.

        Default implementation returns []. Implementations should log with the
        [RECALL][Counterfactual] prefix for auditability.
        """
        try:
            _ = (node or "").strip()
            _ = remove_edge  # ignored by default
            return []
        except Exception:
            return []


class DisabledBeliefGraph(BeliefGraphBase):
    """Fail-closed, no-op backend when Belief Graph is disabled or unsupported.

    Selected when AXIOM_BELIEF_GRAPH_ENABLED is falsey, or when an unsupported
    backend is configured. Methods return conservative defaults and never raise.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        try:
            self._logger.info("[RECALL][BeliefGraph] disabled backend active")
        except Exception:
            pass

    def upsert_belief(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        confidence: float = 0.5,
        sources: Optional[Iterable[str]] = None,
    ) -> Optional[str]:
        return None

    def get_beliefs(self, subjects: List[str], *, hops: int = 1) -> List[Dict[str, Any]]:
        return []

    def link_beliefs(self, id1: str, id2: str, relation: str) -> Optional[str]:
        return None

    def get_related_beliefs(self, subject: str, depth: int = 1) -> List[Dict[str, Any]]:  # type: ignore[override]
        return []

    def get_associative_beliefs(self, entity: str, depth: int = 2) -> List[Dict[str, Any]]:  # type: ignore[override]
        return []

    def get_causal_beliefs(self, entity: str, *, direction: str = "forward", depth: int = 1) -> List[Dict[str, Any]]:  # type: ignore[override]
        return []

    def set_belief_state(self, belief_id: str, state: str) -> bool:  # type: ignore[override]
        return False

    def simulate_counterfactual(
        self,
        node: str,
        remove_edge: Tuple[str, str, str] | None = None,
    ) -> List[Dict[str, Any]]:  # type: ignore[override]
        try:
            self._logger.info("[RECALL][Counterfactual] disabled backend – simulation skipped")
        except Exception:
            pass
        return []

