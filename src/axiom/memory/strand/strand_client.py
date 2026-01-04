import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    uri: str
    user: Optional[str] = None
    password: Optional[str] = None


TRUE_SET = {"1", "true", "yes", "on"}


def strand_graph_enabled() -> bool:
    return os.getenv("ENABLE_STRAND_GRAPH", "").strip().lower() in TRUE_SET


def load_config_from_env() -> Neo4jConfig:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687").strip()
    user = os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j")).strip()
    password = os.getenv("NEO4J_PASSWORD", os.getenv("NEO4J_PASS", "")).strip() or None
    return Neo4jConfig(uri=uri, user=user, password=password)


def get_driver(config: Optional[Neo4jConfig] = None):
    """
    Lazily import the Neo4j driver and return a driver instance.
    Returns None if the driver is not installed or config is incomplete.
    """
    if not strand_graph_enabled():
        return None

    config = config or load_config_from_env()
    try:
        from neo4j import GraphDatabase  # Local import to isolate dependency
    except Exception:  # pragma: no cover
        logger.info("[strand_sync] Strand graph disabled—neo4j driver not installed.")
        return None

    # If no password set, assume authless (e.g., dev or local with no auth)
    auth = (config.user, config.password) if (config.user and config.password) else None
    if auth is None:
        logger.info(
            "[strand_sync] No NEO4J_USER/NEO4J_PASSWORD provided; attempting unauthenticated connection to %s",
            config.uri,
        )
    try:
        driver = GraphDatabase.driver(config.uri, auth=auth)
        return driver
    except Exception as e:
        logger.warning(
            "[strand_sync] Failed to create Neo4j driver; running in no-op mode: %s", e
        )
        return None


def run_cypher(
    driver,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    log: Optional[logging.Logger] = None,
    dry_run: bool = False,
) -> Iterable[Dict[str, Any]]:
    """
    Execute a Cypher query. If driver is None or dry_run=True, echo the query and return empty results.
    """
    params = params or {}
    log = log or logger

    if dry_run or driver is None:
        log.info("[strand_sync][dry_run] Cypher: %s | params=%s", query.strip(), params)
        return []

    try:
        with driver.session() as session:
            result = session.run(query, params)
            records = [r.data() for r in result]
            log.debug(
                "[strand_sync] Ran Cypher: %s | params=%s | rows=%d",
                query.strip(),
                params,
                len(records),
            )
            return records
    except Exception:
        # Let caller handle detailed error logging with context (memory UUID, etc.)
        raise
