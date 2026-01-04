from __future__ import annotations

import os
import time

import pytest


def _mk(bid: str, conf: float, ts: int) -> dict:
    return {"id": bid, "confidence": conf, "last_updated": ts, "recency": ts}


@pytest.fixture(autouse=True)
def phase7_env(monkeypatch):
    monkeypatch.setenv("AXIOM_CONTRADICTION_RESOLUTION", "1")
    yield


def test_confidence_strategy_keeps_higher(monkeypatch):
    from contradiction_resolver import resolve_conflict

    monkeypatch.setenv("AXIOM_RESOLUTION_STRATEGY", "confidence")

    a = _mk("A", 0.9, int(time.time()) - 10)
    b = _mk("B", 0.6, int(time.time()))

    # Stub belief_graph.set_belief_state to capture calls
    calls = []

    class StubBG:
        def set_belief_state(self, bid, state):
            calls.append((str(bid), str(state)))
            return True

    monkeypatch.setattr("contradiction_resolver.BELIEF_GRAPH", StubBG())

    survivor = resolve_conflict(a, b)
    assert survivor == "A"
    assert ("B", "superseded") in calls


def test_recency_strategy_keeps_newer(monkeypatch):
    from contradiction_resolver import resolve_conflict

    monkeypatch.setenv("AXIOM_RESOLUTION_STRATEGY", "recency")

    now = int(time.time())
    a = _mk("A", 0.6, now - 100)
    b = _mk("B", 0.6, now)

    calls = []

    class StubBG:
        def set_belief_state(self, bid, state):
            calls.append((str(bid), str(state)))
            return True

    monkeypatch.setattr("contradiction_resolver.BELIEF_GRAPH", StubBG())

    survivor = resolve_conflict(a, b)
    assert survivor == "B"
    assert ("A", "superseded") in calls


def test_uncertain_strategy_marks_both(monkeypatch):
    from contradiction_resolver import resolve_conflict

    monkeypatch.setenv("AXIOM_RESOLUTION_STRATEGY", "uncertain")

    a = _mk("A", 0.6, int(time.time()))
    b = _mk("B", 0.9, int(time.time()))

    calls = []

    class StubBG:
        def set_belief_state(self, bid, state):
            calls.append((str(bid), str(state)))
            return True

    monkeypatch.setattr("contradiction_resolver.BELIEF_GRAPH", StubBG())

    survivor = resolve_conflict(a, b)
    assert survivor is None
    assert ("A", "uncertain") in calls and ("B", "uncertain") in calls


def test_resolution_skipped_when_flag_off(monkeypatch):
    from contradiction_resolver import resolve_conflict

    monkeypatch.setenv("AXIOM_CONTRADICTION_RESOLUTION", "0")
    # ensure strategy doesn't matter when disabled
    monkeypatch.setenv("AXIOM_RESOLUTION_STRATEGY", "confidence")

    a = _mk("A", 0.6, int(time.time()))
    b = _mk("B", 0.9, int(time.time()))

    # ensure no crashes without BELIEF_GRAPH
    monkeypatch.setattr("contradiction_resolver.BELIEF_GRAPH", None)

    survivor = resolve_conflict(a, b)
    assert survivor is None

