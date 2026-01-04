#!/usr/bin/env python3

import argparse
import json
import os
import sys
import tarfile
import tempfile
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Filter

    QDRANT_AVAILABLE = True
except Exception as e:
    print(f"❌ qdrant-client import failed: {e}")
    QDRANT_AVAILABLE = False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Qdrant snapshot/export with safe fallback"
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6333)
    parser.add_argument(
        "--collection",
        action="append",
        default=None,
        help="Collection(s) to snapshot; repeatable",
    )
    parser.add_argument(
        "--out", default=None, help="[Deprecated] Output tar.gz path; prefer --dir"
    )
    parser.add_argument(
        "--dir",
        dest="out_dir",
        default="snapshots/",
        help="Output directory to save snapshots (default: snapshots/)",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--print-collections",
        action="store_true",
        help="Print unified collection names from memory.collections and exit",
    )
    return parser.parse_args()


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def collection_dir(base_dir: str, collection: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dir_path = os.path.join(base_dir, f"{collection}_{stamp}")
    ensure_dir(dir_path)
    return dir_path


def try_native_snapshot(client, collection: str, dest_dir: str) -> bool:
    """Attempt native snapshot/export if supported by server/API version."""
    try:
        api = client._client  # low-level http client
        if hasattr(api, "create_snapshot"):
            resp = api.create_snapshot(collection_name=collection)
            download = getattr(resp, "download_url", None) or getattr(
                resp, "download_path", None
            )
            if download:
                import requests

                r = requests.get(download, stream=True, timeout=60)
                r.raise_for_status()
                out_path = os.path.join(dest_dir, "native_snapshot.tar")
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"✅ Snapshot downloaded to {out_path}")
                return True
            else:
                print(
                    "ℹ️ Snapshot created on server; no download URL. Falling back to scroll-dump."
                )
                return False
        else:
            return False
    except Exception as e:
        print(f"⚠️ Native snapshot not available/failed: {e}")
        return False


def sample_field_list(client, collection: str, limit: int = 500) -> list:
    fields = set()
    offset = None
    seen = 0
    while seen < limit:
        points, offset = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=min(200, limit - seen),
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break
        for p in points:
            payload = p.payload or {}
            for k in payload.keys():
                fields.add(k)
            seen += 1
            if seen >= limit:
                break
    return sorted(list(fields))


def fallback_scroll_dump(
    client, collection: str, dest_dir: str, batch_size: int
) -> dict:
    """Dump IDs, payloads, and vectors via paginated scroll into a directory."""
    points_exported = 0
    vector_dim = None
    jsonl_path = os.path.join(dest_dir, "points.jsonl")
    offset = None

    with open(jsonl_path, "w", encoding="utf-8") as out:
        while True:
            try:
                res = client.scroll(
                    collection_name=collection,
                    offset=offset,
                    limit=batch_size,
                    with_payload=True,
                    with_vectors=True,
                )
                points, offset = res
                if not points:
                    break
                for p in points:
                    obj = {
                        "id": str(p.id),
                        "payload": p.payload or {},
                        "vector": p.vector,
                    }
                    if vector_dim is None and p.vector is not None:
                        vector_dim = (
                            len(p.vector)
                            if isinstance(p.vector, (list, tuple))
                            else None
                        )
                    out.write(json.dumps(obj) + "\n")
                    points_exported += 1
            except Exception as e:
                print(f"❌ Scroll failed: {e}")
                break

    # Best-effort info
    info = client.get_collection(collection)
    metric = None
    dim = None
    count = getattr(info, "points_count", None)
    try:
        vectors_cfg = getattr(info, "vectors", None)
        if vectors_cfg and hasattr(vectors_cfg, "config"):
            cfg = vectors_cfg.config
            dim = getattr(cfg, "size", None)
            metric = getattr(cfg, "distance", None)
    except Exception:
        metric = None

    return {
        "points_exported": points_exported,
        "vector_dim": dim if dim is not None else vector_dim,
        "distance": str(metric) if metric is not None else None,
        "collection_size": count,
    }


def write_meta(dest_dir: str, collection: str, meta: dict, fields: list):
    meta_path = os.path.join(dest_dir, "snapshot_meta.json")
    payload = {
        "collection": collection,
        "vector_dimension": meta.get("vector_dim"),
        "distance": meta.get("distance"),
        "field_list": fields,
        "collection_size": meta.get("collection_size"),
        "exported_at": datetime.utcnow().isoformat(),
    }
    with open(meta_path, "w", encoding="utf-8") as mf:
        json.dump(payload, mf, indent=2)
    print(f"📝 Metadata written: {meta_path}")


def main():
    args = parse_args()
    # Allow printing collections without requiring qdrant-client
    if args.print_collections:
        try:
            from memory.memory_collections import (
                archive_collection,
                beliefs_collection,
                memory_collection,
            )

            print("Unified collections:")
            print(f"  memory:  {memory_collection()}")
            print(f"  beliefs: {beliefs_collection()}")
            print(f"  archive: {archive_collection()}")
        except Exception as e:
            print(f"WARN: could not load memory.collections: {e}")
        finally:
            sys.exit(0)

    if not QDRANT_AVAILABLE:
        print("❌ qdrant-client not available. Please: pip install qdrant-client")
        sys.exit(1)

    client = QdrantClient(host=args.host, port=args.port, timeout=60)

    base_dir = ensure_dir(args.out_dir) if args.out_dir else ensure_dir("snapshots/")
    # Default to unified collection names; CLI --collection overrides
    if args.collection:
        collections = args.collection
    else:
        try:
            from memory.memory_collections import (
                memory_collection as _memory_collection,
            )

            collections = [_memory_collection()]
        except Exception:
            collections = ["axiom_memories"]

    print(f"Snapshotting collections: {collections} -> {base_dir}")
    for collection in collections:
        print(f"--- {collection} ---")
        c_dir = collection_dir(base_dir, collection)
        # Try native snapshot first, then fallback
        ok = try_native_snapshot(client, collection, c_dir) if not args.out else False
        stats = None
        if not ok:
            stats = fallback_scroll_dump(client, collection, c_dir, args.batch_size)
            # Collect fields from the produced dump (quick sample from server)
            fields = sample_field_list(client, collection)
            write_meta(
                c_dir,
                collection,
                {
                    "vector_dim": stats.get("vector_dim"),
                    "distance": stats.get("distance"),
                    "collection_size": stats.get("collection_size"),
                },
                fields,
            )
            print(f"Points exported: {stats['points_exported']}")
            print(f"Vector dim: {stats['vector_dim']}")
            print(f"Distance metric: {stats['distance']}")
        else:
            # Best-effort info from collection
            try:
                info = client.get_collection(collection)
                vectors_cfg = getattr(info, "vectors", None)
                dim = None
                metric = None
                count = getattr(info, "points_count", None)
                if vectors_cfg and hasattr(vectors_cfg, "config"):
                    cfg = vectors_cfg.config
                    dim = getattr(cfg, "size", None)
                    metric = getattr(cfg, "distance", None)
                fields = sample_field_list(client, collection)
                write_meta(
                    c_dir,
                    collection,
                    {
                        "vector_dim": dim,
                        "distance": str(metric) if metric is not None else None,
                        "collection_size": count,
                    },
                    fields,
                )
                print(f"✅ Snapshot created. Vector dim: {dim}, distance: {metric}")
                if count is not None:
                    print(f"Collection size: {count}")
            except Exception as e:
                print(f"⚠️ Could not read collection info: {e}")


if __name__ == "__main__":
    main()
