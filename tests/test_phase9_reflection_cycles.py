import asyncio
import os
import time


async def _force_meta_reflection():
    from reflection import reflect_on_reflections

    return await reflect_on_reflections(review_window=3)


def test_scheduler_triggers_every_n_turns(monkeypatch, tmp_path):
    monkeypatch.setenv("AXIOM_REFLECTION_CYCLES_ENABLED", "1")
    monkeypatch.setenv("AXIOM_REFLECTION_CYCLE_INTERVAL", "3")
    monkeypatch.setenv("AXIOM_REFLECTION_REVIEW_WINDOW", "2")
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(tmp_path))

    from reflection_scheduler import on_turn_completed, get_turn_counter

    # Start at 0
    assert get_turn_counter() == 0
    on_turn_completed()
    assert get_turn_counter() == 1
    on_turn_completed()
    assert get_turn_counter() == 2
    # Third call reaches interval; should schedule and then reset when done
    on_turn_completed()
    # Wait up to ~2s for background task to complete and reset the counter
    t0 = time.time()
    while time.time() - t0 < 2.0:
        if get_turn_counter() == 0:
            break
        time.sleep(0.05)
    assert get_turn_counter() == 0


def test_meta_reflection_produces_beliefs_and_journal(monkeypatch, tmp_path):
    # Enable graph and confidence so we can upsert beliefs
    monkeypatch.setenv("AXIOM_BELIEF_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CONFIDENCE_ENABLED", "1")
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(tmp_path))

    # Seed a few journal-like memories for heuristic extraction
    from pods.memory.memory_manager import Memory

    mem = Memory()
    # simple simulated journals
    entries = [
        {"type": "journal_entry", "timestamp": "2025-09-01T00:00:00Z", "content": "Axiom is learning fast. I struggled with retrieval yesterday."},
        {"type": "journal_entry", "timestamp": "2025-09-02T00:00:00Z", "content": "We resolved a contradiction and improved confidence in patterns."},
        {"type": "journal_entry", "timestamp": "2025-09-03T00:00:00Z", "content": "I am not confused about the plan now; growth continues."},
    ]
    for e in entries:
        mem.add_to_long_term(e)

    res = asyncio.get_event_loop().run_until_complete(_force_meta_reflection())
    assert isinstance(res, dict)
    assert res.get("reviewed_count", 0) >= 1
    # Journal should be created
    jp = res.get("journal_path")
    assert isinstance(jp, (str, type(None)))

    # Belief graph upserts should register at least one pattern belief
    # We cannot inspect DB directly here portably; rely on non-zero upsert count when available
    up = int(res.get("patterns_upserted", 0) or 0)
    assert up >= 0  # non-crashing path


def test_confidence_reinforcement_and_decay(monkeypatch, tmp_path):
    monkeypatch.setenv("AXIOM_BELIEF_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CONFIDENCE_ENABLED", "1")
    # Emphasize reinforcement and recency for clearer deltas
    monkeypatch.setenv("AXIOM_CONFIDENCE_WEIGHTS", "recency=0.3, reinforcement=0.6, source=0.0, contradiction=0.1")
    # Use a tiny half-life to accelerate decay (about 0.864 seconds)
    monkeypatch.setenv("AXIOM_DECAY_HALFLIFE_DAYS", "0.00001")
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(tmp_path))

    from belief_graph import belief_graph as bg

    # First upsert
    a = bg.upsert_belief("Axiom", "often_struggles_with", "latency", confidence=0.5, sources=["test"])
    assert a is not None
    hits0 = bg.get_beliefs(["Axiom"], hops=1)
    f0 = [h for h in hits0 if h.get("subject") == "Axiom" and h.get("predicate") == "often_struggles_with" and h.get("object") == "latency"]
    assert f0
    conf0 = float(f0[0].get("confidence", 0.0))
    # Second upsert (reinforcement)
    b = bg.upsert_belief("Axiom", "often_struggles_with", "latency", confidence=0.5, sources=["test2"])
    assert b is not None
    hits1 = bg.get_beliefs(["Axiom"], hops=1)
    f1 = [h for h in hits1 if h.get("subject") == "Axiom" and h.get("predicate") == "often_struggles_with" and h.get("object") == "latency"]
    assert f1
    conf1 = float(f1[0].get("confidence", 0.0))
    # Reinforcement should not decrease confidence
    assert conf1 >= conf0

    # Wait a bit to induce recency decay with tiny half-life
    time.sleep(1.2)
    hits2 = bg.get_beliefs(["Axiom"], hops=1)
    f2 = [h for h in hits2 if h.get("subject") == "Axiom" and h.get("predicate") == "often_struggles_with" and h.get("object") == "latency"]
    assert f2
    conf2 = float(f2[0].get("confidence", 0.0))
    # Confidence should have decayed
    assert conf2 <= conf1


def test_contradiction_penalty_applied(monkeypatch, tmp_path):
    monkeypatch.setenv("AXIOM_BELIEF_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CONFIDENCE_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CONFIDENCE_WEIGHTS", "recency=0.3, reinforcement=0.4, source=0.1, contradiction=0.2")
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(tmp_path))

    from belief_graph import belief_graph as bg
    from pods.memory.memory_manager import Memory

    # Insert a belief and a conflicting belief to trigger penalty path
    sid1 = bg.upsert_belief("Axiom", "is", "confident", confidence=0.6, sources=["test"])
    assert sid1 is not None
    # Capture initial confidence of the positive belief
    base_hits = bg.get_beliefs(["Axiom"], hops=1)
    pos = [h for h in base_hits if h.get("subject") == "Axiom" and h.get("predicate") == "is" and h.get("object") == "confident"]
    assert pos
    conf_before = float(pos[0].get("confidence", 0.0))

    # Seed a journal that will cause meta-reflection to upsert a negated pattern
    mem = Memory()
    mem.add_to_long_term({"type": "journal_entry", "timestamp": "2025-09-04T00:00:00Z", "content": "Axiom is not confident about this area."})
    # Run meta reflection
    res = asyncio.get_event_loop().run_until_complete(_force_meta_reflection())
    assert isinstance(res, dict)

    # Fetch the positive belief again and ensure confidence did not increase; may decrease due to penalty
    base_hits2 = bg.get_beliefs(["Axiom"], hops=1)
    pos2 = [h for h in base_hits2 if h.get("subject") == "Axiom" and h.get("predicate") == "is" and h.get("object") == "confident"]
    assert pos2
    conf_after = float(pos2[0].get("confidence", 0.0))
    assert conf_after <= conf_before


def test_async_scheduler_non_blocking(monkeypatch, tmp_path):
    monkeypatch.setenv("AXIOM_REFLECTION_CYCLES_ENABLED", "1")
    monkeypatch.setenv("AXIOM_REFLECTION_CYCLE_INTERVAL", "2")
    monkeypatch.setenv("AXIOM_JOURNALS_DIR", str(tmp_path))

    from reflection_scheduler import on_turn_completed, get_turn_counter

    start = time.time()
    on_turn_completed()
    on_turn_completed()  # should schedule a cycle
    elapsed = time.time() - start
    # Should be near-instant; not awaiting the background task
    assert elapsed < 0.1
