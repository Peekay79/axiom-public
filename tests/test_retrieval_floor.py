#!/usr/bin/env python3
import json
import pytest


flask = pytest.importorskip("flask")


class DummyHit:
    def __init__(self, score):
        self.score = score
        self.content = "x"
        self.tags = []


class DummyResp:
    def __init__(self, scores):
        self.hits = [types.SimpleNamespace(score=s) for s in scores]


def _monkey_vector(monkeypatch, scores):
    from vector import unified_client as uvc

    class _Dummy:
        def search(self, req, request_id=None):
            class R:
                def __init__(self, scores):
                    self.hits = [type("H", (), {"score": s, "content": "", "tags": []}) for s in scores]
            return R(scores)

    monkeypatch.setattr(uvc, "UnifiedVectorClient", lambda env: _Dummy())


def test_ok_header(monkeypatch):
    from pods.memory import pod2_memory_api as mod
    monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    _monkey_vector(monkeypatch, [0.80, 0.6, 0.5, 0.4, 0.3])
    app = mod.app
    client = app.test_client()
    r = client.post("/vector/query", data=json.dumps({"question": "q", "k": 5}), content_type="application/json")
    assert r.status_code == 200
    assert r.headers.get("X-Axiom-Retrieval") == "ok"


def test_thin_header(monkeypatch):
    from pods.memory import pod2_memory_api as mod
    monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    _monkey_vector(monkeypatch, [0.60, 0.55])  # 2 hits (<3) => thin
    app = mod.app
    client = app.test_client()
    r = client.post("/vector/query", data=json.dumps({"question": "q", "k": 2}), content_type="application/json")
    assert r.status_code == 200
    assert r.headers.get("X-Axiom-Retrieval") == "thin"


def test_none_header(monkeypatch):
    from pods.memory import pod2_memory_api as mod
    monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    _monkey_vector(monkeypatch, [])
    app = mod.app
    client = app.test_client()
    r = client.post("/vector/query", data=json.dumps({"question": "q", "k": 1}), content_type="application/json")
    assert r.status_code == 200
    assert r.headers.get("X-Axiom-Retrieval") == "none"


def test_missing_scores_treated_as_zero(monkeypatch):
    from pods.memory import pod2_memory_api as mod
    monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    # Return hits with score None via dict shape
    from vector import unified_client as uvc

    class _Dummy:
        def search(self, req, request_id=None):
            class R:
                def __init__(self):
                    self.hits = [type("H", (), {"score": None, "content": "", "tags": []})() for _ in range(2)]
            return R()

    monkeypatch.setattr(uvc, "UnifiedVectorClient", lambda env: _Dummy())
    app = mod.app
    client = app.test_client()
    r = client.post("/vector/query", data=json.dumps({"question": "q", "k": 2}), content_type="application/json")
    assert r.status_code == 200
    # 2 hits but top_sim=0 => thin
    assert r.headers.get("X-Axiom-Retrieval") == "thin"


def test_custom_header_name(monkeypatch):
    from pods.memory import pod2_memory_api as mod
    monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    monkeypatch.setenv("AXIOM_RETRIEVAL_HEADER", "X-Custom-Retrieval")
    _monkey_vector(monkeypatch, [0.80, 0.7, 0.6, 0.5])
    app = mod.app
    client = app.test_client()
    r = client.post("/vector/query", data=json.dumps({"question": "q", "k": 4}), content_type="application/json")
    assert r.status_code == 200
    assert r.headers.get("X-Custom-Retrieval") == "ok"

