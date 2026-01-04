import os
import time


def test_meta_ticker_respects_disable(monkeypatch):
    import meta_cognition

    monkeypatch.setenv("AXIOM_META_LOOP_ENABLED", "0")
    assert meta_cognition.start_meta_ticker_if_enabled() is False


def test_meta_ticker_tick_once(monkeypatch):
    import meta_cognition

    t = meta_cognition._ticker  # internal
    # Ensure no overlap and manual tick works
    res = t.tick_once()
    assert res["status"] in {"ok", "skipped"}

