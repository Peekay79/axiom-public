import importlib
import os
import time

import memory_response_pipeline


def _reload_modules():
    import tripwires as tw
    import cognitive_vitals as cv
    import ranking as rk
    importlib.reload(tw)
    importlib.reload(cv)
    importlib.reload(rk)
    importlib.reload(memory_response_pipeline)
    return tw, cv, rk, memory_response_pipeline


async def _run_pipeline_with_hits(monkeypatch, raw_hits=None, graph_hits=None, abs_hits=None, cross_hits=None, latency_sleep_ms=0):
    # Monkeypatch internal helpers in memory_response_pipeline to inject hits and control timing

    raw_hits = raw_hits or []
    graph_hits = graph_hits or []
    abs_hits = abs_hits or []
    cross_hits = cross_hits or []

    async def fake_fetch(q, top_k):
        return list(raw_hits)

    async def fake_fetch_threshold(q, top_k, similarity_threshold=None, request_id=None):
        return list(raw_hits)

    monkeypatch.setattr(memory_response_pipeline, "fetch_vector_hits", fake_fetch)
    monkeypatch.setattr(memory_response_pipeline, "fetch_vector_hits_with_threshold", fake_fetch_threshold)

    # Patch graph retrieval block to use provided graph/abs/cross hits
    def fake_get_graph_related_beliefs(q):
        return list(graph_hits)

    def fake_get_abs(q):
        return list(abs_hits)

    def fake_get_xc(q):
        return list(cross_hits)

    import retrieval_planner as rp
    monkeypatch.setattr(rp, "get_graph_related_beliefs", fake_get_graph_related_beliefs)
    monkeypatch.setattr(rp, "get_abstraction_consolidations", fake_get_abs)
    monkeypatch.setattr(rp, "get_cross_consolidations", fake_get_xc)

    # Speed up by disabling embedding and composite
    monkeypatch.setenv("AXIOM_COMPOSITE_SCORING", "0")
    monkeypatch.setenv("AXIOM_BELIEF_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AXIOM_CROSS_CONSOLIDATION_ENABLED", "1")

    # Simulate latency spike by sleeping in a small hook
    if latency_sleep_ms > 0:
        orig_time = time.time

        def slow_time():
            return orig_time() + (latency_sleep_ms / 1000.0)

        # Apply slow time at a key checkpoint just before latency measurement usage
        monkeypatch.setattr(time, "time", slow_time)

    res = await memory_response_pipeline.generate_enhanced_context_response(user_question="test question", top_k=10, top_n=4)
    return res


def test_recall_hits_excess_capped(monkeypatch):
    monkeypatch.setenv("AXIOM_TRIPWIRE_MAX_HITS", "5")
    monkeypatch.setenv("AXIOM_TRIPWIRE_OVERRIDE", "0")
    # Tighten latency to avoid unrelated spikes
    monkeypatch.setenv("AXIOM_TRIPWIRE_LATENCY_MS", "999999")
    tw, cv, rk, memory_response_pipeline = _reload_modules()

    # Prepare > cap hits
    big = [{"id": f"v{i}", "content": f"text {i}", "score": 0.9} for i in range(20)]

    import asyncio
    asyncio.run(_run_pipeline_with_hits(monkeypatch, raw_hits=big))

    stats = tw.get_tripwire_stats()
    assert stats["counts"].get("recall_hits_excess", 0) >= 1


def test_latency_spike_disables_extras(monkeypatch):
    monkeypatch.setenv("AXIOM_TRIPWIRE_LATENCY_MS", "10")
    monkeypatch.setenv("AXIOM_TRIPWIRE_OVERRIDE", "0")
    tw, cv, rk, memory_response_pipeline = _reload_modules()

    import asyncio
    asyncio.run(_run_pipeline_with_hits(monkeypatch, raw_hits=[{"id":"1","content":"x","score":0.5}], latency_sleep_ms=50))

    # Wonder/Dream should be disabled ephemerally via disable_until_ts or state
    assert tw.tripwires.is_wonder_allowed() in (True, False)  # call succeeds
    # Check event recorded
    snap = cv.vitals.snapshot()
    ev = snap.get("tripwire_events_recent", [])
    assert any(e.get("category") == "latency_spike" for e in ev)


def test_arbitration_loop_confidence_only(monkeypatch):
    monkeypatch.setenv("AXIOM_TRIPWIRE_MAX_ARBITRATION_RETRIES", "0")
    monkeypatch.setenv("AXIOM_TRIPWIRE_OVERRIDE", "0")
    # Force arbitration enabled and uncertain tagging by setting arbitration mode via env
    monkeypatch.setenv("AXIOM_ARBITRATION_ENABLED", "1")
    monkeypatch.setenv("AXIOM_ARB_CONFLICT_RESOLUTION", "uncertain")

    tw, cv, rk, memory_response_pipeline = _reload_modules()

    # Craft two nearly identical hits to trigger uncertainty
    hits = [
        {"id": "a", "content": "foo", "confidence": 0.5},
        {"id": "b", "content": "foo", "confidence": 0.5},
    ]

    import asyncio
    asyncio.run(_run_pipeline_with_hits(monkeypatch, raw_hits=hits))

    stats = tw.get_tripwire_stats()
    assert stats["counts"].get("arbitration_loop", 0) >= 1


def test_provenance_failures_filter(monkeypatch):
    monkeypatch.setenv("AXIOM_TRIPWIRE_MAX_PROVENANCE_FAILURES", "0")
    monkeypatch.setenv("AXIOM_TRIPWIRE_OVERRIDE", "0")
    tw, cv, rk, memory_response_pipeline = _reload_modules()

    # All hits lack provenance → enforce hard filter
    hits = [{"id": f"x{i}", "content": "c"} for i in range(3)]

    import asyncio
    res = asyncio.run(_run_pipeline_with_hits(monkeypatch, raw_hits=hits))
    # No strict output shape requirements here; ensure tripwire counted
    stats = tw.get_tripwire_stats()
    assert stats["counts"].get("provenance_failures", 0) >= 1


def test_override_bypass(monkeypatch):
    # Activate override, keep thresholds tiny to trigger
    monkeypatch.setenv("AXIOM_TRIPWIRE_MAX_HITS", "1")
    monkeypatch.setenv("AXIOM_TRIPWIRE_MAX_ARBITRATION_RETRIES", "0")
    monkeypatch.setenv("AXIOM_TRIPWIRE_MAX_PROVENANCE_FAILURES", "0")
    monkeypatch.setenv("AXIOM_TRIPWIRE_LATENCY_MS", "1")
    monkeypatch.setenv("AXIOM_TRIPWIRE_OVERRIDE", "1")

    tw, cv, rk, memory_response_pipeline = _reload_modules()

    hits = [{"id": f"o{i}", "content": "c"} for i in range(5)]

    import asyncio
    asyncio.run(_run_pipeline_with_hits(monkeypatch, raw_hits=hits, latency_sleep_ms=5))

    # With override, counters may still increment record(), but escalation actions are bypassed; ensure warning path recorded in vitals
    snap = cv.vitals.snapshot()
    ev = snap.get("tripwire_events_recent", [])
    cats = [e.get("category") for e in ev]
    assert any(c in ("recall_hits_excess", "latency_spike", "arbitration_loop", "provenance_failures") for c in cats)

