import asyncio
import json
import logging

import pytest


pytest.importorskip("pytest_asyncio")
llm_mod = pytest.importorskip("llm_connector")


@pytest.mark.asyncio
async def test_llm_client_retries_backoff_and_circuit_breaker(monkeypatch, caplog):
    # Arrange: create client with default retries (3 attempts total)
    client = llm_mod.RobustLLMClient(base_url="http://localhost:9999", provider="testprov")
    caplog.set_level(logging.WARNING)

    # Track async sleeps to verify backoff pattern (0.2s -> 0.8s)
    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    # Make _make_request raise on every attempt for the first 3 high-level calls
    # and succeed afterwards
    high_level_call_count = {"count": 0}
    per_call_attempts = {"count": 0}

    async def failing_then_success_request(prompt: str, **kwargs):
        per_call_attempts["count"] += 1
        raise asyncio.TimeoutError("simulated timeout")

    # Wrap call_llm so we can count high-level calls and swap behavior later
    real_make_request = failing_then_success_request

    async def call_llm_and_count(prompt: str, **kwargs):
        high_level_call_count["count"] += 1
        return await llm_mod.RobustLLMClient.call_llm(client, prompt, **kwargs)

    monkeypatch.setattr(client, "_make_request", real_make_request)

    # Act 1: First call should perform 3 attempts with backoff sleeps, then fail
    per_call_attempts_before = per_call_attempts["count"]
    with pytest.raises(RuntimeError):
        await call_llm_and_count("prompt-1")
    per_call_attempts_after = per_call_attempts["count"]

    # Assert retries = 2 sleeps (3 attempts)
    attempts_this_call = per_call_attempts_after - per_call_attempts_before
    assert attempts_this_call == 3

    # Check backoff jittered ranges for first two sleeps (0.2..0.3, 0.8..0.9)
    assert 0.2 <= sleep_calls[0] <= 0.3
    assert 0.8 <= sleep_calls[1] <= 0.9

    # Act 2: Two more failing calls to open circuit (3 consecutive failures)
    with pytest.raises(RuntimeError):
        await call_llm_and_count("prompt-2")
    with pytest.raises(RuntimeError):
        await call_llm_and_count("prompt-3")

    # Circuit should open after the 3rd consecutive failure
    assert client.is_circuit_open() is True

    # The circuit open event should be logged once as JSON WARN
    found_open_log = False
    for rec in caplog.records:
        try:
            payload = json.loads(rec.getMessage())
        except Exception:
            continue
        if payload == {"component": "llm", "event": "circuit_open", "provider": client.provider or "<unknown>"}:
            found_open_log = True
            break
    assert found_open_log, "Expected JSON WARN for circuit_open not found"

    # Act 3: While open, calls should short-circuit without invoking _make_request
    per_call_attempts_before = per_call_attempts["count"]
    with pytest.raises(RuntimeError):
        await call_llm_and_count("prompt-open-shortcircuit")
    per_call_attempts_after = per_call_attempts["count"]
    assert (
        per_call_attempts_after == per_call_attempts_before
    ), "_make_request should not be called when circuit is open"

    # Prepare half-open: advance time by > 20s
    last_failure = client.circuit_breaker.last_failure_time
    fake_now = last_failure + 21

    # Monkeypatch time.time used inside the module
    monkeypatch.setattr(llm_mod.time, "time", lambda: fake_now)

    # Make the request succeed for the half-open probe
    async def success_request(prompt: str, **kwargs):
        return {"content": "ok", "tokens_used": 1}

    monkeypatch.setattr(client, "_make_request", success_request)

    # Act 4: Next call should be allowed as half-open single probe and succeed
    resp = await call_llm_and_count("prompt-half-open")
    assert resp.content == "ok"
    assert client.is_circuit_open() is False

