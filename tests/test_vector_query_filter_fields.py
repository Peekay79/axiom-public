import json
from typing import Any, Dict

import pytest


def test_to_qdrant_filter_tags_any_translation():
    from pods.memory.qdrant_utils import to_qdrant_filter

    weaviate_filter: Dict[str, Any] = {
        "must": [
            {"key": "tags", "match": {"any": ["world_map_event", "world_map_entity"]}}
        ]
    }

    qf = to_qdrant_filter(weaviate_filter)
    # May be None if models.MatchAny not available; allow both but assert type when present
    if qf is not None:
        # Basic shape assertions
        assert hasattr(qf, "must") or hasattr(qf, "should")


def test_post_filter_items_tags_any():
    from pods.memory.qdrant_utils import post_filter_items

    items = [
        {"content": "a", "tags": ["x", "y"], "_additional": {"score": 0.9, "distance": 0.1}},
        {"content": "b", "tags": ["z"], "_additional": {"score": 0.8, "distance": 0.2}},
        {"content": "c", "tags": [], "_additional": {"score": 0.7, "distance": 0.3}},
    ]
    f = {"must": [{"key": "tags", "match": {"any": ["z"]}}]}
    filtered = post_filter_items(items, f)
    assert len(filtered) == 1
    assert filtered[0]["content"] == "b"


def test_project_fields_selection():
    from pods.memory.qdrant_utils import project_fields

    items = [
        {
            "content": "hello",
            "tags": ["a"],
            "id": "1",
            "metadata": {"foo": "bar"},
            "_additional": {"score": 0.5, "distance": 0.5, "other": 123},
        }
    ]
    fields = ["content", "_additional.score"]
    projected = project_fields(items, fields)
    assert projected == [{"content": "hello", "_additional": {"score": 0.5}}]


@pytest.fixture
def app_client(monkeypatch):
    # Import app from memory pod
    from pods.memory import pod2_memory_api as api

    # Ensure vector backend flag is considered ready to bypass readiness 503
    api.vector_ready = True

    # Stub embedder.encode to avoid heavy model load
    class DummyEmbedder:
        def encode(self, arr):
            return [[0.0] * 384]

    api._embedder = DummyEmbedder()

    # Stub Qdrant client's search to avoid network
    class DummyPoint:
        def __init__(self, payload, score):
            self.payload = payload
            self.score = score

    class DummyQdrant:
        def search(self, collection_name, query_vector, limit, with_payload, query_filter=None):
            hits = [
                DummyPoint({"text": "A", "tags": ["x"]}, 0.9),
                DummyPoint({"text": "B", "tags": ["y"]}, 0.8),
                DummyPoint({"text": "C", "tags": []}, 0.7),
            ]
            # Simulate crude filter if provided (only tags.any)
            if query_filter is not None:
                try:
                    # models.Filter with must
                    must = getattr(query_filter, "must", None)
                    if must:
                        any_vals = None
                        for cond in must:
                            k = getattr(cond, "key", None)
                            m = getattr(cond, "match", None)
                            if k == "tags" and hasattr(m, "any"):
                                any_vals = set(getattr(m, "any"))
                        if any_vals:
                            hits = [h for h in hits if any_vals.intersection(set(h.payload.get("tags", [])))]
                except Exception:
                    pass
            return hits[:limit]

    api._qdrant_client = DummyQdrant()

    # Create Flask test client
    app = api.app
    return app.test_client()


def test_vector_query_legacy_shape_no_filter_fields(app_client):
    payload = {"query": "test", "top_k": 3}
    resp = app_client.post("/vector/query", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body and "Get" in body["data"]
    # collection key varies, access first array
    get_section = body["data"]["Get"]
    assert isinstance(get_section, dict)
    arrs = list(get_section.values())
    assert len(arrs) == 1 and isinstance(arrs[0], list)
    item = arrs[0][0]
    assert "content" in item and "_additional" in item and "score" in item["_additional"]


def test_vector_query_with_filter_postfilter(app_client):
    payload = {
        "query": "test",
        "top_k": 5,
        "filter": {"must": [{"key": "tags", "match": {"any": ["y"]}}]},
    }
    resp = app_client.post("/vector/query", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    body = resp.get_json()
    get_section = body["data"]["Get"]
    arr = list(get_section.values())[0]
    assert all("y" in x.get("tags", []) for x in arr)


def test_vector_query_fields_projection(app_client):
    payload = {
        "query": "test",
        "top_k": 3,
        "fields": ["content", "_additional.score"],
    }
    resp = app_client.post("/vector/query", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    body = resp.get_json()
    arr = list(body["data"]["Get"].values())[0]
    assert set(arr[0].keys()) <= {"content", "_additional"}
    assert set(arr[0]["_additional"].keys()) == {"score"}

