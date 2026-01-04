#!/usr/bin/env python3
# AUDIT: Contradiction Pipeline – contradiction_monitor.py
# - Purpose: Retest unresolved contradictions, scheduling, clustering, narrative, confidence propagation.
# - Findings:
#   - ✅ Async: retest_unresolved_contradictions awaits pairwise detector correctly.
#   - ⚠️ API coupling: imports _as_belief from belief_engine (private); consider public export or local wrapper.
#   - ⚠️ Schema drift: uses fields {timestamp|detected_at|created_at|logged_at|observed_at}; ensure all producers align.
#   - ⚠️ Journal keys: mixes 'type', 'source', nested 'conflict' with variations; document canonical event schema.
#   - ⚠️ Dream queue: queue_unresolved_for_dreaming sets 'dream_resolution' flag; ensure downstream consumers exist.
#   - ✅ No obvious infinite loops; retest uses in-memory throttle _RETEST_CHECK_CACHE.
#   - Cleanup targets: unify conflict identity scheme, centralize timestamp parsing, minimize broad try/except.
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from memory.utils.journal import safe_log_event
from memory.utils.time_utils import parse_timestamp
from memory.utils.contradiction_utils import resolve_conflict_timestamp, conflict_identity

# Belief engine for pairwise detection
from .belief_engine import (  # type: ignore  # AUDIT_OK: use public alias
    as_belief,
    detect_contradictions_pairwise,
    ensure_structured_beliefs,
)

try:
    from .contradiction_resolver import (
        suggest_contradiction_resolution as _resolver_probe,  # type: ignore
    )

    _HAS_RESOLVER = True
except Exception:
    _HAS_RESOLVER = False

# Memory manager for persistence (optional)
try:
    from pods.memory.memory_manager import Memory  # ⚠️ optional external dependency

    _HAS_MEMORY = True
except Exception:
    _HAS_MEMORY = False

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    from memory.utils.time_utils import utc_now_iso  # AUDIT_OK: centralized

    return utc_now_iso()


# DEPRECATED: use safe_log_event({...}, default_source="contradiction_monitor") directly
def _log_journal(event: Dict[str, Any]) -> None:
    safe_log_event(event, default_source="contradiction_monitor")


# In-memory cache for retest scheduling last-check tracking (non-persistent by design)
_RETEST_CHECK_CACHE: Dict[str, str] = {}
# ASYNC-AUDIT: Guard shared cache with a lock to prevent race conditions
from threading import Lock

_RETEST_CHECK_LOCK: Lock = Lock()


