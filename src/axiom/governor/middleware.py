#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Any

from .ids import normalize_correlation_id, idempotency_key


_UNSAFE_HEADER_PREFIXES = ("X-Forwarded-", "X-Real-IP", "X-Client-IP")


def sanitize_headers(req_headers: Dict[str, Any] | None) -> Dict[str, str]:
    """Strip unsafe or hop-by-hop headers before forwarding.

    Fail-closed: if headers missing or invalid types, returns a safe empty dict.
    Logs enforcement with canonical Governor tag where possible.
    """
    try:
        headers: Dict[str, str] = {}
        for k, v in dict(req_headers or {}).items():
            ks = str(k)
            if any(ks.startswith(p) for p in _UNSAFE_HEADER_PREFIXES):
                # canonical recall tag for enforcement
                try:
                    import logging as _logging

                    _logging.getLogger(__name__).warning("[RECALL][Governor] enforcement=sanitize_header stripped=%s", ks)
                except Exception:
                    pass
                continue
            headers[ks] = str(v)
        return headers
    except Exception:
        return {}


def ensure_correlation_and_idempotency(
    req_headers: Dict[str, Any] | None,
    payload: Dict[str, Any] | None,
    require_cid: bool = True,
    require_idem: bool = True,
) -> Dict[str, str]:
    # Sanitize first
    headers: Dict[str, str] = sanitize_headers(req_headers)
    # Correlation ID
    if require_cid:
        cid = normalize_correlation_id(headers.get("X-Correlation-ID"))
        headers["X-Correlation-ID"] = cid
    else:
        cid = headers.get("X-Correlation-ID")  # optional

    # Idempotency key
    if require_idem:
        if not headers.get("Idempotency-Key"):
            headers["Idempotency-Key"] = idempotency_key(payload or {})

    return headers

