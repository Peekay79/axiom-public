# vector_adapter.py - Qdrant-only implementation

import json
import logging
import os
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
from datetime import datetime
from uuid import uuid4

try:
    import aiohttp  # type: ignore
except Exception:  # pragma: no cover
    aiohttp = None  # type: ignore
try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore
_SENTENCE_MODEL = None
def get_sentence_model():
    global _SENTENCE_MODEL
    if _SENTENCE_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer as _ST
            try:
                logger.info("[RECALL][Vector] Loading SentenceTransformer for vector adapter: %s", EMBEDDING_MODEL)
            except Exception:
                pass
            _SENTENCE_MODEL = _ST(EMBEDDING_MODEL)
            try:
                logger.info("[RECALL][Vector] SentenceTransformer ready: %s", EMBEDDING_MODEL)
            except Exception:
                pass
        except Exception as e:
            try:
                logger.warning("[RECALL][Vector] SentenceTransformer unavailable: %s", e)
            except Exception:
                pass
            _SENTENCE_MODEL = None
    return _SENTENCE_MODEL

logger = logging.getLogger("vector_adapter")
try:
    # Ensure emoji-safe formatting available for recall logs
    from utils.logging_utf8 import emoji
except Exception:
    def emoji(a: str, b: str) -> str:  # type: ignore
        return a

# Correlation helper
try:
    from tracing.correlation import get_or_create_request_id, HEADER_NAME as _RID_HEADER
except Exception:  # pragma: no cover - safe fallback
    def get_or_create_request_id(_headers):  # type: ignore
        from uuid import uuid4 as _u

        return _u().hex

    _RID_HEADER = "X-Request-ID"


# Use QDRANT_URL for vector database operations
def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


USE_QDRANT_BACKEND = _env_bool("USE_QDRANT_BACKEND", False)
VECTOR_RECALL_DISABLED = _env_bool("VECTOR_RECALL_DISABLED", False)

# Endpoint resolution precedence: QDRANT_URL -> VECTOR_POD_URL -> QDRANT_HOST:QDRANT_PORT
# IMPORTANT:
# - Do NOT default to localhost here. If nothing is configured, treat vector as disabled.
# - Do NOT perform any network calls at import time.
_QDRANT_URL_ENV = (os.getenv("QDRANT_URL", "") or "").strip()
_VECTOR_POD_URL_ENV = (os.getenv("VECTOR_POD_URL", "") or "").strip()
_QDRANT_HOST_ENV = (os.getenv("QDRANT_HOST", "") or "").strip()
_QDRANT_PORT_ENV = (os.getenv("QDRANT_PORT", "") or "").strip() or "6333"

_QDRANT_CONFIGURED = bool(_QDRANT_URL_ENV or _VECTOR_POD_URL_ENV or _QDRANT_HOST_ENV)
if _QDRANT_URL_ENV:
    QDRANT_URL = _QDRANT_URL_ENV
elif _VECTOR_POD_URL_ENV:
    QDRANT_URL = _VECTOR_POD_URL_ENV
elif _QDRANT_HOST_ENV:
    QDRANT_URL = f"http://{_QDRANT_HOST_ENV}:{_QDRANT_PORT_ENV}"
else:
    QDRANT_URL = ""

_VECTOR_ENABLED = bool(_QDRANT_CONFIGURED) and (not VECTOR_RECALL_DISABLED)
_VECTOR_DISABLED_LOGGED = False

AXIOM_EMBEDDING_URL = (
    os.getenv("AXIOM_EMBEDDING_URL", "")
    or os.getenv("EMBEDDINGS_API_URL", "")
    or os.getenv("EMBEDDINGS_POD_URL", "")
    or os.getenv("VECTOR_EMBEDDING_URL", "")
    or ""
).strip()
AXIOM_EMBEDDING_MODEL = (os.getenv("AXIOM_EMBEDDING_MODEL", "") or "").strip() or "BAAI/bge-small-en-v1.5"


class EmbedderError(RuntimeError):
    pass


