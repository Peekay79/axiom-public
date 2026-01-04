#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .model import Belief
from .provenance import has_external_evidence, normalize_provenance


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "y"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except Exception:
        return int(default)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_when(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value)
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _last_evidence_at(belief: Belief, payload: Dict[str, Any] | None = None) -> Optional[datetime]:
    # Prefer explicit provenance timestamps
    latest: Optional[datetime] = None
    for item in normalize_provenance(belief.provenance):
        for key in ("ts", "timestamp", "date", "observed_at"):
            d = _parse_when(item.get(key)) if isinstance(item, dict) else None
            if d and (latest is None or d > latest):
                latest = d
    # Fallback to payload-level hints
    if payload:
        for key in ("last_evidence_at", "updated_at", "created_at"):
            d = _parse_when(payload.get(key))
            if d and (latest is None or d > latest):
                latest = d
    return latest


def _days_between(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 86400.0


def _has_contradiction_since(belief_id: str, since_iso: str | None) -> bool:
    """
    Best-effort local check: read cockpit signals for governor.belief_contradiction.
    Hermetic by default (returns False if unavailable). Tests can monkeypatch this.
    """
    try:
        from pathlib import Path
        import json

        signal_dir = Path(os.getenv("COCKPIT_SIGNAL_DIR", "axiom_boot"))
        # Check a few possible files (latest-only semantics)
        candidates = [signal_dir / "governor.belief_contradiction.json"]
        since_dt = _parse_when(since_iso) if since_iso else None
        for f in candidates:
            if not f.exists():
                continue
            data = json.loads(f.read_text() or "{}")
            ts = _parse_when(data.get("ts"))
            if since_dt and ts and ts <= since_dt:
                continue
            payload = data.get("data", {}) or {}
            a = str(payload.get("belief") or payload.get("a") or "")
            b = str(payload.get("counter") or payload.get("b") or "")
            if a == str(belief_id) or b == str(belief_id):
                return True
    except Exception:
        return False
    return False


def recompute_one(belief: Belief, now: datetime | None = None, payload_hint: Dict[str, Any] | None = None) -> Belief:
    """
    Apply governance corrections to a single belief. Does not mutate the input.

    Rules:
    - Cap: if no external evidence, cap to CAP_NO_EXTERNAL
    - Dormancy decay: conf *= 0.5 ** (days_since_last_evidence / HALFLIFE_DAYS)
    - Counter-evidence: if contradictions since last_recompute, subtract PENALTY
    """
    now = now or datetime.now(timezone.utc)
    cap_no_external = _env_float("BELIEF_CONFIDENCE_CAP_NO_EXTERNAL", 0.6)
    halflife_days = max(1.0, _env_float("BELIEF_DORMANCY_HALFLIFE_DAYS", 30.0))
    penalty = max(0.0, _env_float("BELIEF_COUNTEREVIDENCE_PENALTY", 0.2))

    conf = float(belief.confidence)
    capped = False
    decayed = False
    penalized = False

    # Normalize provenance defensively
    prov = normalize_provenance(belief.provenance)

    # Cap without external evidence
    if not has_external_evidence(prov):
        if conf > cap_no_external:
            conf = min(conf, cap_no_external)
            capped = True

    # Dormancy decay using last evidence timestamp
    last_ev = _last_evidence_at(belief, payload_hint)
    if last_ev is not None and halflife_days > 0:
        days_since = _days_between(last_ev, now)
        if days_since > 0:
            factor = 0.5 ** (days_since / float(halflife_days))
            new_conf = conf * factor
            if new_conf < conf:
                conf = new_conf
                decayed = True

    # Counter-evidence penalty once per recompute window
    if belief.last_recompute:
        if _has_contradiction_since(belief.id, belief.last_recompute):
            conf = max(0.0, conf - penalty)
            penalized = True

    # Clamp to [0,1]
    conf = max(0.0, min(1.0, conf))

    updated = replace(belief, confidence=conf, last_recompute=now.isoformat())
    return updated


def _emit_counters(stats: Dict[str, int], avg_conf: Optional[float]) -> None:
    try:
        from pods.cockpit.cockpit_reporter import write_signal

        write_signal("beliefs", "recompute", stats)
        if avg_conf is not None:
            write_signal("beliefs", "recompute_summary", {"avg_confidence": float(avg_conf)})
    except Exception:
        pass


def _iter_beliefs_from_qdrant(batch_size: int) -> Iterable[Tuple[str, Dict[str, Any], List[float]]]:
    """Yield (id, payload, vector) from Qdrant beliefs collection in batches.
    Fails closed (empty iterator) if not available.
    """
    try:
        from axiom_qdrant_client import QdrantClient
        from memory.memory_collections import beliefs_collection as _beliefs_collection

        client = QdrantClient()
        collection = _beliefs_collection()
        # Scroll through all points with payloads and vectors
        offset = None
        while True:
            try:
                points, next_page = client.client.scroll(
                    collection_name=collection,
                    limit=int(batch_size),
                    with_payload=True,
                    with_vectors=True,
                    offset=offset,
                )
            except TypeError:
                # Older client signatures may not support offset kwarg
                result = client.client.scroll(
                    collection_name=collection,
                    limit=int(batch_size),
                    with_payload=True,
                    with_vectors=True,
                )
                # result may be a tuple
                try:
                    points, next_page = result
                except Exception:
                    points, next_page = result, None

            if not points:
                break
            for p in points:
                pid = str(getattr(p, "id", ""))
                payload = getattr(p, "payload", {}) or {}
                vector = getattr(p, "vector", None) or [0.0] * 384
                if pid:
                    yield pid, payload, vector
            if not next_page:
                break
            offset = next_page
    except Exception:
        return


def run_recompute(batch_size: int = 200) -> Dict[str, Any]:
    if not _env_bool("BELIEF_RECOMPUTE_ENABLED", True):
        return {"status": "disabled"}

    total = 0
    changed = 0
    capped = 0
    decayed = 0
    penalized = 0
    conf_sum = 0.0
    conf_count = 0

    backend = os.getenv("BELIEF_STORAGE_MODE", "qdrant").strip().lower() or "qdrant"
    try:
        from axiom_qdrant_client import QdrantClient
        from memory.memory_collections import beliefs_collection as _beliefs_collection

        client = QdrantClient()
        collection = _beliefs_collection()

        for pid, payload, vector in _iter_beliefs_from_qdrant(batch_size):
            total += 1
            belief = Belief.from_payload({**payload, "id": pid})
            # Precompute rule flags from original state
            cap_no_external = _env_float("BELIEF_CONFIDENCE_CAP_NO_EXTERNAL", 0.6)
            halflife_days = max(1.0, _env_float("BELIEF_DORMANCY_HALFLIFE_DAYS", 30.0))
            rule_capped = (not has_external_evidence(belief.provenance)) and (belief.confidence > cap_no_external)
            last_ev = _last_evidence_at(belief, payload)
            rule_decayed = bool(last_ev and _days_between(last_ev, datetime.now(timezone.utc)) > 0 and halflife_days > 0)
            rule_penalized = bool(belief.last_recompute and _has_contradiction_since(belief.id, belief.last_recompute))

            updated = recompute_one(belief, payload_hint=payload)

            conf_sum += float(updated.confidence)
            conf_count += 1

            if updated.confidence != belief.confidence or updated.last_recompute != belief.last_recompute:
                changed += 1
                if rule_capped:
                    capped += 1
                if rule_decayed:
                    decayed += 1
                if rule_penalized:
                    penalized += 1

                new_payload = payload.copy()
                new_payload["confidence"] = float(updated.confidence)
                new_payload["last_recompute"] = updated.last_recompute
                # Keep updated_at to support optimistic patterns elsewhere
                new_payload["updated_at"] = _iso_now()

                # Idempotent upsert (direct to Qdrant). If API exists, it will enforce its own idempotency.
                client.upsert_memory(collection_name=collection, memory_id=pid, vector=vector, payload=new_payload)

        avg_conf = (conf_sum / conf_count) if conf_count else None
        stats = {
            "beliefs.recomputed": changed,
            "beliefs.scanned": total,
            "beliefs.capped_no_external": capped,
            "beliefs.decayed_by_dormancy": decayed,
            "beliefs.penalized_counterevidence": penalized,
        }
        # Emit Cockpit counters + backend label
        try:
            from pods.cockpit.cockpit_reporter import write_signal as _ck_write

            _emit_counters(stats, avg_conf)
            _ck_write("beliefs", "backend", {"backend": backend})
        except Exception:
            _emit_counters(stats, avg_conf)
        return {"status": "ok", **stats, "avg_confidence": avg_conf, "backend": backend}
    except Exception as e:
        _emit_counters({"beliefs.recompute_error": 1}, None)
        return {"status": "error", "error": str(e)}


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Belief governance recompute CLI")
    parser.add_argument("--once", action="store_true", help="Run one pass and exit")
    parser.add_argument("--batch-size", type=int, default=200)
    return parser.parse_args(argv)


def _main():
    args = _parse_args()
    if args.once:
        res = run_recompute(batch_size=args.batch_size)
        # Print minimal status for ops
        print(res)
        return
    # If no scheduler exists, a simple loop could be added here. We keep it single-run for safety.
    res = run_recompute(batch_size=args.batch_size)
    print(res)


if __name__ == "__main__":
    _main()

