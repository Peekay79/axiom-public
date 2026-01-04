#!/usr/bin/env python3
from __future__ import annotations

"""
Lightweight contradictions reconciliation tool.

Default --dry-run: scans available source if configured, attempts to normalize each
item using schemas.contradiction.normalize, and prints a one-line JSON summary.

--commit: best-effort write of canonical copies to metadata.canonical_contradiction
(original payloads are untouched).

Respects QDRANT_URL. If not configured, exits successfully with zero counts.
No external dependencies beyond what's already in the repo environment.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List, Tuple


def _load_qdrant_client():
    try:
        from qdrant_client import QdrantClient  # type: ignore
    except Exception:
        return None
    return QdrantClient


def _parse_qdrant_url(url: str) -> Tuple[str, int]:
    try:
        from urllib.parse import urlparse

        p = urlparse(url)
        host = p.hostname or "localhost"
        port = p.port or 6333
        return host, int(port)
    except Exception:
        return "localhost", 6333


def _normalize_payload(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from schemas.contradiction import normalize  # type: ignore

        c, warns = normalize(payload)
        return (c is not None), list(warns or [])
    except Exception as e:
        return False, [f"normalize_import_error:{type(e).__name__}"]


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="Write canonical copies")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry run (default): do not write anything",
    )
    args = ap.parse_args(argv)

    # If --commit is set, override dry-run
    dry_run = not args.commit

    summary = {"scanned": 0, "normalized": 0, "warn": 0, "err": 0}
    sample_warns: List[str] = []

    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        # Graceful no-op: print summary and exit 0
        print(json.dumps({**summary, "samples": sample_warns}))
        return 0

    QdrantClient = _load_qdrant_client()
    if QdrantClient is None:
        print(json.dumps({**summary, "samples": ["qdrant_client_unavailable"]}))
        return 0

    host, port = _parse_qdrant_url(qdrant_url)
    try:
        client = QdrantClient(host=host, port=port)
    except Exception:
        print(json.dumps({**summary, "samples": ["qdrant_connect_failed"]}))
        return 0

    # Collection name: env override or default
    collection = os.getenv("QDRANT_MEMORY_COLLECTION", "axiom_memories")

    # Best-effort scroll with small page size to avoid heavy scans
    page_limit = 128
    next_offset = None
    try:
        while True:
            resp = client.scroll(collection_name=collection, with_payload=True, limit=page_limit, offset=next_offset)
            points = getattr(resp, "points", []) or []
            next_offset = getattr(resp, "next_page_offset", None)
            if not points:
                break
            for pt in points:
                payload = getattr(pt, "payload", None) or {}
                # Heuristic: only attempt normalization for items that look like contradictions
                if isinstance(payload, dict) and any(k in payload for k in ("claim", "statement", "text", "conflict_id")):
                    summary["scanned"] += 1
                    ok, warns = _normalize_payload(payload)
                    if ok:
                        summary["normalized"] += 1
                    else:
                        summary["err"] += 1
                    if warns:
                        summary["warn"] += len(warns)
                        # keep small sample
                        for w in warns:
                            if len(sample_warns) < 5:
                                sample_warns.append(w)

                    # Write canonical copy if committing
                    if not dry_run and ok:
                        try:
                            from schemas.contradiction import to_payload, normalize  # type: ignore

                            c_obj, _ = normalize(payload)
                            if c_obj is not None:
                                canonical = to_payload(c_obj)
                                # Merge under metadata.canonical_contradiction
                                meta = payload.get("metadata") or {}
                                if not isinstance(meta, dict):
                                    meta = {}
                                meta["canonical_contradiction"] = canonical
                                payload["metadata"] = meta
                                # Persist back
                                client.set_payload(
                                    collection_name=collection,
                                    payload=payload,
                                    points=[getattr(pt, "id", None)],
                                )
                        except Exception:
                            # continue non-fatally
                            pass

            if next_offset is None:
                break
    except Exception:
        # On any error, provide partial summary and exit successfully
        pass

    print(json.dumps({**summary, "samples": sample_warns}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