class Embedder:
    """Small abstraction over embedding backends."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_text(self, text: str) -> list[float]:
        vecs = self.embed_texts([text])
        if not vecs:
            raise EmbedderError("embedder_returned_empty")
        return vecs[0]


class DisabledEmbedder(Embedder):
    def __init__(self, reason: str):
        self._reason = reason

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise EmbedderError(
            "embedder_unavailable: "
            + self._reason
            + " (set AXIOM_EMBEDDING_URL or EMBEDDINGS_API_URL to a remote embedding service, or install sentence-transformers/torch)"
        )


class LocalSentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is not None:
            return self._model
        # Import-safe: only import when actually needed.
        from sentence_transformers import SentenceTransformer as _ST  # type: ignore

        logger.info("[RECALL][Vector] Loading SentenceTransformer embedder: %s", self._model_name)
        self._model = _ST(self._model_name)
        logger.info("[RECALL][Vector] SentenceTransformer ready: %s", self._model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        m = self._get_model()
        vecs = m.encode(texts, normalize_embeddings=True)
        try:
            return vecs.tolist()
        except Exception:
            return [list(map(float, v)) for v in vecs]


class RemoteHttpEmbedder(Embedder):
    def __init__(self, base_url: str, model_name: str):
        self._base = (base_url or "").rstrip("/")
        m = (model_name or "").strip()
        if not m or m == "default":
            m = AXIOM_EMBEDDING_MODEL
        # Never send "default" to the service; always send a concrete model name.
        if m == "default":
            m = "BAAI/bge-small-en-v1.5"
        self._model = m
        self._timeout = float(os.getenv("AXIOM_EMBEDDING_TIMEOUT_SEC", "12") or 12)

    @property
    def endpoint(self) -> str:
        return f"{self._base}/embed"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Keep payload minimal; never log texts/vectors.
        body = {"texts": texts, "model": self._model}
        try:
            r = requests.post(self.endpoint, json=body, timeout=self._timeout)
            r.raise_for_status()
            data = r.json() or {}
            vecs = data.get("vectors")
            if not isinstance(vecs, list):
                raise EmbedderError("remote_embedder_invalid_response: missing 'vectors' list")
            # Defensive normalization to list[list[float]]
            out: list[list[float]] = []
            for v in vecs:
                if isinstance(v, list):
                    out.append([float(x) for x in v])
            if len(out) != len(texts):
                raise EmbedderError(
                    f"remote_embedder_count_mismatch: expected={len(texts)} got={len(out)}"
                )
            return out
        except EmbedderError:
            raise
        except Exception as e:
            raise EmbedderError(f"remote_embedder_failed: {type(e).__name__}: {str(e)[:200]}") from e


def _log_vector_disabled_once(reason: str) -> None:
    global _VECTOR_DISABLED_LOGGED
    if _VECTOR_DISABLED_LOGGED:
        return
    _VECTOR_DISABLED_LOGGED = True
    try:
        logger.warning("[VectorAdapter] Vector/Qdrant disabled (%s)", reason)
    except Exception:
        pass

# Diagnostics feature flag
RECALL_DIAGNOSTICS = str(os.getenv("RECALL_DIAGNOSTICS", "false")).strip().lower() in {"1", "true", "yes"}

# Emit adapter init diagnostics and warnings about localhost
try:
    if RECALL_DIAGNOSTICS:
        logger.info(json.dumps({
            "component": "vector",
            "event": "vector_adapter_init",
            "qdrant_url": QDRANT_URL,
            "use_qdrant": bool(USE_QDRANT_BACKEND)
        }))
except Exception:
    pass

# ── Retrieval drift sampling controls (env-gated, fail-closed) ───────────────
RETRIEVAL_DRIFT_ENABLED = _env_bool("RETRIEVAL_DRIFT_ENABLED", True)
_DRIFT_SAMPLE_EVERY_N = int(os.getenv("DRIFT_SAMPLE_EVERY_N", "100") or 100)
_DRIFT_COUNTER = 0

# Environment configuration
VECTOR_DB_HOST = QDRANT_URL
try:
    # Prefer Memory's source-of-truth (AXIOM_* first)
    from memory.embedding_config import embedding_model_name as _embedding_model_name
    EMBEDDING_MODEL = _embedding_model_name()
except Exception:
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CERTAINTY_MIN = float(os.getenv("VECTOR_CERTAINTY_MIN", "0.25"))
TOP_K_FRAGMENTS = int(os.getenv("VECTOR_TOPK", "10"))

# Ingest chunking envs (defaults tuned for Axiom)
_INGEST_MAX_TOKENS_PER_CHUNK = int(os.getenv("AXIOM_INGEST_MAX_TOKENS_PER_CHUNK", "512") or 512)
_INGEST_CHUNK_OVERLAP = int(os.getenv("AXIOM_INGEST_CHUNK_OVERLAP", "64") or 64)
_INGEST_CHUNK_TYPES = [
    t.strip().lower()
    for t in (os.getenv(
        "AXIOM_INGEST_CHUNK_TYPES",
        "short_term,episodic,semantic,relationship,entity",
    )
        or ""
    ).split(",")
    if t.strip()
]
_MAX_SINGLE_MEMORY_TOKENS = int(os.getenv("AXIOM_MAX_SINGLE_MEMORY_TOKENS", "1200") or 1200)

def _tok_est(s: str) -> int:
    try:
        return max(1, len((s or "")) // 4)
    except Exception:
        return 1

def _chunk_text_by_tokens(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """Chunk text approximately by tokens using len/4 heuristic with overlap.
    Returns list of chunk strings in order.
    """
    if not text:
        return []
    max_tokens = max(1, int(max_tokens))
    overlap_tokens = max(0, int(overlap_tokens))
    approx_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    chunks: list[str] = []
    i = 0
    n = len(text)
    if n <= approx_chars:
        return [text]
    while i < n:
        j = min(n, i + approx_chars)
        chunk = text[i:j]
        chunks.append(chunk)
        if j >= n:
            break
        # slide with overlap
        i = max(0, j - overlap_chars)
    return chunks

# Vector recall configuration - using Qdrant collections
# Use unified collection names
from memory.memory_collections import beliefs_collection as _beliefs_collection
from memory.memory_collections import memory_collection as _memory_collection

MEMORY_COLLECTION = _memory_collection()
BELIEF_COLLECTION = _beliefs_collection()
try:
    from memory.memory_collections import archive_collection as _archive_collection

    ARCHIVE_COLLECTION = _archive_collection()
except Exception:
    ARCHIVE_COLLECTION = "axiom_memory_archives"

# Load vector environment configuration
try:
    from dotenv import load_dotenv

    load_dotenv(".env.vector")  # Load vector-specific config
    load_dotenv()  # Fallback to general .env
except ImportError:
    pass

import requests

try:
    from axiom_qdrant_client import QdrantClient  # type: ignore
except Exception as _e:  # pragma: no cover
    # Import-safe: LLM pod may not have qdrant-client installed.
    QdrantClient = None  # type: ignore
    try:
        logger.warning("[VectorAdapter] Qdrant client unavailable: %s", str(_e)[:160])
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# Resiliency (timeouts, retries, circuit breaker) for Qdrant calls
_m = None
try:
    from observability import metrics as _m  # type: ignore
except Exception:
    class _NullMetrics:
        def inc(self, *_args, **_kwargs):
            pass

        def observe_ms(self, *_args, **_kwargs):
            pass

    _m = _NullMetrics()  # type: ignore


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return int(default)


VECTOR_ADAPTER_TIMEOUT_SEC = _env_int("VECTOR_ADAPTER_TIMEOUT_SEC", 8)
VECTOR_ADAPTER_RETRIES = _env_int("VECTOR_ADAPTER_RETRIES", 2)  # total attempts = retries + 1
VECTOR_ADAPTER_CIRCUIT_OPEN_SEC = _env_int("VECTOR_ADAPTER_CIRCUIT_OPEN_SEC", 20)


class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, open_seconds: int = 20):
        self._failure_threshold = max(1, int(failure_threshold))
        self._open_seconds = max(1, int(open_seconds))
        self._state = "closed"  # closed | open | half_open
        self._opened_at = 0.0
        self._consecutive_failures = 0
        self._lock = threading.Lock()

    def is_open(self) -> bool:
        # Non-mutating check: returns True only if fully open and still within open window
        with self._lock:
            if self._state != "open":
                return False
            return (time.monotonic() - self._opened_at) < self._open_seconds

    def can_execute(self) -> bool:
        # May transition from open -> half_open when window elapses
        with self._lock:
            if self._state == "open":
                if (time.monotonic() - self._opened_at) >= self._open_seconds:
                    self._state = "half_open"
                    return True
                return False
            return True

    def on_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._state = "closed"

    def on_failure(self) -> bool:
        # Returns True if this call transitioned the breaker to open
        opened = False
        with self._lock:
            if self._state == "half_open":
                # Any failure during half-open immediately opens the breaker again
                self._state = "open"
                self._opened_at = time.monotonic()
                self._consecutive_failures = 0
                opened = True
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_threshold:
                    self._state = "open"
                    self._opened_at = time.monotonic()
                    self._consecutive_failures = 0
                    opened = True
        return opened


_CB = _CircuitBreaker(failure_threshold=3, open_seconds=VECTOR_ADAPTER_CIRCUIT_OPEN_SEC)
_EXECUTOR = ThreadPoolExecutor(max_workers=8)


def _current_request_id() -> str | None:
    try:
        from flask import request as _req  # type: ignore

        return get_or_create_request_id(_req.headers)
    except Exception:
        return None


def _jitter(seconds: float) -> float:
    # Apply +/-25% jitter
    if seconds <= 0:
        return 0.0
    factor = random.uniform(0.75, 1.25)
    return max(0.0, seconds * factor)


def _with_resiliency(func, *args, **kwargs):
    """
    Execute a synchronous callable with timeout/retries/circuit breaker.

    kwargs supported:
      - request_id: optional correlation id for logs
      - timeout_sec: per-attempt timeout (default VECTOR_ADAPTER_TIMEOUT_SEC)
      - retries: number of retries (default VECTOR_ADAPTER_RETRIES)
    """
    request_id = kwargs.pop("request_id", None) or _current_request_id()
    timeout_sec = int(kwargs.pop("timeout_sec", VECTOR_ADAPTER_TIMEOUT_SEC))
    retries = int(kwargs.pop("retries", VECTOR_ADAPTER_RETRIES))

    if not _CB.can_execute():
        raise RuntimeError("circuit_open")

    attempts = 0
    backoffs = [0.2, 0.8]
    # Ensure we only sleep for the configured retries count
    backoffs = backoffs[: max(0, retries)]

    while True:
        if attempts > 0:
            # sleep before retry attempt
            idx = attempts - 1
            if idx < len(backoffs):
                time.sleep(_jitter(backoffs[idx]))

        start = time.perf_counter()
        try:
            future = _EXECUTOR.submit(func, *args, **kwargs)
            result = future.result(timeout=timeout_sec)
            try:
                _m.observe_ms("adapter.qdrant.ms", (time.perf_counter() - start) * 1000.0)
                _m.inc("adapter.qdrant.ok")
            except Exception:
                pass
            _CB.on_success()
            return result
        except _FutTimeout as e:
            try:
                _m.observe_ms("adapter.qdrant.ms", (time.perf_counter() - start) * 1000.0)
                _m.inc("adapter.qdrant.err")
            except Exception:
                pass
            opened = _CB.on_failure()
            if opened:
                try:
                    _m.inc("adapter.circuit.open")
                    line = {"component": "vector", "event": "circuit_open", "path": "qdrant"}
                    if request_id:
                        line["request_id"] = request_id
                    logger.warning(json.dumps(line))
                except Exception:
                    pass
            if attempts >= retries:
                raise TimeoutError("vector adapter qdrant call timed out") from e
        except Exception as e:
            try:
                _m.observe_ms("adapter.qdrant.ms", (time.perf_counter() - start) * 1000.0)
                _m.inc("adapter.qdrant.err")
            except Exception:
                pass
            opened = _CB.on_failure()
            if opened:
                try:
                    _m.inc("adapter.circuit.open")
                    line = {"component": "vector", "event": "circuit_open", "path": "qdrant"}
                    if request_id:
                        line["request_id"] = request_id
                    logger.warning(json.dumps(line))
                except Exception:
                    pass
            if attempts >= retries:
                raise
        attempts += 1

def _list_collection_names(client):
    """
    Return a set of collection names for both old and new qdrant-client versions.
    """
    # Newer clients:
    if hasattr(client, "get_collections"):
        try:
            resp = client.get_collections()
            # v1.6+ returns an object with .collections list with .name fields
            return {
                getattr(c, "name", None)
                for c in getattr(resp, "collections", [])
                if getattr(c, "name", None)
            }
        except Exception:
            pass
    # Fallbacks:
    try:
        # Some older clients had .get_collection or .collections property
        if hasattr(client, "collections"):
            col = client.collections
            return {
                getattr(c, "name", None)
                for c in getattr(col, "collections", [])
                if getattr(c, "name", None)
            }
    except Exception:
        pass
    # Try get_collections().collections pattern
    try:
        resp = client.get_collections()
        cols = getattr(resp, "collections", None)
        if cols:
            return {getattr(c, "name", c) for c in cols}
    except AttributeError:
        # REST API fallback
        try:
            import requests

            host = getattr(client, "host", "localhost")
            port = getattr(
                client, "port", int(os.getenv("QDRANT_PORT", "6333"))
            )  # ⚠️ Replaced hardcoded fallback with env-respecting default
            url = f"http://{host}:{port}/collections"

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            if (
                isinstance(data, dict)
                and "result" in data
                and "collections" in data["result"]
            ):
                collections = data["result"]["collections"]
                names = set()
                for c in collections:
                    if isinstance(c, dict) and "name" in c:
                        names.add(c["name"])
                    elif hasattr(c, "name"):
                        names.add(c.name)
                return names
        except Exception:
            pass
    return set()


async def check_vector_server_health(host: str):
    """Check Qdrant server health respecting QDRANT_HEALTH_PATH with fallback.

    - If QDRANT_HEALTH_PATH is set (default '/collections'), GET that path and treat 200 as healthy.
    - If health path is '/health' and returns 404, fallback to '/collections' and treat 200 as healthy.
    - Log clear status lines for visibility.
    """
    health_path = os.getenv("QDRANT_HEALTH_PATH", "/collections") or "/collections"
    base = host.rstrip("/")
    primary = f"{base}{health_path if health_path.startswith('/') else '/' + health_path}"
    fallback = f"{base}/collections"
    try:
        if aiohttp is not None:
            async with aiohttp.ClientSession() as session:  # type: ignore
                async with session.get(primary, timeout=5) as resp:
                    if resp.status == 200:
                        logger.info(f"[Vector][Health] path={health_path} status=200 (OK)")
                        return True
                    if health_path == "/health" and resp.status == 404:
                        async with session.get(fallback, timeout=5) as r2:
                            if r2.status == 200:
                                logger.info("[Vector][Health] path=/health status=404 → fallback /collections=200 (OK)")
                                return True
                            logger.error(f"[Vector][Health] fallback /collections status={r2.status}")
                            return False
                    body = await resp.text()
                    logger.error(f"[Vector][Health] path={health_path} status={resp.status} body_len={len(body)}")
                    return False
        # Fallback without aiohttp (best-effort; blocks the event loop only in health checks)
        r = requests.get(primary, timeout=5)
        if r.status_code == 200:
            logger.info(f"[Vector][Health] path={health_path} status=200 (OK)")
            return True
        if health_path == "/health" and r.status_code == 404:
            r2 = requests.get(fallback, timeout=5)
            if r2.status_code == 200:
                logger.info("[Vector][Health] path=/health status=404 → fallback /collections=200 (OK)")
                return True
            logger.error(f"[Vector][Health] fallback /collections status={r2.status_code}")
            return False
        logger.error(f"[Vector][Health] path={health_path} status={r.status_code} body_len={len(r.text or '')}")
        return False
    except Exception as e:
        logger.warning(f"[Vector][Health] probe failed: {e}")
        return False


def _http_collection_names(base_url: str, timeout_sec: float = 2.0) -> set[str] | None:
    """HTTP /collections probe that doesn't depend on qdrant-client."""
    if not base_url:
        return None
    url = base_url.rstrip("/") + "/collections"
    try:
        r = requests.get(url, timeout=timeout_sec)
        if r.status_code != 200:
            return None
        data = r.json() or {}
        cols = (((data or {}).get("result") or {}).get("collections")) or []
        out: set[str] = set()
        if isinstance(cols, list):
            for c in cols:
                if isinstance(c, dict) and isinstance(c.get("name"), str):
                    out.add(c["name"])
        return out
    except Exception:
        return None


