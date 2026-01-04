from tests.utils.env import temp_env


def test_penalty_applied_in_ranking_when_missing_provenance(monkeypatch):
    # Two hits with same base scores; one missing provenance should be penalized
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "1", "AXIOM_PROVENANCE_PENALTY": "0.2"}):
        from ranking import rank_candidates

        vec_hits = [
            {"id": "p", "_additional": {"score": 0.9}, "provenance": "ok"},
            {"id": "m", "_additional": {"score": 0.9}},  # missing provenance
        ]
        bel_hits = []
        ranked = rank_candidates(vec_hits, bel_hits, judger_scores={}, weights={"vector": 1.0, "confidence": 0.0, "judger": 0.0}, confidence_only=False)
        # Find scores
        scores = {h["id"]: h["final_score"] for h in ranked}
        assert scores["m"] < scores["p"], scores
        # 0.9 * (1 - 0.2) = 0.72 expected for missing; baseline remains 0.9
        assert abs(scores["m"] - 0.72) < 1e-6
