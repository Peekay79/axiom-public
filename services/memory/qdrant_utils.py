"""
Qdrant Memory Loading Utilities
─────────────────────────────────────
Helper functions for loading memory data from Qdrant vector store.
"""

import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional, Set

import requests
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import PointStruct
try:
    # Prefer new models namespace for filters
    from qdrant_client import models as qm
except Exception:  # pragma: no cover - defensive import
    qm = None

# Import collections with fallback
try:
    from memory.memory_collections import memory_collection as _memory_collection

    DEFAULT_COLLECTION = _memory_collection()
except ImportError:
    DEFAULT_COLLECTION = "axiom_memories"


# Load vector environment configuration
try:
    from dotenv import load_dotenv

    load_dotenv(".env.vector")  # Load vector-specific config
    load_dotenv()  # Fallback to general .env
except ImportError:
    pass

logger = logging.getLogger(__name__)


def _list_collection_names(client) -> Set[str]:
    """
    Get list of collection names from Qdrant client, compatible with old/new qdrant-client versions.

    Args:
        client: QdrantClient instance

    Returns:
        Set of collection names
    """
    try:
        # Newer clients - prefer get_collections()
        resp = client.get_collections()
        cols = getattr(resp, "collections", None)
        if cols is not None:
            names = []
            for c in cols:
                n = getattr(c, "name", None)
                if n:
                    names.append(n)
            return set(names)
    except (AttributeError, Exception) as e:
        logger.warning(f"get_collections() not available or failed: {e}")

    try:
        # Fallback for older clients - get_collections().collections
        resp = client.get_collections()
        if hasattr(resp, "collections"):
            names = []
            for c in resp.collections:
                n = getattr(c, "name", None)
                if n:
                    names.append(n)
            return set(names)
        elif isinstance(resp, list):
            # Some versions return a list directly
            return set(resp)
    except AttributeError as e:
        logger.warning(f"get_collections() method not available: {e}")
        # REST API fallback as requested
        try:
            host = getattr(client, "host", "localhost")
            port = getattr(
                client, "port", int(os.getenv("QDRANT_PORT", "6333"))
            )  # ⚠️ Replaced hardcoded fallback with env-respecting default
            url = f"http://{host}:{port}/collections"

            logger.info(f"Falling back to REST API: {url}")
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
                return set(names)
        except Exception as rest_e:
            logger.error(f"REST API fallback failed: {rest_e}")
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")

    return set()


def get_qdrant_client(
    host: Optional[str] = None, port: Optional[int] = None, timeout: int = 10
) -> QdrantClient:
    """
    Create Qdrant client with standardized environment variable handling.
    Alias for create_qdrant_client for compatibility.

    Args:
        host: Qdrant host (overrides environment)
        port: Qdrant port (overrides environment)
        timeout: Connection timeout in seconds

    Returns:
        QdrantClient instance
    """
    if host is not None or port is not None:
        # Use specific host/port if provided
        final_host = host or "localhost"
        final_port = port or int(
            os.getenv("QDRANT_PORT", "6333")
        )  # ⚠️ Replaced hardcoded fallback with env-respecting default
        logger.info(f"🔌 Connecting to Qdrant at {final_host}:{final_port}")
        return QdrantClient(host=final_host, port=final_port, timeout=timeout)
    else:
        # Use standardized connection info from environment
        return create_qdrant_client(timeout=timeout)


def test_qdrant_connection(client: Optional[QdrantClient] = None) -> bool:
    """
    Test Qdrant connection and basic functionality.

    Args:
        client: Optional QdrantClient instance (creates one if None)

    Returns:
        True if connection successful, False otherwise
    """
    if client is None:
        try:
            client = create_qdrant_client()
        except Exception as e:
            logger.error(f"Failed to create Qdrant client: {e}")
            return False

    try:
        # Test basic connectivity by listing collections
        collections = _list_collection_names(client)
        logger.info(f"Qdrant connection successful. Collections: {sorted(collections)}")
        return True
    except Exception as e:
        logger.error(f"Qdrant connection test failed: {e}")
        return False


