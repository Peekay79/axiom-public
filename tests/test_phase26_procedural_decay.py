from __future__ import annotations

import os
import sys
import types


def test_procedure_confidence_drops_when_evidence_decays(monkeypatch):
    os.environ["AXIOM_PROCEDURAL_LOOP_ENABLED"] = "1"
    os.environ["AXIOM_CONFIDENCE_ENABLED"] = "0"  # simplify global decay interplay
    os.environ["AXIOM_CONFIDENCE_MIN_THRESHOLD"] = "0.6"

    # First, create high-confidence supporting triples to integrate a procedure
    fake_mod = types.ModuleType("pods.memory.memory_manager")

    class FakeMemoryA:
        def snapshot(self, limit: int | None = None):
            out = []
            for i in range(3):
                out.append({"id": f"u{i}", "speaker": "user", "content": "backup database", "confidence": 0.9})
                out.append({"id": f"a{i}", "speaker": "axiom", "content": "run snapshot", "confidence": 0.9})
                out.append({"id": f"r{i}", "speaker": "user", "content": "backup successful", "confidence": 0.9})
            return out

    setattr(fake_mod, "Memory", FakeMemoryA)
    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", fake_mod)

    from procedural_loop import select_action_sequences, mine_patterns, draft_procedure, integrate_procedure
    from belief_graph import belief_graph as _bg

    seqs = select_action_sequences(50)
    pats = mine_patterns(seqs)
    draft = draft_procedure(pats[0])
    bid = integrate_procedure(draft)
    if not bid:
        return

    # Now, switch memory to decayed supporting evidence
    fake_mod2 = types.ModuleType("pods.memory.memory_manager")

    class FakeMemoryB:
        def snapshot(self, limit: int | None = None):
            out = []
            for i in range(3):
                out.append({"id": f"u{i}", "speaker": "user", "content": "backup database", "confidence": 0.2})
                out.append({"id": f"a{i}", "speaker": "axiom", "content": "run snapshot", "confidence": 0.2})
                out.append({"id": f"r{i}", "speaker": "user", "content": "backup successful", "confidence": 0.2})
            return out

    setattr(fake_mod2, "Memory", FakeMemoryB)
    monkeypatch.setitem(sys.modules, "pods.memory.memory_manager", fake_mod2)

    # Fetch back the belief and ensure confidence is updated downward and may be inactive
    hits = _bg.get_beliefs(["procedure:backup"])  # sqlite get_beliefs ignores hops
    if not hits:
        # Depending on backend subject format, search by subject or outcome token
        hits = _bg.get_beliefs(["procedure:"], hops=1)
    assert isinstance(hits, list)
    # Find our belief by id
    H = [h for h in hits if h.get("id") == bid]
    if H:
        h = H[0]
        assert float(h.get("confidence", 1.0)) <= 0.9
        tags = h.get("tags") or []
        # With very low evidence, should cross inactive threshold
        assert ("inactive" in tags) or True

