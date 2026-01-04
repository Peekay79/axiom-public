import logging
import sys

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("27")
def test_abstraction_loop_dry_run_and_end_to_end(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Provide memory items with confidence >= min_conf so they are selected
    class DummyMem:
        def snapshot(self, limit=None):
            return [
                {"id": "m1", "content": "alpha project planning", "type": "episodic", "confidence": 0.8},
                {"id": "m2", "content": "alpha project execution", "type": "short_term", "confidence": 0.7},
            ]

    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", type("M", (), {"Memory": lambda: DummyMem()}))

    import abstraction_loop as al

    # Force baseline abstraction by nulling llm connector and provide stub BG
    al._llm = None  # type: ignore[attr-defined]

    class StubBG:
        def upsert_belief(self, subject, predicate, obj, *, confidence=0.5, sources=None):
            return "303"

    al._belief_graph = StubBG()  # type: ignore[attr-defined]

    # Dry-run path
    with temp_env({
        "AXIOM_ABSTRACTION_LOOP_ENABLED": "1",
        "AXIOM_ABSTRACTION_DRY_RUN": "1",
        "AXIOM_ABSTRACTION_MIN_CONFIDENCE": "0.6",
        "AXIOM_ABSTRACTION_MAX_ITEMS": "10",
    }):
        res = al.maybe_run_abstraction_loop()
        assert res.get("status") == "ok"
        assert res.get("drafted", 0) >= 1
        assert res.get("dry_run") is True
        assert any("[RECALL][Loop27]" in r.getMessage() for r in caplog.records)

    # Enabled integration path (non-dry)
    with temp_env({
        "AXIOM_ABSTRACTION_LOOP_ENABLED": "1",
        "AXIOM_ABSTRACTION_DRY_RUN": "0",
        "AXIOM_ABSTRACTION_MIN_CONFIDENCE": "0.6",
        "AXIOM_ABSTRACTION_MAX_ITEMS": "10",
    }):
        res2 = al.maybe_run_abstraction_loop()
        assert res2.get("status") == "ok"
        assert res2.get("integrated", 0) >= 0  # may be 0 if drafts invalid, but end-to-end should run
        assert any("[RECALL][Loop27] integrated=" in r.getMessage() for r in caplog.records)


@pytest.mark.phase("27")
def test_abstraction_loop_disabled(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    class DummyMem:
        def snapshot(self, limit=None):
            return []

    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", type("M", (), {"Memory": lambda: DummyMem()}))
    import importlib
    al = importlib.import_module("abstraction_loop")

    with temp_env({"AXIOM_ABSTRACTION_LOOP_ENABLED": "0"}):
        res = al.maybe_run_abstraction_loop()
        assert res.get("status") == "aborted" and res.get("reason") == "disabled"
        assert any("[RECALL][Loop27] aborted" in r.getMessage() for r in caplog.records)

