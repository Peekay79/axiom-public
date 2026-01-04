import os


def test_champ_meta_blend_disabled(monkeypatch):
    from champ_decision_engine import ChampDecisionEngine, ChampMetrics

    monkeypatch.setenv("AXIOM_CHAMP_META_ENABLED", "0")
    engine = ChampDecisionEngine()
    m = ChampMetrics(confidence=0.6, payoff=0.5, refinement_cost=0.5, tempo=0.5, decay=0.1, volatility=0.0)
    base_score = engine.calculate_champ_score(m)
    res = engine.evaluate_decision(ChampMetrics(confidence=0.6, payoff=0.5, refinement_cost=0.5, tempo=0.5, decay=0.1, volatility=0.0))
    assert abs(res["champ_score"] - base_score) < 1e-9


def test_champ_meta_blend_enabled(monkeypatch):
    import meta_cognition
    from champ_decision_engine import ChampDecisionEngine, ChampMetrics

    # Seed a meta snapshot with known values via events
    meta_cognition.record_event("retrieval_judged", {"candidates": 10, "kept": 1})  # low retrieval
    meta_cognition.record_event("contradiction_detected", {"count": 4})
    meta_cognition.record_event("contradiction_resolved", {"count": 2})
    meta_cognition.record_event("dream_cycle", {"drafted": 2, "integrated": 0, "aborted": 0})
    meta_cognition.record_event("abstraction_cycle", {"drafted": 1, "validated": 0, "integrated": 0, "aborted": 0})
    meta_cognition.compute_cycle()

    monkeypatch.setenv("AXIOM_CHAMP_META_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CHAMP_META_WEIGHT", "0.3")

    engine = ChampDecisionEngine()

    m = ChampMetrics(confidence=0.8, payoff=0.5, refinement_cost=0.5, tempo=0.5, decay=0.1, volatility=0.0)
    base_score = engine.calculate_champ_score(ChampMetrics(**m.__dict__))
    res = engine.evaluate_decision(m)
    # With meta blending lowering effective confidence (likely), score should be <= base
    assert res["champ_score"] <= base_score + 1e-6

