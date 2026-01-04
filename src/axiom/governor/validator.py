#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple, Dict, Any


def _schema_path(kind: str) -> Path:
    base = Path(__file__).parent / "schemas" / "v1"
    mapping = {
        "journal": "journal.json",
        "belief": "belief.json",
        "memory_write": "memory_write.json",
        "vector_write": "vector_write.json",
    }
    fname = mapping.get(kind)
    if not fname:
        raise ValueError(f"unknown schema kind: {kind}")
    return base / fname


def validate_payload(kind: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate payload against Governor v1 schema.

    Returns (ok, detail). On validator import error or missing schema file,
    returns (True, "validator_unavailable").
    """
    try:
        from jsonschema import validate  # type: ignore
    except Exception:
        return True, "validator_unavailable"

    try:
        path = _schema_path(kind)
        if not path.exists():
            return True, "schema_missing"
        with open(path, "r") as f:
            schema = json.load(f)
        validate(instance=payload or {}, schema=schema)
        return True, "ok"
    except Exception as e:
        return False, f"schema_violation:{e.__class__.__name__}"

