import os


def test_emit_meta_beliefs_dry_run(monkeypatch, caplog):
    import meta_cognition

    monkeypatch.setenv("AXIOM_META_DRY_RUN", "1")
    scores = {
        "retrieval_score": 0.5,
        "contradiction_score": 0.8,
        "abstraction_score": 0.4,
        "dream_score": 0.6,
        "meta_confidence": 0.55,
    }
    res = meta_cognition.emit_meta_beliefs(scores, dry_run=True)
    assert res["dry_run"] is True
    assert res["written"] == 0


class _MockBeliefGraph:
    def __init__(self):
        self.calls = []

    def upsert_belief(self, s, p, o, confidence=0.6, sources=None):
        self.calls.append((s, p, o, confidence, sources))
        return "ok"


def test_emit_meta_beliefs_real_write(monkeypatch):
    import meta_cognition

    mock = _MockBeliefGraph()
    monkeypatch.setitem(meta_cognition.__dict__, "_belief_graph", mock)

    scores = {
        "retrieval_score": 0.5,
        "contradiction_score": 0.8,
        "abstraction_score": 0.4,
        "dream_score": 0.6,
        "meta_confidence": 0.55,
    }
    res = meta_cognition.emit_meta_beliefs(scores, dry_run=False)
    assert res["dry_run"] is False
    # Expect 5 upserts
    assert res["written"] == 5
    assert len(mock.calls) == 5
    # Check tag payload shape
    for _, pred, obj, conf, sources in mock.calls:
        assert isinstance(obj, str)
        assert conf == 0.6
        assert sources and isinstance(sources, list)
        assert isinstance(sources[0], dict)
        assert sources[0].get("origin") == "meta"
        assert sources[0].get("scope") == "system"
        assert "meta_cognition" in sources[0].get("tags", [])

