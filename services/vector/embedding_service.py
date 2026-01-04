"""
Minimal HTTP embedding service for the Vector pod.

Endpoints:
- GET /healthz
- POST /embed  { "texts": [...], "model": "BAAI/bge-small-en-v1.5" } -> { "vectors": [[...], ...] }

This lets the LLM pod do embedding-based recall without installing torch/sentence-transformers.
"""

from __future__ import annotations

import argparse
import logging
import os
import threading
import time
from typing import Any

from flask import Flask, jsonify, request

app = Flask(__name__)

log = logging.getLogger("axiom.embedding_service")

# Default embedding model for the vector pod.
# NOTE: this service must work without sentence_transformers as long as fastembed is installed.
# Env: AXIOM_EMBEDDING_MODEL_DEFAULT (preferred)
DEFAULT_MODEL = (os.getenv("AXIOM_EMBEDDING_MODEL_DEFAULT") or "").strip() or "BAAI/bge-small-en-v1.5"


def _expected_vector_size() -> int:
    """
    Expected embedding dimensionality. Default matches the Qdrant collections (384-d).
    """
    v = (
        os.getenv("AXIOM_QDRANT_VECTOR_SIZE")
        or os.getenv("AXIOM_EMBEDDING_DIM")
        or os.getenv("EMBEDDING_DIMS")
        or "384"
    )
    try:
        return int(str(v).strip())
    except Exception:
        return 384


EXPECTED_DIMS = _expected_vector_size()


def _fastembed_default_model_name() -> str:
    """
    Service-side default model selection (FastEmbed).

    Env:
      - AXIOM_EMBEDDING_MODEL_DEFAULT (preferred)
    """
    # DEFAULT_MODEL already resolves env + fallback.
    return DEFAULT_MODEL


def _parse_model_request(raw: Any) -> tuple[str, str]:
    """
    Returns (backend_hint, model_name) where backend_hint is one of:
      - "auto" (default)
      - "fastembed"
      - "sentence-transformers"

    Rules:
      - Missing/empty/"default" -> "auto" + service default model name
      - Explicit sentence-transformers request:
          "sentence-transformers/<name>"
          "sentence_transformers/<name>"
          "sentence-transformers:<name>"
          "sentence_transformers:<name>"
          "st:<name>"
    """
    s = ""
    try:
        s = str(raw or "").strip()
    except Exception:
        s = ""

    if s == "" or s.lower() == "default":
        return ("auto", _fastembed_default_model_name())

    low = s.lower()
    for pfx in ("sentence-transformers/", "sentence_transformers/"):
        if low.startswith(pfx):
            return ("sentence-transformers", s.split("/", 1)[1].strip() or _fastembed_default_model_name())
    for pfx in ("sentence-transformers:", "sentence_transformers:", "st:"):
        if low.startswith(pfx):
            return ("sentence-transformers", s.split(":", 1)[1].strip() or _fastembed_default_model_name())

    # No explicit backend: treat as "auto" (prefer fastembed if available; do not guess ST on failure).
    return ("auto", s)


class BackendUnavailableError(RuntimeError):
    pass


