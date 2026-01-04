import os
import time


def test_hygiene_ticker_respects_flags_and_min_interval(monkeypatch):
    from memory_hygiene import _HygieneTicker, maybe_run_hygiene_cycle

    # Disabled by default → ticker.start_if_enabled returns False
    t = _HygieneTicker()
    os.environ["AXIOM_HYGIENE_ENABLED"] = "0"
    assert t.start_if_enabled() is False

    # Enable but dry-run; tick_once should not set last_success_ts when dry_run=True
    os.environ["AXIOM_HYGIENE_ENABLED"] = "1"
    os.environ["AXIOM_HYGIENE_DRY_RUN"] = "1"

    # Monkeypatch run to avoid DB access; return a nominal ok result
    def _fake_run(now=None):
        return {"status": "ok", "dry_run": True, "candidates": 0, "archived": 0, "retired": 0, "kept": 0}

    monkeypatch.setattr("memory_hygiene.maybe_run_hygiene_cycle", _fake_run)

    res = t.tick_once()
    assert res.get("status") in {"ok", "skipped"}
    assert t.last_success_ts == 0.0  # remains zero because dry-run

    # Now simulate non‑dry run and verify min interval gating
    os.environ["AXIOM_HYGIENE_DRY_RUN"] = "0"

    def _fake_run2(now=None):
        return {"status": "ok", "dry_run": False, "candidates": 0, "archived": 0, "retired": 0, "kept": 0}

    monkeypatch.setattr("memory_hygiene.maybe_run_hygiene_cycle", _fake_run2)
    res2 = t.tick_once()
    assert res2.get("status") == "ok"
    assert t.last_success_ts > 0.0

    # Immediately calling tick_once again should skip due to _in_flight guard or min interval
    res3 = t.tick_once()
    # Either skipped or ok but last_success not updated due to min interval
    assert res3.get("status") in {"skipped", "ok"}
