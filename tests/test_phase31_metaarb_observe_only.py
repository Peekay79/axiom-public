import json
import os

import meta_arbitration as marb


def test_observe_only_skips_writes(tmp_path, monkeypatch):
    os.environ["AXIOM_META_ARB_ENABLED"] = "1"
    os.environ["AXIOM_META_ARB_OBSERVE_ONLY"] = "1"
    os.environ["AXIOM_META_ARB_TICK_SEC"] = "1"
    os.environ["AXIOM_META_ARB_MIN_INTERVAL_SEC"] = "1"
    p = tmp_path / "profile.json"
    os.environ["AXIOM_META_ARB_PROFILE_PATH"] = str(p)

    # Provide minimal observables via vitals
    class V:
        def get_meta_arb_observables(self, *_):
            return {
                "judger_kept_rate_by_type": {"base": 0.6, "episodic": 0.4, "procedural": 0.5, "abstraction": 0.5},
                "uncertain_rate_by_type": {"base": 0.0, "episodic": 0.0, "procedural": 0.0, "abstraction": 0.0},
                "contradictions": {"rate": 0.0, "severity_by_type": {t: 0.0 for t in ("base","episodic","procedural","abstraction")}},
                "retrieval_usefulness_by_type": {t: 0.5 for t in ("base","episodic","procedural","abstraction")},
                "reinforcement_vs_decay_by_type": {t: 0.0 for t in ("base","episodic","procedural","abstraction")},
                "cross_consolidation_synergy_rate": 0.0,
                "recent_variance_by_type": {t: 0.0 for t in ("base","episodic","procedural","abstraction")},
                "judger_confidence_margin_by_type": {t: 0.0 for t in ("base","episodic","procedural","abstraction")},
            }

        def record_meta_arb_event(self, *a, **k):
            return None

        def snapshot(self):
            return {"cross_consolidation": {"hits_used_recent": 0, "boosts_applied_recent": 0}}

    import builtins
    vit = V()
    def _fake_import(name, *args, **kwargs):
        if name == "cognitive_vitals":
            return type("M", (), {"vitals": vit})
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    # Run ticker once with observe-only: should not create a profile file
    marb.maybe_run_meta_arbitration(now=1000000.0)
    assert not p.exists()

