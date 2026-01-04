"""Neo4j belief graph backend (stub / not supported).

At present, SQLite is the only supported Belief Graph backend. This module is a
placeholder for future development and should not be used in production. Any
imports of `Neo4jBeliefGraph` are considered deprecated. See README for details.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from .base import BeliefGraphBase

logger = logging.getLogger(__name__)


class Neo4jBeliefGraph(BeliefGraphBase):
    """Stub implementation: logs usage and returns safe defaults."""

    def __init__(self, *_, **__):
        logger.warning("[BeliefGraph] Neo4j backend not supported; this is a stub placeholder")

    def upsert_belief(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        confidence: float = 0.5,
        sources: Optional[Iterable[str]] = None,
    ) -> Optional[str]:
        logger.info(
            "[BeliefGraph] (stub) upsert_belief called: %s – %s – %s",
            subject,
            predicate,
            obj,
        )
        return None

    def get_beliefs(self, subjects: List[str], *, hops: int = 1) -> List[Dict[str, Any]]:
        logger.info("[BeliefGraph] (stub) get_beliefs called for %d subject(s)", len(subjects or []))
        return []

    def link_beliefs(self, id1: str, id2: str, relation: str) -> Optional[str]:
        logger.info("[BeliefGraph] (stub) link_beliefs called: %s -[%s]-> %s", id1, relation, id2)
        return None

    def get_causal_beliefs(self, entity: str, *, direction: str = "forward", depth: int = 1) -> List[Dict[str, Any]]:  # type: ignore[override]
        logger.info("[BeliefGraph] (stub) get_causal_beliefs entity=%r direction=%s depth=%s", entity, direction, depth)
        return []

    def get_related_beliefs(self, subject: str, depth: int = 1) -> List[Dict[str, Any]]:
        logger.info("[BeliefGraph] (stub) get_related_beliefs subject=%r depth=%s", subject, depth)
        return []

    def get_associative_beliefs(self, entity: str, depth: int = 2) -> List[Dict[str, Any]]:  # type: ignore[override]
        logger.info("[BeliefGraph] (stub) get_associative_beliefs entity=%r depth=%s", entity, depth)
        return []

    def set_belief_state(self, belief_id: str, state: str) -> bool:  # type: ignore[override]
        try:
            logger.info("[BeliefGraph] (stub) set_belief_state id=%s state=%s", belief_id, state)
        except Exception:
            pass
        return False

    def simulate_counterfactual(self, node: str, remove_edge: tuple[str, str, str] | None = None):  # type: ignore[override]
        try:
            logger.info("[RECALL][Counterfactual] (stub) starting simulation for node=%s", (node or "").strip())
            if isinstance(remove_edge, tuple) and len(remove_edge) == 3:
                subj, rel, obj = remove_edge
                logger.info(
                    "[RECALL][Counterfactual] (stub) removed edge: %s --(%s)--> %s",
                    (subj or "").strip(), (rel or "").strip(), (obj or "").strip(),
                )
            logger.info("[RECALL][Counterfactual] (stub) alternate path: (none)")
        except Exception:
            pass
        return []

