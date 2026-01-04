#!/usr/bin/env python3
import json
import types
import pytest


flask = pytest.importorskip("flask")
requests = pytest.importorskip("requests")


def make_memory_app(monkeypatch=None):
    import os
    # Force adapter path to exercise HTTP path in UnifiedVectorClient
    if monkeypatch is not None:
        monkeypatch.setenv("VECTOR_PATH", "adapter")
        monkeypatch.setenv("QDRANT_URL", "http://vector")

    from pods.memory import pod2_memory_api as mod
    # Force vector_ready on for tests (no network)
    if monkeypatch is not None:
        monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    return mod.app


class _Capture:
    def __init__(self):
        self.headers = []
        self.bodies = []

    def post(self, url, json=None, timeout=None, headers=None):  # type: ignore[override]
        # Record headers for assertion
        self.headers.append(dict(headers or {}))
        # Return a minimal fake response with a vector shape the Memory expects
        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"hits": []}

            @property
            def headers(self):
                return {}

        return Resp()


def test_propagates_provided_request_id(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(requests, "post", cap.post)

    app = make_memory_app(monkeypatch)
    client = app.test_client()

    rid = "demo-req-123"
    payload = {"question": "hello", "k": 1}
    r = client.post("/vector/query", data=json.dumps(payload), content_type="application/json", headers={"X-Request-ID": rid})
    assert r.status_code == 200

    # Adapter call should receive the same header
    assert cap.headers, "no outbound calls captured"
    assert cap.headers[-1].get("X-Request-ID") == rid

    # Response body unchanged shape
    body = r.get_json()
    assert isinstance(body, dict)
    assert "data" in body
    assert "Get" in body["data"]
    assert "axiom_memories" in body["data"]["Get"]


def test_generates_request_id_when_missing(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(requests, "post", cap.post)

    app = make_memory_app(monkeypatch)
    client = app.test_client()

    payload = {"question": "hello", "k": 1}
    r = client.post("/vector/query", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200

    # Adapter call should receive a non-empty request id
    assert cap.headers, "no outbound calls captured"
    got = cap.headers[-1].get("X-Request-ID")
    assert isinstance(got, str) and len(got) > 0

    # Response body unchanged
    body = r.get_json()
    assert isinstance(body, dict)
    assert "data" in body
    assert "Get" in body["data"]
    assert "axiom_memories" in body["data"]["Get"]


def test_unified_client_forwards_req_id(monkeypatch):
    # Capture outbound HTTP to adapter
    cap = _Capture()
    monkeypatch.setattr(requests, "post", cap.post)

    # Use a Flask request context so UnifiedVectorClient can read flask.g
    app = flask.Flask(__name__)
    rid = "rid-from-context"
    from vector.unified_client import UnifiedVectorClient, VectorSearchRequest

    with app.test_request_context("/"):
        from flask import g as _g

        _g.req_id = rid
        env = {"VECTOR_PATH": "adapter", "QDRANT_URL": "http://vector"}
        client = UnifiedVectorClient(env)
        _ = client.search(VectorSearchRequest(query="hello", top_k=1))

    assert cap.headers, "no outbound calls captured"
    assert cap.headers[-1].get("X-Request-ID") == rid

