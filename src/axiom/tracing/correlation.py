#!/usr/bin/env python3
"""
Tiny correlation helper for request IDs.

Rules:
- If X-Request-ID is present and non-empty in incoming headers, use it.
- Otherwise generate a fresh uuid4 hex.
"""

from __future__ import annotations

from typing import Mapping, Optional, Any
from uuid import uuid4


HEADER_NAME: str = "X-Request-ID"


def get_or_create_request_id(incoming_headers: Optional[Mapping[str, Any]]) -> str:
    """Return an existing X-Request-ID or generate a new one.

    Accepts any mapping-like object supporting .get(). Safe for None.
    """
    try:
        if incoming_headers and hasattr(incoming_headers, "get"):
            rid = incoming_headers.get(HEADER_NAME)  # type: ignore[arg-type]
            if isinstance(rid, str) and rid.strip():
                return rid.strip()
    except Exception:
        # Fall through to generation on any unexpected error
        pass
    return uuid4().hex

