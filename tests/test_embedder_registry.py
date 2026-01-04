#!/usr/bin/env python3
from __future__ import annotations

import os


def test_registry_current_hash(monkeypatch):
    monkeypatch.setenv("EMBEDDER_NAME", "text-embedding-3-large")
    monkeypatch.setenv("EMBEDDER_VERSION", "3.0.0")
    monkeypatch.setenv("EMBEDDER_DIM", "3072")
    from vector.embedder_registry import current

    cfg = current()
    assert cfg["name"] == "text-embedding-3-large"
    assert cfg["version"] == "3.0.0"
    assert int(cfg["dim"]) == 3072
    assert isinstance(cfg["hash"], str) and len(cfg["hash"]) == 64


def test_with_registry_attaches_block(monkeypatch):
    monkeypatch.setenv("EMBEDDER_REGISTRY_ENABLED", "true")
    from vector.embedder_registry import with_registry, current

    payload = {"content": "x"}
    out = with_registry(payload)
    emb = out.get("embedder") or {}
    cur = current()
    assert emb.get("name") == cur.get("name")
    assert emb.get("version") == cur.get("version")
    assert emb.get("hash") == cur.get("hash")


def test_bluegreen_cutover_noop_without_flag(monkeypatch):
    monkeypatch.delenv("BLUEGREEN_ENABLED", raising=False)
    from retrieval.bluegreen import maybe_cutover
    ok, prev, new = maybe_cutover(client=object(), alias="mem_current", shadow="mem_shadow", min_delta=-0.01)
    assert ok is False and prev is None and new is None

