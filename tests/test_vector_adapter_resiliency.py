#!/usr/bin/env python3
import os
import sys
import time
import types
import unittest
from unittest.mock import patch


def install_stubs():
    # Ensure adapter import does not require external URLs
    os.environ.setdefault("USE_QDRANT_BACKEND", "true")

    # Stub sentence_transformers to avoid model download
    if "sentence_transformers" not in sys.modules:
        m = types.ModuleType("sentence_transformers")

        class _StubModel:
            def __init__(self, *args, **kwargs):
                pass

            def encode(self, text, normalize_embeddings=True):
                class _Vec:
                    def __init__(self, arr):
                        self._arr = list(arr)

                    def tolist(self):
                        return list(self._arr)

                    def __len__(self):
                        return len(self._arr)

                return _Vec([0.1, 0.2, 0.3])

        m.SentenceTransformer = _StubModel
        sys.modules["sentence_transformers"] = m

    # Stub axiom_qdrant_client to avoid importing qdrant-client
    # Provide QdrantClient with methods used by vector_adapter
    if "axiom_qdrant_client" not in sys.modules:
        m2 = types.ModuleType("axiom_qdrant_client")

        class _GetColsResp:
            def __init__(self):
                self.collections = [types.SimpleNamespace(name="axiom_memories"), types.SimpleNamespace(name="axiom_beliefs")]

        class QdrantClient:
            def __init__(self, *args, **kwargs):
                self.host = "localhost"
                self.port = 6333

            # Compatibility method used by vector_adapter._list_collection_names
            def get_collections(self):
                return _GetColsResp()

            # Methods used by adapter paths
            def query_memory(self, *args, **kwargs):
                return []

            def upsert_memory(self, *args, **kwargs):
                return True

        m2.QdrantClient = QdrantClient
        sys.modules["axiom_qdrant_client"] = m2

    # Stub memory.memory_collections used by adapter
    if "memory" not in sys.modules:
        mem_pkg = types.ModuleType("memory")
        sys.modules["memory"] = mem_pkg
    if "memory.memory_collections" not in sys.modules:
        mc = types.ModuleType("memory.memory_collections")

        def memory_collection():
            return "axiom_memories"

        def beliefs_collection():
            return "axiom_beliefs"

        mc.memory_collection = memory_collection
        mc.beliefs_collection = beliefs_collection
        sys.modules["memory.memory_collections"] = mc

    # Stub numpy to avoid heavy dep
    if "numpy" not in sys.modules:
        np = types.ModuleType("numpy")
        sys.modules["numpy"] = np

    # Stub aiohttp to avoid network and dependency
    if "aiohttp" not in sys.modules:
        aio = types.ModuleType("aiohttp")

        class _Resp:
            def __init__(self, status=200):
                self.status = status

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class ClientSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, *args, **kwargs):
                class _Ctx:
                    async def __aenter__(self_inner):
                        return _Resp(200)

                    async def __aexit__(self_inner, exc_type, exc, tb):
                        return False

                return _Ctx()

        aio.ClientSession = ClientSession
        sys.modules["aiohttp"] = aio

    # Stub requests imported in adapter (only used for startup list collections fallback)
    if "requests" not in sys.modules:
        req = types.ModuleType("requests")

        class _Resp:
            def __init__(self, *args, **kwargs):
                self.status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"result": {"collections": [{"name": "axiom_memories"}, {"name": "axiom_beliefs"}]}}

        def get(*args, **kwargs):
            return _Resp()

        req.get = get
        sys.modules["requests"] = req

    # Stub flask fully to allow route tests
    if "flask" not in sys.modules:
        flask = types.ModuleType("flask")

        class Response:
            def __init__(self, payload):
                self._payload = payload
                self.headers = {}
                self.status_code = 200

            def get_json(self):
                return self._payload

        class _Request:
            def __init__(self):
                self.headers = {}
                self._json = None

            def get_json(self):
                return self._json

        flask.request = _Request()

        def jsonify(obj):
            return Response(obj)

        flask.jsonify = jsonify

        class Flask:
            def __init__(self, name):
                self._routes = {}

            def route(self, path, methods=None):
                methods = methods or ["GET"]

                def deco(fn):
                    for m in methods:
                        self._routes[(path, m.upper())] = fn
                    return fn

                return deco

            def test_client(self):
                routes = self._routes

                class Client:
                    def _call(self, path, method, json=None, headers=None):
                        flask.request.headers = headers or {}
                        flask.request._json = json
                        fn = routes.get((path, method.upper()))
                        if fn is None:
                            raise RuntimeError(f"route {method} {path} not found")
                        rv = fn()
                        status = 200
                        resp_obj = None
                        if isinstance(rv, tuple):
                            resp_obj = rv[0]
                            if len(rv) >= 2 and isinstance(rv[1], int):
                                status = rv[1]
                        else:
                            resp_obj = rv
                        if not isinstance(resp_obj, Response):
                            resp_obj = Response(resp_obj)
                        resp_obj.status_code = status
                        return resp_obj

                    def get(self, path, headers=None):
                        return self._call(path, "GET", None, headers)

                    def post(self, path, json=None, headers=None):
                        return self._call(path, "POST", json, headers)

                return Client()

        flask.Flask = Flask
        sys.modules["flask"] = flask

    # Stub observability.metrics for counters/timers
    if "observability" not in sys.modules:
        obs = types.ModuleType("observability")
        sys.modules["observability"] = obs
    if "observability.metrics" not in sys.modules:
        m = types.ModuleType("observability.metrics")
        _counters = {}
        _timers = {}

        def inc(name: str, value: int = 1):
            _counters[name] = _counters.get(name, 0) + int(value)

        def observe_ms(name: str, ms: float):
            arr = _timers.get(name, [])
            arr.append(float(ms))
            _timers[name] = arr

        def snapshot():
            # Minimal snapshot
            return {"counters": dict(_counters), "timers": {k: {"count": len(v)} for k, v in _timers.items()}}

        m.inc = inc
        m.observe_ms = observe_ms
        m.snapshot = snapshot
        sys.modules["observability.metrics"] = m


class VectorAdapterResiliencyHermetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_stubs()

    def setUp(self):
        import importlib
        import os as _os
        import sys as _sys
        # Ensure direct import path works even without packages
        vector_dir = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "pods", "vector"))
        if vector_dir not in _sys.path:
            _sys.path.insert(0, vector_dir)

        self.adapter_mod = importlib.import_module("vector_adapter")
        importlib.reload(self.adapter_mod)

        # Speed up and make deterministic
        self.adapter_mod.VECTOR_ADAPTER_TIMEOUT_SEC = 1
        self.adapter_mod.VECTOR_ADAPTER_RETRIES = 2
        self.adapter_mod._CB._open_seconds = 1
        self.adapter_mod._CB._state = "closed"
        self.adapter_mod._CB._consecutive_failures = 0

        from observability import metrics

        self.metrics = metrics

    def _counter(self, name: str) -> int:
        return int(self.metrics.snapshot().get("counters", {}).get(name, 0))

    def test_retry_then_circuit_open_and_half_open_reset(self):
        mod = self.adapter_mod
        # Fail 3x, then succeed
        call_count = {"n": 0}

        def failing_then_success(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] <= 3:
                raise RuntimeError("boom")
            return []

        with patch.object(mod.QdrantClient, "query_memory", side_effect=failing_then_success):
            adapter = mod.VectorAdapter()
            # Ensure breaker is closed before starting
            mod._CB._state = "closed"
            mod._CB._consecutive_failures = 0
            t0 = time.perf_counter()
            res = adapter.search("hello", top_k=1, certainty_min=0.1)
            # search() swallows and returns [] after failures
            self.assertIsInstance(res, list)
            # Allow zero backoff during CI; just assert attempts occurred
            self.assertEqual(call_count["n"], 3)

            # Circuit should be open
            self.assertTrue(mod._CB.is_open())
            self.assertGreaterEqual(self._counter("adapter.qdrant.err"), 1)

            # Subsequent call should short-circuit at route layer (simulated): can_execute False
            self.assertFalse(mod._CB.can_execute())

            # Wait for open window and ensure half-open
            time.sleep(1.1)
            self.assertTrue(mod._CB.can_execute())

            # Next call succeeds and closes circuit
            res2 = adapter.search("hello", top_k=1, certainty_min=0.1)
            self.assertIsInstance(res2, list)
            self.assertFalse(mod._CB.is_open())

        self.assertGreaterEqual(self._counter("adapter.circuit.open"), 1)

    def test_health_includes_circuit_open_flag(self):
        mod = self.adapter_mod
        client = mod.app.test_client()
        # Force open
        mod._CB._state = "open"
        mod._CB._opened_at = time.monotonic()
        rv = client.get("/health")
        self.assertEqual(rv.status_code, 200)
        body = rv.get_json()
        self.assertIn("circuit_open", body)

    def test_routes_short_circuit_503_when_open(self):
        mod = self.adapter_mod
        client = mod.app.test_client()

        # Open the circuit explicitly
        mod._CB._state = "open"
        mod._CB._opened_at = time.monotonic()

        # /recall should return 503 with error body and not call qdrant
        with patch.object(mod.QdrantClient, "query_memory", side_effect=AssertionError("should not be called")):
            rv = client.post("/recall", json={"query": "hello"})
        self.assertEqual(rv.status_code, 503)
        body = rv.get_json()
        self.assertIsInstance(body, dict)
        self.assertIn("error", body)

        # /v1/search should also return 503 with error body and not call qdrant
        with patch.object(mod.QdrantClient, "query_memory", side_effect=AssertionError("should not be called")):
            rv2 = client.post("/v1/search", json={"query": "hello"})
        self.assertEqual(rv2.status_code, 503)
        body2 = rv2.get_json()
        self.assertIsInstance(body2, dict)
        self.assertIn("error", body2)


if __name__ == "__main__":
    unittest.main()

