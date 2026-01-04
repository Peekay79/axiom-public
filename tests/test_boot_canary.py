import os
import json
import asyncio
from pathlib import Path

import memory_response_pipeline


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_boot_canary_runs_and_reports(tmp_path, monkeypatch):
    # Prepare a tiny dataset
    ds = tmp_path / "canaries.jsonl"
    ds.write_text(json.dumps({"query": "hello"}) + "\n")

    # Stub retrieval to return 1 hit
    async def stub_fetch(q, top_k):
        return [{"content": "hit"}]

    monkeypatch.setattr(memory_response_pipeline, "fetch_vector_hits", stub_fetch, raising=True)

    from retrieval.boot_canary import run_boot_canary
    r = run(run_boot_canary(str(ds), 3))
    assert 0.0 <= r <= 1.0
