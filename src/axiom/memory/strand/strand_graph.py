import logging
import os
import time
import traceback
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .strand_client import (
    get_driver,
    load_config_from_env,
    run_cypher,
    strand_graph_enabled,
)

logger = logging.getLogger(__name__)

# ── Lightweight Observability ──────────────────────────────────────────────
# Rolling window of recent events (timestamp, success_bool, latency_ms)
_EVENTS: deque[Tuple[datetime, bool, float]] = deque(maxlen=2000)
_LAST_SUCCESS_TS: Optional[datetime] = None
_LAST_ERROR_TS: Optional[datetime] = None
_TOTAL_ATTEMPTS: int = 0
_TOTAL_SUCCESSES: int = 0
_TOTAL_FAILURES: int = 0


def _record_event(*, success: bool, latency_ms: float) -> None:
    global _LAST_SUCCESS_TS, _LAST_ERROR_TS, _TOTAL_ATTEMPTS, _TOTAL_SUCCESSES, _TOTAL_FAILURES
    now = datetime.now(timezone.utc)
    _EVENTS.append((now, success, latency_ms))
    _TOTAL_ATTEMPTS += 1
    if success:
        _TOTAL_SUCCESSES += 1
        _LAST_SUCCESS_TS = now
    else:
        _TOTAL_FAILURES += 1
        _LAST_ERROR_TS = now


