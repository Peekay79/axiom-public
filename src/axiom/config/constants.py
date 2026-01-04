"""
Global constants for retrieval gating and similarity handling.

These defaults are intentionally conservative and can be overridden via
environment variables without requiring code changes.
"""

from __future__ import annotations

import os

# --- Coverage-aware gating thresholds ----------------------------------------
# Allow "don't-know" ONLY if both conditions hold:
#   1) coverage < COVERAGE_THRESHOLD
#   2) no chunk has similarity >= STRONG_SIM_THRESHOLD
# These are surfaced as env-configurable knobs while retaining explicit
# code-level defaults.

COVERAGE_THRESHOLD: float = float(os.getenv("COVERAGE_THRESHOLD", "0.35"))
STRONG_SIM_THRESHOLD: float = float(os.getenv("STRONG_SIM_THRESHOLD", "0.75"))

__all__ = [
    "COVERAGE_THRESHOLD",
    "STRONG_SIM_THRESHOLD",
]
