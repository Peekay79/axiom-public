#!/usr/bin/env python3

import argparse
import json
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm

    QDRANT_AVAILABLE = True
except Exception as e:
    print(f"❌ qdrant-client import failed: {e}")
    QDRANT_AVAILABLE = False

# Safe default values for required fields
REQUIRED_DEFAULTS = {
    "source_trust": 0.6,
    "confidence": 0.5,
    "times_used": 0,
    "beliefs": [],
    "importance": 0.5,
    "memory_type": "default",
    "schema_version": 3,
}

REQUIRED_OPTIONAL = ["timestamp", "last_migrated_at"]

logger = logging.getLogger(__name__)
INVALID_SENTINELS = {"", "null", "undefined", "nan"}


def _is_invalid_sentinel(value):
    if isinstance(value, str):
        return value.strip().lower() in INVALID_SENTINELS
    return False


def _is_invalid_required_value(field: str, value):
    if value is None:
        return True
    if _is_invalid_sentinel(value):
        return True
    if field == "beliefs":
        return not isinstance(value, list)
    if field == "memory_type":
        return not isinstance(value, str) or _is_invalid_sentinel(value)
    if field == "times_used":
        return not isinstance(value, int) or isinstance(value, bool)
    if field == "schema_version":
        return not isinstance(value, int) or isinstance(value, bool)
    if field in ("source_trust", "confidence", "importance"):
        return not (isinstance(value, (int, float)) and not isinstance(value, bool))
    return False


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    p = argparse.ArgumentParser(
        description="Backfill required payload fields in Qdrant (idempotent, resumable). Defaults to --dry-run; pass --yes to write."
    )
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=6333)
    # Default to unified collection names; CLI --collection overrides
    default_collection = None
    try:
        from memory.memory_collections import memory_collection as _memory_collection

        default_collection = _memory_collection()
    except Exception:
        default_collection = "axiom_memories"
    p.add_argument("--collection", default=default_collection)
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--resume-file", default=".backfill_state.json")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--yes", action="store_true", help="Actually write changes")
    p.add_argument(
        "--where", default=None, help="Optional JSON filter for Qdrant scroll"
    )
    p.add_argument(
        "--fields",
        default=None,
        help="Comma-separated list of fields to backfill (subset of required)",
    )
    p.add_argument(
        "--skip-present",
        dest="skip_present",
        action="store_true",
        default=True,
        help="Do not overwrite non-null fields (default)",
    )
    p.add_argument(
        "--overwrite-present",
        dest="skip_present",
        action="store_false",
        help="Overwrite even if field is present (use with caution)",
    )
    p.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Concurrency for updates (number of threads)",
    )
    p.add_argument(
        "--coerce-types",
        action="store_true",
        help="Treat invalid or incorrectly typed required field values as missing and replace with defaults; logs coerced fields.",
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


def apply_patch(client: QdrantClient, collection: str, pid: str, patch: dict):
    client.set_payload(collection_name=collection, payload=patch, points=[pid])


def main():
    if not QDRANT_AVAILABLE:
        print("❌ qdrant-client not available. Install with: pip install qdrant-client")
        sys.exit(1)
    args = parse_args()
    client = QdrantClient(host=args.host, port=args.port, timeout=60)

    # Determine target fields
    all_required = list(REQUIRED_DEFAULTS.keys()) + REQUIRED_OPTIONAL
    if args.fields:
        requested = [f.strip() for f in args.fields.split(",") if f.strip()]
        # Validate requested subset
        target_fields = [f for f in requested if f in all_required]
        invalid = sorted(set(requested) - set(target_fields))
        if invalid:
            print(f"⚠️ Ignoring unknown fields: {', '.join(invalid)}")
    else:
        target_fields = all_required

    state = load_state(args.resume_file)
    offset = state.get("offset")
    processed = 0
    total_points_updated = 0
    missing_counts = {k: 0 for k in all_required}
    injected_counts = {k: 0 for k in all_required}

    # Prepare filter if provided
    qfilter = None
    if args.where:
        try:
            where = json.loads(args.where)
            # Expect full Filter dict; pass through best-effort
            qfilter = qm.Filter(**where)
        except Exception as e:
            print(f"⚠️ Invalid --where JSON, ignoring: {e}")

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
            patch = {}
            # Compute missing counts and patch according to target_fields
            for k in target_fields:
                if k in REQUIRED_DEFAULTS:
                    default_val = REQUIRED_DEFAULTS[k]
                    current_val = payload.get(k)
                    if args.skip_present:
                        if current_val is None:
                            patch[k] = default_val
                            missing_counts[k] += 1
                        elif args.coerce_types and _is_invalid_required_value(k, current_val):
                            patch[k] = default_val
                            logger.info(f"[coerce] Field '{k}' was invalid, coerced to default for UUID {p.id}")
                    else:
                        # overwrite
                        if current_val is None:
                            missing_counts[k] += 1
                        patch[k] = default_val
                elif k == "timestamp":
                    if payload.get("timestamp") is None:
                        patch["timestamp"] = iso_now()
                        missing_counts["timestamp"] += 1
                elif k == "last_migrated_at":
                    if payload.get("last_migrated_at") is None:
                        patch["last_migrated_at"] = iso_now()
                        missing_counts["last_migrated_at"] += 1
            # Aggregate
            if patch:
                for fld in patch.keys():
                    injected_counts[fld] += 1
                payload_patches[str(p.id)] = patch
            recorded_any = bool(patch)
            if recorded_any:
                total_points_updated += 1
        # count processed once per point in batch
        processed += len(points)

        # Apply partial updates in parallel if requested
        if payload_patches:
            if args.dry_run or not args.yes:
                print(
                    f"[DRY-RUN] Would update {len(payload_patches)} points (skip_present={args.skip_present}, parallel={args.parallel})"
                )
            else:
                if args.parallel and args.parallel > 1:
                    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
                        futures = [
                            executor.submit(
                                apply_patch, client, args.collection, pid, patch
                            )
                            for pid, patch in payload_patches.items()
                        ]
                        for fut in as_completed(futures):
                            _ = fut.result()
                    print(
                        f"✅ Updated {len(payload_patches)} points (parallel={args.parallel})"
                    )
                else:
                    for pid, patch in payload_patches.items():
                        apply_patch(client, args.collection, pid, patch)
                    print(f"✅ Updated {len(payload_patches)} points")

        # Save resume state
        offset = next_offset
        save_state(args.resume_file, {"offset": offset})
        if not next_offset:
            break

    print(f"Processed: {processed}")
    print(f"Points updated: {total_points_updated}")
    print("Missing field counts (encountered as missing):")
    for k in all_required:
        print(f" - {k}: {missing_counts.get(k, 0)}")
    print("Injected fields (counts per field):")
    for k in all_required:
        if injected_counts.get(k, 0) > 0:
            print(f" - {k}: {injected_counts[k]}")

    if args.dry_run or not args.yes:
        print("Dry-run mode: No mutations were performed. Re-run with --yes to write.")


if __name__ == "__main__":
    main()
