import logging
from tests.utils.env import temp_env


def test_legacy_mode_accepts_missing_provenance_logs(monkeypatch, caplog):
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "0"}):
        # Use the planner filter directly; with flag=0 it should accept all
        from retrieval_planner import _filter_missing_provenance as _f  # type: ignore

        mixed = [
            {"id": "x", "content": "a"},
            {"id": "y", "content": "b", "provenance": "ok"},
        ]
        caplog.set_level(logging.INFO)
        kept = _f(mixed)
        assert len(kept) == 2
        # Check that legacy mode log line was emitted
        found = any("[RECALL][Provenance] missing provenance accepted under legacy mode" in rec.getMessage() for rec in caplog.records)
        assert found
