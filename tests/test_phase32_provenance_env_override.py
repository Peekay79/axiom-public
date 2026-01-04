import importlib
from tests.utils.env import temp_env


def _make_client():
    mod = importlib.import_module("pods.memory.pod2_memory_api")
    return getattr(mod, "app").test_client()


def test_legacy_override_allows_missing_provenance_when_flag_zero(monkeypatch):
    with temp_env({"AXIOM_PROVENANCE_REQUIRED": "0", "AXIOM_AUTH_ENABLED": "false"}):
        tc = _make_client()
        rv = tc.post(
            "/memory/add",
            json={
                "content": "legacy mode payload",
            },
        )
        # Allowed under legacy mode
        assert rv.status_code in (200, 202)

