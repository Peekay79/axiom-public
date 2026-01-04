#!/usr/bin/env python3
"""
Backfill recent journal entries into the vector store (optional).

Usage:
  JOURNAL_VECTOR_ENABLED=true python scripts/journal_backfill.py --file /workspace/data/journal/entries.jsonl --limit 100

This is a safe, read-only scan of a JSONL journal file that sends minimal
{content, metadata} items to the UnifiedVectorClient upsert path.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import List, Dict


def _load_last_n(path: str, limit: int) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        if limit and limit > 0:
            out = out[-limit:]
    except Exception as e:
        print(f"[journal_backfill] failed to read journal: {e}")
        out = []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="/workspace/data/journal/entries.jsonl")
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    if str(os.getenv("JOURNAL_VECTOR_ENABLED", "0")).strip().lower() not in {"1", "true", "yes"}:
        print("{" + "\"component\":\"journal_backfill\",\"status\":\"disabled\"" + "}")
        return 0

    entries = _load_last_n(args.file, args.limit)
    if not entries:
        print("{" + "\"component\":\"journal_backfill\",\"status\":\"empty\"" + "}")
        return 0

    from vector.unified_client import UnifiedVectorClient  # type: ignore

    client = UnifiedVectorClient(os.environ)
    items = []
    for e in entries:
        try:
            title = e.get("title") or ""
            summary = e.get("summary") or ""
            timestamp = (e.get("timestamp") or "")
            tags = (e.get("metadata", {}) or {}).get("tags", [])
            if not isinstance(tags, list):
                tags = []
            tags = list(set(tags + ["journal_entry"]))
            content = f"{title}\n\n{summary}".strip()
            if not content:
                continue
            items.append({
                "content": content,
                "metadata": {
                    "tags": tags,
                    "type": "memory",
                    "timestamp": timestamp,
                    "source": "journal_ingest",
                },
            })
        except Exception:
            continue

    if not items:
        print("{" + "\"component\":\"journal_backfill\",\"status\":\"no_items\"" + "}")
        return 0

    try:
        res = client.upsert(collection="axiom_memories", items=items)
        inserted = int(res.get("inserted", 0)) if isinstance(res, dict) else 0
        print("{" + f"\"component\":\"journal_backfill\",\"status\":\"ok\",\"inserted\":{inserted}" + "}")
    except Exception as e:
        reason = str(e)
        if len(reason) > 200:
            reason = reason[:200]
        print("{" + f"\"component\":\"journal_backfill\",\"status\":\"fail\",\"reason\":\"{reason}\"" + "}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

