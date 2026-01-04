#!/usr/bin/env python3
from __future__ import annotations

import math
import statistics
from typing import List

try:
    from pods.cockpit.cockpit_reporter import write_signal
except Exception:  # soft fallback
    def write_signal(pod_name: str, signal_name: str, payload: dict) -> None:  # type: ignore
        try:
            pass
        except Exception:
            pass


def sample_vector_norm(vec: List[float] | None) -> float:
    if not vec:
        return 0.0
    try:
        return math.sqrt(sum((v or 0.0) * (v or 0.0) for v in vec))
    except Exception:
        return 0.0


def report_embedding_stats(namespace: str, norms: List[float]) -> None:
    if not norms:
        return
    try:
        p95 = None
        try:
            qs = statistics.quantiles(norms, n=100)
            p95 = qs[94]
        except Exception:
            # Fallback approximate
            p95 = sorted(norms)[int(max(0, len(norms) - 1) * 0.95) or 0]
        write_signal(
            "governor",
            f"embedding_stats.{namespace}",
            {"n": len(norms), "mean": statistics.fmean(norms), "p95": float(p95)},
        )
    except Exception:
        pass


def report_recall_cohort(namespace: str, cohort: str, k: int, hits: int, total: int) -> None:
    recall = (float(hits) / float(total)) if total else 0.0
    try:
        write_signal(
            "governor",
            f"recall_cohort.{namespace}.{cohort}",
            {"k": int(k or 0), "hits": int(hits or 0), "total": int(total or 0), "recall": float(recall)},
        )
    except Exception:
        pass


def bm25_baseline_hook(query: str) -> list[str]:
    """Placeholder hook: return top ids from BM25 if available, else []."""
    return []

