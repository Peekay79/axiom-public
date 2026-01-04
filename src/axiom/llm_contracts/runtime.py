#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict

from . import PROMPT_CONTRACTS_ENABLED
from .decode_policy import apply_deterministic_kwargs, is_stateful
from .json_tools import call as parse_tool_json
from governor.middleware import ensure_correlation_and_idempotency


def _enabled() -> bool:
    return str(os.getenv("PROMPT_CONTRACTS_ENABLED", "true")).strip().lower() == "true"


def _try_parse_json_best_effort(text: str) -> Dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    # salvage fenced JSON
    try:
        m = re.search(r"```json\s*([\s\S]*?)```", text, re.IGNORECASE)
        if m:
            return json.loads(m.group(1))
    except Exception:
        pass
    # salvage by first/last brace
    try:
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            return json.loads(text[first : last + 1])
    except Exception:
        pass
    return None


def run_tool(
    tool_name: str,
    model_kwargs: Dict[str, Any],
    llm_generate_fn: Callable[[Dict[str, Any]], str] | None,
    raw_text_response: str,
) -> Dict[str, Any]:
    """
    Parse tool response and enforce deterministic decode for stateful tools.

    - When PROMPT_CONTRACTS_ENABLED and tool is stateful:
      • apply deterministic kwargs (temperature/top_p)
      • parse+validate JSON payload against v1 schema
      • attach Governor correlation + idempotency headers
    - Else legacy best‑effort JSON parse or raw passthrough.

    Note: llm_generate_fn is accepted for symmetry with some orchestrators but
    is not used in this minimal helper; call sites may pass None.
    """
    if _enabled() and is_stateful(tool_name):
        # Ensure deterministic generation settings are applied upstream if used
        try:
            _ = apply_deterministic_kwargs(model_kwargs or {})
        except Exception:
            pass

        payload = parse_tool_json(tool_name, raw_text_response)
        headers = ensure_correlation_and_idempotency({}, payload, require_cid=True, require_idem=True)
        payload["_headers"] = headers
        return payload

    # Legacy fallback (non‑stateful or disabled)
    best = _try_parse_json_best_effort(raw_text_response)
    if isinstance(best, dict):
        return best
    return {"raw": raw_text_response}


__all__ = ["run_tool"]

