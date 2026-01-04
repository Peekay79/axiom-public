import json
import os
import tempfile

import meta_arbitration as marb


def test_apply_delta_enforces_clamp_and_damping(tmp_path):
    os.environ["AXIOM_META_ARB_MAX_SHIFT"] = "0.10"
    os.environ["AXIOM_META_ARB_DAMPING"] = "0.20"
    profile = {"base": 0.40, "episodic": 0.20, "procedural": 0.20, "abstraction": 0.20}
    delta = {"base": 0.50, "episodic": -0.50, "procedural": 0.0, "abstraction": 0.0}
    newp = marb.apply_delta(profile, delta)
    # Base should move by at most 0.10 * damping 0.20 => +0.02 before normalize
    assert newp["base"] > profile["base"]
    assert newp["episodic"] < profile["episodic"]
    assert 0.0 < sum(newp.values()) <= 1.00001
    # Floors respected
    assert all(v >= 0.05 for v in newp.values())


def test_persistence_sidecar_written(tmp_path):
    p = tmp_path / "profile.json"
    os.environ["AXIOM_META_ARB_PROFILE_PATH"] = str(p)
    os.environ["AXIOM_META_ARB_DAMPING"] = "0.2"
    os.environ["AXIOM_META_ARB_MAX_SHIFT"] = "0.1"
    profile = {"base": 0.25, "episodic": 0.25, "procedural": 0.25, "abstraction": 0.25}
    delta = {"base": 0.10, "episodic": -0.10, "procedural": 0.0, "abstraction": 0.0}
    newp = marb.apply_delta(profile, delta)
    assert p.exists()
    data = json.loads(p.read_text())
    assert set(data.keys()) == {"base", "episodic", "procedural", "abstraction"}

