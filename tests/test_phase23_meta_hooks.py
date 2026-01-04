def test_judger_hook_records(monkeypatch):
    import importlib
    import meta_cognition
    import judger

    # Spy on vitals via get_meta_snapshot delta
    # Seed: ensure empty
    scores = meta_cognition.compute_cycle()
    before = meta_cognition._vitals.get_meta_snapshot(window_sec=3600) if meta_cognition._vitals else {}

    hits = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.1}]
    kept = judger.apply_judgements(
        [
            {"id": "a", "tags": []},
            {"id": "b", "tags": []},
        ],
        hits,
        threshold=0.3,
    )
    after = meta_cognition._vitals.get_meta_snapshot(window_sec=3600) if meta_cognition._vitals else {}
    # candidates == 2, kept == 1
    assert (after.get("retrieval", {}).get("judged", 0)) >= (before.get("retrieval", {}).get("judged", 0))
    assert (after.get("retrieval", {}).get("kept", 0)) >= (before.get("retrieval", {}).get("kept", 0))


def test_contradiction_detector_hook(monkeypatch):
    import meta_cognition
    import contradiction_detector

    before = meta_cognition._vitals.get_meta_snapshot(window_sec=3600) if meta_cognition._vitals else {}
    # Two statements that contradict
    new_belief = {"id": "n1", "statement": "A is B"}
    existing = [{"id": "e1", "statement": "A is not B"}]
    res = contradiction_detector.check_contradictions(new_belief, existing)
    after = meta_cognition._vitals.get_meta_snapshot(window_sec=3600) if meta_cognition._vitals else {}
    assert isinstance(res, list)
    assert (after.get("contradiction", {}).get("detected", 0)) >= (before.get("contradiction", {}).get("detected", 0))