def _stats_last_hour() -> Tuple[int, int, int, Optional[float]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = [(ts, ok, lat) for (ts, ok, lat) in list(_EVENTS) if ts >= cutoff]
    if not recent:
        return (0, 0, 0, None)
    attempts = len(recent)
    successes = sum(1 for (_, ok, _) in recent if ok)
    failures = attempts - successes
    latencies = sorted(lat for (_, _, lat) in recent)
    # p95 index
    idx = max(0, int(0.95 * len(latencies)) - 1)
    p95 = latencies[idx] if latencies else None
    return (attempts, successes, failures, p95)


def strand_health_snapshot() -> Dict[str, Any]:
    """Return a cheap snapshot of strand sync health/metrics."""
    # Determine whether neo4j driver is importable (without importing our client)
    try:
        import importlib.util as _u

        neo4j_driver_loaded = _u.find_spec("neo4j") is not None
    except Exception:
        neo4j_driver_loaded = False

    attempts_1h, success_1h, failure_1h, p95_latency_ms_1h = _stats_last_hour()
    return {
        "enabled": strand_graph_enabled(),
        "neo4j_driver_loaded": bool(neo4j_driver_loaded),
        "last_success_ts": _LAST_SUCCESS_TS.isoformat() if _LAST_SUCCESS_TS else None,
        "last_error_ts": _LAST_ERROR_TS.isoformat() if _LAST_ERROR_TS else None,
        "attempts_1h": attempts_1h,
        "success_1h": success_1h,
        "failure_1h": failure_1h,
        "p95_latency_ms_1h": p95_latency_ms_1h,
    }


def _load_schema_statements() -> Iterable[str]:
    schema_path = Path(__file__).resolve().parent / "schema.cypher"
    if not schema_path.exists():
        # Minimal default schema if file missing
        default = """
		CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE (m.id) IS UNIQUE;
		CREATE INDEX memory_type_index IF NOT EXISTS FOR (m:Memory) ON (m.memory_type);
		CREATE INDEX memory_speaker_index IF NOT EXISTS FOR (m:Memory) ON (m.speaker);
		CREATE INDEX memory_created_at_index IF NOT EXISTS FOR (m:Memory) ON (m.created_at);
		"""
        return [s for s in default.split(";") if s.strip()]

    text = schema_path.read_text(encoding="utf-8")
    # Split on semicolons but keep statements with content
    return [s for s in text.split(";") if s.strip()]


def ensure_schema(
    driver=None, *, log: Optional[logging.Logger] = None, dry_run: bool = False
) -> None:
    log = log or logger
    for stmt in _load_schema_statements():
        query = stmt.strip()
        if not query.endswith(";"):
            query = query + ";"
        try:
            run_cypher(driver, query, {}, log=log, dry_run=dry_run)
        except Exception as e:
            log.warning("[strand_sync] Schema statement failed: %s | err=%s", query, e)


def build_upsert_memory_query(payload: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    params = {
        "id": payload.get("id"),
        "content": payload.get("content"),
        "speaker": payload.get("speaker"),
        "memory_type": payload.get("type") or payload.get("memory_type"),
        "tags": payload.get("tags", []),
        "timestamp": payload.get("timestamp")
        or payload.get("created_at")
        or payload.get("stored_at"),
        "schema_version": payload.get("schema_version"),
    }

    query = """
	MERGE (m:Memory {id: $id})
	ON CREATE SET
		m.content = $content,
		m.speaker = $speaker,
		m.memory_type = $memory_type,
		m.tags = $tags,
		m.created_at = coalesce(datetime($timestamp), datetime()),
		m.schema_version = $schema_version
	ON MATCH SET
		m.content = coalesce($content, m.content),
		m.speaker = coalesce($speaker, m.speaker),
		m.memory_type = coalesce($memory_type, m.memory_type),
		m.tags = coalesce($tags, m.tags),
		m.updated_at = datetime()
	RETURN m.id AS id
	"""
    return query, params


def build_link_query(
    from_id: str,
    to_id: str,
    *,
    reason: Optional[str] = None,
    score: Optional[float] = None,
) -> tuple[str, Dict[str, Any]]:
    params = {"from_id": from_id, "to_id": to_id, "reason": reason, "score": score}
    query = """
	MATCH (a:Memory {id: $from_id}), (b:Memory {id: $to_id})
	MERGE (a)-[r:RELATED]->(b)
	ON CREATE SET r.created_at = datetime()
	SET r.reason = coalesce($reason, r.reason),
		r.score = coalesce($score, r.score),
		r.updated_at = datetime()
	RETURN a.id AS from_id, b.id AS to_id
	"""
    return query, params


def query_strand(
    driver,
    start_id: str,
    *,
    depth: int = 3,
    log: Optional[logging.Logger] = None,
    dry_run: bool = False,
) -> Iterable[Dict[str, Any]]:
    log = log or logger
    # Cypher does not allow parameterizing variable length; inline depth safely as an int
    depth_n = max(1, int(depth))
    query = f"""
	MATCH p = (m:Memory {{id: $start_id}})-[:RELATED*1..{depth_n}]->(n:Memory)
	RETURN p
	LIMIT 100
	"""
    return run_cypher(driver, query, {"start_id": start_id}, log=log, dry_run=dry_run)


def sync_strand(
    *,
    memory_id: str,
    payload: Dict[str, Any],
    related_ids: Optional[List[str]] = None,
    logger_ref: Optional[logging.Logger] = None,
) -> None:
    """
    Env-gated synchronization hook invoked after vector insertion.
    - Upserts the memory node into the Neo4j graph
    - Optionally links to provided related_ids

    All failures are logged with memory UUID and timing. No exceptions escape.
    """
    _log = logger_ref or logger
    start = time.monotonic()
    attempt_success = True
    try:
        if not strand_graph_enabled():
            return

        # Prepare connection and detect dry-run
        config = load_config_from_env()
        driver = get_driver(config)
        dry_run = driver is None

        # Ensure schema exists
        ensure_schema(driver, log=_log, dry_run=dry_run)

        # Upsert the memory node
        upsert_q, upsert_params = build_upsert_memory_query(
            {"id": memory_id, **(payload or {})}
        )
        try:
            run_cypher(driver, upsert_q, upsert_params, log=_log, dry_run=dry_run)
            _log.info("[strand_sync] upsert memory_id=%s", memory_id)
            _log.debug(
                "[strand_sync] Cypher: %s | params=%s", upsert_q.strip(), upsert_params
            )
        except Exception as e:
            attempt_success = False
            _log.error("[strand_sync] upsert failed memory_id=%s err=%s", memory_id, e)
            _log.debug("[strand_sync] upsert traceback:\n%s", traceback.format_exc())

        # Link to any provided related IDs
        for rid in related_ids or []:
            try:
                link_q, link_params = build_link_query(memory_id, rid)
                run_cypher(driver, link_q, link_params, log=_log, dry_run=dry_run)
                _log.info("[strand_sync] link %s -> %s", memory_id, rid)
                _log.debug(
                    "[strand_sync] Cypher: %s | params=%s", link_q.strip(), link_params
                )
            except Exception as e:
                attempt_success = False
                _log.error(
                    "[strand_sync] link failed %s -> %s err=%s", memory_id, rid, e
                )
                _log.debug("[strand_sync] link traceback:\n%s", traceback.format_exc())

    except Exception as outer_e:
        attempt_success = False
        _log.error(
            "[strand_sync] outer failure memory_id=%s err=%s", memory_id, outer_e
        )
        _log.debug("[strand_sync] outer traceback:\n%s", traceback.format_exc())
    finally:
        lat_ms = (time.monotonic() - start) * 1000.0
        _record_event(success=attempt_success, latency_ms=lat_ms)
        _log.info(
            "[strand_sync] done memory_id=%s success=%s latency_ms=%.1f",
            memory_id,
            attempt_success,
            lat_ms,
        )
