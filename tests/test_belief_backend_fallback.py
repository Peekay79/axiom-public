import logging
import importlib


def test_neo4j_backend_falls_back_to_disabled(monkeypatch, caplog):
    # Force neo4j backend selection while graph is enabled
    monkeypatch.setenv("AXIOM_BELIEF_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AXIOM_BELIEF_BACKEND", "neo4j")

    import belief_graph as bgmod

    with caplog.at_level(logging.INFO):
        importlib.reload(bgmod)
        bg = bgmod.belief_graph
        assert bg.__class__.__name__ == "DisabledBeliefGraph"
        # Deprecation log emitted for neo4j fallback
        assert any("[RECALL][Deprecation]" in (r.message or "") and "AXIOM_BELIEF_BACKEND=neo4j" in (r.message or "") for r in caplog.records)

