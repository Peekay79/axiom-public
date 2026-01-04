import importlib


def _reload_all():
    import tripwires as tw
    import cognitive_vitals as cv
    importlib.reload(tw)
    importlib.reload(cv)
    return tw, cv


def test_contradiction_tripwire_blocks_and_logs(monkeypatch, caplog):
    monkeypatch.setenv("AXIOM_TRIPWIRES_ENABLED", "1")
    monkeypatch.setenv("AXIOM_TRIPWIRE_CONTRADICTIONS", "0")
    tw, cv = _reload_all()

    v = cv.vitals
    v.record_contradictions([{ "severity": "critical" }])

    with caplog.at_level("WARNING"):
        v.turn_tick()

    assert "[RECALL][Tripwire]" in caplog.text
    stats = tw.get_tripwire_stats()
    assert stats["counts"].get("contradictions", 0) >= 1
    assert tw.tripwires.is_wonder_allowed() is False
    assert tw.tripwires.is_dream_allowed() is False


def test_latency_tripwire_triggers(monkeypatch, caplog):
    monkeypatch.setenv("AXIOM_TRIPWIRES_ENABLED", "1")
    monkeypatch.setenv("AXIOM_TRIPWIRE_LATENCY_MS", "1")
    tw, cv = _reload_all()

    v = cv.vitals
    v.record_retrieval_latency_ms(10.0)

    with caplog.at_level("WARNING"):
        v.turn_tick()

    stats = tw.get_tripwire_stats()
    assert stats["counts"].get("latency_ms", 0) >= 1


def test_override_bypasses_block(monkeypatch, caplog):
    monkeypatch.setenv("AXIOM_TRIPWIRES_ENABLED", "1")
    monkeypatch.setenv("AXIOM_TRIPWIRE_CONTRADICTIONS", "0")
    monkeypatch.setenv("AXIOM_TRIPWIRE_OVERRIDE", "1")
    tw, cv = _reload_all()

    v = cv.vitals
    v.record_contradictions([{ "severity": "critical" }])

    with caplog.at_level("WARNING"):
        v.turn_tick()

    assert "override=1" in caplog.text
    assert tw.tripwires.is_wonder_allowed() is True
    assert tw.tripwires.is_dream_allowed() is True


def test_fail_closed_when_disabled(monkeypatch, caplog):
    monkeypatch.setenv("AXIOM_TRIPWIRES_ENABLED", "0")
    monkeypatch.setenv("AXIOM_TRIPWIRE_CONTRADICTIONS", "100")
    tw, cv = _reload_all()

    with caplog.at_level("WARNING"):
        cv.vitals.turn_tick()

    assert "disabled via env; fail-closed blocking extras" in caplog.text
    assert tw.tripwires.is_wonder_allowed() is False
    assert tw.tripwires.is_dream_allowed() is False

