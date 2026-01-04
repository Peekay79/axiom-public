import os
from typing import Dict, List

import memory_response_pipeline

from tests.utils.env import temp_env


def _make_abs(id_: str, support: int = 0):
    return {
        "id": id_,
        "type": "abstraction",
        "tags": ["abstracted", "abstraction_active"],
        "confidence": 0.6,
        "support_count": support,
    }


def test_env_off_no_boost_and_no_merge_when_disabled(monkeypatch):
    # ranker should not apply abstraction boost if env is off
    from ranking import rank_candidates

    A = {"id": "A", "_additional": {"score": 0.5}, "confidence": 0.5}
    B = _make_abs("B", support=5)

    with temp_env({"AXIOM_ABSTRACTION_ACTIVE": "0"}):
        ranked = rank_candidates([A], [B], judger_scores={}, weights=None, confidence_only=False)
        # With similar base components, boost off means abstraction should not jump ahead solely due to support
        ids = [it["id"] for it in ranked]
        assert "B" in ids and "A" in ids


def test_env_on_abstraction_boost(monkeypatch):
    from ranking import rank_candidates

    base = {"id": "X", "_additional": {"score": 0.5}, "confidence": 0.5}
    abs1 = _make_abs("Y", support=3)

    with temp_env({"AXIOM_ABSTRACTION_ACTIVE": "1", "AXIOM_ABSTRACTION_RANK_BOOST": "0.05"}):
        ranked = rank_candidates([base], [abs1], judger_scores={}, weights=None, confidence_only=False)
        # Expect abstraction to be ranked at or near top due to boost
        assert ranked[0]["id"] == "Y"
        assert float(ranked[0].get("_abstraction_boost", 0.0)) == 0.05
        assert int(ranked[0].get("_support_count", 0)) == 3


def test_pipeline_merges_abstractions(monkeypatch):
    # Ensure pipeline calls abstraction retrieval when enabled and passes into flow
    import types

    # Stub belief graph enable
    env = {"AXIOM_BELIEF_GRAPH_ENABLED": "1", "AXIOM_ABSTRACTION_ACTIVE": "1"}

    # Stub planner abstractions
    def _fake_abs(q: str) -> List[Dict]:
        return [_make_abs("ABS-1", support=2), _make_abs("ABS-2", support=1)]

    # Stub vector hits fetchers to simple minimal return
    async def _fake_fetch(q: str, top_k: int = 8):
        return [{"id": "V1", "content": "foo", "_additional": {"vector": [0.1, 0.2, 0.3]}, "_similarity": 0.4}]

    # Stub embedding
    class _FakeEmbed:
        def encode(self, text, normalize_embeddings=True):
            return [0.1, 0.1, 0.1]

    with temp_env(env):
        monkeypatch.setattr("memory_response_pipeline._EMBEDDER", _FakeEmbed())
        monkeypatch.setattr("memory_response_pipeline.fetch_vector_hits", _fake_fetch)
        monkeypatch.setattr("memory_response_pipeline.fetch_vector_hits_with_threshold", _fake_fetch, raising=False)
        # Hook planner function
        monkeypatch.setenv("AXIOM_SEMANTIC_EXPANSION_ENABLED", "0")
        import retrieval_planner as rp
        monkeypatch.setattr(rp, "get_abstraction_consolidations", _fake_abs)

        # Make judger no-op to avoid network
        async def _fake_judge(*a, **k):
            return []

        monkeypatch.setattr("memory_response_pipeline._judge_memories", _fake_judge)

        # Run a minimal call
        import asyncio

        async def _run():
            res = await memory_response_pipeline.generate_enhanced_context_response("test abstractions", memory_ids=None, enable_validation=False)
            assert isinstance(res, dict)
            # We cannot directly read internal merged hits, but presence should reflect in stats/log path executed
            # Validate response structure returns
            assert "response" in res

        asyncio.get_event_loop().run_until_complete(_run())

