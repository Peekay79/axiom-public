import logging
import uuid
from typing import Optional

from .strand_client import (
    get_driver,
    load_config_from_env,
    run_cypher,
    strand_graph_enabled,
)
from .strand_graph import (
    build_link_query,
    build_upsert_memory_query,
    ensure_schema,
    query_strand,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("strand_demo")


def main():
    enabled = strand_graph_enabled()
    log.info("ENABLE_STRAND_GRAPH=%s", enabled)

    config = load_config_from_env()
    driver = get_driver(config)
    dry_run = driver is None

    # Ensure schema
    ensure_schema(driver, log=log, dry_run=dry_run)

    # Create two dummy memories (UUIDv4, same format as system uses)
    m1 = str(uuid.uuid4())
    m2 = str(uuid.uuid4())

    payload1 = {
        "id": m1,
        "content": "Demo memory A: testing strand graph",
        "speaker": "axiom",
        "type": "episodic",
        "tags": ["demo", "strand", "graph"],
    }
    payload2 = {
        "id": m2,
        "content": "Demo memory B: related to A",
        "speaker": "axiom",
        "type": "episodic",
        "tags": ["demo", "strand", "graph"],
    }

    # Upsert
    q1, p1 = build_upsert_memory_query(payload1)
    q2, p2 = build_upsert_memory_query(payload2)

    log.info("Upserting A → id=%s", m1)
    run_cypher(driver, q1, p1, log=log, dry_run=dry_run)
    log.info("Cypher: %s | params=%s", q1.strip(), p1)

    log.info("Upserting B → id=%s", m2)
    run_cypher(driver, q2, p2, log=log, dry_run=dry_run)
    log.info("Cypher: %s | params=%s", q2.strip(), p2)

    # Link
    lq, lp = build_link_query(m1, m2, reason="demo_link", score=0.9)
    log.info("Linking A -> B")
    run_cypher(driver, lq, lp, log=log, dry_run=dry_run)
    log.info("Cypher: %s | params=%s", lq.strip(), lp)

    # Query strand from A
    log.info("Querying strand from A (depth=3)")
    results = query_strand(driver, m1, depth=3, log=log, dry_run=dry_run)
    log.info("Results: %s", results)


if __name__ == "__main__":
    main()
