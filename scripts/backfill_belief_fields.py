#!/usr/bin/env python3

import argparse
import json
import os
import sys
from datetime import datetime, timezone

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm

    _Q_OK = True
except Exception as e:
    print(f"❌ qdrant-client import failed: {e}")
    _Q_OK = False

try:
    from memory.belief_engine import ensure_structured_beliefs

    _HAS_BE = True
except Exception:
    _HAS_BE = False

    # Minimal fallback: wrap strings as +1 beliefs
    def ensure_structured_beliefs(items):
        items = items or []
        out = []
        if isinstance(items, (list, tuple)):
            iter_items = items
        else:
            iter_items = [items]
        for it in iter_items:
            if isinstance(it, str):
                out.append(
                    {
                        "key": it.lower().replace(" ", "_")[:128],
                        "text": it,
                        "polarity": 1,
                        "confidence": 0.5,
                        "scope": "general",
                        "source": "ingest",
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                        "key_version": 1,
                    }
                )
            elif isinstance(it, dict):
                if "key_version" not in it:
                    it["key_version"] = 1
                out.append(it)
        return out


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    p = argparse.ArgumentParser(
        description="Backfill normalized belief fields into axiom_memory payloads (idempotent)"
    )
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=6333)
    # Default to unified collection names; CLI --collection overrides
    try:
        from memory.memory_collections import memory_collection as _memory_collection

        _default_coll = _memory_collection()
    except Exception:
        _default_coll = "axiom_memories"
    p.add_argument("--collection", default=_default_coll)
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--resume-file", default=".belief_backfill_state.json")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--yes", action="store_true", help="Actually write changes")
    p.add_argument(
        "--where",
        default=None,
        help="Optional JSON filter for Qdrant scroll (default: schema_version < 3)",
    )
    return p.parse_args()


def load_state(path: str):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save resume state: {e}")


def main():
    if not _Q_OK:
        print("❌ qdrant-client not available. Install with: pip install qdrant-client")
        sys.exit(1)
    args = parse_args()
    client = QdrantClient(host=args.host, port=args.port, timeout=60)

    state = load_state(args.resume_file)
    offset = state.get("offset")
    processed = 0
    updated = 0
    counters = {
        "structured_beliefs": 0,
        "schema_bumped": 0,
    }

    # Prepare filter: default guard to schema_version < 3
    qfilter = None
    if args.where:
        try:
            where = json.loads(args.where)
            qfilter = qm.Filter(**where)
        except Exception as e:
            print(f"⚠️ Invalid --where JSON, ignoring: {e}")
    else:
        # client-side check will enforce schema_version < 3 regardless
        qfilter = None

    while True:
        points, next_offset = client.scroll(
            collection_name=args.collection,
            offset=offset,
            limit=args.batch_size,
            with_payload=True,
            with_vectors=False,
            filter=qfilter,
        )
        if not points:
            break

        payload_patches = {}
        for p in points:
            payload = p.payload or {}
            # enforce migration guard
            try:
                sv = int(payload.get("schema_version", 2))
            except Exception:
                sv = 2
            if sv >= 3:
                processed += 1
                continue
            patch = {}
            # beliefs normalization
            structured = ensure_structured_beliefs(payload.get("beliefs"))
            if payload.get("beliefs") != structured:
                patch["beliefs"] = structured
                counters["structured_beliefs"] += 1
            # schema bump
            patch["schema_version"] = 3
            counters["schema_bumped"] += 1
            # migration timestamp
            patch["last_migrated_at"] = iso_now()
            if patch:
                payload_patches[str(p.id)] = patch
                updated += 1
            processed += 1

        # Apply partial updates
        if payload_patches:
            if args.dry_run or not args.yes:
                print(f"[DRY-RUN] Would update {len(payload_patches)} points")
            else:
                for pid, patch in payload_patches.items():
                    client.set_payload(
                        collection_name=args.collection,
                        payload=patch,
                        points=[pid],
                    )
                print(f"✅ Updated {len(payload_patches)} points")

        # Save resume state
        offset = next_offset
        save_state(args.resume_file, {"offset": offset})
        if not next_offset:
            break

    print(f"Processed: {processed}")
    print(f"Updated (had changes): {updated}")
    print("Counters:")
    for k, v in counters.items():
        print(f" - {k}: {v}")
    if args.dry_run or not args.yes:
        print("Dry-run mode: No mutations were performed. Re-run with --yes to write.")


if __name__ == "__main__":
    main()
