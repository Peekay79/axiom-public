import logging
import sys

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("26")
def test_procedural_loop_gating_and_drafting(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Build a simple user → axiom → user triple, repeated to exceed support
    class DummyMem:
        def snapshot(self, limit=None):
            items = [
                {"id": "u1", "content": "how to deploy app", "type": "user"},
                {"id": "a1", "content": "use docker compose", "type": "axiom"},
                {"id": "u2", "content": "deployment succeeded", "type": "user"},
                {"id": "u3", "content": "how to deploy app", "type": "user"},
                {"id": "a2", "content": "use docker compose", "type": "axiom"},
                {"id": "u4", "content": "deployment succeeded", "type": "user"},
            ]
            return items

    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", type("M", (), {"Memory": lambda: DummyMem()}))

    import procedural_loop as pl

    class StubBG:
        def upsert_belief(self, subject, predicate, obj, *, confidence=0.5, sources=None):
            return "202"

        def set_belief_state(self, bid, state):
            return True

        def link_beliefs(self, id1, id2, relation):
            return None

    pl._belief_graph = StubBG()  # type: ignore[attr-defined]

    with temp_env({
        "AXIOM_PROCEDURAL_LOOP_ENABLED": "1",
        "AXIOM_PROCEDURAL_WINDOW_TURNS": "12",
        "AXIOM_PROCEDURAL_MIN_SUPPORT": "2",
    }):
        res = pl.maybe_run_procedural_loop()
        assert res.get("status") == "ok"
        assert res.get("drafted", 0) >= 1
        assert res.get("integrated", 0) >= 1
        assert any("[RECALL][Loop26]" in r.getMessage() for r in caplog.records)


@pytest.mark.phase("26")
def test_procedural_loop_disabled(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    class DummyMem:
        def snapshot(self, limit=None):
            return []

    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", type("M", (), {"Memory": lambda: DummyMem()}))
    import importlib
    pl = importlib.import_module("procedural_loop")

    with temp_env({"AXIOM_PROCEDURAL_LOOP_ENABLED": "0"}):
        res = pl.maybe_run_procedural_loop()
        assert res.get("status") == "aborted" and res.get("reason") == "disabled"
        assert any("[RECALL][Loop26] aborted" in r.getMessage() for r in caplog.records)

