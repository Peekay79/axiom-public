import os

from ranking import compute_arbitration_weights


def test_disabled_uses_phase30_weights(monkeypatch):
    # Meta-Arb disabled
    os.environ["AXIOM_META_ARB_ENABLED"] = "0"
    # Phase 30 enabled in context mode
    os.environ["AXIOM_ARBITRATION_ENABLED"] = "1"
    os.environ["AXIOM_ARBITRATION_MODE"] = "context"
    os.environ["AXIOM_ARB_W_BASE"] = "0.30"
    os.environ["AXIOM_ARB_W_EPISODIC"] = "0.25"
    os.environ["AXIOM_ARB_W_PROCEDURAL"] = "0.30"
    os.environ["AXIOM_ARB_W_ABSTRACTION"] = "0.30"

    w = compute_arbitration_weights("fact")
    # Verify it is normalized and has expected keys (fallback to Phase 30 behavior)
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert set(w.keys()) == {"base", "episodic", "procedural", "abstraction"}

