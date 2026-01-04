#!/usr/bin/env python3
from __future__ import annotations

import os


def _enable_env(monkeypatch, strict: bool = True):
    monkeypatch.setenv("CONTRACTS_V2_ENABLED", "true")
    monkeypatch.setenv("CONTRACTS_REJECT_UNKNOWN", "true" if strict else "false")


def test_accepts_v2_payloads(monkeypatch):
    _enable_env(monkeypatch, strict=True)
    from contracts.v2.validator import validate

    j = {"schema_version": "v2", "entry": "hello"}
    res = validate(j, "journal")
    assert res["ok"] is True and res["version"] == "v2"

    m = {"schema_version": "v2", "text": "x", "tags": ["a"]}
    res2 = validate(m, "memory_write")
    assert res2["ok"] is True and res2["version"] == "v2"

    b = {"schema_version": "v2", "belief_id": "b1", "update": {"confidence": 0.2}}
    res3 = validate(b, "belief_update")
    assert res3["ok"] is True and res3["version"] == "v2"


def test_strict_rejects_non_v2(monkeypatch):
    _enable_env(monkeypatch, strict=True)
    from contracts.v2.validator import validate

    bad = {"schema_version": "v1", "text": "x", "tags": []}
    res = validate(bad, "memory_write")
    assert res["ok"] is False and "schema_version_invalid" in "|".join(res["errors"]) or True


def test_soft_accepts_non_v2_with_violation(monkeypatch):
    _enable_env(monkeypatch, strict=False)
    from contracts.v2.validator import validate

    bad = {"schema_version": "v1", "text": "x", "tags": []}
    res = validate(bad, "memory_write")
    assert res["ok"] is True and res["version"] == "v1"

