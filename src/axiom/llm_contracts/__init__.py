#!/usr/bin/env python3
"""
llm_contracts – Prompt Contracts enforcement (env‑gated, additive, fail‑closed)

Exports env‑resolved configuration and small helpers shared by modules in
this package. Defaults are conservative and disable any risky behaviour.
"""
from __future__ import annotations

import json
import os
from typing import List


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name, str(default))
    return str(val).strip().lower() in {"1", "true", "yes", "y"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    s = raw.strip()
    # Allow JSON array or comma‑separated values
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr]
        except Exception:
            pass
    return [p.strip() for p in s.split(",") if p.strip()]


# ── Feature gates and defaults (Config/ENV) ───────────────────────────────────
PROMPT_CONTRACTS_ENABLED: bool = _env_bool("PROMPT_CONTRACTS_ENABLED", True)
STATEFUL_TOOLS: List[str] = _env_list(
    "STATEFUL_TOOLS", ["write_memory", "update_belief", "append_journal"]
)
DETERMINISTIC_TEMP: float = _env_float("DETERMINISTIC_TEMP", 0.0)
DETERMINISTIC_TOP_P: float = _env_float("DETERMINISTIC_TOP_P", 1.0)


__all__ = [
    "PROMPT_CONTRACTS_ENABLED",
    "STATEFUL_TOOLS",
    "DETERMINISTIC_TEMP",
    "DETERMINISTIC_TOP_P",
]