def _select_effective_qdrant_url(resolved_url: str) -> str:
    """
    Safety: when QDRANT_URL points to an empty instance but VECTOR_POD_URL has the real collections,
    prefer VECTOR_POD_URL unless QDRANT_URL is explicitly set.
    """
    vector_pod_url = _VECTOR_POD_URL_ENV
    if not resolved_url or not vector_pod_url:
        return resolved_url

    expected = {MEMORY_COLLECTION, BELIEF_COLLECTION, ARCHIVE_COLLECTION}
    q_cols = _http_collection_names(resolved_url, timeout_sec=2.0)
    v_cols = _http_collection_names(vector_pod_url, timeout_sec=2.0)

    if q_cols == set() and isinstance(v_cols, set) and expected.issubset(v_cols):
        msg = (
            "[VectorAdapter] Qdrant endpoint mismatch: QDRANT_URL /collections is empty, "
            f"but VECTOR_POD_URL has expected collections {sorted(expected)}. "
            f"QDRANT_URL={resolved_url} VECTOR_POD_URL={vector_pod_url}"
        )
        if _QDRANT_URL_ENV:
            # User explicitly set QDRANT_URL; do not override.
            logger.error(msg + " (keeping QDRANT_URL because it is explicitly set)")
            return resolved_url
        logger.warning(msg + " (preferring VECTOR_POD_URL)")
        return vector_pod_url

    # If both are reachable but disagree, emit a loud warning for visibility.
    if isinstance(q_cols, set) and isinstance(v_cols, set) and q_cols != v_cols and expected.issubset(v_cols):
        try:
            logger.warning(
                "[VectorAdapter] Qdrant endpoints differ: QDRANT_URL cols=%s VECTOR_POD_URL cols=%s",
                sorted(q_cols),
                sorted(v_cols),
            )
        except Exception:
            pass
    return resolved_url


