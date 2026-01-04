def test_simple_contradiction_detects_opposite_claims():
    from beliefs.contradictions import detect_contradictions

    # Two memories with same belief tag and opposing polarity
    candidates = [
        {
            "id": "A",
            "beliefs": ["topic.entity"],
            "content": "Alpha is not available today.",
            "timestamp": "2025-01-01T00:00:00Z",
        },
        {
            "id": "B",
            "beliefs": ["topic.entity"],
            "content": "Alpha is available today.",
            "timestamp": "2025-01-02T00:00:00Z",
        },
    ]

    conflicts = detect_contradictions(candidates)
    assert isinstance(conflicts, list)
    assert conflicts, "Expected at least one contradiction to be detected"
    ids = {c.get("a_id"), c.get("b_id") for c in conflicts}
    flat_ids = set()
    for pair in ids:
        if isinstance(pair, set):
            flat_ids |= pair
        elif isinstance(pair, (list, tuple)):
            flat_ids |= set(pair)
        elif isinstance(pair, str):
            flat_ids.add(pair)
    assert "A" in flat_ids and "B" in flat_ids

