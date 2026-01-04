import os
from datetime import datetime, timedelta, timezone

import pytest

from dream_loop import select_candidates


def _mk(mem_type: str, days_ago: int, consolidated: bool = False):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    meta = {"dream_consolidated": True} if consolidated else {}
    return {"id": f"m_{mem_type}_{days_ago}", "memory_type": mem_type, "timestamp": ts, "meta": meta, "content": f"{mem_type} d{days_ago}"}


def test_select_candidates_respects_window_and_limit(monkeypatch):
    # Build a fake Memory with snapshot
    class _Mem:
        def snapshot(self):
            return [
                _mk("episodic", 1),
                _mk("short_term", 2),
                _mk("semantic", 1),
                _mk("episodic", 10),
                _mk("episodic", 3, consolidated=True),
            ]

    monkeypatch.setenv("AXIOM_DREAM_LOOP_ENABLED", "1")
    monkeypatch.setenv("AXIOM_DREAM_DRY_RUN", "1")

    # Patch Memory class used by dream_loop
    import dream_loop as dl

    monkeypatch.setattr(dl, "Memory", _Mem)

    # 7d window, limit 2
    out = select_candidates(window="7d", limit=2)
    # Should include recent episodic/short_term only, exclude consolidated and semantic
    ids = {m["id"] for m in out}
    assert ids.issubset({"m_episodic_1", "m_short_term_2"})
    assert len(out) <= 2

    # 1d window, should filter to only episodic_1
    out2 = select_candidates(window="1d", limit=10)
    ids2 = {m["id"] for m in out2}
    assert ids2 == {"m_episodic_1"}

