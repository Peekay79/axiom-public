import logging
from types import SimpleNamespace

import pytest

from tests.utils.env import temp_env


def _setup_fake_champ(monkeypatch, action: str):
    def fake_eval(**kwargs):
        return {
            "champ_score": 0.8 if action == "execute" else 0.4,
            "action": action,
            "reason": f"unit_{action}",
            "confidence": 0.7,
            "timestamp": 0.0,
        }

    monkeypatch.setitem(
        __import__("sys").modules,
        "champ_decision_engine",
        SimpleNamespace(evaluate_champ_score=fake_eval),
    )
    # Also patch already-imported consciousness_pilot binding if present
    import sys as _sys
    mod = _sys.modules.get("consciousness_pilot")
    if mod is not None:
        setattr(mod, "evaluate_champ_score", fake_eval)


@pytest.mark.parametrize("champ_action", ["execute", "refine"])
def test_pilot_decision_paths_and_logging(monkeypatch, caplog, champ_action):
    caplog.set_level(logging.INFO)
    _setup_fake_champ(monkeypatch, champ_action)

    # Patch memory/journal hooks used inside pilot logging path
    class _Mem:
        def add_to_long_term(self, *_a, **_k):
            return True

    monkeypatch.setitem(
        __import__("sys").modules,
        "pods.memory.memory_manager",
        SimpleNamespace(Memory=lambda: _Mem()),
    )
    _events = []

    def _log_event(tag, payload):
        _events.append((tag, payload))

    monkeypatch.setitem(
        __import__("sys").modules,
        "utils.logger",
        SimpleNamespace(log_event=_log_event),
    )

    # Note: vitals pushed by CHAMP engine; since we're using a fake, skip here

    from consciousness_pilot import ConsciousnessPilot
    import consciousness_pilot as _cp
    # Ensure module-level log_event points to this test's collector
    monkeypatch.setattr(_cp, "log_event", _log_event, raising=False)

    pilot = ConsciousnessPilot(enable_validation=True, strict_validation=False)
    decision = pilot.decide({
        "user_query": "How are you?",
        "memory": "m",
        "beliefs": "b",
        "goals": [{"title": "g"}],
    })

    assert decision.get("champ_action") == champ_action
    # Canonical tag present
    assert any("[RECALL][ConsciousnessPilot]" in r.getMessage() for r in caplog.records)
    # Journaling via utils.logger
    assert any(t == "champ_decision" for t, _ in _events)


def test_pilot_vitals_journaling_and_env_gating(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    # Provide a vitals module and reload pilot to use real CHAMP engine
    import types as _t, importlib, sys as _sys

    class DummyVitals:
        def __init__(self):
            self.calls = 0

        def get_meta_snapshot(self, window_sec: int):
            return {"meta_confidence": 0.25}

        def push_champ_decision(self, payload):
            self.calls += 1

    _vit = DummyVitals()
    monkeypatch.setitem(
        __import__("sys").modules,
        "cognitive_vitals",
        _t.SimpleNamespace(vitals=_vit),
    )
    # Reload CHAMP to bind to our dummy vitals
    import champ_decision_engine as _cde
    importlib.reload(_cde)
    monkeypatch.setitem(
        __import__("sys").modules,
        "pods.memory.memory_manager",
        _t.SimpleNamespace(Memory=lambda: object()),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "utils.logger",
        _t.SimpleNamespace(log_event=lambda *a, **k: None),
    )

    # Ensure pilot uses real champ (reload module)
    _sys.modules.pop("consciousness_pilot", None)
    from consciousness_pilot import ConsciousnessPilot  # re-import after cleanup

    # With gating disabled (0), meta blend skipped by CHAMP but pilot runs and pushes vitals
    with temp_env({"AXIOM_CHAMP_META_ENABLED": "0"}):
        pilot = ConsciousnessPilot()
        decision = pilot.decide({"user_query": "Ping?"})
        assert decision["champ_action"] in {"execute", "refine"}
        # Canonical tag still logged
        assert any("[RECALL][ConsciousnessPilot]" in r.getMessage() for r in caplog.records)
        # Ensure meta-blend log did not occur
        assert not any("[RECALL][CHAMP] meta_blend" in r.getMessage() for r in caplog.records)
        # Vitals recorded
        assert _vit.calls >= 1