# DEPRECATED: prefer memory.utils.contradiction_utils.conflict_identity()
def _conflict_identity(conf: dict) -> str:
    """Best-effort stable identity for a contradiction record.

    Preference order:
      - explicit uuid/id on conflict
      - belief-side uuids/ids
      - hash of normalized belief texts
    """
    try:
        uid = str(conf.get("uuid") or conf.get("id") or "").strip()
        if uid:
            return uid
        a_meta = conf.get("belief_a_meta") or {}
        b_meta = conf.get("belief_b_meta") or {}
        for k in ("uuid", "id", "belief_uuid"):
            if a_meta.get(k):
                return f"a:{a_meta.get(k)}"
            if b_meta.get(k):
                return f"b:{b_meta.get(k)}"
        a_text = (conf.get("belief_a") or "").strip()
        b_text = (conf.get("belief_b") or "").strip()
        combo = "|".join(sorted([a_text, b_text]))
        return "h:" + hashlib.sha1(combo.encode("utf-8")).hexdigest()[:16]
    except Exception:
        # Absolute fallback to unpredictable but unique-ish repr hash
        try:
            return (
                "h:"
                + hashlib.sha1(
                    json.dumps(conf, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()[:16]
            )
        except Exception:
            return f"anon:{id(conf)}"


def suggest_contradiction_resolution(conflict: Dict[str, Any]) -> str:
    """Suggest a resolution strategy for a conflict.

    Inputs: conflict dict with keys: belief_a, belief_b, confidence (optional)
    Strategy:
      - If confidence < 0.4 → Low severity — may be tolerable
      - If either belief has low confidence or high decay → Archive weaker belief
      - If belief marked 'deprecated', 'refuted', or newer overrides older → Favor newer
    Returns suggestion string.
    """
    try:
        conf_val = float(conflict.get("confidence", 0.0) or 0.0)
    except Exception:
        conf_val = 0.0

    # Rule 1: Low severity threshold
    if conf_val < 0.4:
        return "Low severity — may be tolerable"

    # Inspect embedded metadata if present
    belief_a_meta = conflict.get("belief_a_meta", {})
    belief_b_meta = conflict.get("belief_b_meta", {})

    a_conf = float(belief_a_meta.get("confidence", 0.5) or 0.5)
    b_conf = float(belief_b_meta.get("confidence", 0.5) or 0.5)

    # Check deprecation/refutation flags
    a_tags = set((belief_a_meta.get("tags") or []))
    b_tags = set((belief_b_meta.get("tags") or []))

    a_is_deprecated = any(t in a_tags for t in {"deprecated", "refuted"})
    b_is_deprecated = any(t in b_tags for t in {"deprecated", "refuted"})

    # Check recency
    a_time = parse_timestamp(belief_a_meta.get("last_updated"))
    b_time = parse_timestamp(belief_b_meta.get("last_updated"))

    # Rule 2: Prefer newer if one is deprecated/refuted or strictly newer
    if a_is_deprecated and not b_is_deprecated:
        return "Favor newer"
    if b_is_deprecated and not a_is_deprecated:
        return "Favor newer"
    if a_time and b_time and b_time > a_time:
        # favor B if it's newer and no strong reason otherwise
        return "Favor newer"

    # Rule 3: Archive weaker belief based on confidence
    if a_conf < 0.5 or b_conf < 0.5:
        return "Archive weaker belief"

    # Fallback suggestion
    return "Review context manually or escalate"


def _load_pending_contradictions_from_memory() -> List[Dict[str, Any]]:
    """Best-effort load of pending contradictions from memory store.

    This function scans memory for journal or system entries that include
    contradiction conflicts with resolution == "pending". It is a heuristic
    bridge until a dedicated contradiction store exists.
    """
    if not _HAS_MEMORY:
        return []
    try:
        mem = Memory()
        mem.load()
        pending: List[Dict[str, Any]] = []
        for m in mem.long_term_memory:
            conflicts = None
            # Look for belief_engine journal format
            if m.get("type") in {"journal_entry", "memory", "reflection"}:
                conflicts = m.get("conflicts") or m.get("detected_contradictions")
            if not conflicts:
                continue
            for c in conflicts or []:
                if str(c.get("resolution", "pending")) == "pending":
                    pending.append(c)
        return pending
    except Exception:
        return []


def get_all_contradictions() -> List[Dict[str, Any]]:
    """Return all contradiction records found in memory (best-effort).

    Scans the Memory store for journal entries that embed contradictions,
    flattening common containers like "conflicts" and "detected_contradictions".
    Returns an empty list on any failure.
    """
    if not _HAS_MEMORY:
        return []
    try:
        mem = Memory()
        mem.load()
        records: List[Dict[str, Any]] = []
        for m in mem.long_term_memory:
            if not isinstance(m, dict):
                continue
            conflicts = m.get("conflicts") or m.get("detected_contradictions")
            if not conflicts:
                continue
            if isinstance(conflicts, list):
                for c in conflicts:
                    if isinstance(c, dict):
                        records.append(c)
        return records
    except Exception:
        return []


async def retest_unresolved_contradictions() -> List[Dict[str, Any]]:
    """Re-test contradictions whose resolution remains pending.

    - Loads conflicts with resolution == "pending"
    - Re-runs detect_contradictions_pairwise on original beliefs
    - Logs status: still exists, changed, or resolved
    - Marks resolution to "expired"/"auto-resolved" in emitted journal event
    Returns list of updated conflict records for reporting.
    """
    # ASYNC-AUDIT: _load_pending_contradictions_from_memory can touch disk; run in thread
    pending = await asyncio.to_thread(_load_pending_contradictions_from_memory)
    if not pending:
        return []

    updated: List[Dict[str, Any]] = []
    for conflict in pending:
        belief_a_text = conflict.get("belief_a") or ""
        belief_b_text = conflict.get("belief_b") or ""
        if not belief_a_text or not belief_b_text:
            continue

        a_obj = {
            "text": belief_a_text,
            "polarity": 1,
            "confidence": conflict.get("confidence", 0.5),
        }
        b_obj = {
            "text": belief_b_text,
            "polarity": -1,
            "confidence": conflict.get("confidence", 0.5),
        }

        # Re-run pairwise with the two beliefs
        try:
            recheck = await detect_contradictions_pairwise(a_obj, [b_obj])
        except Exception:
            recheck = []

        if recheck:
            # Still conflicting (status may have changed)
            new_conf = recheck[0]
            status = (
                "still_conflicts"
                if new_conf.get("resolution") == "pending"
                else "changed"
            )
            result = {**new_conf, "status": status, "retested_at": _iso_now()}
        else:
            # Resolved
            result = {
                "belief_a": belief_a_text,
                "belief_b": belief_b_text,
                "confidence": 0.0,
                "conflict": "retest: no longer detected",
                "resolution": "auto-resolved",
                "retested_at": _iso_now(),
            }

        updated.append(result)

        # Log to journal/logbook
        _log_journal(
            {
                "type": "contradiction_retest",
                "source": "contradiction_monitor",
                "original": conflict,
                "result": result,
                "created_at": _iso_now(),  # AUDIT_OK
            }
        )

    return updated


def queue_unresolved_for_dreaming(
    conflict: Dict[str, Any], *, days_threshold: int = 7, max_attempts: int = 3
) -> Optional[Dict[str, Any]]:
    """Queue a conflict for dream resolution if criteria met.

    - If unresolved after X days or >3 failed resolution attempts → mark dream_resolution True
    - Emit journal/logbook entry of type "dream_queue"
    Returns the queued record or None if not queued.
    """
    last_attempt = conflict.get("last_attempt_at")
    attempts = int(conflict.get("attempt_count", 0) or 0)

    is_old_enough = False
    if last_attempt:
        try:
            when = datetime.fromisoformat(str(last_attempt).replace("Z", "+00:00"))
            is_old_enough = (datetime.now(timezone.utc) - when) >= timedelta(
                days=days_threshold
            )
        except Exception:
            is_old_enough = False

    if not is_old_enough and attempts <= max_attempts:
        return None

    queued = {
        **conflict,
        "dream_resolution": True,
        "queued_at": _iso_now(),
    }

    _log_journal(
        {
            "type": "dream_queue",
            "source": "contradiction_monitor",
            "conflict": queued,
            "created_at": _iso_now(),  # AUDIT_OK: standardized timestamp
        }
    )

    return queued


__all__ = [
    "retest_unresolved_contradictions",
    "suggest_contradiction_resolution",
    "queue_unresolved_for_dreaming",
    "cluster_contradictions_by_theme",
    "log_contradiction_outcome",
    "prioritize_contradictions_by_emotion",
    "schedule_contradiction_retest",
    "export_contradiction_graph",
    "narrate_contradiction_story",
    "log_contradiction_nag",
    "narrate_contradiction_chain",
    "get_all_contradictions",
]


def cluster_contradictions_by_theme(conflicts: List[dict]) -> Dict[str, List[dict]]:
    """Group contradiction records by a derived theme.

    Theme precedence:
      1) conflict.get("world_map", {}).get("theme")
      2) conflict.get("theme")
      3) conflict.get("key") or keys from embedded belief meta
      4) Derived from belief_a/b text via belief canonicalization

    Returns: dict of theme -> [conflict dicts]
    Emits journal event type: "contradiction_clustered" with summary counts.
    """
    buckets: Dict[str, List[dict]] = {}

    # Optional world map index (best-effort)
    world_theme_lookup: Dict[str, str] = {}
    try:
        wm_path = os.path.join(os.path.dirname(__file__), "..", "world_map.json")
        wm_path = os.path.normpath(wm_path)
        if os.path.exists(wm_path):
            with open(wm_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Accept formats: {key: {theme: ...}} or list of nodes
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict) and v.get("theme"):
                        world_theme_lookup[str(k)] = str(v.get("theme"))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("key") and item.get("theme"):
                        world_theme_lookup[str(item.get("key"))] = str(
                            item.get("theme")
                        )
    except Exception:
        world_theme_lookup = {}

    def _derive_key_from_conflict(conf: dict) -> Optional[str]:
        # Direct key on conflict
        k = conf.get("key") or conf.get("belief_key")
        if isinstance(k, str) and k.strip():
            return k
        # Embedded meta
        for meta_key in ("belief_a_meta", "belief_b_meta"):
            meta = conf.get(meta_key) or {}
            mk = meta.get("key")
            if isinstance(mk, str) and mk.strip():
                return mk
        # Fallback: attempt canonicalization via _as_belief
        try:
            a_text = conf.get("belief_a")
            b_text = conf.get("belief_b")
            a_obj = as_belief({"text": a_text} if a_text else None)
            b_obj = as_belief({"text": b_text} if b_text else None)
            if a_obj and getattr(a_obj, "key", None):
                return a_obj.key
            if b_obj and getattr(b_obj, "key", None):
                return b_obj.key
        except Exception:
            pass
        return None

    for conf in conflicts or []:
        # World theme or direct theme first
        theme = None
        wm = conf.get("world_map") or {}
        if isinstance(wm, dict):
            theme = wm.get("theme")
        if not theme:
            theme = conf.get("theme")

        # If still missing, attempt via keys and world map lookup
        if not theme:
            key = _derive_key_from_conflict(conf)
            if key and key in world_theme_lookup:
                theme = world_theme_lookup[key]
            else:
                theme = key

        theme_name = str(theme).strip() if theme else "unclassified"
        buckets.setdefault(theme_name, []).append(conf)

    # Emit clustering summary
    try:
        _log_journal(
            {
                "type": "contradiction_clustered",
                "source": "contradiction_monitor",
                "summary": {k: len(v) for k, v in buckets.items()},
                "count": sum(len(v) for v in buckets.values()),
                "created_at": _iso_now(),  # AUDIT_OK
            }
        )
    except Exception:
        pass

    return buckets


def log_contradiction_outcome(conflict: dict, method: str) -> dict:
    """Record the outcome of a contradiction's lifecycle and emit a journal event.

    method examples: "synthesized", "archived", "deprecated", "escalated", "unresolvable".
    Emits: "contradiction_resolved" or "contradiction_unresolvable".
    """
    updated = dict(conflict or {})
    updated["resolution"] = "resolved" if method != "unresolvable" else "unresolvable"
    updated["resolved_method"] = str(method)
    updated["resolved_at"] = _iso_now()

    event_type = (
        "contradiction_resolved"
        if method != "unresolvable"
        else "contradiction_unresolvable"
    )
    try:
        _log_journal(
            {
                "type": event_type,
                "source": "contradiction_monitor",
                "conflict": updated,
            }
        )
    except Exception:
        pass

    # Emit a brief narrative entry as a background narrator
    try:
        narrative = narrate_contradiction_story(updated)
        if narrative:
            _log_journal(
                {
                    "type": "contradiction_narrative",
                    "source": "contradiction_monitor",
                    "narrative": narrative,
                    "conflict": updated,
                    "method": method,
                }
            )
    except Exception:
        pass

    # Confidence propagation on resolution (best-effort)
    try:
        _propagate_confidence_from_resolution(updated)
    except Exception:
        pass

    return updated


def prioritize_contradictions_by_emotion(
    conflicts: List[dict], *, top_n: Optional[int] = None
) -> List[dict]:
    """Return conflicts sorted by emotional salience.

    Score = abs(emotion_score) * confidence if both present, otherwise passthrough.
    Scaffold only: if no conflicts include emotion_score, returns input order.
    Emits journal event type: "contradiction_priority_scored".
    """
    if not conflicts:
        return []

    def _score(c: dict) -> Optional[float]:
        try:
            emotion = c.get("emotion_score")
            conf = c.get("confidence")
            if emotion is None or conf is None:
                # Look into nested meta if present
                meta = c.get("belief_a_meta") or {}
                if emotion is None:
                    emotion = meta.get("emotion_score")
                if conf is None:
                    conf = meta.get("confidence")
            if emotion is None or conf is None:
                return None
            return abs(float(emotion)) * float(conf)
        except Exception:
            return None

    scored: List[tuple] = []
    for c in conflicts:
        s = _score(c)
        if s is not None:
            scored.append((s, c))

    if not scored:
        return conflicts

    scored.sort(key=lambda t: t[0], reverse=True)
    ordered = [c for _, c in scored]
    if isinstance(top_n, int) and top_n > 0:
        ordered = ordered[:top_n]

    try:
        _log_journal(
            {
                "type": "contradiction_priority_scored",
                "source": "contradiction_monitor",
                "count": len(ordered),
                "has_emotion": True,
            }
        )
    except Exception:
        pass

    return ordered


def schedule_contradiction_retest(
    pending_conflicts: List[dict],
    age_threshold: int = 7,
    *,
    hours_threshold: Optional[int] = None,
) -> List[dict]:
    """Select unresolved contradictions older than a threshold for re-evaluation.

    Enhancements:
    - Tracks last_checked in in-memory cache to avoid excessive churn.
    - Supports prioritization by hours_threshold (default: 24h) when provided; otherwise days.
    - Emits journal event type: "contradiction_retest_scheduled" for scheduled items.
    - Logs per-item schedule events with reason and last_checked.
    """
    try:
        if not pending_conflicts:
            return []

        # DEPRECATED: prefer memory.utils.contradiction_utils.resolve_conflict_timestamp()
        def _conflict_time(conf: dict) -> datetime:
            # Prefer primary timestamp field
            for key in (
                "timestamp",
                "detected_at",
                "created_at",
                "logged_at",
                "observed_at",
            ):
                val = conf.get(key)
                if val:
                    return parse_timestamp(val)
            # Fall back to resolution-related fields
            for key in ("last_attempt_at", "retested_at", "resolved_at"):
                val = conf.get(key)
                if val:
                    return parse_timestamp(val)
            # Inspect embedded belief metadata if present
            try:
                a_meta = conf.get("belief_a_meta") or {}
                b_meta = conf.get("belief_b_meta") or {}
                for key in ("last_updated", "created_at"):
                    if a_meta.get(key):
                        return parse_timestamp(a_meta.get(key))
                    if b_meta.get(key):
                        return parse_timestamp(b_meta.get(key))
            except Exception:
                pass
            return datetime.fromtimestamp(0, tz=timezone.utc)

        now = datetime.now(timezone.utc)
        threshold_seconds = None
        if isinstance(hours_threshold, int) and hours_threshold > 0:
            threshold_seconds = hours_threshold * 3600.0
        else:
            # days fallback
            try:
                threshold_seconds = float(age_threshold) * 86400.0
            except Exception:
                threshold_seconds = 7 * 86400.0

        selected: List[dict] = []
        for conf in pending_conflicts:
            if str(conf.get("resolution", "pending")) != "pending":
                continue

            # Use canonical identity helper for stability
            cid = conflict_identity(conf)
            # Retain local timestamp heuristic, but prefer canonical helper if available
            try:
                base_time = resolve_conflict_timestamp(conf)
            except Exception:
                base_time = _conflict_time(conf)
            age_seconds = max(0.0, (now - base_time).total_seconds())

            # Respect last_checked from cache
            # ASYNC-AUDIT: read cache under lock
            with _RETEST_CHECK_LOCK:
                last_checked = _RETEST_CHECK_CACHE.get(cid)
            last_checked_dt = parse_timestamp(last_checked) if last_checked else None
            last_gap_ok = True
            if last_checked_dt is not None:
                since_last = (now - last_checked_dt).total_seconds()
                # Require at least half of threshold between checks to avoid thrash
                last_gap_ok = since_last >= (threshold_seconds * 0.5)

            if age_seconds >= threshold_seconds and last_gap_ok:
                selected.append(
                    {
                        **conf,
                        "_selected_reason": "age_threshold",
                        "_age_seconds": age_seconds,
                    }
                )
                # Update cache
                # ASYNC-AUDIT: write cache under lock
                with _RETEST_CHECK_LOCK:
                    _RETEST_CHECK_CACHE[cid] = _iso_now()
                # Per-item schedule log
                try:
                    _log_journal(
                        {
                            "type": "contradiction_retest_scheduled",
                            "source": "contradiction_monitor",
                            "conflict_id": cid,
                            "last_checked": last_checked,
                            "age_seconds": int(age_seconds),
                            "threshold_seconds": int(threshold_seconds),
                        }
                    )
                except Exception:
                    pass

        # Summary log
        try:
            _log_journal(
                {
                    "type": "contradiction_retest_scheduled",
                    "source": "contradiction_monitor",
                    "count": len(selected),
                    "threshold_days": (
                        int(threshold_seconds // 86400) if threshold_seconds else None
                    ),
                    "threshold_hours": (
                        int(threshold_seconds // 3600) if threshold_seconds else None
                    ),
                    "created_at": _iso_now(),  # AUDIT_OK
                }
            )
        except Exception:
            pass

        return [
            {
                k: v
                for k, v in conf.items()
                if not str(k).startswith("_selected_")
                and not str(k).startswith("_age_")
            }
            for conf in selected
        ]
    except Exception:
        # Fail silent per safety requirements
        return []


def export_contradiction_graph(
    conflicts: List[dict], path: str = "contradiction_graph.json"
) -> None:
    """Export contradictions as a node-link JSON file.

    Structure:
    {
      "nodes": [{ "id": belief_uuid, "label": belief_key }],
      "links": [{ "source": A, "target": B, "confidence": X }]
    }

    Best-effort extraction; falls back to text-derived identifiers if uuids/keys are missing.
    Emits journal event type: "contradiction_graph_exported".
    """
    try:
        if not conflicts:
            data = {"nodes": [], "links": []}
        else:
            nodes: Dict[str, Dict[str, str]] = {}
            links: List[Dict[str, Any]] = []

            def _node_id_and_label(
                text: Optional[str], meta: Optional[dict]
            ) -> tuple[str, str]:
                meta = meta or {}
                text = (text or "").strip()
                # Prefer explicit UUID/id from metadata, otherwise hash of text
                uid = str(
                    meta.get("uuid") or meta.get("id") or meta.get("belief_uuid") or ""
                ).strip()
                if not uid:
                    if text:
                        uid = "t:" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
                    else:
                        uid = (
                            "unknown:"
                            + hashlib.sha1(
                                json.dumps(meta, sort_keys=True).encode("utf-8")
                            ).hexdigest()[:12]
                        )
                # Prefer human-readable label from key; fallback to truncated text
                label = str(meta.get("key") or meta.get("belief_key") or "").strip()
                if not label:
                    label = (
                        (text[:80] + ("…" if len(text) > 80 else "")) if text else uid
                    )
                return uid, label

            for conf in conflicts:
                a_text = conf.get("belief_a")
                b_text = conf.get("belief_b")
                a_meta = conf.get("belief_a_meta") or {}
                b_meta = conf.get("belief_b_meta") or {}
                a_id, a_label = _node_id_and_label(a_text, a_meta)
                b_id, b_label = _node_id_and_label(b_text, b_meta)
                if a_id not in nodes:
                    nodes[a_id] = {"id": a_id, "label": a_label}
                if b_id not in nodes:
                    nodes[b_id] = {"id": b_id, "label": b_label}
                try:
                    conf_val = float(conf.get("confidence", 0.0) or 0.0)
                except Exception:
                    conf_val = 0.0
                links.append({"source": a_id, "target": b_id, "confidence": conf_val})

            data = {"nodes": list(nodes.values()), "links": links}

        # Ensure parent directory exists if path includes a directory component
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        _log_journal(
            {
                "type": "contradiction_graph_exported",
                "source": "contradiction_monitor",
                "path": path,
                "node_count": len(data.get("nodes", [])),
                "link_count": len(data.get("links", [])),
                "created_at": _iso_now(),  # AUDIT_OK
            }
        )
    except Exception:
        # Swallow all errors by design of scaffold; do not raise
        try:
            _log_journal(
                {
                    "type": "contradiction_graph_exported",
                    "source": "contradiction_monitor",
                    "path": path,
                    "error": True,
                    "created_at": _iso_now(),  # AUDIT_OK
                }
            )
        except Exception:
            pass


def narrate_contradiction_story(conflict: dict) -> str:
    """Return a brief journal-style narrative describing a contradiction.

    Example: "Axiom noted a contradiction between its belief about autonomy and a newer belief about user-guided evolution."
    """
    if not isinstance(conflict, dict):
        return ""

    def _label_from(text: Optional[str], meta: Optional[dict]) -> str:
        meta = meta or {}
        key = str(meta.get("key") or meta.get("belief_key") or "").strip()
        if key:
            return key
        txt = (text or "").strip()
        if not txt:
            return "an unspecified topic"
        return txt[:60] + ("…" if len(txt) > 60 else "")

    a_text = conflict.get("belief_a")
    b_text = conflict.get("belief_b")
    a_meta = conflict.get("belief_a_meta") or {}
    b_meta = conflict.get("belief_b_meta") or {}

    a_label = _label_from(a_text, a_meta)
    b_label = _label_from(b_text, b_meta)

    # Determine recency if possible
    def _ts(meta: dict) -> Optional[datetime]:
        for key in ("last_updated", "created_at", "timestamp"):
            val = meta.get(key)
            if val:
                try:
                    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                except Exception:
                    continue
        return None

    newer_phrase = "another"
    ta, tb = _ts(a_meta), _ts(b_meta)
    if ta and tb:
        if tb > ta:
            newer_phrase = "a newer"
        elif ta > tb:
            newer_phrase = "an earlier"

    return f"Axiom noted a contradiction between its belief about {a_label} and {newer_phrase} belief about {b_label}."


def log_contradiction_nag() -> None:
    """Emit a summary nag log about contradictions.

    Summary includes: total unresolved, oldest conflict age, top themes (best-effort).
    """
    try:
        records = get_all_contradictions()
    except Exception:
        records = []

    unresolved = [
        c for c in records if str(c.get("resolution", "pending")) == "pending"
    ]

    # Oldest age computation
    now = datetime.now(timezone.utc)
    oldest_age_seconds = None
    try:
        for c in unresolved:
            # Reuse the same timestamp resolution used in scheduler
            when = None
            for key in (
                "timestamp",
                "detected_at",
                "created_at",
                "logged_at",
                "observed_at",
            ):
                val = c.get(key)
                if val:
                    when = parse_timestamp(val)
                    break
            if when is None:
                # Fall back to embedded belief metadata
                a_meta = c.get("belief_a_meta") or {}
                b_meta = c.get("belief_b_meta") or {}
                when = parse_timestamp(
                    a_meta.get("last_updated")
                    or a_meta.get("created_at")
                    or b_meta.get("last_updated")
                    or b_meta.get("created_at")
                )
            age = (
                now - (when or datetime.fromtimestamp(0, tz=timezone.utc))
            ).total_seconds()
            if oldest_age_seconds is None or age > oldest_age_seconds:
                oldest_age_seconds = age
    except Exception:
        oldest_age_seconds = None

    # Top themes using cluster helper (best-effort)
    top_themes = []
    try:
        clusters = cluster_contradictions_by_theme(unresolved)
        # Sort by size
        top_themes = sorted(
            ((k, len(v)) for k, v in clusters.items()), key=lambda t: t[1], reverse=True
        )[:5]
    except Exception:
        top_themes = []

    # Emit nag log
    try:
        _log_journal(
            {
                "type": "contradiction_nag",
                "source": "contradiction_monitor",
                "summary": {
                    "total_unresolved": len(unresolved),
                    "oldest_conflict_age_seconds": (
                        int(oldest_age_seconds)
                        if oldest_age_seconds is not None
                        else None
                    ),
                    "top_themes": top_themes,
                },
                "created_at": _iso_now(),  # AUDIT_OK
            }
        )
    except Exception:
        pass


def narrate_contradiction_chain(
    *,
    for_belief_key: Optional[str] = None,
    for_theme: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Aggregate and stitch prior contradiction narratives for a given belief key or theme.

    Looks up existing journal-style narratives by scanning Memory contradiction records, then
    concatenates into a timeline-like summary. Falls back to generating narratives on the fly
    for available conflicts if dedicated logs are missing.
    """
    try:
        records = get_all_contradictions()
    except Exception:
        records = []

    if not records:
        try:
            _log_journal(
                {
                    "type": "contradiction_chain_summary",
                    "source": "contradiction_monitor",
                    "summary": "",
                    "note": "no_records",
                    "created_at": _iso_now(),  # AUDIT_OK
                }
            )
        except Exception:
            pass
        return ""

    def _matches(c: dict) -> bool:
        if for_belief_key:
            k_a = (
                (c.get("belief_a_meta") or {}).get("key")
                or (c.get("belief_a_meta") or {}).get("belief_key")
                or ""
            ).strip()
            k_b = (
                (c.get("belief_b_meta") or {}).get("key")
                or (c.get("belief_b_meta") or {}).get("belief_key")
                or ""
            ).strip()
            if for_belief_key in {k_a, k_b}:
                return True
        if for_theme:
            theme = (c.get("world_map") or {}).get("theme") or c.get("theme")
            if isinstance(theme, str) and theme.strip() == for_theme:
                return True
        return False

    # Filter and sort by any available time
    subset = (
        [c for c in records if _matches(c)]
        if (for_belief_key or for_theme)
        else list(records)
    )

    def _when(c: dict) -> datetime:
        for key in (
            "resolved_at",
            "retested_at",
            "timestamp",
            "detected_at",
            "created_at",
            "logged_at",
            "observed_at",
        ):
            val = c.get(key)
            if val:
                return parse_timestamp(val)
        a_meta = c.get("belief_a_meta") or {}
        b_meta = c.get("belief_b_meta") or {}
        return parse_timestamp(
            a_meta.get("last_updated")
            or a_meta.get("created_at")
            or b_meta.get("last_updated")
            or b_meta.get("created_at")
        )

    subset.sort(key=_when)
    subset = subset[-max(1, int(limit)) :] if subset else []

    # Prefer existing narratives if present in records; else synthesize
    lines: List[str] = []
    for c in subset:
        # Embedded narrative if exists
        narrative = c.get("narrative") or c.get("contradiction_narrative")
        if not narrative:
            narrative = narrate_contradiction_story(c)
        if narrative:
            ts = _when(c)
            lines.append(f"[{ts.date().isoformat()}] {narrative}")

    result = "\n".join(lines)

    try:
        _log_journal(
            {
                "type": "contradiction_chain_summary",
                "source": "contradiction_monitor",
                "summary": result,
                "filter": {"belief_key": for_belief_key, "theme": for_theme},
                "count": len(lines),
                "created_at": _iso_now(),  # AUDIT_OK
            }
        )
    except Exception:
        pass

    return result


def _propagate_confidence_from_resolution(conflict: dict) -> None:
    """Adjust confidence scores of beliefs when a contradiction is resolved.

    Heuristics:
    - If resolved_method indicates one belief superseded the other (e.g., "synthesized", "favor_newer", "archived"),
      gently boost the belief that appears to be preferred and decay the other.
    - If method is "unresolvable", decay both slightly to reflect uncertainty.
    - Best-effort write-back to Memory entries if available; otherwise only journal a log.
    """
    # Extract method and meta
    method = str(
        conflict.get("resolved_method") or conflict.get("method") or ""
    ).lower()
    a_meta = (conflict.get("belief_a_meta") or {}).copy()
    b_meta = (conflict.get("belief_b_meta") or {}).copy()

    # Identify target directions
    prefer_b = False
    prefer_a = False
    if "favor_newer" in method or "synth" in method:
        # Determine which is newer using timestamps
        try:
            ta = parse_timestamp(a_meta.get("last_updated") or a_meta.get("created_at"))
            tb = parse_timestamp(b_meta.get("last_updated") or b_meta.get("created_at"))
            if tb > ta:
                prefer_b = True
            elif ta > tb:
                prefer_a = True
        except Exception:
            pass
    elif "archived" in method or "deprecated" in method or "refuted" in method:
        # If tags indicate which was archived, infer from tags
        a_tags = set(a_meta.get("tags") or [])
        b_tags = set(b_meta.get("tags") or [])
        if any(t in a_tags for t in {"archived", "deprecated", "refuted"}):
            prefer_b = True
        if any(t in b_tags for t in {"archived", "deprecated", "refuted"}):
            prefer_a = True

    # Compute adjustments
    def _clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    a_conf = float(a_meta.get("confidence", conflict.get("confidence", 0.5)) or 0.5)
    b_conf = float(b_meta.get("confidence", conflict.get("confidence", 0.5)) or 0.5)

    boost = 0.08
    decay = 0.10

    if method == "unresolvable":
        a_new = _clamp(a_conf - decay * 0.5)
        b_new = _clamp(b_conf - decay * 0.5)
        a_delta, b_delta = a_new - a_conf, b_new - b_conf
    else:
        if prefer_a:
            a_new = _clamp(a_conf + boost)
            b_new = _clamp(b_conf - decay)
        elif prefer_b:
            a_new = _clamp(a_conf - decay)
            b_new = _clamp(b_conf + boost)
        else:
            # Neutral: small decay on both to incentivize future validation
            a_new = _clamp(a_conf - decay * 0.3)
            b_new = _clamp(b_conf - decay * 0.3)
        a_delta, b_delta = a_new - a_conf, b_new - b_conf

    # Best-effort write-back to Memory store if present
    write_ok = False
    try:
        if _HAS_MEMORY:
            mem = Memory()
            mem.load()

            def _match_and_update(side_meta: dict, new_conf: float) -> bool:
                # Match by uuid/id if possible; else attempt by key/text
                sid = str(
                    side_meta.get("uuid")
                    or side_meta.get("id")
                    or side_meta.get("belief_uuid")
                    or ""
                ).strip()
                skey = str(
                    side_meta.get("key") or side_meta.get("belief_key") or ""
                ).strip()
                updated = False
                for entry in mem.long_term_memory:
                    if entry.get("type") != "belief":
                        continue
                    if (
                        sid
                        and str(entry.get("id") or entry.get("uuid") or "").strip()
                        == sid
                    ):
                        entry["confidence"] = _clamp(
                            float(entry.get("confidence", 0.5))
                            + (
                                new_conf
                                - float(
                                    side_meta.get(
                                        "confidence", entry.get("confidence", 0.5)
                                    )
                                )
                            )
                        )
                        entry["last_updated"] = _iso_now()
                        updated = True
                        break
                    if (
                        skey
                        and str(
                            entry.get("key") or entry.get("belief_key") or ""
                        ).strip()
                        == skey
                    ):
                        entry["confidence"] = _clamp(
                            float(entry.get("confidence", 0.5))
                            + (
                                new_conf
                                - float(
                                    side_meta.get(
                                        "confidence", entry.get("confidence", 0.5)
                                    )
                                )
                            )
                        )
                        entry["last_updated"] = _iso_now()
                        updated = True
                        break
                if updated:
                    try:
                        mem.save()
                    except Exception:
                        pass
                return updated

            ua = _match_and_update(a_meta, a_new)
            ub = _match_and_update(b_meta, b_new)
            write_ok = ua or ub
    except Exception:
        write_ok = False

    # Journal the confidence adjustment event
    try:
        _log_journal(
            {
                "type": "belief_confidence_adjusted",
                "source": "contradiction_monitor",
                "method": method,
                "adjustments": {
                    "belief_a": {"old": a_conf, "new": a_new, "delta": a_delta},
                    "belief_b": {"old": b_conf, "new": b_new, "delta": b_delta},
                },
                "persisted": bool(write_ok),
                "created_at": _iso_now(),  # AUDIT_OK
            }
        )
    except Exception:
        pass
