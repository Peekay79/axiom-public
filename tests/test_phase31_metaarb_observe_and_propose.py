import os
import types

import meta_arbitration as marb


class DummyVitals:
    def __init__(self, obs):
        self._obs = obs

    def get_meta_arb_observables(self, window_turns: int):
        return self._obs

    def record_meta_arb_event(self, kind, **data):
        return None


def test_propose_delta_signs(monkeypatch):
    obs = {
        "judger_kept_rate_by_type": {"base": 0.9, "episodic": 0.4, "procedural": 0.6, "abstraction": 0.3},
        "uncertain_rate_by_type": {"base": 0.05, "episodic": 0.2, "procedural": 0.1, "abstraction": 0.25},
        "contradictions": {"rate": 0.0, "severity_by_type": {"base": 0.0, "episodic": 0.2, "procedural": 0.1, "abstraction": 0.3}},
        "retrieval_usefulness_by_type": {"base": 0.8, "episodic": 0.4, "procedural": 0.55, "abstraction": 0.3},
        "reinforcement_vs_decay_by_type": {"base": 0.6, "episodic": -0.2, "procedural": 0.2, "abstraction": -0.3},
        "cross_consolidation_synergy_rate": 0.2,
        "recent_variance_by_type": {"base": 0.0, "episodic": 0.4, "procedural": 0.1, "abstraction": 0.2},
        "judger_confidence_margin_by_type": {"base": 0.1, "episodic": 0.0, "procedural": 0.05, "abstraction": 0.0},
    }
    dummy = DummyVitals(obs)
    import builtins
    # Patch cognitive_vitals.vitals to our dummy
    mod = types.SimpleNamespace(vitals=dummy)
    def _fake_import(name, *args, **kwargs):
        if name == "cognitive_vitals":
            return mod
        return orig_import(name, *args, **kwargs)
    orig_import = builtins.__import__
    monkeypatch.setattr("builtins.__import__", _fake_import)

    prof = {"base": 0.25, "episodic": 0.25, "procedural": 0.25, "abstraction": 0.25}
    signals = marb.observe_signals()
    delta = marb.propose_delta(prof, signals)

    assert delta["base"] > 0.0  # strong kept/useful/reinforcement
    assert delta["episodic"] < 0.0  # poor kept, higher uncertainty/contradiction, negative reinforcement
    # Procedural should likely be slightly positive
    assert delta["procedural"] != 0.0
    # Abstraction likely negative due to uncertainty/contradiction
    assert delta["abstraction"] < 0.0

