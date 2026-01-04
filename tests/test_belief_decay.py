import os


def test_belief_recompute_qdrant_path(monkeypatch):
    os.environ["BELIEF_RECOMPUTE_ENABLED"] = "true"
    os.environ["BELIEF_STORAGE_MODE"] = "qdrant"

    class StubClient:
        def __init__(self):
            self.client = self
            self._points = [
                type("P", (), {"id": "b1", "payload": {"statement": "x", "confidence": 0.5}, "vector": [0.0] * 384})
            ]

        def scroll(self, collection_name, limit, with_payload, with_vectors, offset=None):
            return (list(self._points), None)

        def upsert_memory(self, collection_name, memory_id, vector, payload):
            return True

    monkeypatch.setattr(__import__("axiom_qdrant_client"), "QdrantClient", lambda: StubClient(), raising=False)

    from beliefs.recompute import run_recompute

    res = run_recompute(batch_size=10)
    assert res["status"] in ("ok", "error")
    # Presence of backend field
    assert "backend" in res
