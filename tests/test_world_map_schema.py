#!/usr/bin/env python3
"""
World Map Schema Tests
─────────────────────

Unit tests to ensure world_map.json always has valid array-based schema
and all relationships have required fields.
"""

import glob
import json
import os


def load_world_map():
    """Load world map file, preferring normalized versions if available."""
    # Prefer normalized if both exist in CI
    candidates = [
        p
        for p in ("world_map.json",) + tuple(glob.glob("world_map.normalized*.json"))
        if os.path.exists(p)
    ]
    assert candidates, "No world_map file found"

    # Prefer normalized files
    normalized_files = [p for p in candidates if "normalized" in p]
    if normalized_files:
        selected_file = normalized_files[0]
    else:
        selected_file = candidates[0]

    with open(selected_file, "r", encoding="utf-8") as f:
        return json.load(f)


def test_world_map_arrays_and_fields():
    """Test that world map has array schema and required fields."""
    wm = load_world_map()

    # Schema validation
    assert isinstance(wm.get("entities"), list), "entities must be an array"
    assert isinstance(wm.get("relationships"), list), "relationships must be an array"

    # Entity validation
    for i, entity in enumerate(wm["entities"]):
        assert isinstance(entity, dict), f"entity[{i}] must be an object"
        assert "id" in entity, f"entity[{i}] missing 'id': {entity}"
        assert "type" in entity, f"entity[{i}] missing 'type': {entity}"

    # Relationship validation
    for i, rel in enumerate(wm["relationships"]):
        assert isinstance(rel, dict), f"relationship[{i}] must be an object"
        for field in ("id", "type", "source", "target"):
            assert field in rel, f"relationship[{i}] missing '{field}': {rel}"

    # Collect entity IDs
    entity_ids = {e.get("id") for e in wm["entities"]}

    # Ensure every source/target references an entity id
    for i, rel in enumerate(wm["relationships"]):
        source = rel["source"]
        target = rel["target"]

        # Sources and targets should be strings (not lists after normalization)
        assert isinstance(
            source, str
        ), f"relationship[{i}] source must be string after normalization: {source}"
        assert isinstance(
            target, str
        ), f"relationship[{i}] target must be string after normalization: {target}"

        assert (
            source in entity_ids
        ), f"relationship[{i}] unknown source entity: {source}"
        assert (
            target in entity_ids
        ), f"relationship[{i}] unknown target entity: {target}"


def test_no_null_entities_or_dict_relationships():
    """Test that entities is not null and relationships is not a dict."""
    wm = load_world_map()

    # These are the specific problems mentioned in the task
    assert wm.get("entities") is not None, "entities should not be null"
    assert not isinstance(
        wm.get("relationships"), dict
    ), "relationships should not be a dict"


def test_relationship_expansion():
    """Test that list-valued relationships are properly expanded."""
    wm = load_world_map()

    # After normalization, no relationship should have list-valued source/target
    for i, rel in enumerate(wm["relationships"]):
        source = rel.get("source")
        target = rel.get("target")

        assert not isinstance(
            source, (list, tuple, set)
        ), f"relationship[{i}] source should not be a list: {source}"
        assert not isinstance(
            target, (list, tuple, set)
        ), f"relationship[{i}] target should not be a list: {target}"


def test_entities_have_unique_ids():
    """Test that all entities have unique IDs."""
    wm = load_world_map()

    entity_ids = [e.get("id") for e in wm["entities"]]
    unique_ids = set(entity_ids)

    assert len(entity_ids) == len(
        unique_ids
    ), f"Duplicate entity IDs found: {[eid for eid in entity_ids if entity_ids.count(eid) > 1]}"


def test_relationships_have_unique_ids():
    """Test that all relationships have unique IDs."""
    wm = load_world_map()

    rel_ids = [r.get("id") for r in wm["relationships"]]
    unique_ids = set(rel_ids)

    assert len(rel_ids) == len(
        unique_ids
    ), f"Duplicate relationship IDs found: {[rid for rid in rel_ids if rel_ids.count(rid) > 1]}"


if __name__ == "__main__":
    # Run tests directly if script is executed
    test_world_map_arrays_and_fields()
    test_no_null_entities_or_dict_relationships()
    test_relationship_expansion()
    test_entities_have_unique_ids()
    test_relationships_have_unique_ids()
    print("✅ All world map schema tests passed!")