def get_qdrant_connection_info() -> tuple[str, int]:
    """
    Get Qdrant connection info from environment variables.

    Priority:
    1. QDRANT_HOST + QDRANT_PORT
    2. Parse host from QDRANT_URL but use QDRANT_PORT env var
    3. Default to localhost with QDRANT_PORT env var (fallback 6333)

    Returns:
        Tuple of (host, port)
    """
    # Check for direct host/port env vars
    host = os.getenv("QDRANT_HOST")
    port_str = os.getenv("QDRANT_PORT")

    if host and port_str:
        try:
            port = int(port_str)
            return host, port
        except ValueError:
            logger.warning(f"Invalid QDRANT_PORT value: {port_str}, falling back")

    # Try to parse from QDRANT_URL
    vector_url = os.getenv("QDRANT_URL")
    if vector_url:
        try:
            parsed = urllib.parse.urlparse(vector_url)
            if parsed.hostname:
                return parsed.hostname, int(
                    os.getenv("QDRANT_PORT", "6333")
                )  # ⚠️ Replaced hardcoded fallback with env-respecting default
        except Exception as e:
            logger.warning(f"Failed to parse QDRANT_URL: {e}")

    # Default fallback
    return "localhost", int(
        os.getenv("QDRANT_PORT", "6333")
    )  # ⚠️ Replaced hardcoded fallback with env-respecting default


def get_required_collections() -> Dict[str, str]:
    """
    Get required collection names from environment variables with defaults.

    Returns:
        Dict with 'memory' and 'beliefs' collection names
    """
    memory_collection = os.getenv("QDRANT_MEMORY_COLLECTION", "axiom_memories")
    beliefs_collection = os.getenv("QDRANT_BELIEF_COLLECTION", "axiom_beliefs")

    return {"memory": memory_collection, "beliefs": beliefs_collection}


def verify_required_collections(
    client, required_collections: Dict[str, str]
) -> Dict[str, bool]:
    """
    Verify that required collections exist in Qdrant.

    Args:
        client: QdrantClient instance
        required_collections: Dict of collection type -> collection name

    Returns:
        Dict mapping collection names to existence status
    """
    available_collections = _list_collection_names(client)
    logger.info(f"Available Qdrant collections: {sorted(available_collections)}")

    verification_results = {}
    for coll_type, coll_name in required_collections.items():
        exists = coll_name in available_collections
        verification_results[coll_name] = exists

        if exists:
            logger.info(f"✅ Required collection '{coll_name}' ({coll_type}) found")
        else:
            logger.error(f"❌ Required collection '{coll_name}' ({coll_type}) missing")

    return verification_results


def create_qdrant_client(timeout: int = 10) -> QdrantClient:
    """
    Create a Qdrant client with standardized connection handling.

    Args:
        timeout: Connection timeout in seconds

    Returns:
        QdrantClient instance
    """
    host, port = get_qdrant_connection_info()
    logger.info(f"🔌 Connecting to Qdrant at {host}:{port}")

    return QdrantClient(host=host, port=port, timeout=timeout)


