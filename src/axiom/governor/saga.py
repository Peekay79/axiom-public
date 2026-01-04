#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
from typing import Dict, Any

try:
    from pods.cockpit.cockpit_reporter import write_signal
except Exception:  # soft fallback to avoid import-time crash
    def write_signal(pod_name: str, signal_name: str, payload: dict) -> None:  # type: ignore
        try:
            pass
        except Exception:
            pass


log = logging.getLogger(__name__)


def _truthy(val: str | None, default: bool = False) -> bool:
    if val is None:
        return bool(default)
    return str(val).strip().lower() in {"1", "true", "yes", "on", "y"}


def _saga_enabled() -> bool:
    try:
        return _truthy(os.getenv("AXIOM_SAGA_ENABLED"), False)
    except Exception:
        return False


def _record(kind: str) -> None:
    # Best-effort vitals counter
    try:
        from cognitive_vitals import vitals  # type: ignore

        if kind == "begin":
            vitals.record_saga_event("begin")
        elif kind == "end_ok":
            vitals.record_saga_event("end_ok")
        elif kind == "end_fail":
            vitals.record_saga_event("end_fail")
    except Exception:
        pass


def saga_begin(correlation_id: str, saga_type: str, meta: Dict[str, Any] | None = None) -> None:
    if not _saga_enabled():
        try:
            log.info("[RECALL][Saga] disabled")
        except Exception:
            pass
        return
    _record("begin")
    try:
        log.info(f"[RECALL][Saga] begin cid={correlation_id} type={saga_type}")
    except Exception:
        pass
    write_signal("governor", f"saga_begin.{saga_type}", {"cid": correlation_id, "meta": meta or {}})


def saga_step(
    correlation_id: str,
    saga_type: str,
    step: str,
    ok: bool,
    info: Dict[str, Any] | None = None,
) -> None:
    if not _saga_enabled():
        try:
            log.info("[RECALL][Saga] disabled")
        except Exception:
            pass
        return
    try:
        tag = "ok" if ok else "fail"
        log.info(f"[RECALL][Saga] step {tag} cid={correlation_id} type={saga_type} step={step}")
    except Exception:
        pass
    write_signal(
        "governor",
        f"saga_step.{saga_type}.{step}",
        {"cid": correlation_id, "ok": bool(ok), "info": info or {}},
    )


def saga_end(correlation_id: str, saga_type: str, ok: bool, summary: Dict[str, Any] | None = None) -> None:
    if not _saga_enabled():
        try:
            log.info("[RECALL][Saga] disabled")
        except Exception:
            pass
        return
    _record("end_ok" if ok else "end_fail")
    try:
        tag = "ok" if ok else "fail"
        log.info(f"[RECALL][Saga] end {tag} cid={correlation_id} type={saga_type}")
    except Exception:
        pass
    write_signal("governor", f"saga_end.{saga_type}", {"cid": correlation_id, "ok": bool(ok), "summary": summary or {}})

