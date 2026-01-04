import os
import sqlite3


def test_hygiene_dry_run_no_mutation(tmp_path, caplog):
    from belief_graph.sqlite_backend import SQLiteBeliefGraph
    from memory_hygiene import run_cycle

    db_path = tmp_path / "belief_graph.sqlite"
    g = SQLiteBeliefGraph(str(db_path))

    # Seed a low-confidence, stale belief
    bid = g.upsert_belief("X", "is", "noise", confidence=0.05)
    assert bid

    os.environ["AXIOM_HYGIENE_ENABLED"] = "1"
    os.environ["AXIOM_HYGIENE_DRY_RUN"] = "1"
    os.environ["AXIOM_BELIEF_SQLITE_PATH"] = str(db_path)

    with caplog.at_level("INFO"):
        summary = run_cycle(dry_run=True)
        assert summary.get("dry_run") is True
        # Logs should mention would_set
        assert any("would_set" in r.message for r in caplog.records)

    # Verify DB state unchanged (should remain 'active')
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT state FROM beliefs WHERE id=?", (int(bid),))
    row = cur.fetchone()
    assert row and row[0] == "active"