def load_memory_from_qdrant(
    host: str = None, port: int = None, collection_name: str = None, timeout: int = 10
) -> List[Dict[str, Any]]:
    """
    Load all memory items from a Qdrant vector store collection.

    Args:
        host: Qdrant server host (uses env vars if None)
        port: Qdrant server port (uses env vars if None)
        collection_name: Collection name to load from (uses env vars if None)
        timeout: Connection timeout in seconds

    Returns:
        List of memory items in dictionary format

    Raises:
        Exception: If connection fails or no items found
    """
    # Use environment-based defaults if not provided
    if host is None or port is None:
        env_host, env_port = get_qdrant_connection_info()
        host = host or env_host
        port = port or env_port

    if collection_name is None:
        required_collections = get_required_collections()
        collection_name = required_collections["memory"]

    try:
        logger.info(f"🔌 Connecting to Qdrant at {host}:{port}")
        client = QdrantClient(host=host, port=port, timeout=timeout)

        # Check if collection exists
        try:
            # Guard against missing get_collection method
            if hasattr(client, "get_collection"):
                collection_info = client.get_collection(collection_name)
                logger.info(
                    f"📂 Found collection '{collection_name}' with {collection_info.points_count} points"
                )
            else:
                # Fallback: check if collection exists in list
                available_collections = _list_collection_names(client)
                if collection_name not in available_collections:
                    raise Exception(
                        f"Collection '{collection_name}' not found in Qdrant"
                    )
                logger.info(
                    f"📂 Found collection '{collection_name}' (exact count unavailable)"
                )
        except UnexpectedResponse as e:
            if "Not found" in str(e):
                raise Exception(f"Collection '{collection_name}' not found in Qdrant")
            raise

        # Get all points from the collection
        # Note: For large collections, consider implementing pagination
        scroll_result = client.scroll(
            collection_name=collection_name,
            limit=10000,  # Adjust based on expected memory size
            with_payload=True,
            with_vectors=False,  # We only need the payload data
        )

        points, next_page_offset = scroll_result
        memory_data = []

        for point in points:
            if point.payload:
                # Convert Qdrant point payload to memory item format
                memory_item = dict(point.payload)

                # Ensure required fields exist
                if "uuid" not in memory_item and hasattr(point, "id"):
                    memory_item["uuid"] = str(point.id)

                # Add point ID if not present in payload
                if "point_id" not in memory_item:
                    memory_item["point_id"] = str(point.id)

                memory_data.append(memory_item)

        # Handle pagination if there are more results
        while next_page_offset:
            scroll_result = client.scroll(
                collection_name=collection_name,
                offset=next_page_offset,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )

            points, next_page_offset = scroll_result

            for point in points:
                if point.payload:
                    memory_item = dict(point.payload)
                    if "uuid" not in memory_item and hasattr(point, "id"):
                        memory_item["uuid"] = str(point.id)
                    if "point_id" not in memory_item:
                        memory_item["point_id"] = str(point.id)
                    memory_data.append(memory_item)

        logger.info(
            f"✅ Successfully loaded {len(memory_data)} memory items from Qdrant"
        )
        return memory_data

    except Exception as e:
        logger.error(f"❌ Failed to load memory from Qdrant: {e}")
        raise


def get_qdrant_collection_count(
    host: str = None, port: int = None, collection_name: str = None, timeout: int = 5
) -> int:
    """
    Get the count of items in a Qdrant collection.

    Args:
        host: Qdrant server host (uses env vars if None)
        port: Qdrant server port (uses env vars if None)
        collection_name: Collection name (uses env vars if None)
        timeout: Connection timeout in seconds

    Returns:
        Number of points in the collection, or -1 if count unavailable

    Raises:
        Exception: If connection fails or collection not found
    """
    # Use environment-based defaults if not provided
    if host is None or port is None:
        env_host, env_port = get_qdrant_connection_info()
        host = host or env_host
        port = port or env_port

    if collection_name is None:
        required_collections = get_required_collections()
        collection_name = required_collections["memory"]

    try:
        client = QdrantClient(host=host, port=port, timeout=timeout)

        # Guard with hasattr check
        if hasattr(client, "get_collection"):
            collection_info = client.get_collection(collection_name)
            return collection_info.points_count
        else:
            logger.warning("get_collection method not available, skipping exact count")
            return -1

    except Exception as e:
        logger.error(f"❌ Failed to get Qdrant collection count: {e}")
        raise


