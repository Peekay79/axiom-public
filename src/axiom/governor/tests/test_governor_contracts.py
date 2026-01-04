#!/usr/bin/env python3
import json
import os
from pathlib import Path


def _write_signal(tmp: Path, signal: str, data: dict):
    payload = {"pod": "governor", "signal": signal, "ts": "2025-01-01T00:00:00", "data": data}
    (tmp / f"governor.{signal}.json").write_text(json.dumps(payload))


def test_ids_helpers():
    from governor.ids import new_correlation_id, normalize_correlation_id, idempotency_key

    cid = new_correlation_id()
    assert cid.startswith("corr_")
    assert normalize_correlation_id(cid) == cid
    assert normalize_correlation_id(None).startswith("corr_")
    idem = idempotency_key({"a": 1, "b": 2})
    assert idem.startswith("idem_") and len(idem) > 10


def test_middleware_injection():
    from governor.middleware import ensure_correlation_and_idempotency

    headers = ensure_correlation_and_idempotency({}, {"x": 1}, require_cid=True, require_idem=True)
    assert headers.get("X-Correlation-ID", "").startswith("corr_")
    assert headers.get("Idempotency-Key", "").startswith("idem_")


def test_saga_and_aggregator(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))

    from governor.saga import saga_begin, saga_step, saga_end
    saga_begin("corr_abc", "WriteMemorySaga", {"route": "/memory/add"})
    saga_step("corr_abc", "WriteMemorySaga", "journal_append", True, {"id": "j1"})
    saga_end("corr_abc", "WriteMemorySaga", False, {"rolled_back": False})

    from pods.cockpit.cockpit_aggregator import aggregate_status

    snap = aggregate_status()
    gov = snap.get("governor", {})
    assert isinstance(gov.get("sagas", {}), dict)
    wm = gov.get("sagas", {}).get("WriteMemorySaga", {})
    assert int(wm.get("began", 0)) >= 1


def test_retrieval_monitor(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    from governor.retrieval_monitor import report_embedding_stats, report_recall_cohort
    report_embedding_stats("mem", [1.0, 2.0, 3.0])
    report_recall_cohort("mem", "canary", 5, 3, 5)

    from pods.cockpit.cockpit_aggregator import aggregate_status
    snap = aggregate_status()
    gov = snap.get("governor", {})
    assert "mem" in gov.get("retrieval", {}).get("embedding_norms", {})
    assert "mem" in gov.get("retrieval", {}).get("recall_cohorts", {})


def test_schema_validation_soft(monkeypatch, tmp_path):
    # This test exercises the validator indirectly by simulating a violation signal
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    _write_signal(tmp_path, "contract_violation.schema_violation", {"route": "/memory/add", "detail": "schema_violation:ValidationError"})
    from pods.cockpit.cockpit_aggregator import aggregate_status
    snap = aggregate_status()
    cv = (snap.get("governor", {}) or {}).get("contract_violations", {})
    assert int(cv.get("schema_violation", 0)) == 1


def test_contract_violation_counters(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    _write_signal(tmp_path, "contract_violation.missing_correlation_id", {"route": "/x"})
    _write_signal(tmp_path, "contract_violation.missing_idempotency_key", {"route": "/y"})
    _write_signal(tmp_path, "belief_contradiction", {"belief": "b1", "counter": "b2"})

    from pods.cockpit.cockpit_aggregator import aggregate_status
    snap = aggregate_status()
    cv = (snap.get("governor", {}) or {}).get("contract_violations", {})
    assert int(cv.get("missing_correlation_id", 0)) == 1
    assert int(cv.get("missing_idempotency_key", 0)) == 1
    assert int((snap.get("governor", {}) or {}).get("belief", {}).get("contradictions", 0)) == 1

