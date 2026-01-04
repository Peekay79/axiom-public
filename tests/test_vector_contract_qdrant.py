import types

from vector.unified_client import UnifiedVectorClient, VectorSearchRequest


class FakeQdrantPoint:
    def __init__(self, score, payload):
        self.score = score
        self.payload = payload


class FakeQdrantClient:
    def __init__(self, hits):
        self._hits = hits

    def get_collections(self):  # health
        return types.SimpleNamespace(collections=[types.SimpleNamespace(name="axiom_memories")])

    def search(self, collection_name, query_vector, limit, with_vectors, query_filter=None):
        # ignore vector, collection and filter for this fake; emulate limit and simple tags.any filtering
        items = list(self._hits)
        # Very small filter simulation (tags.any)
        if query_filter and hasattr(query_filter, "must"):
            # Fallback: client-side tags.any will be applied in client; we return all here
            pass
        return items[:limit]


def test_qdrant_path_filters_and_shape(monkeypatch):
    # Arrange: env defaults → qdrant path
    env = {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "VECTOR_PATH": "qdrant",
        # Prefer canonical, but keep legacy to validate deprecation path
        "AXIOM_EMBEDDING_MODEL": "tests/no-embedder",
    }

    # Monkeypatch embedder and qdrant client
    import vector.unified_client as uv

    class FakeEmbedder:
        def encode(self, text, normalize_embeddings=True):
            return [0.0] * 3 if isinstance(text, str) else [[0.0] * 3]

    uv._SentenceTransformer = lambda name: FakeEmbedder()

    hits = [
        FakeQdrantPoint(0.9, {"text": "alpha", "tags": ["x", "y"]}),
        FakeQdrantPoint(0.6, {"content": "beta", "tags": ["y"]}),
        FakeQdrantPoint(0.4, {"text": "gamma", "tags": ["z"]}),
    ]

    fake_client = FakeQdrantClient(hits)

    class FakeQdrMod:
        class Filter:
            def __init__(self, must=None, should=None):
                self.must = must or []
                self.should = should or []

        class FieldCondition:
            def __init__(self, key, match):
                self.key = key
                self.match = match

        class MatchAny:
            def __init__(self, any):
                self.any = any

        class MatchValue:
            def __init__(self, value):
                self.value = value

    uv._qmodels = FakeQdrMod

    def fake_get_qdrant(self):
        return fake_client

    # Act
    client = UnifiedVectorClient(env)
    client._get_qdrant = fake_get_qdrant.__get__(client, UnifiedVectorClient)

    # Filter should keep only tags that intersect with {"y"}
    req = VectorSearchRequest(query="test", top_k=5, filter={"must": [{"key": "tags", "match": {"any": ["y"]}}]})
    resp = client.search(req)

    # Assert mapping
    assert len(resp.hits) == 2
    assert resp.hits[0].content in {"alpha", "beta"}
    # Ensure tags surfaced
    assert any("y" in h.tags for h in resp.hits)


def test_qdrant_circuit_breaker_opens(monkeypatch):
    env = {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "VECTOR_PATH": "qdrant",
        "AXIOM_EMBEDDING_MODEL": "tests/no-embedder",
    }

    import vector.unified_client as uv

    class FakeEmbedder:
        def encode(self, text, normalize_embeddings=True):
            return [0.0] * 3 if isinstance(text, str) else [[0.0] * 3]

    uv._SentenceTransformer = lambda name: FakeEmbedder()

    class FailingClient:
        def get_collections(self):
            return types.SimpleNamespace(collections=[types.SimpleNamespace(name="axiom_memories")])

        def search(self, **kwargs):
            raise RuntimeError("boom")

    client = UnifiedVectorClient(env)

    # Force qdrant client to failing stub
    client._get_qdrant = (lambda self=client: FailingClient())  # type: ignore

    # 3 consecutive failures → circuit opens
    for _ in range(3):
        _ = client.search(VectorSearchRequest(query="x"))

    # Next call should be blocked by circuit (no exceptions; empty)
    resp = client.search(VectorSearchRequest(query="x"))
    assert resp.hits == []


def test_qdrant_threshold_not_set_omits_parameter(monkeypatch):
    # Arrange: no threshold env set → client must NOT pass score_threshold kwarg
    env = {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "VECTOR_PATH": "qdrant",
        "AXIOM_EMBEDDING_MODEL": "tests/no-embedder",
    }

    import vector.unified_client as uv

    class FakeEmbedder:
        def encode(self, text, normalize_embeddings=True):
            return [0.0] * 3 if isinstance(text, str) else [[0.0] * 3]

    uv._SentenceTransformer = lambda name: FakeEmbedder()
    uv._qmodels = None

    class AssertNoThresholdClient:
        def __init__(self, hits):
            self._hits = hits

        def get_collections(self):
            return types.SimpleNamespace(collections=[types.SimpleNamespace(name="axiom_memories")])

        def search(self, collection_name=None, query_vector=None, limit=None, with_vectors=None, query_filter=None, **kwargs):
            assert "score_threshold" not in kwargs, "score_threshold should not be passed when env is unset"
            return list(self._hits)[: int(limit or 5)]

    hits = [
        FakeQdrantPoint(0.83, {"text": "example_person"}),
        FakeQdrantPoint(0.72, {"text": "axiom"}),
    ]
    fake_client = AssertNoThresholdClient(hits)

    client = UnifiedVectorClient(env)
    client._get_qdrant = (lambda self=client: fake_client)  # type: ignore

    resp = client.search(VectorSearchRequest(query="ExamplePerson Axiom", top_k=5))
    assert len(resp.hits) == 2


def test_qdrant_threshold_env_forwards_and_filters(monkeypatch):
    # Arrange: threshold env set → forwarded to client and low scores filtered out by mock
    env = {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "VECTOR_PATH": "qdrant",
        "AXIOM_EMBEDDING_MODEL": "tests/no-embedder",
        "AXIOM_VECTOR_SCORE_THRESHOLD": "0.90",
    }

    import vector.unified_client as uv

    class FakeEmbedder:
        def encode(self, text, normalize_embeddings=True):
            return [0.0] * 3 if isinstance(text, str) else [[0.0] * 3]

    uv._SentenceTransformer = lambda name: FakeEmbedder()
    uv._qmodels = None

    class ThresholdFilteringClient:
        def __init__(self, hits):
            self._hits = hits
            self.last_threshold = None

        def get_collections(self):
            return types.SimpleNamespace(collections=[types.SimpleNamespace(name="axiom_memories")])

        def search(self, collection_name=None, query_vector=None, limit=None, with_vectors=None, query_filter=None, **kwargs):
            self.last_threshold = kwargs.get("score_threshold")
            items = list(self._hits)
            thr = self.last_threshold
            if thr is not None:
                items = [p for p in items if float(getattr(p, "score", 0.0)) >= float(thr)]
            return items[: int(limit or 5)]

    hits = [
        FakeQdrantPoint(0.83, {"text": "example_person"}),
        FakeQdrantPoint(0.88, {"text": "axiom"}),
    ]
    fake_client = ThresholdFilteringClient(hits)

    client = UnifiedVectorClient(env)
    client._get_qdrant = (lambda self=client: fake_client)  # type: ignore

    resp = client.search(VectorSearchRequest(query="ExamplePerson Axiom", top_k=5))
    # Threshold should be forwarded and both hits are < 0.90 → empty
    assert fake_client.last_threshold == 0.90 or fake_client.last_threshold == 0.9
    assert len(resp.hits) == 0

