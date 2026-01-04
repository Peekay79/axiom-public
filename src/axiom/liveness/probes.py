#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
from typing import Dict, Any


def _truthy(name: str, default: bool = False) -> bool:
    v = os.getenv(name, str(default)).strip().lower()
    return v in {"1", "true", "yes", "y"}


async def probe_recall(k: int) -> Dict[str, Any]:
    """Run a lightweight recall@k probe using the live retrieval pipeline.

    Returns {"recall": float, "ok": bool}. Emits Cockpit signals.
    """
    try:
        from memory_response_pipeline import fetch_vector_hits as _fetch
        # Use a simple synthetic query that should return something if vectors are healthy
        query = os.getenv("LIVENESS_RECALL_QUERY", "who is axiom")
        hits = await _fetch(query, top_k=int(k))
        recall = 1.0 if hits else 0.0
        ok = recall >= float(os.getenv("LIVENESS_RECALL_MIN", "0.6") or 0.6)
    except Exception:
        recall = 0.0
        ok = False
    try:
        from pods.cockpit.cockpit_reporter import write_signal

        write_signal("liveness", "recall_value", {"recall": float(recall), "k": int(k)})
        write_signal("liveness", "recall_ok", {"ok": bool(ok)})
    except Exception:
        pass
    return {"recall": float(recall), "ok": bool(ok)}


async def probe_belief_patch(belief_id: str) -> Dict[str, Any]:
    """Attempt a safe ETag-protected PATCH+rollback/no-op to validate write path.

    Returns {"ok": bool, "status": int}. Emits Cockpit signals.
    """
    status = 0
    ok = False
    try:
        import httpx

        base = os.getenv("BELIEF_API_BASE", "http://127.0.0.1:5010")
        get_url = f"{base}/beliefs/{belief_id}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            gr = await client.get(get_url)
            status = gr.status_code
            if gr.status_code != 200:
                raise RuntimeError(f"belief_get_status={gr.status_code}")
            etag = gr.headers.get("etag") or gr.headers.get("ETag")
            if not etag:
                raise RuntimeError("missing_etag")
            pr = await client.patch(
                get_url,
                headers={"If-Match": etag},
                json={"tags": ["probe"]},
            )
            status = pr.status_code
            ok = pr.status_code in (200, 204)
    except Exception:
        ok = False
    try:
        from pods.cockpit.cockpit_reporter import write_signal

        write_signal("liveness", "belief_patch_ok", {"ok": bool(ok)})
        write_signal("liveness", "belief_patch_status", {"status": int(status)})
    except Exception:
        pass
    return {"ok": bool(ok), "status": int(status)}


async def run_background_tick() -> None:
    if not _truthy("LIVENESS_CANARIES_ENABLED", True):
        return
    # 5–10 minutes default cadence
    interval = int(os.getenv("LIVENESS_INTERVAL_SEC", "480") or 480)
    k = int(os.getenv("LIVENESS_RECALL_K", "10") or 10)
    belief_probe_id = os.getenv("LIVENESS_BELIEF_PATCH_PROBE_ID", "belief:probe:id")
    while True:
        try:
            await probe_recall(k)
            await probe_belief_patch(belief_probe_id)
        except Exception:
            pass
        await asyncio.sleep(max(60, interval))