def test_qdrant_connection(
    host: str = None, port: int = None, collection_name: str = None, limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Test Qdrant connection and return first few items.

    Args:
        host: Qdrant server host (uses env vars if None)
        port: Qdrant server port (uses env vars if None)
        collection_name: Collection name (uses env vars if None)
        limit: Number of items to return for testing

    Returns:
        List of first few memory items

    Raises:
        Exception: If connection fails
    """
    # Use environment-based defaults if not provided
    if host is None or port is None:
        env_host, env_port = get_qdrant_connection_info()
        host = host or env_host
        port = port or env_port

    if collection_name is None:
        required_collections = get_required_collections()
        collection_name = required_collections["memory"]

    try:
        client = QdrantClient(host=host, port=port, timeout=5)

        # Get first few points for testing
        scroll_result = client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        points, _ = scroll_result
        test_data = []

        for point in points:
            if point.payload:
                memory_item = dict(point.payload)
                if "uuid" not in memory_item and hasattr(point, "id"):
                    memory_item["uuid"] = str(point.id)
                if "point_id" not in memory_item:
                    memory_item["point_id"] = str(point.id)
                test_data.append(memory_item)

        return test_data

    except Exception as e:
        logger.error(f"❌ Qdrant connection test failed: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# Filter translation and post-filter utilities
# ─────────────────────────────────────────────────────────────

def to_qdrant_filter(weaviate_like_filter: Dict[str, Any]):
    """
    Translate a minimal Weaviate-like filter into a Qdrant Filter.

    Supported structure (minimal):
        {
          "must": [
            { "key": "tags", "match": { "any": ["foo", "bar"] } }
          ]
        }

    Returns a qdrant_client.models.Filter instance if translation is supported,
    otherwise returns None.
    """
    try:
        if not isinstance(weaviate_like_filter, dict):
            return None

        must = weaviate_like_filter.get("must")
        if not isinstance(must, list) or not must:
            return None

        # Only support tags.any for now
        conds = []
        for clause in must:
            if not isinstance(clause, dict):
                continue
            key = clause.get("key")
            match = clause.get("match")
            if key != "tags" or not isinstance(match, dict):
                continue
            any_values = match.get("any")
            if not isinstance(any_values, list) or not any_values:
                continue

            # Prefer MatchAny if available; otherwise, build OR via should
            if qm is not None and hasattr(qm, "MatchAny"):
                conds.append(qm.FieldCondition(key="tags", match=qm.MatchAny(any=any_values)))
            else:
                # Fallback: we'll return a Filter with should of MatchValue conditions
                should_conds = [
                    qm.FieldCondition(key="tags", match=qm.MatchValue(value=v))
                    for v in any_values
                ] if qm is not None else []
                if qm is None or not should_conds:
                    return None
                return qm.Filter(should=should_conds)

        if not conds:
            return None

        return qm.Filter(must=conds) if qm is not None else None
    except Exception as _e:  # pragma: no cover - defensive
        logger.warning(f"to_qdrant_filter translation failed: {_e}")
        return None


def post_filter_items(items: List[Dict[str, Any]], weaviate_like_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Server-side post-filtering of result items using minimal Weaviate-like filter.

    Supports only tags.any structure described in to_qdrant_filter.
    If unsupported, returns the input items unchanged.
    """
    try:
        if not isinstance(weaviate_like_filter, dict):
            return items
        must = weaviate_like_filter.get("must")
        if not isinstance(must, list) or not must:
            return items

        # Only look for tags.any within must clauses
        any_values: List[str] = []
        for clause in must:
            if not isinstance(clause, dict):
                continue
            if clause.get("key") != "tags":
                continue
            match = clause.get("match")
            if not isinstance(match, dict):
                continue
            vals = match.get("any")
            if isinstance(vals, list):
                any_values.extend([v for v in vals if isinstance(v, str)])

        if not any_values:
            return items

        any_set = set(any_values)
        filtered = []
        for it in items:
            tags = it.get("tags", []) if isinstance(it, dict) else []
            try:
                if any_set.intersection(set(tags)):
                    filtered.append(it)
            except Exception:
                # Be permissive if tags is malformed
                pass
        return filtered
    except Exception:  # pragma: no cover - defensive
        return items


def project_fields(items: List[Dict[str, Any]], fields: Optional[List[str]]) -> List[Dict[str, Any]]:
    """
    Project result items to requested fields.

    - If fields is None: return items unchanged (back-compat)
    - Known top-level: content, tags, id, metadata
    - Special nested: _additional.score, _additional.distance
    - Unknown fields ignored silently
    """
    if fields is None:
        return items

    try:
        requested: Set[str] = {f for f in fields if isinstance(f, str)}
        want_content = "content" in requested
        want_tags = "tags" in requested
        want_id = "id" in requested
        want_metadata = "metadata" in requested

        addl_keys: Set[str] = set()
        for f in list(requested):
            if f.startswith("_additional."):
                addl_keys.add(f.split(".", 1)[1])
        want_additional = bool(addl_keys)

        projected: List[Dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                projected.append(it)
                continue

            out: Dict[str, Any] = {}
            if want_content and "content" in it:
                out["content"] = it["content"]
            if want_tags and "tags" in it:
                out["tags"] = it["tags"]
            if want_id and "id" in it:
                out["id"] = it["id"]
            if want_metadata and "metadata" in it:
                out["metadata"] = it["metadata"]
            if want_additional and "_additional" in it and isinstance(it["_additional"], dict):
                sub = {}
                for k in addl_keys:
                    if k in it["_additional"]:
                        sub[k] = it["_additional"][k]
                if sub:
                    out["_additional"] = sub

            projected.append(out)

        return projected
    except Exception:  # pragma: no cover - defensive
        return items
