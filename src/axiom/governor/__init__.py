#!/usr/bin/env python3
"""
Governor – Contracts & Invariants (Phase 5)

Flag-gated helpers for correlation IDs, idempotency, saga observability,
retrieval quality monitors, belief governance, and schema validation.

All helpers are additive and fail-closed by design. Integrations at pod edges
should read env flags and choose strict vs soft behavior.
"""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name, "")
    if val is None:
        return bool(default)
    return str(val).strip().lower() in {"1", "true", "yes", "y"}


def governor_enabled() -> bool:
    return _env_bool("GOVERNOR_ENABLED", True)


def strict_mode() -> bool:
    return _env_bool("GOVERNOR_STRICT_MODE", False)


def require_correlation_id() -> bool:
    return _env_bool("GOVERNOR_REQUIRE_CORRELATION_ID", True)


def require_idempotency() -> bool:
    return _env_bool("GOVERNOR_REQUIRE_IDEMPOTENCY", True)


def retrieval_monitor_enabled() -> bool:
    return _env_bool("GOVERNOR_RETRIEVAL_MONITOR_ENABLED", True)


def belief_governance_enabled() -> bool:
    return _env_bool("GOVERNOR_BELIEF_GOVERNANCE_ENABLED", True)


__all__ = [
    "governor_enabled",
    "strict_mode",
    "require_correlation_id",
    "require_idempotency",
    "retrieval_monitor_enabled",
    "belief_governance_enabled",
]

