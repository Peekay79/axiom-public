import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.utils.env import temp_env


@pytest.mark.phase("X")
def test_consciousness_pilot_evaluate_and_decide_entrypoints(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Patch CHAMP evaluate to a deterministic execute action
    def fake_eval(**kwargs):
        return {"champ_score": 0.9, "action": "execute", "reason": "test", "confidence": 0.8, "timestamp": 0.0}

    monkeypatch.setitem(__import__("sys").modules, "champ_decision_engine", SimpleNamespace(evaluate_champ_score=fake_eval))

    # Patch journal/memory hooks used inside pilot logging path
    fake_mem = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "pods.memory.memory_manager", SimpleNamespace(Memory=lambda: fake_mem))

    logged_events = []

    def fake_log_event(tag, payload):
        logged_events.append((tag, payload))

    monkeypatch.setitem(__import__("sys").modules, "utils.logger", SimpleNamespace(log_event=fake_log_event))

    # Import entrypoints
    from consciousness_pilot import evaluate as pilot_evaluate
    from consciousness_pilot import ConsciousnessPilot

    # Validate evaluate() legacy shim
    ok = pilot_evaluate({"content": "This is a minimally valid response."})
    assert isinstance(ok, bool)

    # Call decide() with dummy inputs
    pilot = ConsciousnessPilot(enable_validation=True, strict_validation=False)
    decision = pilot.decide({
        "user_query": "What is the status?",
        "memory": "Some memory",
        "beliefs": "Some beliefs",
        "goals": [{"title": "g1", "priority": 5, "importance": 0.8}],
        "contradictions": [],
    })

    assert decision.get("champ_action") in {"execute", "refine"}
    # CHAMP was invoked -> log lines present and Memory.add_to_long_term attempted
    assert any("CHAMP evaluation:" in rec.getMessage() for rec in caplog.records)
    assert fake_mem.add_to_long_term.called

    # Event logged via utils.logger.log_event
    assert any(tag == "champ_decision" for tag, _ in logged_events)


@pytest.mark.phase("X")
def test_consciousness_pilot_champ_raise_propagates(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # CHAMP evaluate raises
    def bad_eval(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setitem(__import__("sys").modules, "champ_decision_engine", SimpleNamespace(evaluate_champ_score=bad_eval))

    # Provide safe fallbacks for optional imports
    monkeypatch.setitem(__import__("sys").modules, "pods.memory.memory_manager", SimpleNamespace(Memory=lambda: MagicMock()))
    monkeypatch.setitem(__import__("sys").modules, "utils.logger", SimpleNamespace(log_event=lambda *a, **k: None))

    from consciousness_pilot import ConsciousnessPilot

    pilot = ConsciousnessPilot(enable_validation=True, strict_validation=False)
    # Current implementation propagates CHAMP errors; document behavior
    with pytest.raises(RuntimeError):
        pilot.decide({"user_query": "Ping?"})

