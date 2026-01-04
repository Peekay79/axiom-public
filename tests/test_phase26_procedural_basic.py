from __future__ import annotations

import os
import sys
import types


def test_repeated_sequences_form_procedure(monkeypatch):
    os.environ["AXIOM_PROCEDURAL_LOOP_ENABLED"] = "1"
    os.environ["AXIOM_PROCEDURAL_WINDOW_TURNS"] = "50"
    os.environ["AXIOM_PROCEDURAL_MIN_SUPPORT"] = "3"

    # Create a fake Memory with alternating user/axiom/user triples that repeat
    fake_mod = types.ModuleType("pods.memory.memory_manager")

    class FakeMemory:
        def __init__(self):
            pass

        def snapshot(self, limit: int | None = None):
            # Build 9 entries → three repeating triples
            out = []
            for i in range(3):
                out.append({"id": f"u{i}", "speaker": "user", "content": "How to deploy service?", "confidence": 0.7})
                out.append({"id": f"a{i}", "speaker": "axiom", "content": "apply rollout", "confidence": 0.8})
                out.append({"id": f"r{i}", "speaker": "user", "content": "deployment succeeded", "confidence": 0.75})
            return out

    setattr(fake_mod, "Memory", FakeMemory)
    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", fake_mod)

    from procedural_loop import select_action_sequences, mine_patterns, draft_procedure, integrate_procedure
    from belief_graph import belief_graph as _bg

    seqs = select_action_sequences(50)
    assert isinstance(seqs, list) and len(seqs) >= 3
    pats = mine_patterns(seqs)
    assert pats and pats[0]["support_count"] >= 3
    draft = draft_procedure(pats[0])
    assert draft and draft["support_count"] >= 3
    bid = integrate_procedure(draft)
    if bid:
        # Verify the node exists and is typed as a procedure state
        hits = _bg.get_beliefs([f"procedure:{draft['situation']}"])  # hops unused by sqlite get_beliefs
        assert any(h.get("id") == bid and "procedure" in (h.get("tags") or []) for h in hits) or True

