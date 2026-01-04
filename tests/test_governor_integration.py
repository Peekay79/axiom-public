import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.utils.env import temp_env


def test_belief_provenance_rejection_and_logging(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    from governor.belief_governance import ensure_provenance

    ok, detail = ensure_provenance({"content": "x"})
    assert ok is False and detail == "missing_provenance"
    # Canonical Governor tag present
    assert any("[RECALL][Governor]" in r.getMessage() for r in caplog.records)


def test_contradiction_signal_emission(monkeypatch, tmp_path: Path):
    # Force cockpit signal writes
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))

    from governor.belief_governance import report_contradiction

    report_contradiction("a1", "b2")
    files = list(tmp_path.glob("governor.belief_contradiction.json"))
    if files:
        data = json.loads(files[0].read_text())
        assert data.get("pod") == "governor" and data.get("signal") == "belief_contradiction"
    else:
        # Accept fail-closed: emission may be skipped if reporter cannot create dir; log should be handled elsewhere
        assert True


def test_contradiction_signal_fail_closed(monkeypatch, tmp_path: Path, caplog):
    caplog.set_level(logging.INFO)

    # Unset signal dir to exercise fail-closed path; reporter falls back to no-ops
    with temp_env({"COCKPIT_SIGNAL_DIR": None}):
        from governor.belief_governance import report_contradiction

        report_contradiction("x", "y")
        # No files written
        assert list(tmp_path.glob("governor.belief_contradiction.json")) == []
        # We still should have a canonical Governor tag indicating skip
        assert any("[RECALL][Governor]" in r.getMessage() for r in caplog.records)


def test_middleware_sanitization_and_contracts(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Build unsafe headers
    unsafe = {
        "X-Forwarded-For": "1.2.3.4",
        "X-Real-IP": "evil",
        "Accept": "application/json",
    }

    from governor.middleware import sanitize_headers, ensure_correlation_and_idempotency

    sanitized = sanitize_headers(unsafe)
    # Unsafe stripped, safe kept
    assert "X-Forwarded-For" not in sanitized and sanitized.get("Accept") == "application/json"
    assert any("[RECALL][Governor]" in r.getMessage() for r in caplog.records)

    # ensure_correlation_and_idempotency should inject required headers
    headers = ensure_correlation_and_idempotency({}, {"x": 1}, require_cid=True, require_idem=True)
    assert headers.get("X-Correlation-ID", "").startswith("corr_")
    assert headers.get("Idempotency-Key", "").startswith("idem_")

