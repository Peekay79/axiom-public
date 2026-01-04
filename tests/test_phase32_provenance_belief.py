import importlib
from tests.utils.env import temp_env


def _make_client():
    # Use vector adapter v1 writes path for beliefs via memory pod JSON path
    # Here we test memory add path with a belief-like payload including provenance
    mod = importlib.import_module("pods.memory.pod2_memory_api")
    return getattr(mod, "app").test_client()


def test_belief_style_upsert_with_provenance_ok(monkeypatch):
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "1", "AXIOM_AUTH_ENABLED": "false"}):
        tc = _make_client()
        rv = tc.post(
            "/memory/add",
            json={
                "content": "I believe testing is vital",
                "tags": ["belief"],
                "metadata": {"provenance": "belief_test"},
            },
        )
        assert rv.status_code in (200, 202)


def test_belief_style_upsert_missing_provenance_rejected(monkeypatch):
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "1", "AXIOM_AUTH_ENABLED": "false"}):
        tc = _make_client()
        rv = tc.post(
            "/memory/add",
            json={
                "content": "I believe provenance should be enforced",
                "tags": ["belief"],
            },
        )
        assert rv.status_code == 400
        data = rv.get_json() or {}
        assert data.get("error") == "provenance_required"

