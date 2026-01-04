import importlib


def _reload_vitals():
    import cognitive_vitals as cv
    importlib.reload(cv)
    return cv


def test_vitals_record_and_logging(monkeypatch, caplog):
    monkeypatch.setenv("AXIOM_VITALS_ENABLED", "1")
    monkeypatch.setenv("AXIOM_VITALS_LOG_EVERY", "1")
    cv = _reload_vitals()

    v = cv.vitals
    v.record_episodic_run(last_run_ts=0.0, episodes_created=3, avg_episode_size=2.5, retrieval_hit_ratio=0.6, aborted=False, ms_elapsed=12)
    v.record_procedural_run(last_run_ts=0.0, procedures_created=2, avg_support_count=1.2, top_confidence_procedure="p1")
    v.record_abstraction_run(last_run_ts=0.0, selected_count=2, cluster_count=1, drafted_count=1, validated_count=1, integrated_count=1, aborted=False, ms_elapsed=7)
    v.record_retrieval_latency_ms(111.0)

    with caplog.at_level("INFO"):
        v.turn_tick()

    snap = v.snapshot()
    assert snap["episodic"]["episodes_created"] >= 3
    assert snap["procedural"]["procedures_created"] >= 2
    assert snap["abstraction"]["selected_count"] >= 2
    assert "[RECALL][Vitals]" in caplog.text


def test_vitals_disabled_env_noop(monkeypatch, caplog):
    monkeypatch.setenv("AXIOM_VITALS_ENABLED", "0")
    monkeypatch.setenv("AXIOM_VITALS_LOG_EVERY", "1")
    cv = _reload_vitals()

    v = cv.vitals
    v.record_episodic_run(last_run_ts=0.0, episodes_created=5, avg_episode_size=1.0, retrieval_hit_ratio=0.1, aborted=False, ms_elapsed=1)
    v.record_retrieval_latency_ms(999.0)
    before = v.snapshot()
    v.turn_tick()
    after = v.snapshot()

    assert after["episodic"]["episodes_created"] == before["episodic"]["episodes_created"]
    # No vitals log emitted
    assert "[RECALL][Vitals]" not in caplog.text

