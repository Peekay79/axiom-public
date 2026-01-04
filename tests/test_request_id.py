#!/usr/bin/env python3
import json
import re
import pytest


flask = pytest.importorskip("flask")


def test_memory_echoes_header(monkeypatch):
    from pods.memory import pod2_memory_api as mod

    # Ensure vector readiness does not block health
    monkeypatch.setattr(mod, "vector_ready", True, raising=False)
    app = mod.app
    client = app.test_client()

    # Provided header is echoed
    rid = "abc-123"
    r = client.get("/health", headers={"X-Request-ID": rid})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == rid

    # Missing header generates UUID v4
    r2 = client.get("/health")
    assert r2.status_code == 200
    hv = r2.headers.get("X-Request-ID")
    assert isinstance(hv, str) and re.match(r"^[0-9a-f\-]{36}$", hv)


def test_adapter_propagation(monkeypatch):
    # Monkeypatch UnifiedVectorClient.search to capture headers used in adapter path
    from vector import unified_client as uvc_mod
    from pods.memory import pod2_memory_api as mem_mod
    monkeypatch.setattr(mem_mod, "vector_ready", True, raising=False)

    captured = {}

    class DummyResp:
        def __init__(self):
            self.hits = []

    def fake_search(self, req, request_id=None):
        captured["request_id"] = request_id
        return DummyResp()

    # Force adapter mode by setting env seen by UnifiedVectorClient
    monkeypatch.setenv("VECTOR_PATH", "adapter")
    monkeypatch.setenv("QDRANT_URL", "http://vector")
    monkeypatch.setattr(uvc_mod.UnifiedVectorClient, "search", fake_search, raising=False)

    app = mem_mod.app
    client = app.test_client()
    rid = "rid-xyz"
    payload = {"question": "hello", "k": 1}
    r = client.post("/vector/query", data=json.dumps(payload), content_type="application/json", headers={"X-Request-ID": rid})
    assert r.status_code == 200
    assert captured.get("request_id") == rid


def test_llm_connector_header(monkeypatch, event_loop):
    import llm_connector as llm

    async def fake_post(self, url, json=None, headers=None):  # type: ignore
        # capture header
        test_llm_connector_header.seen = headers or {}
        class FakeResp:
            status = 200
            async def json(self):
                return {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"total_tokens": 7},
                }
        return FakeResp()

    # Patch aiohttp session.post
    async def fake_ctx_mgr(session, url, json=None, headers=None):  # pragma: no cover - kept simple
        class Ctx:
            async def __aenter__(self_inner):
                return await fake_post(None, url, json=json, headers=headers)
            async def __aexit__(self_inner, exc_type, exc, tb):
                return False
        return Ctx()

    async def run_test():
        c = llm.RobustLLMClient(base_url="http://llm")
        await c.initialize_session()
        # Monkeypatch the session.post to our fake context manager
        c.session.post = lambda url, json=None, headers=None: fake_ctx_mgr(c.session, url, json=json, headers=headers)  # type: ignore
        _ = await c.call_llm("hi", request_id="rid-abc")
        await c.close_session()
        assert test_llm_connector_header.seen.get("X-Request-ID") == "rid-abc"

    event_loop.run_until_complete(run_test())

