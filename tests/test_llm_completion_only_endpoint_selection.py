import pytest


pytest.importorskip("pytest_asyncio")
llm_mod = pytest.importorskip("llm_connector")


@pytest.mark.asyncio
async def test_auto_mode_uses_completions_when_model_is_completion_only(monkeypatch):
    client = llm_mod.RobustLLMClient(base_url="http://localhost:11434", model="m1", provider="openai_compatible")

    calls = {"chat": 0, "completion": 0, "completion_payload": None}

    async def fake_fetch_models(*, timeout_total: float, request_id=None):
        return {"object": "list", "data": [{"id": "m1", "capabilities": ["completion"]}]}

    async def fake_post_chat(*, payload: dict, timeout_total: float, request_id=None):
        calls["chat"] += 1
        raise AssertionError("/v1/chat/completions should not be used for completion-only models")

    async def fake_post_completion(*, payload: dict, timeout_total: float, request_id=None):
        calls["completion"] += 1
        calls["completion_payload"] = payload
        return {"choices": [{"text": "Hello"}], "usage": {"total_tokens": 1}}

    async def fake_init():
        return None

    monkeypatch.setattr(client, "initialize_session", fake_init)
    monkeypatch.setattr(client, "_fetch_openai_models", fake_fetch_models)
    monkeypatch.setattr(client, "_post_openai_chat", fake_post_chat)
    monkeypatch.setattr(client, "_post_openai_completion", fake_post_completion)

    out = await client._make_request("hi")

    assert calls["chat"] == 0
    assert calls["completion"] == 1
    assert (calls["completion_payload"] or {}).get("prompt") == "hi"
    assert out["content"].strip() == "Hello"
