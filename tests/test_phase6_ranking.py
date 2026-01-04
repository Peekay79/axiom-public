import os
from typing import Dict, List

from tests.utils.env import temp_env


def compute_final(v: float, c: float, j: float, w: Dict[str, float]) -> float:
    return w.get("vector", 0.4) * v + w.get("confidence", 0.3) * c + w.get("judger", 0.3) * j


def test_phase6_weighted_ranking_confidence_wins():
    # A: high similarity, low confidence; B: lower similarity, high confidence
    from ranking import rank_candidates

    A = {"id": "A", "_additional": {"score": 0.8}, "confidence": 0.2}
    B = {"id": "B", "_additional": {"score": 0.6}, "confidence": 0.8}
    judger = {"A": 0.5, "B": 0.7}
    weights = {"vector": 0.4, "confidence": 0.3, "judger": 0.3}

    ranked = rank_candidates([A, B], [], judger_scores=judger, weights=weights, confidence_only=False)
    assert ranked[0]["id"] == "B"

    # Logs (not asserting logs, just ensure sample math parity)
    a_final = compute_final(0.8, 0.2, 0.5, weights)
    b_final = compute_final(0.6, 0.8, 0.7, weights)
    print(f"[Test] Candidate A: vector=0.8, confidence=0.2, judger=0.5 → final={a_final:.2f}")
    print(f"[Test] Candidate B: vector=0.6, confidence=0.8, judger=0.7 → final={b_final:.2f}")
    print("[Test] Ranking passed: B > A")


def test_phase6_judger_pushes_ranking():
    from ranking import rank_candidates

    # Similar vector/confidence, judger should lift C
    C = {"id": "C", "_additional": {"score": 0.5}, "confidence": 0.5}
    D = {"id": "D", "_additional": {"score": 0.5}, "confidence": 0.5}
    judger = {"C": 0.9, "D": 0.1}

    ranked = rank_candidates([C, D], [], judger_scores=judger, weights=None, confidence_only=False)
    assert ranked[0]["id"] == "C"


def test_phase6_confidence_only_mode_ignores_vector_and_judger():
    from ranking import rank_candidates

    A = {"id": "A", "_additional": {"score": 0.9}, "confidence": 0.2}
    B = {"id": "B", "_additional": {"score": 0.1}, "confidence": 0.8}
    judger = {"A": 0.9, "B": 0.1}

    ranked = rank_candidates([A, B], [], judger_scores=judger, weights=None, confidence_only=True)
    assert ranked[0]["id"] == "B"
    print("[Test] Confidence-only mode: Candidate B=0.8 > Candidate A=0.2")


def test_phase6_min_score_drop():
    from ranking import rank_candidates

    # We'll emulate the filter by applying env and then filtering like the pipeline
    E = {"id": "E", "_additional": {"score": 0.1}, "confidence": 0.05}
    F = {"id": "F", "_additional": {"score": 0.7}, "confidence": 0.7}
    ranked = rank_candidates([E, F], [], judger_scores={}, weights=None, confidence_only=False)

    # Apply min score = 0.25 filter (as in pipeline)
    with temp_env({"AXIOM_RETRIEVAL_MIN_SCORE": "0.25"}):
        filtered = [it for it in ranked if float(it.get("final_score", 0.0) or 0.0) >= float(os.getenv("AXIOM_RETRIEVAL_MIN_SCORE", "0.25"))]
    ids = [it["id"] for it in filtered]
    assert "F" in ids and "E" not in ids

