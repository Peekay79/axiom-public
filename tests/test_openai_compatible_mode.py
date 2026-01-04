import asyncio

import pytest


pytest.importorskip("pytest_asyncio")
llm_mod = pytest.importorskip("llm_connector")


@pytest.mark.asyncio
async def test_auto_uses_completions_when_models_capabilities_completion(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "auto")

    client = llm_mod.RobustLLMClient(base_url="http://llm", provider="openai_compatible")
    client.model = "m"

    async def noop_init():
        return None

    monkeypatch.setattr(client, "initialize_session", noop_init)

    async def fake_models(*, timeout_total: float, request_id=None):
        return {"object": "list", "data": [{"id": "m", "capabilities": ["completion"]}]}

    called = {"chat": 0, "completion": 0}

    async def fake_post_chat(*, payload: dict, timeout_total: float, request_id=None):
        called["chat"] += 1
        raise AssertionError("chat endpoint should not be used for completion-only model")

    async def fake_post_completion(*, payload: dict, timeout_total: float, request_id=None):
        called["completion"] += 1
        assert "prompt" in payload
        return {"choices": [{"text": "ok-from-completions"}], "usage": {"total_tokens": 3}}

    monkeypatch.setattr(client, "_fetch_openai_models", fake_models)
    monkeypatch.setattr(client, "_post_openai_chat", fake_post_chat)
    monkeypatch.setattr(client, "_post_openai_completion", fake_post_completion)

    out = await client._make_request("hello")
    assert out["content"] == "ok-from-completions"
    assert called["completion"] == 1
    assert called["chat"] == 0


@pytest.mark.asyncio
async def test_auto_falls_back_to_completions_when_chat_times_out(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "auto")

    client = llm_mod.RobustLLMClient(base_url="http://llm", provider="openai_compatible")
    client.model = "m"

    async def noop_init():
        return None

    monkeypatch.setattr(client, "initialize_session", noop_init)

    # models endpoint returns no capabilities => prefer chat with fast fallback
    async def fake_models(*, timeout_total: float, request_id=None):
        return {"object": "list", "data": [{"id": "m"}]}

    called = {"chat": 0, "completion": 0}

    async def fake_post_chat(*, payload: dict, timeout_total: float, request_id=None):
        called["chat"] += 1
        raise asyncio.TimeoutError("simulated hang")

    async def fake_post_completion(*, payload: dict, timeout_total: float, request_id=None):
        called["completion"] += 1
        return {"choices": [{"text": "ok-after-fallback"}], "usage": {"total_tokens": 2}}

    monkeypatch.setattr(client, "_fetch_openai_models", fake_models)
    monkeypatch.setattr(client, "_post_openai_chat", fake_post_chat)
    monkeypatch.setattr(client, "_post_openai_completion", fake_post_completion)

    out = await client._make_request("hello")
    assert out["content"] == "ok-after-fallback"
    assert called["chat"] == 1
    assert called["completion"] == 1
    assert client._resolved_mode == "completion"

