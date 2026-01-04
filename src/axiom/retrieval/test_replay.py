#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure local imports work when run directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_replay")


def _first_line(text: str, limit: int = 80) -> str:
    if not isinstance(text, str):
        return ""
    line = text.strip().splitlines()[0] if text else ""
    return (line[: limit].rstrip() + ("…" if len(line) > limit else "")) if line else ""


async def _run_single_query(query: str, verbose: bool = False) -> Dict[str, Any]:
    from memory_response_pipeline import fetch_vector_hits_with_threshold as _fetch_hits
    from memory_response_pipeline import _compute_coverage as _coverage
    try:
        # Retrieve raw candidates with default top_k
        top_k = int(os.getenv("VECTOR_TOPK", "10") or 10)
        hits = await _fetch_hits(query, top_k=top_k, similarity_threshold=None)
    except Exception as e:
        # Graceful failure: no hits
        logger.warning(f"retrieval failed: {e}")
        hits = []

    # Compute coverage over texts
    texts = []
    for h in hits[:8]:
        txt = h.get("content") or h.get("text") or ""
        if txt:
            texts.append(txt)
    coverage = _coverage(query, texts)
    max_similarity = 0.0
    for h in hits[:8]:
        add = h.get("_additional") or {}
        s = add.get("score") if add.get("score") is not None else add.get("certainty")
        if s is None:
            s = h.get("score")
        try:
            max_similarity = max(max_similarity, float(s or 0.0))
        except Exception:
            pass

    # Prepare top matches output
    out_matches: List[Dict[str, Any]] = []
    for h in hits[: min(10, len(hits))]:
        add = h.get("_additional") or {}
        s = add.get("score") if add.get("score") is not None else add.get("certainty")
        if s is None:
            s = h.get("score")
        rer = h.get("_reranker_score")
        item = {
            "id": h.get("id"),
            "similarity": float(s or 0.0),
            "text": h.get("content") or h.get("text") or "",
        }
        if rer is not None:
            try:
                item["reranker_score"] = float(rer)
            except Exception:
                pass
        if not verbose:
            item["text"] = _first_line(item["text"])
        out_matches.append(item)

    # Heuristic flags (best-effort):
    dont_know_triggered = False  # Not directly accessible here; infer weak signal
    fallback_used = (len(hits) == 0)

    return {
        "query": query,
        "top_matches": out_matches,
        "coverage": round(float(coverage), 4),
        "max_similarity": round(float(max_similarity), 4),
        "dont_know_triggered": bool(dont_know_triggered),
        "fallback_used": bool(fallback_used),
    }


def _iter_queries(args: argparse.Namespace) -> List[str]:
    queries: List[str] = []
    if args.query:
        queries.append(args.query.strip())
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                for line in f:
                    s = (line or "").strip()
                    if not s:
                        continue
                    queries.append(s)
        except Exception as e:
            logger.error(f"Failed to read input file: {e}")
    # Deduplicate while preserving order
    seen = set()
    uniq: List[str] = []
    for q in queries:
        if q and q not in seen:
            uniq.append(q)
            seen.add(q)
    return uniq


def main():
    parser = argparse.ArgumentParser(description="Replay retrieval pipeline for queries")
    parser.add_argument("--query", type=str, help="Single query to run")
    parser.add_argument("--input", type=str, help="Path to queries.txt (one per line)")
    parser.add_argument("--verbose", action="store_true", help="Print full chunk texts and score diffs")
    parser.add_argument("--output", type=str, help="Optional JSONL output path")
    args = parser.parse_args()

    queries = _iter_queries(args)
    if not queries:
        print("{}")
        return

    async def _runner():
        results: List[Dict[str, Any]] = []
        for q in queries:
            try:
                res = await _run_single_query(q, verbose=args.verbose)
                results.append(res)
                line = json.dumps(res, ensure_ascii=False)
                print(line)
                # Append to output file if requested
                if args.output:
                    try:
                        os.makedirs(os.path.dirname(args.output), exist_ok=True)
                    except Exception:
                        pass
                    try:
                        with open(args.output, "a", encoding="utf-8") as f:
                            f.write(line + "\n")
                    except Exception as e:
                        logger.error(f"Failed to write output: {e}")
            except Exception as e:
                logger.error(f"Query failed: {e}")
        return results

    asyncio.run(_runner())


if __name__ == "__main__":
    main()
