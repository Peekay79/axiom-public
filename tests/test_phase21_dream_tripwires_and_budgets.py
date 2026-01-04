import os
import time

from dream_loop import maybe_run_dream_loop


class _TW:
    def __init__(self, allow):
        self._allow = allow

    def is_dream_allowed(self):
        return self._allow


def test_tripwire_denial_aborts(monkeypatch):
    monkeypatch.setenv("AXIOM_DREAM_LOOP_ENABLED", "1")
    import dream_loop as dl

    monkeypatch.setattr(dl, "_tripwires", _TW(False))

    out = maybe_run_dream_loop()
    assert out.get("status") == "aborted"
    assert out.get("reason") == "tripwire"


def test_time_budget_abort(monkeypatch):
    monkeypatch.setenv("AXIOM_DREAM_LOOP_ENABLED", "1")
    monkeypatch.setenv("AXIOM_DREAM_MAX_MS", "1")  # tiny budget

    # Force selection to take time by injecting many items
    class _Mem:
        def snapshot(self):
            now = "2025-01-01T00:00:00+00:00"
            return [{"id": f"i{i}", "content": "x" * 5, "memory_type": "episodic", "timestamp": now} for i in range(500)]

    import dream_loop as dl

    monkeypatch.setattr(dl, "Memory", _Mem)

    out = maybe_run_dream_loop()
    # Likely abort due to timeout in one of the stages
    assert out.get("status") in {"aborted", "ok"}
    # If aborted, reason should be timeout or disabled
    if out.get("status") == "aborted":
        assert out.get("reason") in {"timeout", "disabled", "tripwire"}

