# memory_validator.py
import json
from datetime import datetime

import jsonschema
from jsonschema import validate

# Load schema once at module import
with open("schemas/memory.schema.json", "r") as f:
    MEMORY_SCHEMA = json.load(f)


class MemoryValidationError(Exception):
    pass


def validate_memory_entry(entry: dict) -> dict:
    """
    Validate a memory dict against the canonical schema.
    Raises MemoryValidationError if invalid.
    Returns validated object (optionally enriched with defaults).
    """
    try:
        validate(instance=entry, schema=MEMORY_SCHEMA)
    except jsonschema.exceptions.ValidationError as e:
        raise MemoryValidationError(f"Memory schema violation: {e.message}")

    return entry  # Optionally: enrich here with derived fields if needed


# Optional utility: enforce + add defaults
def normalize_memory(entry: dict) -> dict:
    now = datetime.utcnow().isoformat()
    entry.setdefault("timestamp", now)
    entry.setdefault("tags", [])
    entry.setdefault("importance", 0.5)
    entry.setdefault("source", "unknown")

    return validate_memory_entry(entry)
