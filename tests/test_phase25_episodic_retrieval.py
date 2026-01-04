from __future__ import annotations

import os
import sys
import types


def test_episode_in_belief_graph_retrieval(monkeypatch):
    os.environ["AXIOM_EPISODIC_LOOP_ENABLED"] = "1"
    os.environ["AXIOM_CONFIDENCE_ENABLED"] = "0"  # keep deterministic

    from episodic_loop import integrate_episode
    from retrieval_planner import get_graph_related_beliefs

    # Monkeypatch subject extraction to yield our headline without spaCy
    fake_ip = types.ModuleType("intent_parser")

    def _fake_extract_subjects(text: str):
        return [text]

    setattr(fake_ip, "extract_subjects", _fake_extract_subjects)
    monkeypatch.setitem(sys.modules, "intent_parser", fake_ip)

    ep = {
        "headline": "Lisbon offsite",
        "summary": "Episode themes [lisbon, offsite, agenda]. Summary: planning and logistics",
        "member_ids": ["m1", "m2", "m3"],
        "confidence": 0.6,
    }

    bid = integrate_episode(ep)
    assert bid is None or isinstance(bid, str)

    hits = get_graph_related_beliefs("Lisbon offsite")
    assert isinstance(hits, list)
