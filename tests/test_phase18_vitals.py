import os
import time


def test_cognitive_vitals_basic_metrics(monkeypatch):
    from cognitive_vitals import vitals

    # Reset by creating a fresh instance would be heavy; simulate by recording and ticking
    vitals.record_contradictions([
        {"belief_id": "1", "conflict_type": "contradicts", "confidence": 0.9, "severity": "critical"},
        {"belief_id": "2", "conflict_type": "outdated", "confidence": 0.8, "severity": "structural"},
        {"belief_id": "3", "conflict_type": "uncertain", "confidence": 0.5, "severity": "perspective"},
    ])
    vitals.record_belief_event("add")
    vitals.record_belief_event("remove")
    vitals.record_retrieval_latency_ms(123.0)
    vitals.turn_tick()

    snap = vitals.snapshot()
    assert snap["contradiction_pressure"].get("critical", 0) >= 1
    assert snap["contradiction_pressure"].get("structural", 0) >= 1
    assert snap["contradiction_pressure"].get("perspective", 0) >= 1
    assert snap["belief_churn_rate"] >= 0.1
    assert snap["retrieval_latency_ms_avg"] >= 120.0


def test_tripwire_triggers_and_cooldown(monkeypatch):
    # Set tight thresholds so we can trigger easily
    monkeypatch.setenv("AXIOM_TRIPWIRE_CONTRADICTIONS", "2")
    monkeypatch.setenv("AXIOM_TRIPWIRE_LATENCY_MS", "100")
    monkeypatch.setenv("AXIOM_TRIPWIRE_CHURN", "2")

    # Re-import tripwires to pick up env
    import importlib
    import tripwires as tw
    import cognitive_vitals as cv

    importlib.reload(tw)
    importlib.reload(cv)

    # Use reloaded singletons
    trip = tw.tripwires
    vit = cv.vitals

    # Exceed all thresholds
    vit.record_contradictions([
        {"belief_id": "1", "severity": "critical"},
        {"belief_id": "2", "severity": "critical"},
        {"belief_id": "3", "severity": "structural"},
    ])
    vit.record_retrieval_latency_ms(150.0)
    vit.record_belief_event("add")
    vit.record_belief_event("add")
    vit.record_belief_event("remove")
    vit.turn_tick()  # evaluates tripwires

    assert trip.state.wonder_disabled is True
    assert trip.state.dream_disabled is True

    # Now drop below 80% of thresholds
    # 80% of contradictions=1 (since thresh=2), latency<80 and churn<1.6
    vit.record_contradictions([])
    vit.record_retrieval_latency_ms(10.0)
    # no churn this turn
    vit.turn_tick()

    assert trip.is_wonder_allowed() is True
    assert trip.is_dream_allowed() is True

