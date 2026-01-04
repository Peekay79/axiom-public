import os

from pods.memory.pod2_memory_api import app


def test_memory_debug_factors_present(monkeypatch):
    monkeypatch.setenv("AXIOM_COMPOSITE_SCORING", "1")
    monkeypatch.setenv("AXIOM_DEBUG_OPEN", "1")
    with app.test_client() as c:
        r = c.get("/memory-debug")
        assert r.status_code == 200
        data = r.get_json()
        assert "composite_enabled" in data and data["composite_enabled"] is True
        # Depending on implementation, items may be under data["items"] or data["last"]["items"]
        items = data.get("items")
        if not items and isinstance(data.get("last"), dict):
            items = data["last"].get("items")
        if not items:
            return
        first = items[0]
        for k in ("sim", "rec", "cred", "conf", "bel", "use", "nov", "final_score"):
            assert k in first
