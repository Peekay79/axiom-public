#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from memory.utils.belief_coercion import coerce_belief_dict
from memory.utils.journal import safe_log_event
from memory.utils.time_utils import utc_now_iso


def _safe_log(event: Dict[str, Any]) -> None:
    safe_log_event(event, default_source="contradiction_applier")


def _coerce_belief_dict(obj: Any) -> Dict[str, Any]:
    # Backward-compatible wrapper to the centralized coercion utility
    return coerce_belief_dict(obj)


def _tag_belief(belief: Any, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort in-place update of a belief-like object, returning a dict view.

    Supports objects with attributes or plain dicts. Never raises.
    """
    view = _coerce_belief_dict(belief)
    try:
        if isinstance(belief, dict):
            belief.update(updates)
        else:
            for k, v in updates.items():
                try:
                    setattr(belief, k, v)
                except Exception:
                    pass
        view.update(updates)
    except Exception:
        pass
    return view


def prompt_user_for_resolution(conflict: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a user intervention when confidence is low/ambiguous.

    Returns a dict similar to proposed_resolution with an added user_override flag.
    Logs a journal event type="contradiction_user_intervention".
    """
    # Heuristic: default to flag_for_review when uncertain
    choice = {
        "resolution_strategy": "flag_for_review",
        "confidence": float(conflict.get("confidence", 0.5) or 0.5),
        "notes": "User intervention requested due to low confidence/ambiguity.",
        "created_at": utc_now_iso(),
        "source": "contradiction_applier",
        "user_override": True,
    }
    try:
        bel1 = conflict.get("belief_1") or conflict.get("belief_a")
        bel2 = conflict.get("belief_2") or conflict.get("belief_b")
        _safe_log(
            {
                "type": "contradiction_user_intervention",
                "uuid": conflict.get("uuid"),
                "belief_1": str(bel1),
                "belief_2": str(bel2),
                "proposed_resolution": conflict.get("proposed_resolution"),
                "applied_resolution": choice,
            }
        )
    except Exception:
        pass
    return choice


def apply_contradiction_resolution(conflict: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the proposed resolution to the involved beliefs.

    - inhibit: tag weaker belief with {"inhibited": true}
    - reframe: add reframed_from to weaker belief or attach reframed_belief
    - flag_for_review: tag belief(s) with {"needs_review": true}
    - dream_resolution: emit/leave to Speculative Simulation Module (no-op here)

    Always logs a journal event type="contradiction_resolution_applied" with
    utc timestamps, belief identifiers, resolution type, and source.
    Returns updated conflict dict with applied_resolution attached.
    """
    resolution = dict(conflict.get("proposed_resolution") or {})
    strategy = (
        str(resolution.get("resolution_strategy") or "").strip() or "flag_for_review"
    )
    confidence = float(
        resolution.get("confidence") or conflict.get("confidence") or 0.5
    )

    # If ambiguous confidence, request user intervention
    if 0.4 <= confidence <= 0.6 and not resolution.get("user_override"):
        resolution = prompt_user_for_resolution(conflict)
        strategy = resolution.get("resolution_strategy", strategy)

    # Extract belief references best-effort
    belief_a = conflict.get("belief_a_meta") or conflict.get("belief_a")
    belief_b = conflict.get("belief_b_meta") or conflict.get("belief_b")

    # Apply updates (best-effort; if beliefs are plain strings, just log)
    applied: Dict[str, Any] = {
        "resolution_strategy": strategy,
        "created_at": utc_now_iso(),
    }

    try:
        if strategy == "inhibit":
            # Try to identify the target from resolver hint; otherwise default to belief_b
            target_id = resolution.get("inhibit_belief_id")
            if isinstance(belief_a, dict) and (
                belief_a.get("uuid") == target_id or belief_a.get("text") == target_id
            ):
                view = _tag_belief(belief_a, {"inhibited": True})
                applied["inhibited"] = view.get("uuid") or view.get("text")
            elif isinstance(belief_b, dict) and (
                belief_b.get("uuid") == target_id or belief_b.get("text") == target_id
            ):
                view = _tag_belief(belief_b, {"inhibited": True})
                applied["inhibited"] = view.get("uuid") or view.get("text")
            else:
                # Fallback: tag belief_b if dict-like
                if isinstance(belief_b, dict):
                    view = _tag_belief(belief_b, {"inhibited": True})
                    applied["inhibited"] = view.get("uuid") or view.get("text")
        elif strategy == "reframe":
            # Attach reframed_from to weaker belief; if resolver provided reframed_belief, keep it on conflict
            reframed = resolution.get("reframed_belief")
            if isinstance(belief_b, dict):
                view = _tag_belief(belief_b, {"reframed_from": belief_b.get("text")})
                applied["reframed"] = view.get("uuid") or view.get("text")
            if reframed:
                applied["reframed_belief"] = reframed
        elif strategy == "flag_for_review":
            if isinstance(belief_a, dict):
                _tag_belief(belief_a, {"needs_review": True})
            if isinstance(belief_b, dict):
                _tag_belief(belief_b, {"needs_review": True})
        elif strategy == "dream_resolution":
            # Defer to Speculative Simulation Module; we only log here
            applied["deferred_to_dream"] = True
        else:
            # Unknown strategy -> treat as flag_for_review
            if isinstance(belief_a, dict):
                _tag_belief(belief_a, {"needs_review": True})
            if isinstance(belief_b, dict):
                _tag_belief(belief_b, {"needs_review": True})
            applied["fallback"] = True
    except Exception:
        # Guardrail: never break callers
        pass

    # Journal the application
    try:
        _safe_log(
            {
                "type": "contradiction_resolution_applied",
                "uuid": conflict.get("uuid"),
                "belief_1": conflict.get("belief_1") or conflict.get("belief_a"),
                "belief_2": conflict.get("belief_2") or conflict.get("belief_b"),
                "proposed_resolution": resolution,
                "applied_resolution": applied,
            }
        )
    except Exception:
        pass

    # Attach applied resolution for downstream hooks
    conflict_out = dict(conflict)
    conflict_out["applied_resolution"] = applied
    conflict_out.setdefault("proposed_resolution", resolution)
    return conflict_out


__all__ = [
    "apply_contradiction_resolution",
    "prompt_user_for_resolution",
]
