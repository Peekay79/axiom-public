#!/usr/bin/env python3
import json
import os
import shutil
import tempfile
from pathlib import Path


def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_status_json_shapes():
    tmp = tempfile.mkdtemp(prefix="cockpit_test_")
    try:
        os.environ["COCKPIT_SIGNAL_DIR"] = tmp
        # Write minimal ready/heartbeat files
        _write(Path(tmp) / "llm.ready", "2025-01-01T00:00:00")
        _write(Path(tmp) / "llm.last_heartbeat", "2025-01-01T00:00:59")
        _write(Path(tmp) / "vector.ready", "2025-01-01T00:00:00")
        _write(Path(tmp) / "vector.last_heartbeat", "2025-01-01T00:00:59")
        _write(Path(tmp) / "memory.ready", "2025-01-01T00:00:00")
        _write(Path(tmp) / "belief.ready", "2025-01-01T00:00:00")
        _write(Path(tmp) / "journal.ready", "2025-01-01T00:00:00")

        # Fake some vector recall signals
        vector_signal = {
            "pod": "vector",
            "signal": "vector_recall",
            "ts": "2025-01-01T00:00:30",
            "data": {"ok": True, "latency_ms": 180}
        }
        (Path(tmp) / "vector.vector_recall.0.json").write_text(json.dumps(vector_signal))

        from pods.cockpit.cockpit_aggregator import aggregate_status

        status = aggregate_status()
        assert isinstance(status, dict)
        for key in [
            "pods",
            "blackouts",
            "vector_blackout_active",
            "recall_degraded",
            "last_vector_latency_ms",
            "cognitive_ok",
            "generated_at",
        ]:
            assert key in status
        assert isinstance(status["pods"], dict)
        assert "vector" in status["pods"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_blackout_detection():
    tmp = tempfile.mkdtemp(prefix="cockpit_test_")
    try:
        os.environ["COCKPIT_SIGNAL_DIR"] = tmp
        # Ensure vector ready to make cognitive_ok depend on blackout flag
        _write(Path(tmp) / "vector.ready", "2025-01-01T00:00:00")

        # Three failure signals
        for i in range(3):
            payload = {
                "pod": "vector",
                "signal": "vector_recall",
                "ts": f"2025-01-01T00:00:{10+i:02d}",
                "data": {"ok": False, "err": "timeout"}
            }
            (Path(tmp) / f"vector.vector_recall.{i}.json").write_text(json.dumps(payload))

        from pods.cockpit.cockpit_aggregator import aggregate_status

        status = aggregate_status()
        assert status["vector_blackout_active"] is True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_rate_limit():
    from pods.cockpit.rate_limit import RateLimiter

    rl = RateLimiter(60)
    assert rl.allow() is True
    assert rl.allow() is False


def test_journal_write_failures_count(tmp_path, monkeypatch):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    # Two journal failure signals
    for i in range(2):
        payload = {
            "pod": "journal",
            "signal": "journal_write_failure",
            "ts": "2025-01-01T00:00:00",
            "data": {"reason": "perm denied"}
        }
        (tmp_path / f"journal.journal_write_failure.{i}.json").write_text(json.dumps(payload))

    from pods.cockpit.cockpit_aggregator import aggregate_status

    status = aggregate_status()
    assert int(status.get("journal_write_failures", 0)) == 2


def test_belief_insert_failures_count(tmp_path, monkeypatch):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    payload = {
        "pod": "belief",
        "signal": "belief_insert_failure",
        "ts": "2025-01-01T00:00:00",
        "data": {"reason": "db error"}
    }
    (tmp_path / f"belief.belief_insert_failure.0.json").write_text(json.dumps(payload))

    from pods.cockpit.cockpit_aggregator import aggregate_status

    status = aggregate_status()
    assert int(status.get("belief_insert_failures", 0)) == 1
