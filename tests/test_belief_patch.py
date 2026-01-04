import json
from types import SimpleNamespace


class StubPoint:
    def __init__(self, pid, payload):
        self.id = pid
        self.payload = payload
        self.vector = [0.0] * 384


class StubClient:
    def __init__(self, payloads):
        self._payloads = payloads
        self.client = SimpleNamespace(
            retrieve=lambda collection_name, ids, with_payload, with_vectors: [
                StubPoint(ids[0], self._payloads.get(ids[0], {}))
            ]
        )

    def get_memory_by_id(self, collection, belief_id, include_vector=False):
        p = self._payloads.get(belief_id)
        if p is None:
            return None
        return SimpleNamespace(id=belief_id, payload=p, vector=[0.0] * 384)

    def upsert_memory(self, collection_name, memory_id, vector, payload):
        self._payloads[memory_id] = payload
        return True


def test_belief_patch_ok(monkeypatch):
    # Arrange stubbed Qdrant via belief_registry_api.get_qdrant_client
    payloads = {
        "b1": {"statement": "x", "confidence": 0.5, "updated_at": "etag1"}
    }
    from belief_registry_api import app, get_qdrant_client

    monkeypatch.setattr(
        __import__("belief_registry_api"), "get_qdrant_client", lambda: StubClient(payloads), raising=False
    )

    from fastapi.testclient import TestClient

    c = TestClient(app)
    r = c.patch(
        "/beliefs/b1",
        headers={"If-Match": "etag1"},
        json={"confidence": 0.7},
    )
    assert r.status_code == 200
    assert payloads["b1"]["confidence"] == 0.7


def test_belief_patch_etag_mismatch(monkeypatch):
    payloads = {
        "b2": {"statement": "x", "confidence": 0.5, "updated_at": "etagZ"}
    }
    from belief_registry_api import app
    monkeypatch.setattr(
        __import__("belief_registry_api"), "get_qdrant_client", lambda: StubClient(payloads), raising=False
    )
    from fastapi.testclient import TestClient

    c = TestClient(app)
    r = c.patch(
        "/beliefs/b2",
        headers={"If-Match": "etag1"},
        json={"confidence": 0.6},
    )
    assert r.status_code == 409
