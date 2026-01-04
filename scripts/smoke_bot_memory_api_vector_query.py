#!/usr/bin/env python3
"""
Smoke test: Memory API retrieval-only recall

Validates that the Memory API can serve vector hits without requiring any LLM config:
  POST {MEMORY_API_URL}/vector/query
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def fail(msg: str) -> "None":
    print(f"[SMOKE][memory_api_vector_query] FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    try:
        import requests  # type: ignore
    except Exception as e:
        fail(f"requests not available: {type(e).__name__}")

    base = (os.getenv("MEMORY_API_URL") or os.getenv("MEMORY_POD_URL") or "").strip().rstrip("/")
    if not base:
        fail("MEMORY_API_URL (or MEMORY_POD_URL) is not set")

    query = (os.getenv("SMOKE_VECTOR_QUERY_TEXT") or "CHAMP algorithm").strip()
    url = f"{base}/vector/query"

    r = requests.post(url, json={"query": query, "top_k": 5}, timeout=10)
    if r.status_code != 200:
        fail(f"expected HTTP 200, got {r.status_code}")

    # Respect explicit error headers (treat as failure for the smoke test).
    err_code = r.headers.get("X-Axiom-Error-Code")
    if err_code:
        fail(f"X-Axiom-Error-Code={err_code}")

    try:
        data: Any = r.json()
    except Exception as e:
        fail(f"invalid JSON: {type(e).__name__}")

    items = (data or {}).get("items")
    if not isinstance(items, list):
        fail("response missing .items array")

    print(
        json.dumps(
            {
                "ok": True,
                "url": base,
                "items": len(items),
                "query": query,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

