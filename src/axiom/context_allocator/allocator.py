#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from .buckets import bucketize
from .scoring import score


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return int(default)


def estimate_tokens(text: str) -> int:
    # Cheap estimate: 1 token ~ 4 chars
    try:
        return max(1, int(len((text or "")) / 4))
    except Exception:
        return 1


def allocate(items: List[Dict[str, Any]], token_budget: int | None = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    budget = int(token_budget or _env_int("CONTEXT_TOKEN_BUDGET", 6000))
    min_per = _env_int("CONTEXT_MIN_PER_BUCKET", 1)
    max_per = _env_int("CONTEXT_MAX_PER_BUCKET", 4)

    # Score and annotate tokens
    enriched: List[Dict[str, Any]] = []
    for it in items or []:
        txt = it.get("content") or it.get("text") or it.get("statement") or ""
        enriched.append({**it, "_score": score(it), "_tokens": estimate_tokens(txt)})

    buckets = bucketize(enriched)
    # Seed diversity: take min_per best from each bucket first
    chosen: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    tokens_used = 0
    for key, arr in buckets.items():
        arr.sort(key=lambda x: x.get("_score", 0.0), reverse=True)
        take = min(min_per, len(arr))
        for x in arr[:take]:
            if tokens_used + x["_tokens"] <= budget:
                chosen.append(x)
                tokens_used += x["_tokens"]
            else:
                dropped.append(x)
        buckets[key] = arr[take:]

    # Greedy fill by score/tokens across remaining items, respecting max_per per bucket
    # Build heap of candidates with bucket counts
    per_bucket_counts: Dict[str, int] = {}
    # Flatten remaining
    rest: List[Tuple[str, Dict[str, Any]]] = []
    for key, arr in buckets.items():
        for x in arr:
            rest.append((key, x))
    rest.sort(key=lambda kv: kv[1].get("_score", 0.0) / max(1, kv[1].get("_tokens", 1)), reverse=True)

    for key, x in rest:
        cnt = per_bucket_counts.get(key, 0)
        if cnt >= max_per:
            dropped.append(x)
            continue
        if tokens_used + x["_tokens"] <= budget:
            chosen.append(x)
            per_bucket_counts[key] = cnt + 1
            tokens_used += x["_tokens"]
        else:
            dropped.append(x)

    stats = {
        "tokens_used": int(tokens_used),
        "truncated_count": int(len(dropped)),
        "diversity_buckets": int(len(set([b for (b, _) in rest])))
    }

    # Strip helper fields
    def _strip(xs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for x in xs:
            y = dict(x)
            y.pop("_score", None)
            y.pop("_tokens", None)
            out.append(y)
        return out

    return _strip(chosen), _strip(dropped), stats


__all__ = ["allocate", "estimate_tokens"]

