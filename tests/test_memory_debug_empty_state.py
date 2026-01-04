import os

from pods.memory.pod2_memory_api import app


def test_memory_debug_empty_state(monkeypatch):
    # enable composite, but do not trigger any retrieval
    monkeypatch.setenv("AXIOM_COMPOSITE_SCORING", "1")
    monkeypatch.setenv("AXIOM_DEBUG_OPEN", "1")
    with app.test_client() as c:
        r = c.get("/memory-debug")
        assert r.status_code == 200
        data = r.get_json()
        assert "composite_enabled" in data
        assert "scoring_profile" in data
        assert "items" in data and isinstance(data["items"], list)
