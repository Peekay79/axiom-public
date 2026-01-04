from __future__ import annotations

import logging
from typing import Any, Dict, List

from vector.unified_client import UnifiedVectorClient, VectorSearchRequest


class _Resp:
    def __init__(self, status_code: int = 200, json_data: Dict[str, Any] | None = None):
        self.status_code = status_code
        self._json = dict(json_data or {})

    def raise_for_status(self):
        if int(self.status_code) >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Dict[str, Any]:
        return dict(self._json)


def test_env_resolution_modes():
    # USE_QDRANT_BACKEND forces qdrant
    client = UnifiedVectorClient({"USE_QDRANT_BACKEND": "true"})
    cfg = client.get_debug_config()
    assert cfg.get("mode") == "qdrant"

    # VECTOR_PATH=adapter with QDRANT_URL selects adapter
    client2 = UnifiedVectorClient({"VECTOR_PATH": "adapter", "QDRANT_URL": "http://localhost:9999"})
    cfg2 = client2.get_debug_config()
    assert cfg2.get("mode") == "adapter"


def test_adapter_round_trip_insert_and_search(monkeypatch):
    # In-memory store for adapter stubs
    store: List[Dict[str, Any]] = []

    def fake_get(url: str, timeout: float | int = 5, headers: Dict[str, str] | None = None):
        if url.endswith("/health"):
            return _Resp(200, {"status": "ok"})
        return _Resp(404, {"error": "not found"})

    def fake_post(url: str, json: Dict[str, Any] | None = None, timeout: float | int = 5, headers: Dict[str, str] | None = None):
        payload = dict(json or {})
        if url.endswith("/v1/memories"):
            items = list(payload.get("items", []))
            # Persist a simplified shape for recall stub
            for it in items:
                store.append({
                    "content": (it.get("content") or ""),
                    "tags": list((it.get("metadata", {}) or {}).get("tags", [])),
                })
            return _Resp(200, {"inserted": len(items)})
        if url.endswith("/v1/search"):
            hits = []
            for it in store:
                hits.append({
                    "payload": {"text": it.get("content", ""), "tags": list(it.get("tags", []))},
                    "score": 0.99,
                })
            return _Resp(200, {"hits": hits})
        return _Resp(404, {"error": "not found"})

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    env = {"VECTOR_PATH": "adapter", "QDRANT_URL": "http://adapter.local:5001"}
    client = UnifiedVectorClient(env)
    assert client.health() is True

    to_insert = [
        {"content": "alpha", "metadata": {"tags": ["x"]}},
        {"content": "beta", "metadata": {"tags": ["y"]}},
    ]
    res = client.insert(to_insert)
    assert int(res.get("inserted", 0)) == 2

    resp = client.search(VectorSearchRequest(query="hello", top_k=5))
    assert len(resp.hits) == 2
    assert {h.content for h in resp.hits} == {"alpha", "beta"}

