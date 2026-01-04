from __future__ import annotations

import json
import os
from pathlib import Path


class _DummyQdrantClient:
    def __init__(self):
        self.dumps = []

    def scroll(self, collection_name: str, offset=None, limit=1000, with_payload=True, with_vectors=True):
        if offset is None:
            pts = [type("P", (), {"id": "1", "payload": {"a": 1}, "vector": [0.1, 0.2]})()]
            return pts, "next"
        return [], None

    def get_collections(self):
        return type("R", (), {"collections": [type("C", (), {"name": "axiom_memories"})()]})()

    def upsert(self, collection_name: str, points):
        self.dumps.append((collection_name, points))


def test_take_snapshot_writes_metadata(tmp_path, monkeypatch):
    # Force compat client to return dummy client
    def _mk(**kwargs):
        return _DummyQdrantClient()

    monkeypatch.setenv("QDRANT_SNAPSHOT_ENABLED", "true")
    monkeypatch.setenv("QDRANT_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setenv("QDRANT_SNAPSHOT_KEEP", "7")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("COCKPIT_SIGNAL_DIR", str(tmp_path / "signals"))
    monkeypatch.setattr("lifecycle.snapshot.make_qdrant_client", _mk, raising=False)
    monkeypatch.setattr("lifecycle.snapshot._make_client", lambda: _DummyQdrantClient())

    from lifecycle.snapshot import take_snapshot

    res = take_snapshot(str(tmp_path))
    assert res.get("ns_count", 0) >= 1
    # At least one artifact tar should exist
    found = list(tmp_path.glob("*.tar.gz"))
    assert found


def test_prune_snapshots_respects_keep(tmp_path):
    # Create 5 fake snapshot files
    for i in range(5):
        p = tmp_path / f"mem.{i}.tar.gz"
        p.write_bytes(b"x" * (i + 1))
    from lifecycle.snapshot import prune_snapshots

    out = prune_snapshots(str(tmp_path), keep=2)
    assert out["kept"] == 2
    assert len(list(tmp_path.glob("*.tar.gz"))) == 2

