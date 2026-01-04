import os


def test_meta_low_confidence_increases_aggressiveness(monkeypatch):
    from memory_hygiene import decide_action, score_belief

    # Baseline thresholds
    os.environ["AXIOM_HYGIENE_ARCHIVE_THRESHOLD"] = "0.3"
    os.environ["AXIOM_HYGIENE_RETIRE_THRESHOLD"] = "0.1"

    b = {
        "id": "m",
        "confidence": 0.28,  # slightly below archive threshold
        "recency": 0,
        "last_updated": 0,
        "reinforcement_count": 0,
        "resolution_state": "active",
    }
    s = score_belief(b)

    # With healthy meta_confidence, should archive
    act_normal = decide_action(b, s, {"meta_confidence": 0.8})
    assert act_normal == "archive"

    # If meta_confidence low, more aggressive — keep remains archive, border cases can retire
    b2 = dict(b)
    b2["confidence"] = 0.09  # right at retire threshold; low meta lowers it further
    s2 = score_belief(b2)
    act_low = decide_action(b2, s2, {"meta_confidence": 0.2})
    assert act_low == "retire"
