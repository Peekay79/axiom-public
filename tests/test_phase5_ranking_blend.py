def test_ranking_blend_weights_match_formula(monkeypatch):
    from ranking import rank_candidates

    # Two items with known component scores
    A = {"id": "A", "_additional": {"score": 0.8}, "confidence": 0.2}
    B = {"id": "B", "_additional": {"score": 0.6}, "confidence": 0.8}
    judger = {"A": 0.5, "B": 0.7}

    # Explicit weights
    weights = {"vector": 0.4, "confidence": 0.3, "judger": 0.3}
    ranked = rank_candidates([A, B], [], judger_scores=judger, weights=weights, confidence_only=False)

    assert ranked[0]["id"] == "B"
    # Check that final score computed is equal to declared formula
    def calc(v, c, j):
        return weights["vector"] * v + weights["confidence"] * c + weights["judger"] * j

    for it in ranked:
        v = float(it.get("_vector_similarity", 0.0) or 0.0)
        c = float(it.get("_belief_confidence", 0.0) or 0.0)
        j = float(it.get("_judger_score", 0.0) or 0.0)
        f = float(it.get("final_score", 0.0) or 0.0)
        assert abs(f - calc(v, c, j)) < 1e-9

