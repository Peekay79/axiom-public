from __future__ import annotations

import os


def test_related_memories_form_episode(monkeypatch):
    os.environ["AXIOM_EPISODIC_LOOP_ENABLED"] = "1"
    os.environ["AXIOM_EPISODIC_WINDOW_HOURS"] = "24"
    os.environ["AXIOM_EPISODIC_MIN_LINKS"] = "3"

    from episodic_loop import draft_episode, cluster_and_link

    # 4 related memories around the same theme
    cluster = [
        {"id": "m1", "content": "Team offsite planning in Lisbon next week", "confidence": 0.7},
        {"id": "m2", "content": "Lisbon offsite agenda drafting and logistics", "confidence": 0.6},
        {"id": "m3", "content": "Travel bookings for Lisbon team offsite", "confidence": 0.65},
        {"id": "m4", "content": "Collect dietary restrictions for offsite catering in Lisbon", "confidence": 0.55},
    ]

    clusters = cluster_and_link(cluster)
    # Since these are all related, they should form a single cluster meeting min_links
    assert isinstance(clusters, list)
    assert clusters and any(len(c) >= 3 for c in clusters)

    # Pick the largest cluster
    c = max(clusters, key=lambda x: len(x))
    ep = draft_episode(c)
    assert ep
    assert isinstance(ep.get("member_ids"), list)
    assert len(ep["member_ids"]) >= 3
    assert 0.0 <= float(ep["confidence"]) <= 1.0
