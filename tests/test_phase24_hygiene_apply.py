import os
import sqlite3


def test_hygiene_apply_mutates_state(tmp_path):
    from belief_graph.sqlite_backend import SQLiteBeliefGraph
    from memory_hygiene import run_cycle

    db_path = tmp_path / "belief_graph.sqlite"
    g = SQLiteBeliefGraph(str(db_path))

    # Seed a retire-worthy belief (very low confidence)
    bid = g.upsert_belief("Y", "is", "stale", confidence=0.05)
    assert bid

    os.environ["AXIOM_HYGIENE_ENABLED"] = "1"
    os.environ["AXIOM_HYGIENE_DRY_RUN"] = "0"
    os.environ["AXIOM_HYGIENE_RETIRE_THRESHOLD"] = "0.1"
    os.environ["AXIOM_BELIEF_SQLITE_PATH"] = str(db_path)

    summary = run_cycle(dry_run=False)
    assert summary.get("dry_run") is False
    # Either archived or retired depending on thresholds, but should not be active
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT state FROM beliefs WHERE id=?", (int(bid),))
    row = cur.fetchone()
    assert row and row[0] in {"archived", "retired"}
