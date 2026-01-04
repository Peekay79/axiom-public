#!/usr/bin/env python3
"""Time utilities for consistent timestamp parsing and formatting.

AUDIT_OK: Centralized parsing for contradiction modules and others.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Union


def parse_timestamp(value: Optional[Union[str, int, float, datetime]]) -> datetime:
    """Parse various timestamp representations to a timezone-aware UTC datetime.

    Accepted inputs:
    - ISO 8601 strings, including those ending with 'Z'
    - Unix epoch seconds (int/float) or milliseconds (>= 10^12)
    - datetime (naive assumed UTC)
    - None -> epoch (1970-01-01 UTC)

    Always returns an aware datetime in UTC.
    """
    if value is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    # datetime passthrough
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    # numeric: epoch seconds or milliseconds
    if isinstance(value, (int, float)):
        # Heuristic: treat large numbers as milliseconds
        seconds = float(value) / (1000.0 if float(value) > 1_000_000_000_000 else 1.0)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except Exception:
            return datetime.fromtimestamp(0, tz=timezone.utc)
    # string: attempt ISO parsing
    try:
        s = str(value).strip()
        if not s:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def utc_now_iso() -> str:
    """Return current time in UTC ISO format."""
    return datetime.now(timezone.utc).isoformat()


__all__ = ["parse_timestamp", "utc_now_iso"]
