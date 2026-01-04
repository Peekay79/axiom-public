#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


def _env_flag(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return bool(default)
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else int(default)
    except Exception:
        return int(default)


def _env_str(name: str, default: str) -> str:
    val = os.getenv(name)
    return str(val) if val is not None else str(default)


def _cockpit_signal(signal_name: str, payload: dict) -> None:
    try:
        from pods.cockpit.cockpit_reporter import write_signal

        write_signal("lifecycle", signal_name, payload)
    except Exception:
        pass


QDRANT_SNAPSHOT_ENABLED = _env_flag("QDRANT_SNAPSHOT_ENABLED", True)
QDRANT_SNAPSHOT_DIR = Path(_env_str("QDRANT_SNAPSHOT_DIR", "archive/qdrant"))
QDRANT_SNAPSHOT_KEEP = _env_int("QDRANT_SNAPSHOT_KEEP", 7)


def _make_client():
    try:
        from memory.utils.qdrant_compat import make_qdrant_client  # type: ignore

        # Prefer QDRANT_URL or host/port env
        url = os.getenv("QDRANT_URL", None)
        host = os.getenv("QDRANT_HOST", None)
        port = int(os.getenv("QDRANT_PORT", "6333")) if os.getenv("QDRANT_PORT") else None
        return make_qdrant_client(url=url, host=host, port=port)
    except Exception as e:
        raise RuntimeError(f"qdrant_client_unavailable: {e}")


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _collection_names(client) -> list[str]:
    try:
        from memory.memory_collections import memory_collection

        return [memory_collection()]
    except Exception:
        try:
            # Last resort: list all
            names = []
            resp = client.get_collections()
            cols = getattr(resp, "collections", [])
            for c in cols:
                name = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else None)
                if name:
                    names.append(name)
            return names
        except Exception:
            return ["axiom_memories"]


