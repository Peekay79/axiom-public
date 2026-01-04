import importlib
import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for k in ("AXIOM_AUTH_ENABLED", "AXIOM_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    yield


def _mk_app_client():
    mod = importlib.import_module("pods.memory.pod2_memory_api")
    return getattr(mod, "app").test_client()


def test_default_off_allows_requests(monkeypatch):
    c = _mk_app_client()
    r = c.get("/health")
    assert r.status_code == 200
    r2 = c.post("/vector/query", json={"query": "hi", "top_k": 1})
    # May be 503 if vector not ready; must not be 401 while auth is OFF
    assert r2.status_code != 401


def test_enabled_requires_token(monkeypatch):
    monkeypatch.setenv("AXIOM_AUTH_ENABLED", "true")
    monkeypatch.setenv("AXIOM_AUTH_TOKEN", "secret")
    c = _mk_app_client()
    # health open
    assert c.get("/health").status_code == 200
    # protected endpoint 401 without token
    r = c.post("/vector/query", json={"query": "hi", "top_k": 1})
    assert r.status_code == 401
    # with token -> passes auth layer; downstream status may vary but not 401
    r2 = c.post(
        "/vector/query",
        headers={"Authorization": "Bearer secret"},
        json={"query": "hi", "top_k": 1},
    )
    assert r2.status_code != 401

