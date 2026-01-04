import os
from typing import Dict, List

import memory_response_pipeline

from tests.utils.env import temp_env


def _mk_hit(id_: str, tags: List[str] | None = None, typ: str | None = None, confidence: float = 0.5):
    return {
        "id": id_,
        "tags": list(tags or []),
        "type": typ,
        "confidence": confidence,
        "_additional": {"score": 0.4},
    }


def test_cross_consolidation_disabled_returns_empty(monkeypatch):
    from retrieval_planner import get_cross_consolidations

    with temp_env({
        "AXIOM_CROSS_CONSOLIDATION_ENABLED": "0",
        "AXIOM_EPISODIC_ACTIVE": "1",
        "AXIOM_PROCEDURAL_ACTIVE": "1",
        "AXIOM_ABSTRACTION_ACTIVE": "1",
    }):
        res = get_cross_consolidations("any query")
        assert res == []


def test_cross_consolidation_enabled_merge_and_tags(monkeypatch):
    import retrieval_planner as rp

    # Fabricate per-source consolidations with an overlap id
    E = [_mk_hit("B1", tags=["episode"], typ="belief"), _mk_hit("X1", tags=["episode"], typ="belief")]
    P = [_mk_hit("B1", tags=["procedure"], typ="belief"), _mk_hit("P2", tags=["procedure"], typ="belief")]
    A = [_mk_hit("A3", tags=["abstracted", "abstraction_active"], typ="abstraction")]

    monkeypatch.setattr(rp, "get_episodic_consolidations", lambda q: E)
    monkeypatch.setattr(rp, "get_procedural_consolidations", lambda q: P)
    monkeypatch.setattr(rp, "get_abstraction_consolidations", lambda q: A)

    with temp_env({
        "AXIOM_CROSS_CONSOLIDATION_ENABLED": "1",
        "AXIOM_EPISODIC_ACTIVE": "1",
        "AXIOM_PROCEDURAL_ACTIVE": "1",
        "AXIOM_ABSTRACTION_ACTIVE": "1",
    }):
        merged = rp.get_cross_consolidations("foo")
        ids = {m["id"] for m in merged}
        assert ids == {"B1", "X1", "P2", "A3"}
        # B1 should carry both provenance tags
        b1 = [m for m in merged if m["id"] == "B1"][0]
        p = set(b1.get("provenance_tags") or [])
        assert p >= {"episodic_active", "procedural_active"}


def test_ranking_synergy_boost(monkeypatch):
    from ranking import rank_candidates

    # Build a belief present in both episodic and procedural
    b_multi = _mk_hit("B1", tags=["episodic_active", "procedural_active"], typ="belief", confidence=0.6)
    # Another belief with single provenance
    b_single = _mk_hit("B2", tags=["episodic_active"], typ="belief", confidence=0.6)
    # Ensure provenance_tags is honored
    b_multi["provenance_tags"] = ["episodic_active", "procedural_active"]
    b_single["provenance_tags"] = ["episodic_active"]

    with temp_env({"AXIOM_CROSS_CONSOLIDATION_BOOST": "0.2"}):
        ranked = rank_candidates(vector_hits=[], belief_hits=[b_multi, b_single], judger_scores={}, weights=None, confidence_only=False)
        # The multi-supported belief should get a higher final score due to synergy boost
        assert ranked[0]["id"] == "B1"
        assert float(ranked[0].get("_cross_consolidation_boost", 0.0)) == 0.2


def test_pipeline_passes_cross_consolidations_to_judger_and_vitals(monkeypatch):
    import types

    # Stub graph enable
    env = {
        "AXIOM_BELIEF_GRAPH_ENABLED": "1",
        "AXIOM_CROSS_CONSOLIDATION_ENABLED": "1",
        "AXIOM_EPISODIC_ACTIVE": "1",
        "AXIOM_PROCEDURAL_ACTIVE": "1",
        "AXIOM_ABSTRACTION_ACTIVE": "1",
        "AXIOM_SEMANTIC_EXPANSION_ENABLED": "0",
        "AXIOM_JUDGER_ENABLED": "0",  # simplify
    }

    # Stub vector hits
    async def _fake_fetch(q: str, top_k: int = 8):
        return [{"id": "V1", "content": "foo", "_additional": {"vector": [0.1, 0.2, 0.3]}, "_similarity": 0.4}]

    # Stub embeddings
    class _FakeEmbed:
        def encode(self, text, normalize_embeddings=True):
            return [0.1, 0.1, 0.1]

    # Cross consolidation stubs
    def _fake_eps(q: str):
        return [_mk_hit("B1", tags=["episodic_active"], typ="belief")]

    def _fake_proc(q: str):
        return [_mk_hit("B1", tags=["procedural_active"], typ="belief")]

    def _fake_abs(q: str):
        return []

    import retrieval_planner as rp

    with temp_env(env):
        monkeypatch.setattr("memory_response_pipeline._EMBEDDER", _FakeEmbed())
        monkeypatch.setattr("memory_response_pipeline.fetch_vector_hits", _fake_fetch)
        monkeypatch.setattr("memory_response_pipeline.fetch_vector_hits_with_threshold", _fake_fetch, raising=False)
        monkeypatch.setattr(rp, "get_episodic_consolidations", _fake_eps)
        monkeypatch.setattr(rp, "get_procedural_consolidations", _fake_proc)
        monkeypatch.setattr(rp, "get_abstraction_consolidations", _fake_abs)
        # Compose cross consolidation via real function
        # Run the pipeline (judger is off, so we validate no exceptions and response present)
        import asyncio

        async def _run():
            res = await memory_response_pipeline.generate_enhanced_context_response("test cross consolidate", memory_ids=None, enable_validation=False)
            assert isinstance(res, dict)
            assert "response" in res
            # Cognitive vitals should have recorded cross consolidation hits
            from cognitive_vitals import vitals
            snap = vitals.snapshot()
            cc = snap.get("cross_consolidation", {})
            assert int(cc.get("hits_used_total", 0)) >= 1

        asyncio.get_event_loop().run_until_complete(_run())


def test_judger_receives_cross_consolidation_context(monkeypatch, caplog):
    import judger

    # Prepare minimal candidates with provenance tags
    vecs: List[Dict] = []
    beliefs: List[Dict] = [
        {"id": "B1", "gist": "...", "tags": ["belief"], "provenance_tags": ["episodic_active", "procedural_active"]}
    ]
    contras: List[Dict] = []

    class _MC:
        async def __call__(self, *a, **k):
            return [{"response": '{"vector_hits": [], "belief_hits": [], "contradictions": []}'}]

    # Patch LLM call to avoid network
    import types
    from types import SimpleNamespace
    monkeypatch.setitem(__import__("sys").modules, "llm_connector", type("X", (), {"safe_multiquery_context_pipeline": _MC()})())

    with temp_env({"AXIOM_JUDGER_ENABLED": "1"}):
        caplog.set_level("INFO")
        import asyncio

        async def _run():
            res = await judger.judge_phase4("q", vecs, beliefs, contras, target_n=5)
            assert isinstance(res, dict)

        asyncio.get_event_loop().run_until_complete(_run())
        # Verify log contains CrossConsolidation passed count
        assert any("[RECALL][Judger][CrossConsolidation]" in rec.message for rec in caplog.records)

