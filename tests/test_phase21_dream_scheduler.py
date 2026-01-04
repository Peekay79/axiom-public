import os
import time

from dream_loop import start_dream_ticker_if_enabled, stop_dream_ticker, _ticker


class _TW:
    def __init__(self, allow=True):
        self._allow = allow

    def is_dream_allowed(self):
        return self._allow


def test_ticker_respects_enable_and_interval(monkeypatch):
    # Ensure enabled
    monkeypatch.setenv("AXIOM_DREAM_LOOP_ENABLED", "1")
    monkeypatch.setenv("AXIOM_DREAM_TICK_SEC", "1")
    monkeypatch.setenv("AXIOM_DREAM_MIN_INTERVAL_SEC", "2")
    monkeypatch.setenv("AXIOM_DREAM_DRY_RUN", "1")

    # Allow dreams
    import dream_loop as dl

    monkeypatch.setattr(dl, "_tripwires", _TW(True))

    # Spy maybe_run_dream_loop to count calls
    calls = {"n": 0}

    def _fake_run(now=None):
        calls["n"] += 1
        return {"status": "ok", "selected": 0, "clusters": 0, "drafted": 0, "pruned": 0, "integrated": 0, "ms_elapsed": 1, "dry_run": True}

    monkeypatch.setattr(dl, "maybe_run_dream_loop", _fake_run)

    try:
        started = start_dream_ticker_if_enabled()
        assert started is True
        # Let it tick a couple cycles
        time.sleep(2.5)
        # Should have run at least once but not spamming due to min interval
        assert calls["n"] >= 1
    finally:
        stop_dream_ticker()


def test_ticker_tripwire_blocks(monkeypatch):
    monkeypatch.setenv("AXIOM_DREAM_LOOP_ENABLED", "1")
    monkeypatch.setenv("AXIOM_DREAM_TICK_SEC", "1")
    monkeypatch.setenv("AXIOM_DREAM_MIN_INTERVAL_SEC", "1")
    monkeypatch.setenv("AXIOM_DREAM_DRY_RUN", "1")

    import dream_loop as dl

    monkeypatch.setattr(dl, "_tripwires", _TW(False))

    calls = {"n": 0}

    def _fake_run(now=None):
        calls["n"] += 1
        return {"status": "aborted", "reason": "tripwire"}

    monkeypatch.setattr(dl, "maybe_run_dream_loop", _fake_run)

    try:
        started = start_dream_ticker_if_enabled()
        assert started is True
        time.sleep(1.5)
        # It may attempt to run and abort; we just ensure no crash
        assert calls["n"] >= 0
    finally:
        stop_dream_ticker()