def verify_qdrant_collections() -> bool:
    """Verify that required collections exist in Qdrant"""
    if not _VECTOR_ENABLED:
        return False
    if QdrantClient is None:
        return False
    try:
        # Parse host and port from QDRANT_URL
        if "://" in QDRANT_URL:
            host_port = QDRANT_URL.split("://")[1]
        else:
            host_port = QDRANT_URL

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = int(
                os.getenv("QDRANT_PORT", "6333")
            )  # ⚠️ Replaced hardcoded fallback with env-respecting default

        client = QdrantClient(host=host, port=port)
        collections = _list_collection_names(client)

        required_collections = [MEMORY_COLLECTION, BELIEF_COLLECTION]
        for collection_name in required_collections:
            if collection_name not in collections:
                logger.error(
                    f"[RECALL][Vector] ❌ Qdrant collection '{collection_name}' not found"
                )
                return False

        logger.info(f"[RECALL][Vector] ✅ All required Qdrant collections found")
        return True
    except Exception as e:
        logger.error(f"[RECALL][Vector] ❌ Qdrant collection check failed: {e}")
        return False


def _startup_checks_if_enabled() -> None:
    """
    Best-effort health/collection checks.
    Must never run at import time; callers should invoke only during startup paths.
    """
    if not _VECTOR_ENABLED:
        return
    if os.getenv("AXIOM_CANARIES", "1").strip().lower() in {"0", "false", "no"}:
        return
    try:
        ok = verify_qdrant_collections()
        if not ok:
            logger.warning("[RECALL][Vector] Required Qdrant collections missing; vector may be degraded.")
    except Exception:
        pass
    try:
        import asyncio

        loop = asyncio.get_event_loop()
        ok = loop.run_until_complete(check_vector_server_health(QDRANT_URL))
        if not ok:
            logger.warning("[Vector][Health] Qdrant probe failed; vector may be degraded.")
    except Exception:
        pass


