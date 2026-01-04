import importlib
import os
from tests.utils.env import temp_env


def _make_client():
    mod = importlib.import_module("pods.memory.pod2_memory_api")
    return getattr(mod, "app").test_client()


def test_vector_upsert_with_provenance_required_passes(monkeypatch):
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "1", "AXIOM_AUTH_ENABLED": "false"}):
        tc = _make_client()
        rv = tc.post(
            "/memory/add",
            json={
                "content": "x",
                "metadata": {"provenance": "unit_test"},
            },
        )
        assert rv.status_code in (200, 202)


def test_vector_upsert_without_provenance_required_fails(monkeypatch):
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "1", "AXIOM_AUTH_ENABLED": "false"}):
        tc = _make_client()
        rv = tc.post(
            "/memory/add",
            json={
                "content": "no provenance here",
            },
        )
        assert rv.status_code == 400
        data = rv.get_json() or {}
        assert data.get("error") == "provenance_required"

