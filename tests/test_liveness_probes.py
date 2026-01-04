import os
import asyncio

import memory_response_pipeline


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_probe_recall_emits(monkeypatch):
    async def stub_fetch(q, top_k):
        return [{"content": "hit"}]

    monkeypatch.setattr(memory_response_pipeline, "fetch_vector_hits", stub_fetch, raising=True)

    from liveness.probes import probe_recall
    res = run(probe_recall(5))
    assert res["ok"] in (True, False)
    assert 0.0 <= res["recall"] <= 1.0


def test_probe_belief_patch_handles_errors(monkeypatch):
    async def stub_client(*args, **kwargs):  # never used; ensure no raise
        return None

    from liveness.probes import probe_belief_patch
    res = run(probe_belief_patch("nonexistent"))
    assert "ok" in res and "status" in res