def take_snapshot(output_dir: str) -> dict:
    if not QDRANT_SNAPSHOT_ENABLED:
        reason = "disabled"
        _cockpit_signal("lifecycle.snapshot.failed", {"reason": reason})
        return {"skipped": True, "reason": reason}

    out_dir = _ensure_dir(Path(output_dir) if output_dir else QDRANT_SNAPSHOT_DIR)
    client = _make_client()
    ns = _collection_names(client)
    taken = []
    total_size = 0
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    for name in ns:
        try:
            # Prefer native snapshot API when available
            api = getattr(client, "_client", None)
            tar_path: Optional[Path] = None
            if api is not None and hasattr(api, "create_snapshot"):
                try:
                    resp = api.create_snapshot(collection_name=name)
                    download = getattr(resp, "download_url", None) or getattr(resp, "download_path", None)
                    if download:
                        import requests

                        r = requests.get(download, stream=True, timeout=60)
                        r.raise_for_status()
                        tar_path = out_dir / f"{name}.{stamp}.native.tar"
                        with open(tar_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                except Exception:
                    tar_path = None
            if tar_path is None:
                # Fallback: scroll-dump JSONL and tar up
                cdir = out_dir / f"{name}_{stamp}"
                cdir.mkdir(parents=True, exist_ok=True)
                # Reuse logic similar to scripts/qdrant_snapshot.py (scroll)
                points_exported = 0
                jsonl_path = cdir / "points.jsonl"
                offset = None
                with open(jsonl_path, "w", encoding="utf-8") as out:
                    while True:
                        try:
                            res = client.scroll(
                                collection_name=name,
                                offset=offset,
                                limit=1000,
                                with_payload=True,
                                with_vectors=True,
                            )
                            points, offset = res
                            if not points:
                                break
                            for p in points:
                                obj = {
                                    "id": str(getattr(p, "id", "")),
                                    "payload": getattr(p, "payload", {}) or {},
                                    "vector": getattr(p, "vector", None),
                                }
                                out.write(json.dumps(obj) + "\n")
                                points_exported += 1
                        except Exception as e:
                            raise RuntimeError(f"scroll_failed:{e}")
                # Tar the directory
                tar_path = out_dir / f"{name}.{stamp}.tar.gz"
                with tarfile.open(tar_path, "w:gz") as tar:
                    tar.add(cdir, arcname=cdir.name)
            size_bytes = tar_path.stat().st_size if tar_path and tar_path.exists() else 0
            taken.append({"collection": name, "path": str(tar_path), "size_bytes": size_bytes})
            total_size += size_bytes
        except Exception as e:
            _cockpit_signal("lifecycle.snapshot.failed", {"collection": name, "reason": str(e)})
            return {"error": str(e)}

    summary = {
        "path": str(out_dir),
        "size_bytes": int(total_size),
        "ns_count": len(taken),
        "ts": datetime.utcnow().isoformat(),
        "artifacts": taken,
    }
    _cockpit_signal("lifecycle.snapshot.taken", summary)
    return summary


def prune_snapshots(dir: str, keep: int) -> dict:
    base = Path(dir)
    if not base.exists():
        return {"deleted": 0}
    items = sorted([p for p in base.iterdir() if p.is_file() and p.suffix in (".tar", ".gz")], key=lambda p: p.stat().st_mtime)
    to_delete = max(0, len(items) - int(keep))
    deleted = 0
    for p in items[:to_delete]:
        try:
            p.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            pass
    rec = {"deleted": int(deleted), "kept": int(len(items) - deleted)}
    _cockpit_signal("lifecycle.snapshot.pruned", rec)
    return rec


def restore_snapshot(path: str, ns_alias: str | None = None) -> dict:
    client = _make_client()
    # Safety: do not auto-restore in prod; require explicit operator step
    if _env_flag("PROD_ENV", False):
        raise RuntimeError("restore_disabled_in_prod")
    # Minimal restore: unpack and upsert JSONL back into the target collection or alias
    snap_path = Path(path)
    if not snap_path.exists():
        raise FileNotFoundError(str(path))
    # Infer collection name from filename if alias not provided
    collection = None
    try:
        stem = snap_path.name.split(".")[0]
        collection = ns_alias or stem
    except Exception:
        collection = ns_alias or None
    # If tar.gz, extract JSONL if present
    tmp_dir = snap_path.parent / f"restore_{snap_path.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        if snap_path.suffixes[-2:] == [".tar", ".gz"] or snap_path.suffix == ".tar":
            with tarfile.open(snap_path, "r:*") as tar:
                tar.extractall(tmp_dir)
        # Find points.jsonl
        jsonl = None
        for p in tmp_dir.rglob("points.jsonl"):
            jsonl = p
            break
        if not jsonl:
            raise RuntimeError("points_jsonl_missing")
        # Upsert back
        import json as _json

        with open(jsonl, "r", encoding="utf-8") as f:
            batch = []
            for line in f:
                try:
                    obj = _json.loads(line)
                except Exception:
                    continue
                pid = obj.get("id")
                payload = obj.get("payload") or {}
                vector = obj.get("vector")
                batch.append({"id": pid, "payload": payload, "vector": vector})
                if len(batch) >= 256:
                    client.upsert(collection_name=collection, points=batch)
                    batch = []
            if batch:
                client.upsert(collection_name=collection, points=batch)
    except Exception as e:
        _cockpit_signal("lifecycle.snapshot.failed", {"reason": str(e)})
        raise
    return {"restored_to": collection, "path": str(snap_path)}


def drill_snapshot_cycle(output_dir: str, keep: int, ns_alias: str | None = None) -> dict:
    snap = take_snapshot(output_dir)
    pruned = prune_snapshots(output_dir, keep)
    return {"taken": snap, "pruned": pruned}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qdrant snapshot/restore helpers")
    parser.add_argument("--take", action="store_true")
    parser.add_argument("--drill", action="store_true")
    parser.add_argument("--restore", default=None)
    parser.add_argument("--output", default=str(QDRANT_SNAPSHOT_DIR))
    parser.add_argument("--keep", type=int, default=QDRANT_SNAPSHOT_KEEP)
    parser.add_argument("--alias", default=None)
    args = parser.parse_args()

    if args.take:
        res = take_snapshot(args.output)
        print(json.dumps(res, indent=2))
    elif args.drill:
        res = drill_snapshot_cycle(args.output, args.keep, ns_alias=args.alias)
        print(json.dumps(res, indent=2))
    elif args.restore:
        res = restore_snapshot(args.restore, ns_alias=args.alias)
        print(json.dumps(res, indent=2))
    else:
        parser.print_help()

