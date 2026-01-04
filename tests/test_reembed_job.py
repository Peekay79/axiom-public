from __future__ import annotations

import logging
import sys
import types


def _install_sentence_transformers_stub():
    if "sentence_transformers" in sys.modules:
        return
    m = types.ModuleType("sentence_transformers")

    class _StubModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, text, normalize_embeddings=True):
            class _Vec:
                def tolist(self):
                    return [0.1, 0.2, 0.3]

            return _Vec()

    m.SentenceTransformer = _StubModel
    sys.modules["sentence_transformers"] = m


class _RawStub:
    def __init__(self, points):
        self._points = list(points)

    # Used by _shadow_reset
    def get_collections(self):
        return types.SimpleNamespace(collections=[])

    def create_collection(self, *args, **kwargs):
        return True

    def delete(self, *args, **kwargs):
        return True

    def delete_collection(self, *args, **kwargs):
        return True

    def update_aliases(self, *args, **kwargs):
        return True

    # Upsert accepts either dict list or structs; accept and do nothing
    def upsert(self, *args, **kwargs):
        return True

    # Simple scroll that yields our provided points once
    def scroll(self, *args, **kwargs):
        return (list(self._points), None)

    # Canary eval path may call search; return empty
    def search(self, *args, **kwargs):
        return []


def test_reembed_logs_embedding_and_runs_smoke(tmp_path, caplog, monkeypatch):
    from retrieval import reembed_job as mod

    _install_sentence_transformers_stub()

    # Provide one point with payload text
    raw = _RawStub(points=[{"id": "1", "payload": {"text": "hello world"}}])

    monkeypatch.setattr(mod, "_qdrant_raw_client", lambda: raw)

    # Ensure env gate enabled and tiny batch size so we don't hit the flush path
    monkeypatch.setenv("REEMBED_ENABLED", "true")

    with caplog.at_level(logging.INFO):
        summary = mod.run_reembed(
            source_ns="src", shadow_ns="sh", alias_name="alias", batch_size=1,
            canaries_path=str(tmp_path / "none.jsonl"), eval_k=3,
            pass_kl_max=1.0, pass_recall_delta_min=-1.0, pass_latency_delta_max_ms=1000,
        )
    assert isinstance(summary, dict)
    # Canonical embedding tag present
    assert any("[RECALL][Embedding]" in rec.getMessage() for rec in caplog.records)


def test_reembed_disabled_fail_closed(monkeypatch):
    from retrieval.reembed_job import run_reembed

    monkeypatch.setenv("REEMBED_ENABLED", "false")
    out = run_reembed(
        source_ns="src", shadow_ns="sh", alias_name="alias", batch_size=1,
        canaries_path="canaries/default.jsonl", eval_k=3,
        pass_kl_max=1.0, pass_recall_delta_min=-1.0, pass_latency_delta_max_ms=1000,
    )
    assert out.get("decision") == "disabled"

