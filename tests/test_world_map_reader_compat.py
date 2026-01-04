#!/usr/bin/env python3
"""
World Map Reader Compatibility Tests
───────────────────────────────────

Tests that the ingest_world_map.py loader and validator can handle both:
1. Legacy dict-indexed schema (current world_map.json format)
2. New array-based schema (output from write_world_map)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path to import ingest_world_map
sys.path.insert(0, str(Path(__file__).parent.parent))
from ingest_world_map import load_world_map, validate_world_map_schema


def test_dict_shaped_world_map():
    """Test that loader handles legacy dict-indexed world map format."""
    # Create a small dict-shaped example
    dict_world_map = {
        "axiom": {"type": "agent", "goals": ["understand self", "engage ethically"]},
        "example_person": {"type": "human", "full_name": "Alice Example", "creates": "axiom"},
        "relationships": {
            "kurt_creates_axiom": {
                "source": "example_person",
                "target": "axiom",
                "type": "creator",
                "description": "ExamplePerson creates Axiom",
            }
        },
    }

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(dict_world_map, f, indent=2)
        temp_path = f.name

    try:
        # Test loading and validation
        loaded_data = load_world_map(temp_path)
        validation = validate_world_map_schema(loaded_data)

        # Should pass validation
        assert validation[
            "valid"
        ], f"Dict format should validate: {validation['errors']}"
        assert validation["entity_count"] >= 2, "Should find entities"
        assert validation["relationship_count"] >= 1, "Should find relationships"

        print("✅ Dict-shaped world map loads and validates successfully")

    finally:
        os.unlink(temp_path)


def test_array_shaped_world_map():
    """Test that loader handles new array-based world map format."""
    # Create a small array-shaped example
    array_world_map = {
        "entities": [
            {
                "id": "axiom",
                "type": "agent",
                "goals": ["understand self", "engage ethically"],
            },
            {
                "id": "example_person",
                "type": "human",
                "full_name": "Alice Example",
                "creates": "axiom",
            },
        ],
        "relationships": [
            {
                "id": "kurt_creates_axiom",
                "source": "example_person",
                "target": "axiom",
                "type": "creator",
                "description": "ExamplePerson creates Axiom",
            }
        ],
    }

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(array_world_map, f, indent=2)
        temp_path = f.name

    try:
        # Test loading and validation
        loaded_data = load_world_map(temp_path)
        validation = validate_world_map_schema(loaded_data)

        # Should pass validation
        assert validation[
            "valid"
        ], f"Array format should validate: {validation['errors']}"
        assert validation["entity_count"] >= 2, "Should find entities"
        assert validation["relationship_count"] >= 1, "Should find relationships"

        # With dual-shape support, arrays should remain as arrays
        assert isinstance(
            loaded_data.get("entities"), list
        ), "Entities should remain as array format"
        assert isinstance(
            loaded_data.get("relationships"), list
        ), "Relationships should remain as array format"

        print("✅ Array-shaped world map loads and validates successfully")

    finally:
        os.unlink(temp_path)


def test_array_with_missing_ids():
    """Test that array format with missing IDs gets auto-generated IDs."""
    # Create array format with some missing IDs
    array_world_map = {
        "entities": [
            {"type": "agent", "goals": ["test goal"]},
            {"id": "existing_id", "type": "human"},
        ],
        "relationships": [
            {"source": "entity1", "target": "entity2", "type": "test_relation"}
        ],
    }

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(array_world_map, f, indent=2)
        temp_path = f.name

    try:
        # Test loading
        loaded_data = load_world_map(temp_path)
        validation = validate_world_map_schema(loaded_data)

        # Should remain as array format
        entities = loaded_data.get("entities", [])
        relationships = loaded_data.get("relationships", [])

        assert isinstance(entities, list), "Entities should remain as array"
        assert isinstance(relationships, list), "Relationships should remain as array"

        # Should validate correctly with auto-generated IDs through _iter_section
        assert validation["valid"], f"Should validate: {validation['errors']}"
        assert validation["entity_count"] >= 2, "Should count both entities"
        assert validation["relationship_count"] >= 1, "Should count relationships"

        print("✅ Array format with missing IDs handled correctly")

    finally:
        os.unlink(temp_path)


def test_empty_sections():
    """Test handling of empty entities/relationships sections."""
    test_cases = [
        {"entities": [], "relationships": []},
        {"entities": {}, "relationships": {}},
        {},  # No entities or relationships sections
    ]

    for i, world_map in enumerate(test_cases):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(world_map, f, indent=2)
            temp_path = f.name

        try:
            # Should load without error
            loaded_data = load_world_map(temp_path)
            validation = validate_world_map_schema(loaded_data)

            # Should be valid (just empty)
            assert validation[
                "valid"
            ], f"Empty case {i} should be valid: {validation['errors']}"
            assert (
                validation["entity_count"] == 0
            ), f"Empty case {i} should have 0 entities"
            assert (
                validation["relationship_count"] == 0
            ), f"Empty case {i} should have 0 relationships"

        finally:
            os.unlink(temp_path)

    print("✅ Empty sections handled correctly")


if __name__ == "__main__":
    """Run all compatibility tests."""
    print("🧪 Running world map reader compatibility tests...")

    test_dict_shaped_world_map()
    test_array_shaped_world_map()
    test_array_with_missing_ids()
    test_empty_sections()

    print("🎉 All compatibility tests passed!")