class VectorAdapter:
    def __init__(self):
        # Track Qdrant vs embedder availability independently
        self.qdrant_unavailable: bool = False
        self.embedder_unavailable: bool = False
        self._unavailable_logged: bool = False

        if not _VECTOR_ENABLED:
            self.base_url = ""
            self.vector_host = ""
            self.embedder: Embedder = DisabledEmbedder("vector_disabled")
            self.qdrant_client = None  # type: ignore
            self.qdrant_unavailable = True
            self.embedder_unavailable = True
            _log_vector_disabled_once(
                "VECTOR_RECALL_DISABLED=true"
                if VECTOR_RECALL_DISABLED
                else "QDRANT/VECTOR_POD_URL unset"
            )
            return

        effective_url = _select_effective_qdrant_url(QDRANT_URL)
        self.base_url = (effective_url or "").rstrip("/")
        self.vector_host = effective_url or ""

        # Embedder selection: prefer remote when configured (no torch/sentence_transformers needed),
        # otherwise fall back to local sentence_transformers if available.
        self.embedder = DisabledEmbedder("uninitialized")
        if AXIOM_EMBEDDING_URL:
            # Best-effort: verify embedding service is reachable.
            try:
                hz = f"{AXIOM_EMBEDDING_URL.rstrip('/')}/healthz"
                r = requests.get(hz, timeout=2.0)
                if r.status_code != 200:
                    raise RuntimeError(f"healthz_http_{r.status_code}")
                # Deterministic: always tell the service which model to use (never omit, never "default").
                self.embedder = RemoteHttpEmbedder(AXIOM_EMBEDDING_URL, model_name=AXIOM_EMBEDDING_MODEL)
                self.embedder_unavailable = False
                try:
                    logger.info("[RECALL][Vector] Using remote embeddings: %s", AXIOM_EMBEDDING_URL)
                except Exception:
                    pass
            except Exception as e:
                self.embedder = DisabledEmbedder(f"embeddings_unavailable: {type(e).__name__}: {str(e)[:160]}")
                self.embedder_unavailable = True
                try:
                    logger.warning("[RECALL][Vector] embeddings unavailable → vector recall disabled (%s)", e)
                except Exception:
                    pass
        else:
            try:
                # Probe local embedder availability (avoid torch imports at module import time).
                import torch  # type: ignore  # noqa: F401
                from sentence_transformers import SentenceTransformer as _ST  # type: ignore  # noqa: F401

                self.embedder = LocalSentenceTransformerEmbedder(EMBEDDING_MODEL)
                self.embedder_unavailable = False
            except Exception as e:
                self.embedder = DisabledEmbedder(f"local_embedder_unavailable: {type(e).__name__}: {str(e)[:160]}")
                self.embedder_unavailable = True

        # Initialize Qdrant client
        if QdrantClient is None:
            self.qdrant_client = None  # type: ignore
            self.qdrant_unavailable = True
            self._log_unavailable_once("qdrant_client_missing")
            return
        if "://" in self.vector_host:
            host_port = self.vector_host.split("://")[1]
        else:
            host_port = self.vector_host

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = int(
                os.getenv("QDRANT_PORT", "6333")
            )  # ⚠️ Replaced hardcoded fallback with env-respecting default

        try:
            self.qdrant_client = QdrantClient(host=host, port=port)
            self.qdrant_unavailable = False
        except Exception as e:
            self.qdrant_client = None  # type: ignore
            self.qdrant_unavailable = True
            self._log_unavailable_once(f"qdrant_client_init_failed: {type(e).__name__}")
            return

        # Best-effort startup checks; still no hard failure.
        _startup_checks_if_enabled()

    def _log_unavailable_once(self, reason: str) -> None:
        if self._unavailable_logged:
            return
        self._unavailable_logged = True
        try:
            logger.warning("[VectorAdapter] degraded (%s)", reason)
        except Exception:
            pass

    def _is_transport_error(self, e: BaseException) -> bool:
        msg = str(e).lower()
        # Keep this simple and conservative: only mark unavailable on likely network/transport issues.
        return any(
            k in msg
            for k in (
                "connection refused",
                "failed to connect",
                "connection error",
                "connecttimeout",
                "timeout",
                "unreachable",
                "name or service not known",
                "temporary failure in name resolution",
            )
        )

    def _mark_unavailable_if_transport_error(self, e: BaseException) -> None:
        if self.qdrant_unavailable:
            return
        if self._is_transport_error(e):
            self.qdrant_unavailable = True
            self._log_unavailable_once("qdrant_unreachable")

    async def insert(self, class_name: str, data: dict) -> bool:
        if self.qdrant_unavailable or getattr(self, "qdrant_client", None) is None:
            self._log_unavailable_once("disabled_or_unavailable")
            return False
        try:
            collection_name = (
                MEMORY_COLLECTION if class_name == "Memory" else BELIEF_COLLECTION
            )

            # Generate embedding for content/statement
            content_field = "content" if class_name == "Memory" else "statement"
            text_content = data.get(content_field, "")

            if not text_content:
                logger.warning(f"Empty {content_field} for {class_name} insertion")
                return False

            try:
                vector = self.embedder.embed_text(text_content)
            except EmbedderError as e:
                self.embedder_unavailable = True
                # Make the failure explicit: caller attempted an embedding-dependent operation.
                logger.error("[RECALL][Vector] insert requires embeddings: %s", e)
                raise
            # Drift sampling (1 per N) – best-effort and fail-closed
            global _DRIFT_COUNTER
            _DRIFT_COUNTER += 1
            if RETRIEVAL_DRIFT_ENABLED and _DRIFT_SAMPLE_EVERY_N > 0 and (_DRIFT_COUNTER % _DRIFT_SAMPLE_EVERY_N == 0):
                try:
                    from retrieval.drift import record_vector_sample, maybe_emit_drift  # type: ignore

                    record_vector_sample(collection_name, vector)
                    # Opportunistic drift emission (internally throttled)
                    maybe_emit_drift(collection_name)
                except Exception:
                    pass

            # Format payload
            payload = await self._format_payload(class_name, data)
            point_id = data.get("id", str(uuid4()))

            # Enforce ingestion defaults for composite scoring
            from qdrant_payload_schema import PayloadConverter

            payload = PayloadConverter.validate_payload(payload)

            # Use unified collection names
            if class_name != "Memory":
                from memory.memory_collections import (
                    beliefs_collection as _beliefs_collection,
                )

                collection_name = _beliefs_collection()

            # Ingest chunking for selected memory types
            if class_name == "Memory":
                mem_type = str(payload.get("memory_type") or payload.get("type") or "memory").lower()
                if mem_type in _INGEST_CHUNK_TYPES:
                    text_content = payload.get("text") or payload.get("content") or ""
                    chunks = _chunk_text_by_tokens(text_content, _INGEST_MAX_TOKENS_PER_CHUNK, _INGEST_CHUNK_OVERLAP)
                    if len(chunks) > 1:
                        parent_id = str(point_id)
                        total = len(chunks)
                        up_ok = 0
                        for idx, ch in enumerate(chunks):
                            ch_payload = dict(payload)
                            ch_payload["content"] = ch
                            ch_payload["text"] = ch
                            ch_payload["parent_id"] = parent_id
                            ch_payload["chunk_index"] = idx
                            ch_payload["chunk_total"] = total
                            ch_payload["ingest_version"] = "v1"
                            # New ID per chunk
                            chunk_id = f"{parent_id}:{idx}"
                            ch_vec = self.embedder.embed_text(ch)
                            def _call_upsert_chunk():
                                return self.qdrant_client.upsert_memory(
                                    collection_name=collection_name,
                                    memory_id=chunk_id,
                                    vector=ch_vec,
                                    payload=ch_payload,
                                )
                            ok = _with_resiliency(
                                _call_upsert_chunk,
                                request_id=None,
                                timeout_sec=VECTOR_ADAPTER_TIMEOUT_SEC,
                                retries=VECTOR_ADAPTER_RETRIES,
                            )
                            if ok:
                                up_ok += 1
                        try:
                            avg_tok = int(sum(_tok_est(c) for c in chunks) / max(1, len(chunks)))
                        except Exception:
                            avg_tok = _INGEST_MAX_TOKENS_PER_CHUNK
                        print(f"[RAG][INGEST] parent_id={parent_id} chunk_total={total} avg_tokens={avg_tok}")
                        return up_ok == total
            # Default single upsert path
            def _call_upsert():
                return self.qdrant_client.upsert_memory(
                    collection_name=collection_name,
                    memory_id=point_id,
                    vector=vector,
                    payload=payload,
                )

            success = _with_resiliency(
                _call_upsert,
                request_id=None,
                timeout_sec=VECTOR_ADAPTER_TIMEOUT_SEC,
                retries=VECTOR_ADAPTER_RETRIES,
            )

            if success:
                logger.info(
                    f"✅ {class_name} inserted into Qdrant collection {collection_name}"
                )
                return True
            else:
                logger.warning(f"⚠️ Failed to insert {class_name} into Qdrant")
                return False

        except EmbedderError:
            raise
        except Exception as e:
            logger.error(f"❌ Exception inserting {class_name}: {e}")
        return False

    async def _format_payload(self, class_name: str, data: dict) -> dict:
        """Format data into Qdrant payload structure"""
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())

        if class_name == "Memory":
            payload = {
                "content": data.get("content", ""),
                "text": data.get("content", ""),  # Compatibility field
                "speaker": data.get("speaker", "unknown"),
                "tags": data.get("tags", []),
                "importance": data.get("importance", 0.5),
                "isBelief": data.get("isBelief", False),
                "source": data.get("source", "vector_adapter"),
                "timestamp": timestamp,
                "memory_type": "memory",
            }

            # Handle belief references
            if "beliefs" in data and isinstance(data["beliefs"], list):
                payload["beliefs"] = data["beliefs"]

            return payload

        elif class_name == "Belief":
            payload = {
                "statement": data.get("statement", ""),
                "text": data.get("statement", ""),  # Compatibility field
                "belief_type": data.get("belief_type", "descriptive"),
                "confidence": data.get("confidence", 0.5),
                "importance": data.get("importance", 0.5),
                "source": data.get("source", "vector_adapter"),
                "timestamp": timestamp,
                "tags": data.get("tags", []),
                "memory_type": "belief",
            }
            return payload

        else:
            raise ValueError(f"Unsupported class: {class_name}")

    async def recall_relevant_memories(
        self,
        query: str,
        top_k: int = TOP_K_FRAGMENTS,
        certainty_min: float = CERTAINTY_MIN,
        include_metadata: bool = False,
        *,
        request_id: str | None = None,
    ) -> list[dict]:
        """
        Enhanced recall method using Qdrant that NEVER returns None - always returns a list.
        """
        if self.qdrant_unavailable or getattr(self, "qdrant_client", None) is None:
            self._log_unavailable_once("qdrant_unavailable")
            return []
        if not query or not isinstance(query, str):
            logger.warning(
                "[VectorAdapter] Vector query is empty or invalid. Returning empty list."
            )
            return []

        try:
            vector = self.embedder.embed_text(query)

            # Search in Qdrant via resiliency wrapper
            def _call_query():
                return self.qdrant_client.query_memory(
                    collection_name=MEMORY_COLLECTION,
                    query_vector=vector,
                    limit=top_k,
                    score_threshold=certainty_min,
                    filter_conditions=None,
                    include_vectors=False,
                )

            search_results = _with_resiliency(
                _call_query,
                request_id=request_id,
                timeout_sec=VECTOR_ADAPTER_TIMEOUT_SEC,
                retries=VECTOR_ADAPTER_RETRIES,
            )

            if not search_results:
                logger.debug(
                f"[VectorAdapter] No results found for query: {query[:80]}"
            )
                return []

            # Format results to match expected structure
            formatted_results = []
            for result in search_results:
                payload = result.payload

                if include_metadata:
                    # Return full metadata structure
                    formatted_hit = {
                        "text": payload.get("text", payload.get("content", "")),
                        "confidence": payload.get("confidence", result.score),
                        "importance": payload.get("importance", 0.5),
                        "_additional": {
                            "certainty": result.score,
                            "distance": 1.0 - result.score,
                            "vector": (
                                result.vector if hasattr(result, "vector") else None
                            ),
                        },
                    }
                    formatted_results.append(formatted_hit)
                else:
                    # Return just text content
                    text_content = payload.get("text", payload.get("content", ""))
                    if text_content:
                        formatted_results.append(text_content)

            logger.debug(
                f"[RECALL][Vector] fetched {len(formatted_results)} hits for '{query[:80]}'"
            )
            # Structured diagnostics log
            try:
                if RECALL_DIAGNOSTICS and request_id:
                    line = {
                        "component": "vector",
                        "event": "recall",
                        "ok": True,
                        "hits": len(formatted_results),
                        "top_k": int(top_k),
                        "threshold": float(certainty_min),
                        "request_id": request_id,
                    }
                    logger.info(json.dumps(line))
            except Exception:
                pass
            return formatted_results

        except EmbedderError as e:
            self.embedder_unavailable = True
            logger.error("[VectorAdapter] recall requires embeddings: %s", e)
            raise
        except Exception as e:
            self._mark_unavailable_if_transport_error(e)
            logger.error(
                f"[VectorAdapter] Vector recall failed: {type(e).__name__}: {e}. Returning empty list."
            )
            try:
                if RECALL_DIAGNOSTICS and request_id:
                    line = {
                        "component": "vector",
                        "event": "recall",
                        "ok": False,
                        "error": f"{type(e).__name__}: {str(e)[:180]}",
                        "request_id": request_id,
                    }
                    logger.info(json.dumps(line))
            except Exception:
                pass
            return []

    def search(
        self,
        query: str,
        top_k: int = 3,
        certainty_min: float = None,
        *,
        request_id: str | None = None,
    ) -> list[dict]:
        """
        Enhanced synchronous vector search method using Qdrant - NEVER returns None.
        """
        if self.qdrant_unavailable or getattr(self, "qdrant_client", None) is None:
            self._log_unavailable_once("disabled_or_unavailable")
            return []
        if not query or not isinstance(query, str):
            logger.warning(
                "[VectorAdapter] Vector search query is empty or invalid. Returning empty list."
            )
            return []

        try:
            # Use class default if not specified
            if certainty_min is None:
                certainty_min = CERTAINTY_MIN

            logger.info(
                f"[VectorAdapter] 🔍 Vector search initiated: query='{query[:50]}...', top_k={top_k}, certainty_min={certainty_min}"
            )

            vector_list = self.embedder.embed_text(query)
            logger.info(
                f"[VectorAdapter] 📊 Generated {len(vector_list)}-dimensional embedding vector"
            )

            # Search in Qdrant via resiliency wrapper
            def _call_query_sync():
                return self.qdrant_client.query_memory(
                    collection_name=MEMORY_COLLECTION,
                    query_vector=vector_list,
                    limit=top_k,
                    score_threshold=certainty_min,
                    filter_conditions=None,
                    include_vectors=False,
                )

            search_results = _with_resiliency(
                _call_query_sync,
                request_id=request_id,
                timeout_sec=VECTOR_ADAPTER_TIMEOUT_SEC,
                retries=VECTOR_ADAPTER_RETRIES,
            )

            if not search_results:
                logger.info("[VectorAdapter] No results found in Qdrant search")
                return []

            # Format results to match expected Weaviate-like structure
            formatted_results = []
            for result in search_results:
                payload = result.payload
                similarity = result.score

                # Create Weaviate-compatible hit structure
                formatted_hit = {
                    "id": getattr(result, "id", None),
                    "text": payload.get("text", payload.get("content", "")),
                    "confidence": payload.get("confidence", similarity),
                    "importance": payload.get("importance", 0.5),
                    "speaker": payload.get("speaker"),
                    "timestamp": payload.get("timestamp"),
                    "tags": payload.get("tags", []),
                    "_additional": {
                        "certainty": similarity,
                        "distance": 1.0 - similarity,
                        "vector": result.vector if hasattr(result, "vector") else None,
                    },
                    "_similarity": similarity,
                }

                # Apply similarity threshold (0.3 to match main pipeline)
                SIMILARITY_THRESHOLD = 0.3
                if similarity >= SIMILARITY_THRESHOLD:
                    formatted_results.append(formatted_hit)
                    logger.debug(
                        f"[VectorAdapter] ✅ Result similarity={similarity:.3f} ≥ {SIMILARITY_THRESHOLD} (included)"
                    )
                else:
                    logger.debug(
                        f"[VectorAdapter] ❌ Result similarity={similarity:.3f} < {SIMILARITY_THRESHOLD} (filtered out)"
                    )

            logger.info(
                f"[VectorAdapter] ✅ Vector search completed: {len(formatted_results)} results found"
            )
            try:
                if RECALL_DIAGNOSTICS and request_id:
                    line = {
                        "component": "vector",
                        "event": "search",
                        "ok": True,
                        "hits": len(formatted_results),
                        "top_k": int(top_k),
                        "threshold": float(certainty_min) if certainty_min is not None else None,
                        "request_id": request_id,
                    }
                    logger.info(json.dumps(line))
            except Exception:
                pass
            return formatted_results

        except EmbedderError as e:
            self.embedder_unavailable = True
            logger.error("[VectorAdapter] search requires embeddings: %s", e)
            raise
        except Exception as e:
            self._mark_unavailable_if_transport_error(e)
            logger.error(
                f"[VectorAdapter] Vector search failed: {type(e).__name__}: {e}. Returning empty list."
            )
            try:
                if RECALL_DIAGNOSTICS and request_id:
                    line = {
                        "component": "vector",
                        "event": "search",
                        "ok": False,
                        "error": f"{type(e).__name__}: {str(e)[:180]}",
                        "request_id": request_id,
                    }
                    logger.info(json.dumps(line))
            except Exception:
                pass
            return []

    def query_related_memories(self, query: str, top_k: int = 5, *, request_id: str | None = None) -> list[dict]:
        """Query related memories - NEVER returns None."""
        if not query:
            logger.warning(
                "[VectorAdapter] query_related_memories called with empty query. Returning empty list."
            )
            return []

        try:
            results = self.search(query, top_k=top_k, request_id=request_id)
            if results is None:
                logger.warning(
                    "[VectorAdapter] search() returned None instead of list. Injecting empty list fallback."
                )
                return []
            return results
        except Exception as e:
            logger.error(
                f"[VectorAdapter] query_related_memories failed: {type(e).__name__}: {e}. Returning empty list."
            )
            return []

    def get_vector_matches(self, query: str, limit: int = 10, *, request_id: str | None = None) -> list[dict]:
        """Get vector matches - NEVER returns None."""
        if not query:
            logger.warning(
                "[VectorAdapter] get_vector_matches called with empty query. Returning empty list."
            )
            return []

        try:
            results = self.search(query, top_k=limit, request_id=request_id)
            if results is None:
                logger.warning(
                    "[VectorAdapter] search() returned None instead of list. Injecting empty list fallback."
                )
                return []
            return results
        except Exception as e:
            logger.error(
                f"[VectorAdapter] get_vector_matches failed: {type(e).__name__}: {e}. Returning empty list."
            )
            return []

    def search_memory_vectors(self, query: str, top_k: int = 8, *, request_id: str | None = None) -> list[dict]:
        """Search memory vectors - NEVER returns None."""
        if not query:
            logger.warning(
                "[VectorAdapter] search_memory_vectors called with empty query. Returning empty list."
            )
            return []

        try:
            results = self.search(query, top_k=top_k, request_id=request_id)
            if results is None:
                logger.warning(
                    "[VectorAdapter] search() returned None instead of list. Injecting empty list fallback."
                )
                return []
            return results
        except Exception as e:
            logger.error(
                f"[VectorAdapter] search_memory_vectors failed: {type(e).__name__}: {e}. Returning empty list."
            )
            return []


