#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .scoring import diversity_key


def bucketize(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for it in items or []:
        k = diversity_key(it)
        buckets.setdefault(k, []).append(it)
    return buckets


__all__ = ["bucketize"]

