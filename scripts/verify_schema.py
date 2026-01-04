#!/usr/bin/env python3

import argparse
import json
import random
import sys
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Filter

    QDRANT_AVAILABLE = True
except Exception as e:
    print(f"❌ qdrant-client import failed: {e}")
    QDRANT_AVAILABLE = False

REQUIRED_FIELDS = [
    "timestamp",
    "source_trust",
    "confidence",
    "times_used",
    "beliefs",
    "importance",
    "memory_type",
    "schema_version",
    "last_migrated_at",
]

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
    if field in ("timestamp", "last_migrated_at", "memory_type"):
        return not isinstance(value, str) or _is_invalid_sentinel(value)
    if field == "beliefs":
        return not isinstance(value, list)
    if field in ("times_used", "schema_version"):
        return not isinstance(value, int) or isinstance(value, bool)
    if field in ("source_trust", "confidence", "importance"):
        return not (isinstance(value, (int, float)) and not isinstance(value, bool))
    return False


def parse_args():
    p = argparse.ArgumentParser(
        description="Verify Qdrant collection schema payloads (read-only). Reminder: use --dry-run in backfill script for writes."
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
    p.add_argument(
        "--sample",
        type=int,
        default=1000,
        help="Sample size to check when not using --full (use backfill --dry-run for mutations)",
    )
    p.add_argument(
        "--full",
        action="store_true",
        help="Scan the entire collection instead of a sample. Exits 1 if any required fields are missing.",
    )
    p.add_argument(
        "--flag-invalid",
        action="store_true",
        help="Warn if required fields have present but invalid values (e.g., empty string or wrong type).",
    )
    return p.parse_args()


def main():
    if not QDRANT_AVAILABLE:
        return
    args = parse_args()
    client = QdrantClient(host=args.host, port=args.port, timeout=30)

    # Read collection info
    total_count = None
    try:
        info = client.get_collection(args.collection)
        metric = None
        dim = None
        vectors_cfg = getattr(info, "vectors", None)
        if vectors_cfg and hasattr(vectors_cfg, "config"):
            cfg = vectors_cfg.config
            dim = getattr(cfg, "size", None)
            metric = getattr(cfg, "distance", None)
        total_count = getattr(info, "points_count", None)
        print(f"Collection '{args.collection}': distance={metric}, dim={dim}")
    except Exception as e:
        print(f"⚠️ Failed to get collection info: {e}")

    if total_count is not None:
        print(f"Total points in collection: {total_count}")

    missing_counts = {f: 0 for f in REQUIRED_FIELDS}
    field_types = {}
    checked = 0
    offset = None
    limit = 200

    # Determine how many to check
    target_to_check = (
        total_count
        if args.full and total_count is not None
        else (10**12 if args.full else args.sample)
    )

    while checked < target_to_check:
        res = client.scroll(
            collection_name=args.collection,
            offset=offset,
            limit=min(limit, target_to_check - checked),
            with_payload=True,
            with_vectors=False,
        )
        points, offset = res
        if not points:
            break
        for p in points:
            payload = p.payload or {}
            # Required field presence
            for f in REQUIRED_FIELDS:
                if f not in payload or payload.get(f) is None:
                    missing_counts[f] += 1
            # Flag invalid present values when requested
            if args.flag_invalid:
                for f in REQUIRED_FIELDS:
                    if f in payload and payload.get(f) is not None:
                        v = payload.get(f)
                        if _is_invalid_required_value(f, v):
                            try:
                                v_str = json.dumps(v)
                            except Exception:
                                v_str = str(v)
                            print(f"[warn] Field '{f}' in UUID {p.id} is present but invalid (value: {v_str})")
            # Type tracking (for non-null values)
            for key, val in payload.items():
                if val is not None:
                    ft = type(val).__name__
                    field_types.setdefault(key, set()).add(ft)
            # Additional checks: beliefs structure & schema_version>=3
            beliefs = payload.get("beliefs")
            if beliefs is None:
                missing_counts["beliefs"] += 0  # already counted
            else:
                if not isinstance(beliefs, list):
                    print(f"Non-list beliefs for point {p.id}")
            sv = payload.get("schema_version")
            try:
                if sv is not None and int(sv) < 3:
                    print(f"Old schema_version for point {p.id}: {sv}")
            except Exception:
                print(f"Unparseable schema_version for point {p.id}: {sv}")
            checked += 1
            if checked >= target_to_check:
                break

    print(f"Checked: {checked}")
    print("Missing field counts (and % of checked):")
    for k, v in missing_counts.items():
        pct = (v / checked * 100.0) if checked else 0.0
        print(f" - {k}: {v} ({pct:.2f}%)")

    # Mixed-type fields
    mixed = {k: sorted(list(v)) for k, v in field_types.items() if len(v) > 1}
    if mixed:
        print("Mixed-type payload fields detected:")
        for k, types in mixed.items():
            print(f" - {k}: {', '.join(types)}")
    else:
        print("No mixed-type payload fields detected.")

    # CI failure on full scan if any missing
    if args.full and sum(missing_counts.values()) > 0:
        print("❌ Missing required fields detected in full scan. Failing.")
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
