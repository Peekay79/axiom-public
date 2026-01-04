from dream_loop import cluster_and_associate, draft_consolidations, prune_consolidations


def _mem(id_: str, text: str):
    return {"id": id_, "content": text, "memory_type": "episodic", "timestamp": "2025-01-01T00:00:00+00:00"}


def test_clustering_and_pruning_near_duplicates():
    # Three clusters: fruits, work, weather; include a near duplicate
    items = [
        _mem("a1", "I bought apples and oranges at the store"),
        _mem("a2", "I purchased oranges and apples today"),
        _mem("b1", "We deployed the service to staging"),
        _mem("b2", "Deployment to staging completed successfully"),
        _mem("c1", "The weather was rainy and cold"),
    ]

    clusters = cluster_and_associate(items)
    # Baseline lexical threshold should group similar items, but count >= 2 clusters
    assert len(clusters) >= 2

    drafts = draft_consolidations([c for c in clusters if len(c) >= 2])
    # Drafts exist for multi-item clusters
    assert len(drafts) >= 1

    pruned = prune_consolidations(drafts + drafts[:1])  # duplicate one draft
    # Near-duplicate drafts should be collapsed
    assert len(pruned) <= len(drafts)

