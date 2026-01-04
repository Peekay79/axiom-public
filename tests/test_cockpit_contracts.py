#!/usr/bin/env python3
import json
import os
from pathlib import Path


def _write_json_signal(dir: Path, pod: str, signal: str, data: dict):
    payload = {"pod": pod, "signal": signal, "ts": "2025-01-01T00:00:00", "data": data}
    (dir / f"{pod}.{signal}.json").write_text(json.dumps(payload))


def test_role_gating_blocked_writes(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    # synthesize two blocked writes
    _write_json_signal(tmp_path, "memory", "blocked_write", {"reason": "role=discord_bot"})
    _write_json_signal(tmp_path, "memory", "blocked_write", {"reason": "role=discord_bot"})

    from pods.cockpit.cockpit_aggregator import aggregate_status
    from pods.cockpit.degradation_flags import compute_degradation

    snap = aggregate_status()
    assert int(snap.get("blocked_writes_by_role", 0)) == 2
    d = compute_degradation(snap)
    assert d["memory_persistence_blocked"] is True


def test_reporter_schema_tolerates_malformed(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    # Valid
    _write_json_signal(tmp_path, "vector", "vector_recall", {"ok": True, "latency_ms": 100})
    # Malformed (missing required fields inside data is okay; outer fields are present)
    (tmp_path / "vector.vector_recall.json").write_text("{not json}")

    from pods.cockpit.cockpit_aggregator import aggregate_status

    snap = aggregate_status()
    # Should not crash; at least produces dict
    assert isinstance(snap, dict)


def test_boot_readiness(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    # Fresh ready + heartbeat
    for p in ["belief", "journal"]:
        (tmp_path / f"{p}.ready").write_text("2025-01-01T00:00:00")
        (tmp_path / f"{p}.last_heartbeat").write_text("2025-01-01T00:01:00")

    from pods.cockpit.cockpit_aggregator import aggregate_status
    from pods.cockpit.degradation_flags import compute_degradation

    snap = aggregate_status()
    d = compute_degradation(snap)
    assert d["belief_pipeline_unready"] is False
    assert d["journal_pipeline_unready"] is False

    # Remove heartbeat to simulate unready
    (tmp_path / "belief.last_heartbeat").unlink(missing_ok=True)
    snap2 = aggregate_status()
    d2 = compute_degradation(snap2)
    assert d2["belief_pipeline_unready"] is True


def test_retrieval_degradation(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    # Vector recall failures to trigger blackout
    for i in range(3):
        _write_json_signal(tmp_path, "vector", "vector_recall", {"ok": False, "err": "timeout"})
    # High latencies to trigger degraded
    for i in range(20):
        _write_json_signal(tmp_path, "vector", "vector_recall", {"ok": True, "latency_ms": 999})

    from pods.cockpit.cockpit_aggregator import aggregate_status
    from pods.cockpit.degradation_flags import compute_degradation

    snap = aggregate_status()
    assert snap["vector_blackout_active"] is True
    assert snap["recall_degraded"] is True
    d = compute_degradation(snap)
    assert d["vector_blackout_active"] is True
    assert d["recall_degraded"] is True


def test_composite(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    # Good baseline: ready + heartbeat for pods
    for p in ["belief", "journal"]:
        (tmp_path / f"{p}.ready").write_text("2025-01-01T00:00:00")
        (tmp_path / f"{p}.last_heartbeat").write_text("2025-01-01T00:01:00")
    # No failures, low latency
    _write_json_signal(tmp_path, "vector", "vector_recall", {"ok": True, "latency_ms": 10})

    from pods.cockpit.cockpit_aggregator import aggregate_status
    from pods.cockpit.degradation_flags import compute_degradation

    snap = aggregate_status()
    d = compute_degradation(snap)
    assert d["cognitive_ok"] is True

    # Introduce a single degradation (blocked write)
    _write_json_signal(tmp_path, "memory", "blocked_write", {"reason": "test"})
    snap2 = aggregate_status()
    d2 = compute_degradation(snap2)
    assert d2["cognitive_ok"] is False


def test_startup_slow_and_schema_drift(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    # Startup slow: start then ready after threshold + 5s
    (tmp_path / "journal.start").write_text("2025-01-01T00:00:00")
    (tmp_path / "journal.ready").write_text("2025-01-01T00:02:00")  # 120s > default 60s

    # Two recent schema normalization events with valid ts
    def _emit_norm(idx: int):
        payload = {
            "pod": "memory",
            "signal": "schema_normalization.memory_type",
            "ts": "2025-01-01T00:00:30",
            "data": {"field": "memory_type", "old": "default", "new": "episodic", "reason": "normalize_to_allowed"}
        }
        (tmp_path / f"memory.schema_normalization.memory_type.{idx}.json").write_text(json.dumps(payload))

    _emit_norm(0)
    _emit_norm(1)

    from pods.cockpit.cockpit_aggregator import aggregate_status
    from pods.cockpit.degradation_flags import compute_degradation

    snap = aggregate_status()
    assert isinstance(snap.get("startup_slow"), dict)
    assert bool(snap.get("startup_slow_any")) is True
    assert int(snap.get("schema_normalization_events", 0)) >= 2

    d = compute_degradation(snap)
    assert d["startup_slow_any"] is True
    assert d["memory_schema_drift_active"] is True
    assert d["cognitive_ok"] is False

