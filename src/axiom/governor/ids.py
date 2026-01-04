#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Dict, Any


def new_correlation_id() -> str:
    return f"corr_{uuid.uuid4().hex}"


def normalize_correlation_id(value: str | None) -> str:
    return value if value and str(value).startswith("corr_") else new_correlation_id()


def idempotency_key(payload: Dict[str, Any]) -> str:
    try:
        # Canonicalize as stable tuple list; avoid json dumps differences
        items = sorted(list((payload or {}).items()), key=lambda kv: kv[0])
        data = repr(items).encode("utf-8")
    except Exception:
        data = b"{}"
    return "idem_" + hashlib.sha256(data).hexdigest()[:32]


def now_ms() -> int:
    return int(time.time() * 1000)

