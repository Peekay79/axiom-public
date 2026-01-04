import importlib

import pytest


def _install_fastembed_stub(monkeypatch, mod):
    """
    Hermetic stub: avoid importing fastembed / downloading models.
    We still exercise the /embed request parsing + "default" normalization.
    """

    def _fake_init_fastembed(_model: str):
        def _embed(texts: list[str]) -> list[list[float]]:
            return [[0.0 for _ in range(mod.EXPECTED_DIMS)] for _ in texts]

        return _embed

    monkeypatch.setattr(mod._BACKEND, "_has_fastembed", lambda: True)
    monkeypatch.setattr(mod._BACKEND, "_init_fastembed", _fake_init_fastembed)
    monkeypatch.setattr(mod._BACKEND, "_has_sentence_transformers", lambda: False)


def test_embed_missing_model_and_default_model_return_vectors_384d(monkeypatch):
    pytest.importorskip("flask")

    # Ensure expected dims for the test regardless of runner env.
    monkeypatch.setenv("AXIOM_QDRANT_VECTOR_SIZE", "384")
    monkeypatch.delenv("AXIOM_EMBEDDING_DIM", raising=False)
    monkeypatch.delenv("EMBEDDING_DIMS", raising=False)

    mod = importlib.import_module("pods.vector.embedding_service")
    mod = importlib.reload(mod)
    _install_fastembed_stub(monkeypatch, mod)

    c = mod.app.test_client()

    r1 = c.post("/embed", json={"texts": ["hi"]})
    assert r1.status_code == 200
    assert r1.is_json
    body1 = r1.get_json()
    assert isinstance(body1, dict)
    assert "vectors" in body1
    assert isinstance(body1["vectors"], list)
    assert len(body1["vectors"]) == 1
    assert len(body1["vectors"][0]) == 384

    r2 = c.post("/embed", json={"texts": ["hi"], "model": "default"})
    assert r2.status_code == 200
    assert r2.is_json
    body2 = r2.get_json()
    assert isinstance(body2, dict)
    assert "vectors" in body2
    assert isinstance(body2["vectors"], list)
    assert len(body2["vectors"]) == 1
    assert len(body2["vectors"][0]) == 384

