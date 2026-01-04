#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict

from . import (
    PROMPT_CONTRACTS_ENABLED,
    STATEFUL_TOOLS,
    DETERMINISTIC_TEMP,
    DETERMINISTIC_TOP_P,
)


def is_stateful(tool_name: str) -> bool:
    try:
        return str(tool_name or "").strip() in set(STATEFUL_TOOLS or [])
    except Exception:
        return False


def apply_deterministic_kwargs(kwargs: Dict) -> Dict:
    """Return a copy of kwargs with deterministic decode enforced.

    Sets temperature and top_p to env‑resolved deterministic values and disables
    multi‑sample gimmicks by forcing n=1. Does nothing if PROMPT_CONTRACTS is
    disabled – caller should still gate by is_stateful(tool).
    """
    out = dict(kwargs or {})
    if not PROMPT_CONTRACTS_ENABLED:
        return out
    out["temperature"] = DETERMINISTIC_TEMP
    out["top_p"] = DETERMINISTIC_TOP_P
    # Force single sample
    if "n" in out:
        out["n"] = 1
    # Remove settings that could introduce non‑determinism if present
    for k in ("top_k", "beam_width", "best_of"):
        if k in out:
            try:
                del out[k]
            except Exception:
                pass
    return out


__all__ = ["is_stateful", "apply_deterministic_kwargs"]

