import json
import os

import meta_arbitration as marb


def test_effective_weights_blends_profile_and_intent(tmp_path, monkeypatch):
    # Save a learned profile
    p = tmp_path / ".axiom_meta_arb_profile.json"
    prof = {"base": 0.1, "episodic": 0.2, "procedural": 0.6, "abstraction": 0.1}
    p.write_text(json.dumps(prof))
    os.environ["AXIOM_META_ARB_PROFILE_PATH"] = str(p)

    # Intent multipliers favor procedural for 'how'
    os.environ["AXIOM_ARB_MULT_HOW_PROCEDURAL"] = "1.5"
    w = marb.get_effective_weights("how")
    assert w["procedural"] > w["episodic"]
    assert abs(sum(w.values()) - 1.0) < 1e-6

