#!/usr/bin/env python3
"""Typed environment variable accessors for the memory subsystem.

Provides small helpers to read environment variables with correct types and
warning logs for deprecated aliases.

This module is intentionally tiny and import-safe.
"""
from __future__ import annotations

import logging
import os
from typing import Optional


_logger = logging.getLogger(__name__)

# Deprecated aliases -> canonical names
_ALIASES = {
    # Phase 2 contradictions staleness threshold
    "STALENESS_DAYS": "AXIOM_CONTRADICTION_STALENESS_DAYS",
}

_WARNED: set[str] = set()


def _resolve_name(name: str) -> tuple[str, Optional[str]]:
    """Return tuple (effective_name, alias_used) if a deprecated alias is set.

    If the canonical name is unset but a known alias is set, return the alias
    value by indicating the alias in the second tuple element, so that callers
    can emit a one-time warning.
    """
    if name in os.environ:
        return name, None
    # Check alias only if canonical missing
    alias = None
    for a, canonical in _ALIASES.items():
        if canonical == name and a in os.environ:
            alias = a
            break
    return (alias or name), (alias if alias else None)


def _maybe_warn_alias(alias: Optional[str], canonical: str) -> None:
    if not alias:
        return
    key = f"{alias}->{canonical}"
    if key in _WARNED:
        return
    _WARNED.add(key)
    try:
        _logger.warning(
            "[config] Environment variable '%s' is DEPRECATED. Use '%s' instead.",
            alias,
            canonical,
        )
    except Exception:
        # Fallback to print in environments without configured logging
        print(
            f"[config] WARNING: Env var '{alias}' is DEPRECATED. Use '{canonical}' instead.")


def get_env_str(name: str, default: str = "") -> str:
    """Return string env value with alias support.

    If the canonical name is unset but a deprecated alias is set, returns the
    alias value and logs a warning once.
    """
    effective, alias = _resolve_name(name)
    if effective in os.environ:
        if alias:
            _maybe_warn_alias(alias, name)
        return str(os.getenv(effective, default))
    return str(default)


def get_env_int(name: str, default: int = 0) -> int:
    """Return integer env value (base 10) with safe parsing and alias support."""
    raw = get_env_str(name, str(default))
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


def get_env_flag(name: str, default: bool = False) -> bool:
    """Return boolean flag from common truthy/falsey strings with alias support."""
    raw = get_env_str(name, "1" if default else "0")
    s = str(raw).strip().lower()
    return s in {"1", "true", "yes", "on"}


__all__ = ["get_env_flag", "get_env_int", "get_env_str"]

