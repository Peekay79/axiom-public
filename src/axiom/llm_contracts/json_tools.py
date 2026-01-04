#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from . import PROMPT_CONTRACTS_ENABLED


@dataclass
class ContractViolation(Exception):
    reason: str
    detail: str | None = None

    def __str__(self) -> str:
        if self.detail:
            return f"{self.reason}: {self.detail}"
        return self.reason


def _cockpit_signal(signal_name: str, payload: dict) -> None:
    """Emit Cockpit signal if reporter is available; best‑effort, never raise."""
    try:
        from pods.cockpit.cockpit_reporter import write_signal  # type: ignore

        write_signal("governor", signal_name, payload)
    except Exception:
        # fail‑closed on observability; core logic must not depend on this
        pass


def _load_schema(tool_name: str) -> dict | None:
    try:
        here = Path(__file__).parent
        schema_path = here / "schemas" / "v1" / f"{tool_name}.json"
        if not schema_path.exists():
            return None
        import json as _json

        with open(schema_path, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return None


def _validate(instance: dict, schema: dict | None) -> tuple[bool, str | None]:
    if schema is None:
        return True, None
    try:
        try:
            from jsonschema import validate  # type: ignore
        except Exception:
            # jsonschema missing → accept but emit violation (fail‑closed)
            _cockpit_signal(
                "prompt_contracts.violation.schema",
                {"reason": "jsonschema_unavailable", "tool": instance.get("tool_name")},
            )
            return True, None
        validate(instance=instance, schema=schema)  # may raise
        return True, None
    except Exception as e:  # ValidationError or other
        return False, f"{e.__class__.__name__}: {str(e)}"


def _normalize_fields(tool_name: str, payload: dict) -> dict:
    out = dict(payload)
    def _trim(v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, list):
            return [_trim(x) for x in v]
        if isinstance(v, dict):
            return {k: _trim(val) for k, val in v.items()}
        return v

    out = _trim(out)
    out["tool_name"] = tool_name
    # If Contracts v2 is enabled and the tool is stateful, attach v2 tag; otherwise default to v1
    try:
        if str(os.getenv("CONTRACTS_V2_ENABLED", "true")).strip().lower() in {"1", "true", "yes", "y"}:
            stateful_tools = os.getenv("STATEFUL_TOOLS") or ""
            known = [t.strip() for t in stateful_tools.split(",") if t.strip()] or [
                "write_memory",
                "update_belief",
                "append_journal",
            ]
            if tool_name in known:
                out["schema_version"] = "v2"
            else:
                out["schema_version"] = "v1"
        else:
            out["schema_version"] = "v1"
    except Exception:
        out["schema_version"] = "v1"
    return out


def _extract_first_last_json_block(text: str) -> dict | None:
    # Try to extract first balanced JSON object between the first '{' and last '}'
    try:
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            cand = text[first : last + 1]
            return json.loads(cand)
    except Exception:
        pass

    # Try fenced code block ```json ... ```
    try:
        m = re.search(r"```json\s*([\s\S]*?)```", text, re.IGNORECASE)
        if m:
            return json.loads(m.group(1))
    except Exception:
        pass
    return None


def call(tool_name: str, raw_text: str) -> Dict[str, Any]:
    """
    Parse strict JSON; on failure, try to salvage the first/last JSON block; 
    if still invalid, raise ContractViolation("invalid_json").

    Validate against schemas/v1/<tool_name>.json (jsonschema if available). If
    schema absent or jsonschema unavailable → accept but emit
    governor/prompt_contracts violation. Normalize fields and attach metadata.
    """
    # Unknown tool detection (emit signal but continue)
    stateful_tools = os.getenv("STATEFUL_TOOLS") or ""
    known = [t.strip() for t in stateful_tools.split(",") if t.strip()] or [
        "write_memory",
        "update_belief",
        "append_journal",
    ]
    if tool_name not in known:
        _cockpit_signal(
            "prompt_contracts.violation.unknown_tool",
            {"tool": tool_name},
        )

    text = (raw_text or "").strip()
    try:
        payload = json.loads(text)
    except Exception:
        payload = _extract_first_last_json_block(text)
        if payload is None:
            _cockpit_signal(
                "prompt_contracts.violation.invalid_json",
                {"tool": tool_name, "preview": text[:160]},
            )
            # Strict path: raise. Fallback handled by caller gating
            raise ContractViolation("invalid_json", detail="no_json_found")

    # Validate (best‑effort)
    schema = _load_schema(tool_name)
    ok, detail = _validate(payload, schema)
    if not ok:
        _cockpit_signal(
            "prompt_contracts.violation.schema",
            {"tool": tool_name, "detail": detail or "schema_validation_failed"},
        )
        # Keep accepting; contracts are enforced at the edges; do not throw here

    # Normalize and attach metadata
    normalized = _normalize_fields(tool_name, payload)
    return normalized


__all__ = ["ContractViolation", "call"]

