import os
import time


def test_compute_cycle_scores_and_weights(monkeypatch):
    # Ensure a fresh import path
    import importlib
    import cognitive_vitals
    import meta_cognition

    # Seed events via the public record_event API
    # Retrieval: 10 judged, 7 kept → 0.7
    meta_cognition.record_event("retrieval_judged", {"candidates": 10, "kept": 7})
    # Contradiction: 4 detected, 2 resolved → 0.5
    for _ in range(4):
        meta_cognition.record_event("contradiction_detected", {"count": 1})
    for _ in range(2):
        meta_cognition.record_event("contradiction_resolved", {"count": 1})
    # Dream: 5 drafted, 3 integrated → 0.6
    meta_cognition.record_event("dream_cycle", {"drafted": 5, "integrated": 3, "aborted": 0})
    # Abstraction: 3 drafted, 1 integrated → 0.333..
    meta_cognition.record_event("abstraction_cycle", {"drafted": 3, "validated": 2, "integrated": 1, "aborted": 0})

    monkeypatch.setenv(
        "AXIOM_META_WEIGHTS",
        "retrieval=0.35,contradiction=0.25,abstraction=0.20,dream=0.20",
    )
    # Legacy accepted but canonical should also be used
    monkeypatch.setenv("AXIOM_META_WINDOW", "24h")

    scores = meta_cognition.compute_cycle()
    assert 0.0 <= scores["retrieval_score"] <= 1.0
    assert 0.0 <= scores["contradiction_score"] <= 1.0
    assert 0.0 <= scores["abstraction_score"] <= 1.0
    assert 0.0 <= scores["dream_score"] <= 1.0
    assert 0.0 <= scores["meta_confidence"] <= 1.0

    # Check specific ratios
    assert abs(scores["retrieval_score"] - 0.7) < 1e-6
    assert abs(scores["contradiction_score"] - 0.5) < 1e-6
    assert abs(scores["dream_score"] - 0.6) < 1e-6
    assert abs(scores["abstraction_score"] - (1.0 / 3.0)) < 1e-6

    # Weighted average check (tolerance due to float division)
    expected = (
        0.7 * 0.35
        + 0.5 * 0.25
        + (1.0 / 3.0) * 0.20
        + 0.6 * 0.20
    ) / (0.35 + 0.25 + 0.20 + 0.20)
    assert abs(scores["meta_confidence"] - expected) < 1e-6

