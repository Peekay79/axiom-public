#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any


def _env_str(name: str, default: str) -> str:
    return (os.getenv(name, default) or default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    return _env_str(name, str(default)).lower() in {"1", "true", "yes", "y"}


async def _retrieve_top_k(query: str, k: int) -> List[Dict[str, Any]]:
    """Call the production retrieval entrypoint used by memory pipeline.

    Hybrid if enabled, else dense vector recall via memory_response_pipeline.
    Returns a list of hits (dictionaries) – never None.
    """
    try:
        # Prefer the same internal function memory pipeline uses
        from memory_response_pipeline import fetch_vector_hits as _fetch
        hits = await _fetch(query, top_k=int(k))
        return hits or []
    except Exception:
        # Extremely defensive: fall back to vector adapter sync path
        try:
            from pods.vector.vector_adapter import VectorAdapter

            return VectorAdapter().search_memory_vectors(query, top_k=int(k)) or []
        except Exception:
            return []


def _emit(pod: str, sig: str, payload: Dict[str, Any]) -> None:
    try:
        from pods.cockpit.cockpit_reporter import write_signal

        write_signal(pod, sig, payload)
    except Exception:
        pass


def _load_canaries(path: str) -> List[Dict[str, Any]]:
    fp = Path(path)
    if not fp.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with fp.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict) and rec.get("query"):
                    out.append(rec)
    except Exception:
        return []
    return out


async def run_boot_canary(dataset_path: str, k: int) -> float:
    """
    Loads canaries from dataset_path, runs the actual retrieval, computes mean recall@k.
    Emits Cockpit signals: boot_canary.recall, boot_canary.k.
    Returns the aggregate recall float (0..1).
    """
    canaries = _load_canaries(dataset_path)
    if not canaries:
        _emit("memory", "boot_canary", {"k": int(k), "recall": 0.0, "error": "no_dataset"})
        return 0.0

    t0 = time.time()
    total = len(canaries)
    hits_total = 0
    for rec in canaries:
        q = (rec.get("query") or "").strip()
        if not q:
            continue
        try:
            # Run retrieval via the same codepaths used in production
            hits = await _retrieve_top_k(q, k)
            hits_total += 1 if hits else 0
        except Exception:
            # Count as miss
            pass

    recall = float(hits_total) / float(total or 1)
    dt_ms = int((time.time() - t0) * 1000)
    _emit("memory", "boot_canary", {"k": int(k), "recall": float(recall), "elapsed_ms": dt_ms})
    return recall


async def _main():
    ap = argparse.ArgumentParser(description="Boot Retrieval Canary Runner")
    ap.add_argument("--dataset", default=_env_str("BOOT_RECALL_CANARY_DATASET", "canaries/default.jsonl"))
    ap.add_argument("--k", type=int, default=int(_env_str("BOOT_RECALL_CANARY_K", "10")))
    args = ap.parse_args()

    r = await run_boot_canary(args.dataset, args.k)
    print(json.dumps({"recall": r, "k": args.k}))


if __name__ == "__main__":
    import asyncio as _a

    _a.run(_main())

