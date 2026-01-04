import os


def _make_belief(**kwargs):
    b = {
        "id": "1",
        "confidence": 0.5,
        "recency": 0,
        "last_updated": 0,
        "reinforcement_count": 0,
        "resolution_state": "active",
    }
    b.update(kwargs)
    return b


def test_decisions_archive_retire_keep(monkeypatch):
    from memory_hygiene import decide_action, score_belief

    os.environ["AXIOM_HYGIENE_ARCHIVE_THRESHOLD"] = "0.3"
    os.environ["AXIOM_HYGIENE_RETIRE_THRESHOLD"] = "0.1"

    # Keep: high confidence
    b_keep = _make_belief(id="k", confidence=0.8, last_updated=0)
    s_keep = score_belief(b_keep)
    assert decide_action(b_keep, s_keep, {"meta_confidence": 0.8}) == "keep"

    # Archive: mid confidence
    b_arch = _make_belief(id="a", confidence=0.25, last_updated=0)
    s_arch = score_belief(b_arch)
    assert decide_action(b_arch, s_arch, {"meta_confidence": 0.8}) == "archive"

    # Retire: very low confidence
    b_ret = _make_belief(id="r", confidence=0.05, last_updated=0)
    s_ret = score_belief(b_ret)
    assert decide_action(b_ret, s_ret, {"meta_confidence": 0.8}) == "retire"


def test_contradiction_escalation(monkeypatch):
    from memory_hygiene import decide_action, score_belief

    os.environ["AXIOM_HYGIENE_CONTRA_WINDOW_SEC"] = "1"

    # Contradicted and stale should escalate from archive→retire
    b = _make_belief(id="c", confidence=0.2, resolution_state="uncertain")
    s = score_belief(b)
    # Force old last_updated
    b["last_updated"] = 0
    act = decide_action(b, s, {"meta_confidence": 0.8})
    assert act in {"archive", "retire"}
