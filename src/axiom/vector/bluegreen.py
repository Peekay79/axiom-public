#!/usr/bin/env python3
from __future__ import annotations

# Backwards-compat shim to re-export retrieval.bluegreen helpers
try:
    from retrieval.bluegreen import record_recall_eval, maybe_cutover  # type: ignore
except Exception:  # pragma: no cover - optional
    def record_recall_eval(*args, **kwargs):
        return None
    def maybe_cutover(*args, **kwargs):
        return (False, None, None)

__all__ = ["record_recall_eval", "maybe_cutover"]

