#!/usr/bin/env python3
"""
Project Cockpit – Reporter (Phase 1)

Lightweight helper to emit per‑pod readiness, error, heartbeat, and custom JSON signals.

Usage inside a pod:
    from pods.cockpit.cockpit_reporter import mark_ready, mark_error, heartbeat, write_signal

    # On successful init:
    mark_ready("vector")

    # On fatal init fail:
    mark_error("vector", "qdrant connection failed")

    # Background task (e.g., every 30s):
    heartbeat("vector")
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

# Root directory for signal files (configurable)
SIGNAL_DIR = Path(os.environ.get("COCKPIT_SIGNAL_DIR", "axiom_boot"))


def _ensure_dir() -> None:
    try:
        SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # Never crash caller; just log best-effort
        try:
            logging.getLogger(__name__).warning("[cockpit] failed to create signal dir: %s", e)
        except Exception:
            pass


def mark_ready(pod_name: str) -> None:
    """Create/overwrite <pod>.ready with UTC timestamp."""
    _ensure_dir()
    try:
        (SIGNAL_DIR / f"{pod_name}.ready").write_text(datetime.utcnow().isoformat())
    except Exception as e:
        try:
            logging.getLogger(__name__).error("[cockpit] mark_ready failed: %s", e)
        except Exception:
            pass


def mark_start(pod_name: str) -> None:
    """Call as early as possible in pod boot (before heavy imports)."""
    _ensure_dir()
    try:
        (SIGNAL_DIR / f"{pod_name}.start").write_text(datetime.utcnow().isoformat())
    except Exception as e:
        try:
            logging.getLogger(__name__).warning("[cockpit] mark_start failed: %s", e)
        except Exception:
            pass


def mark_error(pod_name: str, message: str) -> None:
    """Create/overwrite <pod>.error with UTC timestamp and message."""
    _ensure_dir()
    try:
        (SIGNAL_DIR / f"{pod_name}.error").write_text(
            f"{datetime.utcnow().isoformat()} {message}"
        )
    except Exception as e:
        try:
            logging.getLogger(__name__).error("[cockpit] mark_error failed: %s", e)
        except Exception:
            pass


def heartbeat(pod_name: str) -> None:
    """Create/overwrite <pod>.last_heartbeat with UTC timestamp."""
    _ensure_dir()
    try:
        (SIGNAL_DIR / f"{pod_name}.last_heartbeat").write_text(
            datetime.utcnow().isoformat()
        )
    except Exception as e:
        try:
            logging.getLogger(__name__).warning("[cockpit] heartbeat failed: %s", e)
        except Exception:
            pass


def write_signal(pod_name: str, signal_name: str, payload: dict) -> None:
    """Write custom JSON signal to <pod>.<signal_name>.json using standard schema.

    Schema payload format:
        {"pod": pod_name, "signal": signal_name, "ts": iso8601, "data": payload}

    If schema validation fails (or dependency missing), write anyway (fail-closed).
    """
    _ensure_dir()
    record = {
        "pod": pod_name,
        "signal": signal_name,
        "ts": datetime.utcnow().isoformat(),
        "data": payload or {},
    }
    # Try to validate against cockpit_schema.json if jsonschema is available
    try:
        try:
            from jsonschema import validate  # type: ignore
        except Exception:
            validate = None  # type: ignore

        schema_path = Path(__file__).with_name("cockpit_schema.json")
        if validate and schema_path.exists():
            import json as _json

            with open(schema_path, "r") as sf:
                schema = _json.load(sf)
            validate(instance=record, schema=schema)
    except Exception as e:
        try:
            logging.getLogger(__name__).warning(
                "[cockpit] schema validation skipped/failed: %s", e
            )
        except Exception:
            pass

    # Always write the record (fail-closed)
    try:
        with open(SIGNAL_DIR / f"{pod_name}.{signal_name}.json", "w") as f:
            json.dump(record, f)
    except Exception as e:
        try:
            logging.getLogger(__name__).warning("[cockpit] write_signal failed: %s", e)
        except Exception:
            pass


# ─────────────────────────────────────────────
# Resilience convenience reporters (optional)
# ─────────────────────────────────────────────
def report_budget_exceeded(kind: str) -> None:
    try:
        write_signal("resilience", f"budget_exceeded.{kind}", {})
    except Exception:
        pass


def report_breaker_event(dep: str, event: str) -> None:
    try:
        write_signal("resilience", f"breaker.{dep}.{event}", {})
    except Exception:
        pass


def report_degraded(active: bool, depth: int | None = None) -> None:
    try:
        write_signal("resilience", "degraded", {"active": bool(active), "depth": depth})
    except Exception:
        pass


# Optional: tiny background heartbeat runner (manual use)
def run_heartbeat(pod_name: str, interval_sec: int = 30) -> None:
    """Blocking loop to write heartbeat at interval. Caller should run in a thread."""
    interval_sec = max(1, int(interval_sec or 30))
    while True:
        try:
            heartbeat(pod_name)
        except Exception:
            pass
        time.sleep(interval_sec)


# Convenience wrappers (non-breaking additions)
def report_blocked_write(pod_name: str, reason: str) -> None:
    """Report a blocked write (e.g., due to role gating or policy)."""
    try:
        write_signal(pod_name, "blocked_write", {"reason": str(reason or "unknown")})
    except Exception:
        pass


def report_vector_recall(
    pod_name: str, ok: bool, latency_ms: int | None, err: str | None
) -> None:
    """Report a vector recall result (success/failure + latency).

    Args:
        ok: True if recall succeeded
        latency_ms: integer latency milliseconds if measured
        err: optional error string if failed
    """
    try:
        data = {"ok": bool(ok)}
        if latency_ms is not None:
            try:
                data["latency_ms"] = int(latency_ms)
            except Exception:
                data["latency_ms"] = None
        if err:
            data["err"] = str(err)
        write_signal(pod_name, "vector_recall", data)
    except Exception:
        pass


def report_journal_write_failure(pod_name: str, reason: str) -> None:
    """Report a journaling write failure (additive, fail-closed)."""
    try:
        write_signal(pod_name, "journal_write_failure", {"reason": str(reason or "unknown")})
    except Exception:
        pass


def report_belief_insert_failure(pod_name: str, reason: str) -> None:
    """Report a belief insertion failure (additive, fail-closed)."""
    try:
        write_signal(pod_name, "belief_insert_failure", {"reason": str(reason or "unknown")})
    except Exception:
        pass


def report_schema_normalization_event(
    pod_name: str, field: str, old: str, new: str, reason: str = "normalized"
) -> None:
    """Emit when an ingest path fixes/normalizes a payload field (e.g., memory_type)."""
    try:
        write_signal(
            pod_name,
            f"schema_normalization.{field}",
            {"field": field, "old": old, "new": new, "reason": reason},
        )
    except Exception:
        pass