"""
NOTE:
- This module is imported by the LLM pod and must remain import-safe without Flask.
- The Vector Adapter HTTP API server has been moved to `pods/vector/vector_adapter_api.py`.
"""

# ╭─────────────────────────────────────────────────────────╮
# │  Startup Health Check                                   │
# ╰─────────────────────────────────────────────────────────╯


def startup_vector_health_check():
    """Perform startup health check for Qdrant connectivity."""
    try:
        # Parse host and port from QDRANT_URL
        if "://" in QDRANT_URL:
            host_port = QDRANT_URL.split("://")[1]
        else:
            host_port = QDRANT_URL

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = int(
                os.getenv("QDRANT_PORT", "6333")
            )  # ⚠️ Replaced hardcoded fallback with env-respecting default

        client = QdrantClient(host=host, port=port)
        collections = _list_collection_names(client)
        print(f"[VECTOR CHECK] Qdrant OK: {len(collections)} collections available")
        return True
    except Exception as e:
        print(f"[VECTOR CHECK] Connection failed: {e}")
        return False


if __name__ == "__main__":
    # Delegate to the API server entrypoint (kept separate to avoid Flask import in the LLM pod).
    try:
        from pods.vector.vector_adapter_api import main as _main  # type: ignore
    except Exception:
        # Fallback for direct execution (python pods/vector/vector_adapter.py)
        from vector_adapter_api import main as _main  # type: ignore

    _main()
