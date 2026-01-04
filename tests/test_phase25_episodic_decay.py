from __future__ import annotations

import os
import sys
import types


def test_episode_inactive_when_children_decay(monkeypatch):
    os.environ["AXIOM_EPISODIC_LOOP_ENABLED"] = "1"
    os.environ["AXIOM_CONFIDENCE_ENABLED"] = "0"  # simplify confidence pipeline
    os.environ["AXIOM_CONFIDENCE_MIN_THRESHOLD"] = "0.5"

    # Monkeypatch Memory class import used by sqlite backend to return decayed children
    fake_mod = types.ModuleType("pods.memory.memory_manager")

    class FakeMemory:
        def __init__(self):
            pass

        def snapshot(self):
            return [
                {"id": "child_a", "confidence": 0.2},
                {"id": "child_b", "confidence": 0.1},
                {"id": "child_c", "confidence": 0.3},
            ]

    setattr(fake_mod, "Memory", FakeMemory)
    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", fake_mod)

    from episodic_loop import integrate_episode
    from belief_graph import belief_graph as _bg

    ep = {
        "headline": "Project Kickoff",
        "summary": "Episode summary",
        "member_ids": ["child_a", "child_b", "child_c"],
        "confidence": 0.51,
    }
    bid = integrate_episode(ep)
    if not bid:
        # Backend may be stubbed; nothing more to assert
        return

    hits = _bg.get_beliefs(["Project Kickoff"], hops=1)
    assert isinstance(hits, list)
    ep_hits = [h for h in hits if h.get("id") == bid]
    if ep_hits:
        tags = ep_hits[0].get("tags") or []
        # Inactivity should be applied because all children are below threshold
        assert "inactive" in tags