class _EmbedBackend:
    """
    Lazily-initialized embedder with strict backend preference order:
    FastEmbed (fastembed.TextEmbedding) first; only if unavailable, try sentence-transformers.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._embed_fn: Any = None
        self._model_name: str = ""
        self._kind: str = "none"
        self._init_error: str | None = None
        self._key: tuple[str, str] | None = None

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def model_name(self) -> str:
        return self._model_name or _fastembed_default_model_name()

    @property
    def dims(self) -> int:
        return EXPECTED_DIMS

    @property
    def init_error(self) -> str | None:
        return self._init_error

    def _init_fastembed(self, model: str):
        # Optional dependency: must be imported lazily.
        from fastembed import TextEmbedding  # type: ignore

        # Support both keyword and positional init styles across fastembed versions.
        try:
            te = TextEmbedding(model_name=model)
        except TypeError:
            te = TextEmbedding(model)

        def _embed(texts: list[str]) -> list[list[float]]:
            vecs = list(te.embed(texts))
            out: list[list[float]] = []
            for v in vecs:
                try:
                    out.append([float(x) for x in v.tolist()])  # type: ignore[attr-defined]
                except Exception:
                    out.append([float(x) for x in v])
            return out

        return _embed

    def _init_sentence_transformers(self, model: str):
        # Optional dependency: must be imported lazily.
        from sentence_transformers import SentenceTransformer  # type: ignore

        st = SentenceTransformer(model)

        def _embed(texts: list[str]) -> list[list[float]]:
            vecs = st.encode(texts, normalize_embeddings=True)
            try:
                return vecs.tolist()
            except Exception:
                return [list(map(float, v)) for v in vecs]

        return _embed

    def _has_fastembed(self) -> bool:
        try:
            import fastembed  # noqa: F401

            return True
        except Exception:
            return False

    def _has_sentence_transformers(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401

            return True
        except Exception:
            return False

    def ensure(self, *, model_name: str, backend_hint: str) -> None:
        model = (model_name or "").strip() or _fastembed_default_model_name()
        hint = (backend_hint or "auto").strip().lower()
        key = (hint, model)
        with self._lock:
            if self._embed_fn is not None and self._key == key:
                return

            self._embed_fn = None
            self._model_name = model
            self._kind = "none"
            self._init_error = None
            self._key = key

            # Backend selection:
            # - If fastembed is installed, "auto" uses fastembed even if ST exists.
            # - Only use sentence-transformers when fastembed is unavailable OR explicitly requested.
            if hint in ("sentence-transformers", "sentence_transformers", "st"):
                if not self._has_sentence_transformers():
                    self._init_error = "backend_unavailable: sentence_transformers_not_installed"
                    raise BackendUnavailableError(self._init_error)
                try:
                    self._embed_fn = self._init_sentence_transformers(model)
                    self._kind = "sentence-transformers"
                    log.info("[EmbeddingService] backend=sentence-transformers model=%s dims=%d", model, EXPECTED_DIMS)
                    return
                except Exception as e:
                    self._init_error = f"sentence_transformers_init_failed: {type(e).__name__}: {str(e)[:200]}"
                    raise BackendUnavailableError(self._init_error)

            # Default: fastembed if available, otherwise sentence-transformers if available.
            if self._has_fastembed():
                try:
                    self._embed_fn = self._init_fastembed(model)
                    self._kind = "fastembed"
                    log.info("[EmbeddingService] backend=fastembed model=%s dims=%d", model, EXPECTED_DIMS)
                    return
                except Exception as e:
                    # Do NOT guess sentence-transformers on failure when fastembed is installed.
                    self._init_error = f"fastembed_init_failed: {type(e).__name__}: {str(e)[:200]}"
                    raise BackendUnavailableError(self._init_error)

            # fastembed not installed: try sentence-transformers if available.
            if not self._has_sentence_transformers():
                self._init_error = "backend_unavailable: fastembed_not_installed; sentence_transformers_not_installed"
                raise BackendUnavailableError(self._init_error)
            try:
                self._embed_fn = self._init_sentence_transformers(model)
                self._kind = "sentence-transformers"
                log.info("[EmbeddingService] backend=sentence-transformers model=%s dims=%d", model, EXPECTED_DIMS)
                return
            except Exception as e:
                self._init_error = f"sentence_transformers_init_failed: {type(e).__name__}: {str(e)[:200]}"
                raise BackendUnavailableError(self._init_error)

    def embed(self, *, texts: list[str], model_name: str, backend_hint: str) -> list[list[float]]:
        self.ensure(model_name=model_name, backend_hint=backend_hint)
        if self._embed_fn is None:
            raise BackendUnavailableError("backend_unavailable")
        return self._embed_fn(texts)


_BACKEND = _EmbedBackend()

def _startup_init_backend() -> None:
    # Best-effort init to surface backend selection early and emit safe startup logs.
    try:
        _BACKEND.ensure(model_name=_fastembed_default_model_name(), backend_hint="auto")
    except Exception:
        pass

# Initialize at serving-start when possible (still lazy: optional deps import happens here, not at module import time).
try:
    if hasattr(app, "before_serving"):
        app.before_serving(_startup_init_backend)  # type: ignore[attr-defined]
    else:
        app.before_first_request(_startup_init_backend)  # type: ignore[attr-defined]
except Exception:
    pass


@app.get("/healthz")
def healthz():
    model = _fastembed_default_model_name()
    try:
        _BACKEND.ensure(model_name=model, backend_hint="auto")
    except BackendUnavailableError:
        return (
            jsonify(
                {
                    "status": "degraded",
                    "backend": "none",
                    "model": model,
                    "dims": EXPECTED_DIMS,
                    "error": _BACKEND.init_error or "backend_unavailable",
                }
            ),
            503,
        )
    return (
        jsonify(
            {
                "status": "ok",
                "backend": _BACKEND.kind,
                "model": _BACKEND.model_name,
                "dims": EXPECTED_DIMS,
            }
        ),
        200,
    )


@app.post("/embed")
def embed():
    t0 = time.time()
    body: Any = request.get_json(silent=True) or {}
    texts = body.get("texts")
    # Normalize model selection:
    # - Missing/empty/"default" (any case) -> service default model
    raw = (body.get("model") or "").strip()
    if raw == "" or raw.lower() == "default":
        backend_hint, model = ("auto", DEFAULT_MODEL)
    else:
        backend_hint, model = _parse_model_request(raw)

    if not isinstance(texts, list) or not all(isinstance(x, str) for x in texts):
        return jsonify({"error": "invalid_request: expected JSON {texts:[...], model?:...}"}), 400

    try:
        vectors = _BACKEND.embed(texts=texts, model_name=str(model), backend_hint=backend_hint)

        if len(vectors) != len(texts):
            return (
                jsonify(
                    {
                        "error": f"embed_failed: count_mismatch expected={len(texts)} got={len(vectors)}",
                    }
                ),
                400,
            )

        # Enforce expected embedding dimensionality (default: 384).
        for i, v in enumerate(vectors):
            if not isinstance(v, list):
                return jsonify({"error": f"embed_failed: invalid_vector_type index={i}"}), 400
            if len(v) != EXPECTED_DIMS:
                return (
                    jsonify(
                        {
                            "error": (
                                f"embedding_dim_mismatch: expected={EXPECTED_DIMS} got={len(v)} "
                                f"backend={_BACKEND.kind} model={_BACKEND.model_name}"
                            )
                        }
                    ),
                    400,
                )

        # Safe per-request log: never include text contents.
        try:
            log.info(
                "[EmbeddingService] /embed backend=%s count=%d dims=%d ms=%d",
                _BACKEND.kind,
                len(texts),
                EXPECTED_DIMS,
                int((time.time() - t0) * 1000),
            )
        except Exception:
            pass

        return jsonify({"vectors": vectors}), 200
    except Exception as e:
        msg = str(e)[:220]
        if isinstance(e, BackendUnavailableError):
            # The service can't satisfy this request without installing a backend.
            msg = _BACKEND.init_error or msg
            return jsonify({"error": msg}), 400
        return jsonify({"error": f"embed_failed: {type(e).__name__}: {msg}"}), 400


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=os.getenv("AXIOM_EMBEDDING_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.getenv("AXIOM_EMBEDDING_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.getenv("AXIOM_EMBEDDING_PORT", "8020")))
    args = ap.parse_args(argv)
    _startup_init_backend()

    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

