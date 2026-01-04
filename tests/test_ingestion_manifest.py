import json
import logging
from pathlib import Path

import pytest


@pytest.mark.phase("X")
def test_manifest_valid_and_filter(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)

    path = tmp_path / "ingestion_manifest.json"
    manifest = {
        "ingestion_timestamp": "2025-01-01T00:00:00",
        "world_map_path": "/tmp/world_map.json",
        "world_map_hash": "abc123",
        "statistics": {"entities_processed": 10},
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")

    from memory.ingestion_manager import load_ingestion_manifest, filter_memories_by_manifest

    m = load_ingestion_manifest(str(path))
    assert isinstance(m, dict)
    assert any("[RECALL][Manifest]" in r.getMessage() for r in caplog.records)

    # Prepare mixed memories
    mems = [
        {"id": "1", "metadata": {"ingestion_world_map_hash": "abc123"}},
        {"id": "2", "metadata": {"ingestion_world_map_hash": "zzz"}},
        {"id": "3", "ingestion_world_map_hash": "abc123"},
    ]
    kept = filter_memories_by_manifest(mems, m)
    assert {m["id"] for m in kept} == {"1", "3"}
    assert any("[RECALL][Manifest] filter applied" in r.getMessage() for r in caplog.records)


@pytest.mark.phase("X")
def test_manifest_missing_and_invalid(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)

    from memory.ingestion_manager import load_ingestion_manifest, filter_memories_by_manifest

    # Missing
    m = load_ingestion_manifest(str(tmp_path / "nope.json"))
    assert m is None
    assert any("[RECALL][Manifest] mismatch" in r.getMessage() for r in caplog.records)

    # Invalid file
    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    m2 = load_ingestion_manifest(str(bad))
    assert m2 is None
    assert any("[RECALL][Manifest] mismatch" in r.getMessage() for r in caplog.records)

    # Filter with None is a no-op and logs disabled
    mems = [{"id": "a"}, {"id": "b"}]
    out = filter_memories_by_manifest(mems, None)
    assert out == mems
    assert any("[RECALL][Manifest] disabled" in r.getMessage() for r in caplog.records)

