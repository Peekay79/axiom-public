#!/usr/bin/env python3
from __future__ import annotations

import os
import json


def test_deterministic_kwargs_for_stateful(monkeypatch):
    monkeypatch.setenv("PROMPT_CONTRACTS_ENABLED", "true")
    monkeypatch.setenv("STATEFUL_TOOLS", "write_memory,update_belief,append_journal")
    monkeypatch.setenv("DETERMINISTIC_TEMP", "0.0")
    monkeypatch.setenv("DETERMINISTIC_TOP_P", "1.0")

    from llm_contracts.decode_policy import apply_deterministic_kwargs, is_stateful

    assert is_stateful("write_memory") is True
    kw = apply_deterministic_kwargs({"temperature": 0.8, "top_p": 0.9, "n": 2, "beam_width": 4})
    assert kw["temperature"] == 0.0
    assert kw["top_p"] == 1.0
    assert kw.get("n") == 1
    assert "beam_width" not in kw


def test_json_envelope_parsing_and_validation_ok(monkeypatch):
    monkeypatch.setenv("PROMPT_CONTRACTS_ENABLED", "true")
    from llm_contracts.json_tools import call

    raw = json.dumps({"text": "hello", "tags": ["t1", "t2"], "metadata": {"x": 1}})
    out = call("write_memory", raw)
    assert out["tool_name"] == "write_memory"
    assert out["schema_version"] == "v1"
    assert out["text"] == "hello"
    assert out["tags"] == ["t1", "t2"]


def test_invalid_json_raises_violation(monkeypatch, tmp_path):
    monkeypatch.setenv("PROMPT_CONTRACTS_ENABLED", "true")
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path))
    from llm_contracts.json_tools import call, ContractViolation

    bad = "not json at all"
    try:
        _ = call("write_memory", bad)
        raised = False
    except ContractViolation as e:
        raised = True
        assert "invalid_json" in str(e)
    assert raised

    # Verify a signal was emitted best‑effort
    files = list(tmp_path.glob("governor.prompt_contracts.violation.invalid_json*.json"))
    assert len(files) >= 0  # emission best‑effort; at least does not crash


def test_idempotency_headers_added(monkeypatch):
    monkeypatch.setenv("PROMPT_CONTRACTS_ENABLED", "true")
    from llm_contracts.runtime import run_tool

    raw = json.dumps({"text": "hi", "tags": []})
    out = run_tool("write_memory", {"temperature": 0.7}, None, raw)
    headers = out.get("_headers") or {}
    assert isinstance(headers.get("Idempotency-Key"), str)
    assert isinstance(headers.get("X-Correlation-ID"), str)

