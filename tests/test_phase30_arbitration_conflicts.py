import os

from ranking import rank_candidates


def _set_env(d: dict[str, str]):
    for k, v in d.items():
        os.environ[k] = str(v)


def test_conflict_policy_hierarchical_uncertain_tag():
    _set_env({
        "AXIOM_ARBITRATION_ENABLED": "1",
        "AXIOM_ARBITRATION_MODE": "context",
        "AXIOM_ARB_CONFLICT_RESOLUTION": "hierarchical",
        "AXIOM_ARB_UNCERTAIN_THRESHOLD": "0.20",
        # Confidence-only to make testing simpler
        "AXIOM_RETRIEVAL_WEIGHTS": "vector=0.0,confidence=1.0,judger=0.0",
    })

    # Two hits for same assertion with close confidence values
    a1 = {"id": "x1", "confidence": 0.50, "assertion_key": "A", "tags": ["episodic_active"]}
    a2 = {"id": "x2", "confidence": 0.45, "assertion_key": "A", "tags": ["procedural_active"]}
    ranked = rank_candidates([a1, a2], [], judger_scores={}, weights=None, confidence_only=False, arbitration_intent="fact")
    # Ensure uncertain tag applied to winner when within threshold
    top = ranked[0]
    assert "arb_uncertain" in (top.get("provenance_tags") or [])


def test_conflict_policy_confidence_prefers_higher():
    _set_env({
        "AXIOM_ARBITRATION_ENABLED": "1",
        "AXIOM_ARBITRATION_MODE": "context",
        "AXIOM_ARB_CONFLICT_RESOLUTION": "confidence",
        # Confidence-only
        "AXIOM_RETRIEVAL_WEIGHTS": "vector=0.0,confidence=1.0,judger=0.0",
    })
    a1 = {"id": "y1", "confidence": 0.30, "assertion_key": "B", "tags": ["episodic_active"]}
    a2 = {"id": "y2", "confidence": 0.80, "assertion_key": "B", "tags": ["procedural_active"]}
    ranked = rank_candidates([a1, a2], [], judger_scores={}, weights=None, confidence_only=False, arbitration_intent="how")
    assert ranked[0]["id"] == "y2"

