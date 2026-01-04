#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Any, Tuple
import logging
import os
import logging

try:
    from pods.cockpit.cockpit_reporter import write_signal
except Exception:  # soft fallback
    def write_signal(pod_name: str, signal_name: str, payload: dict) -> None:  # type: ignore
        try:
            pass
        except Exception:
            pass


def make_contradiction_object(belief_id: str, counter_belief_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "contradiction",
        "belief": str(belief_id),
        "counter": str(counter_belief_id),
        "context": dict(context or {}),
    }


def ensure_provenance(belief_payload: Dict[str, Any]) -> Tuple[bool, str]:
    prov = belief_payload.get("provenance")
    if prov in (None, "", [], {}):
        try:
            logging.getLogger(__name__).warning("[RECALL][Governor] violation=missing_provenance")
        except Exception:
            pass
        return False, "missing_provenance"
    return True, ""


def report_contradiction(belief_id: str, counter_belief_id: str) -> None:
    try:
        # Fail-closed: if cockpit signal dir is unset, skip emission but log enforcement
        if not (os.getenv("COCKPIT_SIGNAL_DIR") or ""):
            try:
                logging.getLogger(__name__).warning("[RECALL][Governor] signal_skipped=belief_contradiction reason=signal_dir_unset")
            except Exception:
                pass
            return
        write_signal(
            "governor",
            "belief_contradiction",
            {"belief": str(belief_id), "counter": str(counter_belief_id)},
        )
    except Exception:
        try:
            logging.getLogger(__name__).warning("[RECALL][Governor] signal_skipped=belief_contradiction reason=exception")
        except Exception:
            pass

