import os
import types
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def stub_adapter(monkeypatch, hits):
    class StubVA:
        def search_memory_vectors(self, query: str, top_k: int = 8):
            return hits

    monkeypatch.setitem(globals(), "_Stub", StubVA)
    import pods.vector.vector_adapter as va

    monkeypatch.setattr(va, "VectorAdapter", StubVA, raising=True)


def test_vector_recall_enabled_returns_hits(monkeypatch):
    os.environ["VECTOR_RECALL_ENABLED"] = "true"
    os.environ["HYBRID_RETRIEVAL_ENABLED"] = "false"
    from memory_response_pipeline import fetch_vector_hits_with_threshold

    # Provide a stub hit
    hits = [
        {
            "content": "foo",
            "_additional": {"certainty": 0.9, "vector": [0.0, 0.1]},
        }
    ]
    stub_adapter(monkeypatch, hits)

    out = run(fetch_vector_hits_with_threshold("foo", top_k=3, similarity_threshold=0.3))
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["content"] == "foo"


def test_vector_recall_fallback_empty_on_error(monkeypatch):
    os.environ["VECTOR_RECALL_ENABLED"] = "true"
    os.environ["VECTOR_RECALL_FALLBACK"] = "empty"
    from memory_response_pipeline import fetch_vector_hits_with_threshold

    class BadVA:
        def search_memory_vectors(self, query: str, top_k: int = 8):
            raise RuntimeError("boom")

    import pods.vector.vector_adapter as va

    monkeypatch.setattr(va, "VectorAdapter", BadVA, raising=True)

    out = run(fetch_vector_hits_with_threshold("foo", top_k=3, similarity_threshold=0.3))
    assert out == []
