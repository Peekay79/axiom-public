from __future__ import annotations

import logging
import os
from typing import List


def _capture_logs(caplog) -> List[str]:
    return [rec.getMessage() for rec in caplog.records]


def test_stub_guard_blocks_neo4j_and_logs(caplog):
    caplog.set_level(logging.INFO)
    from cockpit.dashboard import is_enabled

    assert is_enabled("neo4j") is False
    msgs = "\n".join(_capture_logs(caplog))
    assert "[RECALL][Stub] neo4j not implemented" in msgs


def test_non_stub_default_on_logs_once(caplog):
    caplog.set_level(logging.INFO)
    from cockpit.dashboard import is_enabled

    assert is_enabled("champ") is True
    msgs = "\n".join(_capture_logs(caplog))
    assert "[RECALL][Subsystem] champ enabled by default" in msgs


def test_belief_backend_neo4j_returns_disabled_and_deprecation_log(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    # Force backend env to neo4j
    monkeypatch.setenv("AXIOM_BELIEF_BACKEND", "neo4j")
    # Ensure graph enabled by default (guard + env default is 1 in code)
    monkeypatch.delenv("AXIOM_BELIEF_GRAPH_ENABLED", raising=False)

    import importlib
    import belief_graph as bgmod
    importlib.reload(bgmod)

    # Instance should be DisabledBeliefGraph
    from belief_graph.base import DisabledBeliefGraph

    assert isinstance(bgmod.belief_graph, DisabledBeliefGraph)
    msgs = "\n".join(_capture_logs(caplog))
    assert "[RECALL][Deprecation] Neo4j stub — disabled by design" in msgs

