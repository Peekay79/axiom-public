"""Belief Graph package

SQLite is the only supported backend at present. The Neo4j backend exists as a
stub for future development but is not active.
"""

from .base import BeliefGraphBase, DisabledBeliefGraph  # re-export
from .sqlite_backend import SQLiteBeliefGraph

__all__ = [
    "BeliefGraphBase",
    "DisabledBeliefGraph",
    "SQLiteBeliefGraph",
]

