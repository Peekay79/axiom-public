from vector.unified_client import UnifiedVectorClient, VectorSearchRequest


class FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def test_adapter_path_search_mapping(monkeypatch):
    env = {
        "VECTOR_PATH": "adapter",
        "QDRANT_URL": "http://localhost:5001",
    }

    # Fake /health and /v1/search
    def fake_get(url, timeout):
        return FakeResp(200, {"status": "ok", "adapter_v1_shim": True})

    def fake_post(url, json, timeout):
        # Return two hits in adapter shape
        return FakeResp(200, {
            "hits": [
                {"payload": {"text": "alpha", "tags": ["x"]}, "score": 0.9},
                {"payload": {"content": "beta", "tags": ["y"]}, "score": 0.7},
            ]
        })

    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    client = UnifiedVectorClient(env)
    assert client.health() is True

    resp = client.search(VectorSearchRequest(query="hello", top_k=3))
    assert len(resp.hits) == 2
    assert resp.hits[0].content == "alpha"
    assert resp.hits[1].content == "beta"
    assert any("x" in h.tags or "y" in h.tags for h in resp.hits)


def test_adapter_circuit_breaker_opens(monkeypatch):
    env = {
        "VECTOR_PATH": "adapter",
        "QDRANT_URL": "http://localhost:5001",
    }

    # First 3 posts fail, 4th would succeed but circuit should open before
    calls = {"post": 0}

    def fake_get(url, timeout):
        return FakeResp(200, {"status": "ok", "adapter_v1_shim": True})

    def fake_post(url, json, timeout):
        calls["post"] += 1
        if calls["post"] <= 3:
            return FakeResp(503, {"error": "unavailable"})
        return FakeResp(200, {"hits": []})

    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    client = UnifiedVectorClient(env)

    # 3 failures trip breaker
    for _ in range(3):
        _ = client.search(VectorSearchRequest(query="hello", top_k=3))

    # Next call is blocked by circuit → empty hits
    resp = client.search(VectorSearchRequest(query="hello", top_k=3))
    assert resp.hits == []


def test_v1_memories_writes_disabled_default(monkeypatch):
    # Spin up Flask test client against the module
    import importlib
    mod = importlib.import_module("pods.vector.vector_adapter")
    app = getattr(mod, "app")
    tc = app.test_client()

    # Default should be disabled
    rv = tc.post("/v1/memories", json={"items": [{"content": "x"}]})
    assert rv.status_code == 403
    data = rv.get_json()
    assert "error" in data


def test_v1_memories_writes_enabled(monkeypatch):
    monkeypatch.setenv("ADAPTER_ENABLE_V1_WRITES", "true")
    import importlib
    mod = importlib.import_module("pods.vector.vector_adapter")
    app = getattr(mod, "app")
    tc = app.test_client()

    # Monkeypatch VectorAdapter.insert to avoid real work
    class FakeAdapter:
        def __init__(self):
            pass
        async def insert(self, class_name: str, data: dict) -> bool:
            return True

    monkeypatch.setattr(mod, "VectorAdapter", FakeAdapter)

    rv = tc.post("/v1/memories", json={"items": [{"content": "x"}, {"content": "y"}]})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get("inserted") == 2

