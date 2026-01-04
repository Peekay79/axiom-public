import importlib
import json
import os


def _reload_stress_and_vitals():
    import stress_harness as sh
    import cognitive_vitals as cv
    import tripwires as tw
    importlib.reload(sh)
    importlib.reload(cv)
    importlib.reload(tw)
    return sh, cv, tw


def test_run_once_writes_and_logs(monkeypatch, tmp_path, caplog):
    log_path = tmp_path / "stress_once.jsonl"
    monkeypatch.setenv("AXIOM_STRESS_ENABLED", "1")
    monkeypatch.setenv("AXIOM_STRESS_LOG_FILE", str(log_path))
    sh, cv, tw = _reload_stress_and_vitals()

    with caplog.at_level("INFO"):
        out = sh.run_once()

    assert out == str(log_path)
    assert os.path.exists(out)
    assert "[RECALL][Stress]" in caplog.text

    with open(out, "r", encoding="utf-8") as f:
        line = f.readline().strip()
        assert line
        obj = json.loads(line)
        assert obj.get("ns") == "RECALL.Stress"


def test_tripwire_trigger_does_not_abort_harness(monkeypatch, tmp_path, caplog):
    log_path = tmp_path / "stress_once_tripwire.jsonl"
    monkeypatch.setenv("AXIOM_STRESS_ENABLED", "1")
    monkeypatch.setenv("AXIOM_STRESS_LOG_FILE", str(log_path))
    monkeypatch.setenv("AXIOM_TRIPWIRE_CONTRADICTIONS", "0")
    sh, cv, tw = _reload_stress_and_vitals()

    cv.vitals.record_contradictions([{ "severity": "critical" }])

    with caplog.at_level("WARNING"):
        out = sh.run_once()

    assert out == str(log_path)
    assert os.path.exists(out)
    # Tripwire should have triggered but harness completed
    stats = tw.get_tripwire_stats()
    assert stats.get("counts", {}).get("contradictions", 0) >= 1
    assert "[RECALL][Tripwire]" in caplog.text


def test_stress_env_gating_fail_closed(monkeypatch, tmp_path, caplog):
    log_path = tmp_path / "stress_disabled.jsonl"
    monkeypatch.setenv("AXIOM_STRESS_ENABLED", "0")
    monkeypatch.setenv("AXIOM_STRESS_LOG_FILE", str(log_path))
    sh, cv, tw = _reload_stress_and_vitals()

    with caplog.at_level("INFO"):
        out = sh.run_once()

    assert out == ""
    assert not os.path.exists(str(log_path))
    assert "[RECALL][Stress] disabled via env; fail-closed no-op" in caplog.text

