from __future__ import annotations

# utils/qdrant_compat.py
import importlib.metadata as im
import os

from packaging.version import parse as V

# Load vector environment configuration
try:
    from dotenv import load_dotenv

    load_dotenv(".env.vector")  # Load vector-specific config
    load_dotenv()  # Fallback to general .env
except ImportError:
    pass

try:
    from qdrant_client import QdrantClient
except Exception as e:  # pragma: no cover
    raise RuntimeError("qdrant-client not installed") from e


def qdrant_version():
    try:
        return V(im.version("qdrant-client"))
    except Exception:
        # If version metadata isn’t available, assume 1.x behavior
        return V("1.0.0")


def make_qdrant_client(
    *,
    host: str | None = None,
    port: int | None = None,
    url: str | None = None,
    api_key: str | None = None,
    use_https: bool = False,
    prefer_grpc: bool = False,
    timeout: float | None = None,
    **kwargs,
):
    """
    Create a QdrantClient that works with both 1.x (`host`, `port`) and 2.x (`url`).
    If `url` is provided, it always wins.
    """
    ver = qdrant_version()

    # Normalized kwargs supported by both
    common = dict(api_key=api_key)
    if timeout is not None:
        common["timeout"] = timeout
    # v1 and v2 both accept prefer_grpc
    common["prefer_grpc"] = prefer_grpc

    if url:
        return QdrantClient(url=url, **common)

    if ver.major >= 2:
        scheme = "https" if use_https else "http"
        if host and port:
            return QdrantClient(url=f"{scheme}://{host}:{port}", **common)
        if host and not port:
            # fallback if only host provided
            return QdrantClient(url=f"{scheme}://{host}", **common)
        # last resort: default local
        # ⚠️ Replaced hardcoded fallback with env-respecting default
        # 🔄 Replaced hardcoded localhost with env-aware _qdrant_from_env()
        default_host = os.getenv("QDRANT_HOST", "localhost")
        default_port = os.getenv("QDRANT_PORT", "6333")
        return QdrantClient(url=f"{scheme}://{default_host}:{default_port}", **common)

    # v1.x path
    # ⚠️ Replaced hardcoded fallback with env-respecting default
    # 🔄 Replaced hardcoded localhost with env-aware default
    default_host = os.getenv("QDRANT_HOST", "localhost")
    default_port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(
        host=host or default_host, port=port or default_port, https=use_https, **common
    )


def list_collections_compat(client: "QdrantClient"):
    """
    Return a list of collection names across client variants.
    """
    try:
        resp = client.get_collections()
    except AttributeError:
        # Some builds exposed get_collections().collections pattern
        try:
            resp = client.get_collections()
            if hasattr(resp, "collections"):
                cols = resp.collections
                if isinstance(cols, list) and cols and hasattr(cols[0], "name"):
                    return [c.name for c in cols]
        except AttributeError:
            # REST API fallback as requested
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
                    names = []
                    for c in collections:
                        if isinstance(c, dict) and "name" in c:
                            names.append(c["name"])
                        elif hasattr(c, "name"):
                            names.append(c.name)
                    return names
            except Exception:
                # Give up gracefully
                return []

    # v1: resp.collections -> list of objects with .name
    cols = getattr(resp, "collections", None)
    if isinstance(cols, list) and cols and hasattr(cols[0], "name"):
        return [c.name for c in cols]

    # v2 can also return dict-like
    if isinstance(resp, dict):
        # {'collections': [{'name': 'foo'}, ...]}
        cols = resp.get("collections") or []
        return [c.get("name") for c in cols if isinstance(c, dict) and "name" in c]

    # Last resort: best effort
    try:
        return [
            getattr(c, "name", None) for c in cols or [] if getattr(c, "name", None)
        ]
    except Exception:
        return []


def get_collection_compat(client: "QdrantClient", name: str):
    """
    Try multiple signatures for get_collection across versions.
    """
    for kwargs in (
        {"collection_name": name},
        {"name": name},
        {"collection_name": name},  # repeat to ensure order
    ):
        try:
            return client.get_collection(**kwargs)  # type: ignore[call-arg]
        except TypeError:
            continue
        except AttributeError:
            # Some versions use a different route; just fall through
            break
    # As a final probe, see if listing shows it exists
    names = list_collections_compat(client)
    return name if name in names else None
