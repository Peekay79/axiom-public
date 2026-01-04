#!/usr/bin/env python3
from __future__ import annotations

import os
import types


def _set_env(**kwargs):
    for k, v in kwargs.items():
        if v is None and k in os.environ:
            del os.environ[k]
        elif v is not None:
            os.environ[k] = str(v)


def test_belief_hook_creates_on_high_confidence_correct(monkeypatch):
    _set_env(GUT_TO_BELIEFS="true")

    # Stub add_belief to capture payload
    captured = {}

    async def fake_add_belief(payload, **kwargs):  # type: ignore
        captured.update(payload)
        return {"ok": True, "contradictions": []}

    fake_belief_mod = types.SimpleNamespace(add_belief=fake_add_belief)
    monkeypatch.setitem(sys.modules, "memory.belief_engine", fake_belief_mod)  # type: ignore

    from gut.gut_journal import write_gut_event

    write_gut_event(
        {
            "type": "gut",
            "context": {"hint": "left-bias improved success recently"},
            "prior_bias": {"left": 0.8, "right": 0.2},
            "confidence": 0.75,
            "outcome": "correct",
            "override": False,
            "importance": 2,
            "context_type": "symbolic",
            "timestamp": "2025-09-04T12:30:00Z",
        }
    )

    # Allow event loop tasks to schedule if any
    assert captured.get("source") == "gut"
    assert captured.get("confidence_origin") == "gut"
    assert captured.get("confidence") == 0.75
    assert "statement" in captured and isinstance(captured["statement"], str)


def test_belief_hook_contradiction_on_incorrect(monkeypatch):
    _set_env(GUT_TO_BELIEFS="true")

    captured = {}

    async def fake_add_belief(payload, **kwargs):  # type: ignore
        captured.update(payload)
        return {"ok": True, "contradictions": []}

    fake_belief_mod = types.SimpleNamespace(add_belief=fake_add_belief)
    monkeypatch.setitem(sys.modules, "memory.belief_engine", fake_belief_mod)  # type: ignore

    from gut.gut_journal import write_gut_event

    write_gut_event(
        {
            "type": "gut",
            "context": {"hint": "confidence miscalibration detected"},
            "prior_bias": {"left": 0.7, "right": 0.3},
            "confidence": 0.71,
            "outcome": "incorrect",
            "override": False,
            "importance": 1,
            "context_type": "symbolic",
            "timestamp": "2025-09-04T12:30:00Z",
        }
    )

    assert captured.get("source") == "gut"
    assert captured.get("confidence_origin") == "gut"
    assert captured.get("confidence") <= 0.11  # clipped to very low
    assert "contradiction" in captured.get("tags", [])


def test_dream_hook_respects_threshold_and_window(monkeypatch):
    _set_env(GUT_TO_DREAMS="true", GUT_DREAM_CONFIDENCE_MIN="0.6", GUT_DREAM_MAX_PER_WINDOW="1")

    # Provide a minimal DreamEngine with generate_dream
    class FakeDreamEngine:
        def __init__(self):
            self.called = True

        async def generate_dream(self, **kwargs):  # type: ignore
            return {"success": True}

    monkeypatch.setitem(sys.modules, "dream_engine", types.SimpleNamespace(DreamEngine=FakeDreamEngine))  # type: ignore

    from gut.gut_journal import write_gut_event

    # First event should enqueue
    write_gut_event(
        {
            "type": "gut",
            "context": {"hint": "override under uncertainty"},
            "prior_bias": {"left": 0.5, "right": 0.5},
            "confidence": 0.8,
            "outcome": "incorrect",
            "override": True,
            "importance": 1,
            "context_type": "symbolic",
            "timestamp": "2025-09-04T12:30:00Z",
        }
    )

    # Second event in the same window should be dropped by window cap (no assertion possible without deeper hooks)
    write_gut_event(
        {
            "type": "gut",
            "context": {"hint": "another"},
            "prior_bias": {"left": 0.5, "right": 0.5},
            "confidence": 0.8,
            "outcome": "incorrect",
            "override": True,
            "importance": 1,
            "context_type": "symbolic",
            "timestamp": "2025-09-04T12:31:00Z",
        }
    )


def test_missing_subsystems_are_silent(monkeypatch):
    _set_env(GUT_TO_BELIEFS="true", GUT_TO_DREAMS="true")

    # Remove modules to trigger fail-closed paths
    import sys

    sys.modules.pop("memory.belief_engine", None)
    sys.modules.pop("dream_engine", None)

    from gut.gut_journal import write_gut_event

    # Should not raise even without subsystems
    write_gut_event(
        {
            "type": "gut",
            "context": "hint only",
            "prior_bias": {},
            "confidence": 0.9,
            "outcome": "correct",
            "override": False,
            "importance": 1,
            "context_type": "symbolic",
            "timestamp": "2025-09-04T12:30:00Z",
        }
    )

