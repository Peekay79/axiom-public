import logging
import sys
from datetime import datetime, timedelta, timezone

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("25")
def test_episodic_loop_gating_and_integration(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Prepare a recent timestamp within the window
    now = datetime.now(timezone.utc)
    ts0 = now.isoformat()
    ts1 = (now + timedelta(minutes=5)).isoformat()
    ts2 = (now + timedelta(minutes=10)).isoformat()

    class DummyMem:
        def snapshot(self, limit=None):  # episodic selection uses all
            return [
                {"id": "e1", "content": "alpha project kickoff", "timestamp": ts0, "type": "episodic", "confidence": 0.8},
                {"id": "e2", "content": "alpha project planning", "timestamp": ts1, "type": "short_term", "confidence": 0.7},
                {"id": "e3", "content": "alpha project execution", "timestamp": ts2, "type": "journal_entry", "confidence": 0.9},
            ]

    # Monkeypatch Memory provider before importing the loop module
    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", type("M", (), {"Memory": lambda: DummyMem()}))

    import episodic_loop as el

    # Stub belief graph to capture integrations
    class StubBG:
        def upsert_belief(self, subject, predicate, obj, *, confidence=0.5, sources=None):
            return "101"

        def set_belief_state(self, bid, state):
            return True

    el._belief_graph = StubBG()  # type: ignore[attr-defined]

    with temp_env({
        "AXIOM_EPISODIC_LOOP_ENABLED": "1",
        "AXIOM_EPISODIC_WINDOW_HOURS": "24",
        "AXIOM_EPISODIC_MIN_LINKS": "3",
    }):
        res = el.maybe_run_episodic_loop()
        assert res.get("status") == "ok"
        assert res.get("drafted", 0) >= 1
        assert res.get("integrated", 0) >= 1
        assert any("[RECALL][Loop25]" in r.getMessage() for r in caplog.records)


@pytest.mark.phase("25")
def test_episodic_loop_disabled(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Provide Memory class but keep loop disabled
    class DummyMem:
        def snapshot(self, limit=None):
            return []

    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", type("M", (), {"Memory": lambda: DummyMem()}))
    import importlib
    el = importlib.import_module("episodic_loop")

    with temp_env({"AXIOM_EPISODIC_LOOP_ENABLED": "0"}):
        res = el.maybe_run_episodic_loop()
        assert res.get("status") == "aborted"
        assert res.get("reason") == "disabled"
        assert any("[RECALL][Loop25] aborted" in r.getMessage() for r in caplog.records)

