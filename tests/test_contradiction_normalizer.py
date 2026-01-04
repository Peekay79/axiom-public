import os
import sys
import json
import types
import logging


def test_normalize_legacy_variants():
    from schemas.contradiction import normalize

    # Legacy timestamps and missing conflict_id
    payload = {
        "claim": "Water boils at 100C",
        "timestamp": 1700000000,
        "confidence": 1.2,  # out of range
        "tags": "physics",  # scalar
        "source": 123,
    }
    c, warns = normalize(payload)
    assert c is not None
    assert isinstance(warns, list)
    assert c.conflict_id and isinstance(c.conflict_id, str)
    assert c.logged_at and isinstance(c.logged_at, str)
    assert 0.0 <= c.confidence <= 1.0
    assert isinstance(c.tags, list)

    # Alternate legacy key mapping
    payload2 = {
        "statement": "The sky is green",
        "detected_at": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "confidence": -0.5,
        "tags": [1, 2, "x"],
        "status": "unknown",
    }
    c2, warns2 = normalize(payload2)
    assert c2 is not None
    assert c2.status == "open"  # invalid -> default
    assert 0.0 <= c2.confidence <= 1.0
    assert isinstance(warns2, list)

    # Hard error: missing claim
    bad, w3 = normalize({"foo": "bar"})
    assert bad is None
    assert isinstance(w3, list) and w3


def test_contradictions_route_body_unchanged_and_metrics(monkeypatch, caplog):
    # Stub heavy deps and memory_response_pipeline before import
    last = {
        "items": [
            {"claim": "A", "confidence": 1.2, "tags": "t1", "timestamp": 1700000100},
            {"id": "x"},  # not normalized (no claim)
            {"statement": "B", "confidence": -1.0, "tags": ["t2"], "created_at": "2025-01-01T00:00:00Z"},
        ]
    }
    stub = types.SimpleNamespace(_LAST_CONTRADICTIONS=last, _METRICS={})
    sys.modules["memory_response_pipeline"] = stub

    # Stub optional heavy modules
    class _DummyST:
        def __init__(self, *args, **kwargs):
            pass

    sys.modules["sentence_transformers"] = types.SimpleNamespace(SentenceTransformer=_DummyST)

    # Build a stubbed qdrant_client with http submodules
    import types as _types
    qdc_mod = _types.ModuleType("qdrant_client")
    class _DummyQdrant:
        def __init__(self, *args, **kwargs):
            pass
    qdc_mod.QdrantClient = _DummyQdrant
    http_mod = _types.ModuleType("qdrant_client.http")
    http_ex = _types.ModuleType("qdrant_client.http.exceptions")
    class _UnexpectedResponse(Exception):
        pass
    http_ex.UnexpectedResponse = _UnexpectedResponse
    http_models = _types.ModuleType("qdrant_client.http.models")
    class _PointStruct:
        pass
    http_models.PointStruct = _PointStruct
    models_mod = _types.ModuleType("qdrant_client.models")
    sys.modules["qdrant_client"] = qdc_mod
    sys.modules["qdrant_client.http"] = http_mod
    sys.modules["qdrant_client.http.exceptions"] = http_ex
    sys.modules["qdrant_client.http.models"] = http_models
    sys.modules["qdrant_client.models"] = models_mod

    # Stub flask_cors
    sys.modules["flask_cors"] = types.SimpleNamespace(CORS=lambda *a, **k: None)

    # Stub requests
    class _Resp:
        def json(self):
            return {}

        def raise_for_status(self):
            return None

    sys.modules["requests"] = types.SimpleNamespace(get=lambda *a, **k: _Resp(), post=lambda *a, **k: _Resp())

    # Stub pydantic BaseModel/Field used by goal_types
    class _BM:
        def __init__(self, *a, **k):
            pass

    def _Field(*a, **k):
        default = k.get("default")
        default_factory = k.get("default_factory")
        return default_factory() if default_factory else default

    pyd = types.SimpleNamespace(BaseModel=_BM, Field=_Field)
    sys.modules["pydantic"] = pyd

    # Patch metrics counters
    counters = {}
    timers = {}

    def inc(name: str, value: int = 1):
        counters[name] = counters.get(name, 0) + int(value)

    def observe_ms(name: str, ms: float):
        timers[name] = timers.get(name, 0) + 1

    import observability.metrics as metrics

    monkeypatch.setattr(metrics, "inc", inc, raising=True)
    monkeypatch.setattr(metrics, "observe_ms", observe_ms, raising=True)

    # Ensure route enabled and no redaction (legacy var maps to canonical)
    monkeypatch.setenv("AXIOM_CONTRADICTIONS", "1")
    monkeypatch.setenv("AXIOM_DEBUG_VERBOSE", "1")

    # Import app
    import importlib

    mpod = importlib.import_module("pods.memory.pod2_memory_api")
    app = getattr(mpod, "app")

    with app.test_client() as client:
        with caplog.at_level(logging.INFO):
            resp = client.get("/contradictions")
        assert resp.status_code == 200
        body = resp.get_json()
        # Body should be unchanged from stub
        assert body == last

    # Metrics observed
    assert counters.get("contradictions.req", 0) >= 1
    assert counters.get("contradictions.normalized", 0) >= 2  # two items normalized

    # Structured log contains a normalization record
    found = False
    for rec in caplog.records:
        try:
            payload = json.loads(rec.message)
        except Exception:
            continue
        if payload.get("component") == "contradictions" and payload.get("action") == "normalize":
            found = True
            assert payload.get("count") == 3
            assert payload.get("normalized") >= 2
            break
    assert found

