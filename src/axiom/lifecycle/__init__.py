#!/usr/bin/env python3
"""Lifecycle utilities: journal compaction and Qdrant snapshots.

Additive, env-gated helpers for data hygiene tasks. Import-safe.
"""

from __future__ import annotations

__all__ = [
    "compaction",
    "snapshot",
]

