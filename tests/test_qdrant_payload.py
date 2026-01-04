from pods.memory.qdrant_backend import _build_payload


def test_build_payload_preserves_markers():
    mem = {
        "id": "entity_axiom",
        "content": "Entity: axiom",
        "source": "world_map_ingestion",
        "tags": ["world_map_entity"],
        "metadata": {},  # gets `source` mirrored here
    }
    payload = _build_payload(mem)
    assert payload["source"] == "world_map_ingestion"
    assert "world_map_entity" in payload.get("tags", [])
    assert payload.get("metadata", {}).get("source") == "world_map_ingestion"
    assert payload["id"] == "entity_axiom"

