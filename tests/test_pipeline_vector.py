from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_pipeline_vector_disabled_logs_and_safe_defaults(monkeypatch, caplog):
    # Disable vector recall and assert canonical tag appears and empty result
    monkeypatch.setenv("VECTOR_RECALL_ENABLED", "false")
    from memory_response_pipeline import fetch_vector_hits

    with caplog.at_level(logging.INFO):
        out = _run(fetch_vector_hits("hello", top_k=3))
    assert out == []
    assert any("[RECALL][Vector]" in r.getMessage() for r in caplog.records)


def test_pipeline_vector_enabled_returns_hits(monkeypatch):
    # Enable and stub adapter to return one hit
    monkeypatch.setenv("VECTOR_RECALL_ENABLED", "true")

    class StubVA:
        def search_memory_vectors(self, query: str, top_k: int = 8, request_id=None):
            return [
                {"content": "alpha", "_additional": {"certainty": 0.91, "vector": [0.0, 0.1]}},
            ]

    import pods.vector.vector_adapter as va
    monkeypatch.setattr(va, "VectorAdapter", StubVA, raising=True)

    from memory_response_pipeline import fetch_vector_hits

    out = _run(fetch_vector_hits("hello", top_k=3))
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0].get("content") == "alpha"

