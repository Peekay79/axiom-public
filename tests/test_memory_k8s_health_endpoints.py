import importlib
import sys
import types


def _install_lightweight_import_stubs():
    """
    The memory pod module imports a large dependency graph at import time.
    For probe endpoint tests we don't need ML backends; stub them to keep tests
    hermetic and avoid requiring heavyweight wheels (torch, sentence-transformers).
    """
    if "sentence_transformers" not in sys.modules:
        st = types.ModuleType("sentence_transformers")

        class _DummySentenceTransformer:  # pragma: no cover
            def __init__(self, *args, **kwargs):
                pass

            def encode(self, *args, **kwargs):
                return []

        st.SentenceTransformer = _DummySentenceTransformer  # type: ignore[attr-defined]
        sys.modules["sentence_transformers"] = st


def test_k8s_style_probe_endpoints_are_present():
    _install_lightweight_import_stubs()
    mod = importlib.import_module("pods.memory.pod2_memory_api")
    app = mod.app
    c = app.test_client()

    # Basic "always ok" probes
    for path in ("/healthz", "/livez"):
        r = c.get(path)
        assert r.status_code == 200
        assert r.data.decode("utf-8") == "ok"
        assert r.headers.get("Content-Type") == "text/plain; charset=utf-8"

    # Root index should exist and be small JSON
    r0 = c.get("/")
    assert r0.status_code == 200
    assert r0.is_json
    assert r0.get_json() == {"service": "axiom_memory", "status": "ok"}


def test_readyz_reflects_internal_readiness_flags(monkeypatch):
    _install_lightweight_import_stubs()
    mod = importlib.import_module("pods.memory.pod2_memory_api")
    app = mod.app
    c = app.test_client()

    prev_state = {
        "vector_ready": bool(getattr(mod, "vector_ready", False)),
        "vector_circuit_open": bool(getattr(mod, "vector_circuit_open", False)),
        "memory_data": list(getattr(mod, "memory_data", []) or []),
    }
    try:
        # Force NOT ready
        monkeypatch.setattr(mod, "vector_ready", False, raising=False)
        monkeypatch.setattr(mod, "vector_circuit_open", True, raising=False)
        monkeypatch.setattr(mod, "memory_data", [], raising=False)
        r1 = c.get("/readyz")
        assert r1.status_code == 503
        assert r1.is_json
        body1 = r1.get_json()
        assert body1.get("status") == "not_ready"

        # Force ready (no network calls)
        monkeypatch.setattr(mod, "vector_ready", True, raising=False)
        monkeypatch.setattr(mod, "vector_circuit_open", False, raising=False)
        monkeypatch.setattr(mod, "memory_data", [{"uuid": "m1", "content": "x"}], raising=False)
        r2 = c.get("/readyz")
        assert r2.status_code == 200
        assert r2.is_json
        body2 = r2.get_json()
        assert body2.get("status") == "ok"
    finally:
        monkeypatch.setattr(mod, "vector_ready", prev_state["vector_ready"], raising=False)
        monkeypatch.setattr(mod, "vector_circuit_open", prev_state["vector_circuit_open"], raising=False)
        monkeypatch.setattr(mod, "memory_data", prev_state["memory_data"], raising=False)


def test_health_route_still_works_and_shape_has_key_fields():
    # IMPORTANT: we do not re-encode the full payload; just assert it still returns 200 JSON
    # with key fields expected by existing callers.
    _install_lightweight_import_stubs()
    mod = importlib.import_module("pods.memory.pod2_memory_api")
    app = mod.app
    c = app.test_client()

    r = c.get("/health")
    assert r.status_code == 200
    assert r.is_json
    body = r.get_json()
    assert isinstance(body, dict)
    assert "status" in body
    assert "memory_size" in body
    assert "vector_ready" in body

