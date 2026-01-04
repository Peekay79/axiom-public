#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from memory.utils.time_utils import utc_now_iso

try:
    import journal as _journal  # type: ignore

    _HAS_JOURNAL = True
except Exception:
    _HAS_JOURNAL = False

try:
    from logbook import log_event as _logbook_event  # type: ignore

    _HAS_LOGBOOK = True
except Exception:
    _HAS_LOGBOOK = False


def safe_log_event(event: Dict[str, Any], default_source: str) -> None:
    """Safely emit a structured event to journal/logbook.

    - Ensures created_at and uuid fields
    - Fills missing source with default_source
    - Never raises
    """
    try:
        if not isinstance(event, dict):
            return

        if "created_at" not in event or not event.get("created_at"):
            event["created_at"] = utc_now_iso()

        if "uuid" not in event or not str(event.get("uuid") or "").strip():
            try:
                event["uuid"] = str(uuid4())
            except Exception:
                # best-effort only
                pass

        if not event.get("source"):
            event["source"] = default_source

        # Primary journal sink (resolve dynamically to support late injection in tests)
        target = None
        try:
            # Prefer a runtime-injected journal module if present (tests may override)
            import sys as _sys  # local import to avoid module-level cost

            injected = _sys.modules.get("journal")
        except Exception:
            injected = None
        if injected is not None and hasattr(injected, "log_event"):
            target = injected
        elif _HAS_JOURNAL and hasattr(_journal, "log_event"):
            target = _journal
        if target is not None and hasattr(target, "log_event"):
            try:
                target.log_event(event)  # type: ignore[attr-defined]
            except Exception:
                pass

        # Cognitive logbook (secondary sink)
        if _HAS_LOGBOOK:
            try:
                _logbook_event(
                    event_type=str(event.get("type", "event")),
                    payload=event,
                    source=str(event.get("source")),
                )
            except Exception:
                pass
    except Exception:
        # Never raise from logging
        pass


__all__ = ["safe_log_event"]
