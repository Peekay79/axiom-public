#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _env_truthy(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


CONTRACTS_V2_ENABLED = _env_truthy("CONTRACTS_V2_ENABLED", True)
CONTRACTS_REJECT_UNKNOWN = _env_truthy("CONTRACTS_REJECT_UNKNOWN", True)


_SCHEMA_DIR = Path(__file__).parent / "schemas"
_KIND_TO_SCHEMA = {
    # external kind -> schema filename
    "journal": "journal_entry.json",
    "memory_write": "memory_write.json",
    "belief_update": "belief_update.json",
}


def _schema_for(kind: str) -> Dict[str, Any] | None:
    fname = _KIND_TO_SCHEMA.get(kind)
    if not fname:
        return None
    path = _SCHEMA_DIR / fname
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None
    return None


def _emit_violation(kind: str, reason: str, detail: Dict[str, Any] | None = None) -> None:
    # Best-effort Cockpit emission
    try:
        from pods.cockpit.cockpit_reporter import write_signal  # type: ignore

        payload = {"kind": kind, "reason": reason}
        if detail:
            payload["detail"] = detail
        write_signal("contracts_v2", f"violation.{kind}", payload)
    except Exception:
        pass


def _emit_version_seen(kind: str, version: str | None) -> None:
    try:
        from pods.cockpit.cockpit_reporter import write_signal  # type: ignore

        write_signal("contracts_v2", "version_seen", {"kind": kind, "version": version or "unknown"})
    except Exception:
        pass


def _validate_jsonschema(instance: Dict[str, Any], schema: Dict[str, Any] | None) -> Tuple[bool, List[str], str]:
    if schema is None:
        return True, [], "no_schema"
    try:
        from jsonschema import validate  # type: ignore
    except Exception:
        # Soft-accept but emit violation so Cockpit can track jsonschema absence
        _emit_violation(str(instance.get("tool_name") or "unknown"), "jsonschema_unavailable")
        return True, [], "jsonschema_unavailable"
    try:
        validate(instance=instance, schema=schema)
        return True, [], "ok"
    except Exception as e:
        return False, [f"{e.__class__.__name__}: {str(e)}"], "schema_violation"


def validate(payload: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """
    Validate a stateful payload under Contracts v2.

    Returns a dict: {ok: bool, errors: list[str], version: "v2"|other}

    Behavior:
    - If CONTRACTS_V2_ENABLED is true: require payload["schema_version"] == "v2".
      If CONTRACTS_REJECT_UNKNOWN is true and version != "v2" → ok False, error schema_version_invalid.
      Otherwise, emit a Cockpit violation and accept (ok True).
    - If version is v2, validate against the v2 jsonschema. If jsonschema is missing,
      soft-accept but emit a Cockpit violation.
    - If CONTRACTS_V2_ENABLED is false: returns ok True (no-op).
    """
    if not CONTRACTS_V2_ENABLED:
        return {"ok": True, "errors": [], "version": str(payload.get("schema_version") or "unknown")}

    version = str(payload.get("schema_version") or "unknown").strip()
    _emit_version_seen(kind, version)

    if version != "v2":
        if CONTRACTS_REJECT_UNKNOWN:
            return {"ok": False, "errors": ["schema_version_invalid"], "version": version}
        # soft mode → emit violation and pass
        _emit_violation(kind, "schema_version_unknown", {"version": version})
        return {"ok": True, "errors": [], "version": version}

    # version == v2 → jsonschema validation
    schema = _schema_for(kind)
    ok, errs, tag = _validate_jsonschema(payload, schema)
    if not ok:
        _emit_violation(kind, tag, {"errors": errs[:3]})
    return {"ok": bool(ok), "errors": errs, "version": "v2"}


__all__ = ["validate"]

