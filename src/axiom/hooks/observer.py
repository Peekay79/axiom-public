import json
import os
import re
import time
import hashlib
import random
from typing import Any, Dict, Optional

_SECRET_PATTERNS = [
    re.compile(r"(?:api|secret|token|key)\s*=\s*[\w\-\.]{12,}", re.I),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-\._]+"),
    re.compile(r"https?://[^\s]+"),
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),
]


def _scrub(text: str) -> str:
    if not text:
        return text
    redacted = text
    for pat in _SECRET_PATTERNS:
        redacted = pat.sub("[REDACTED]", redacted)
    return redacted


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _enabled(kind: str) -> bool:
    if os.getenv("ENABLE_OBSERVER", "false").lower() != "true":
        return False
    return os.getenv(f"ENABLE_OBSERVER_{kind.upper()}", "false").lower() == "true"


def observe(content: str, *, kind: str, meta: Optional[Dict[str, Any]] = None) -> None:
    """Non-blocking, fail-closed observer. Logs structured JSON to stdout when enabled.
    kind: 'memory'|'belief'|'journal'
    meta: optional dict (ids, confidence, importance, request_id, etc.)
    """
    try:
        if not _enabled(kind):
            return
        # sampling
        try:
            rate = float(os.getenv("OBSERVER_SAMPLE_RATE", "1.0"))
        except Exception:
            rate = 1.0
        if rate < 1.0 and random.random() > rate:
            return

        try:
            preview_len = int(os.getenv("OBSERVER_PREVIEW_CHARS", "512"))
        except Exception:
            preview_len = 512

        content = content or ""
        preview = content[:preview_len]
        event = {
            "ts": time.time(),
            "kind": kind,
            "preview": _scrub(preview),
            "content_sha256": _hash(content) if content else None,
            "meta": meta or {},
            "source": "observer",
            "version": 1,
        }
        # single-line JSON for ingestion
        print(json.dumps(event, ensure_ascii=False))
    except Exception:
        # Never raise; fail closed
        return

