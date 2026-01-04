#!/usr/bin/env python3
"""
Cursor Evaluator – Composite Scoring Profiles with MMR Grid and Controls

README (usage):
- Run against the memory API (pod) that exposes /retrieve and /memory-debug.
- Generates per-query JSON logs under logs/scoring_eval/{profile}/{mode}_mmr{lambda}/
- Produces logs/scoring_eval/summary.csv with metrics per (profile,mode,mmr,query)

Examples:
  python scripts/evaluate_scoring_profiles.py \
    --host localhost --port 5000 \
    --queries tests/resources/sample_queries.json \
    --profiles default evergreen personal \
    --topn 8 --topk 80

Modes:
- Baseline-VectorOnly: composite 0, ignore MMR
- Composite-NoMMR: composite 1, mmr_lambda 0
- Composite-MMR: composite 1, mmr_lambda in {0.2, 0.4, 0.6}
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from sklearn.metrics.pairwise import cosine_similarity

# ---------- Helpers ----------


def slugify(text: str) -> str:
    text = text.lower().strip()
    for ch in "\t\n\r":
        text = text.replace(ch, " ")
    text = " ".join(text.split())
    text = text.replace("'", "")
    safe = "".join(c for c in text if c.isalnum() or c in ("-", "_", " "))
    return "-".join(safe.split())[:80] or "q"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")


@dataclass
class EvalConfig:
    host: str
    port: int
    queries_path: Path
    profiles: List[str]
    topn: int
    topk: int
    mmr_grid: List[float]
    out_dir: Path
    timeout: int = 60


# ---------- Diversity metrics ----------


def pairwise_cosine_stats(vectors: List[List[float]]) -> Tuple[float, float]:
    if not vectors or len(vectors) < 2:
        return 0.0, 0.0
    X = np.array(vectors)
    S = cosine_similarity(X)
    # take upper triangle without diagonal
    n = S.shape[0]
    vals: List[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            vals.append(float(S[i, j]))
    if not vals:
        return 0.0, 0.0
    mean_pair = float(np.mean(vals))
    redundancy_rate = float(np.mean([1.0 if v >= 0.95 else 0.0 for v in vals]))
    return mean_pair, redundancy_rate


# ---------- Core evaluator ----------


def run_eval(cfg: EvalConfig) -> None:
    # Load queries
    with open(cfg.queries_path, "r", encoding="utf-8") as f:
        query_items = json.load(f)
    queries: List[str] = [
        q.get("query", "").strip() for q in query_items if isinstance(q, dict)
    ]
    queries = [q for q in queries if q]
    if not queries:
        raise SystemExit("No queries provided")

    # Summary CSV setup
    summary_path = cfg.out_dir / "summary.csv"
    ensure_dir(cfg.out_dir)
    write_header = not summary_path.exists()
    with open(summary_path, "a", encoding="utf-8", newline="") as csvf:
        writer = csv.writer(csvf)
        if write_header:
            writer.writerow(
                [
                    "query_slug",
                    "profile",
                    "mode",
                    "mmr_lambda",
                    "topN",
                    "avg_final_score",
                    "std_final_score",
                    "mean_pairwise_cosine",
                    "redundancy_rate",
                    "sim_avg",
                    "rec_avg",
                    "cred_avg",
                    "conf_avg",
                    "bel_avg",
                    "use_avg",
                    "nov_avg",
                    "latency_ms",
                ]
            )

        for profile in cfg.profiles:
            # Modes setup
            modes = [
                ("Baseline-VectorOnly", [None]),
                ("Composite-NoMMR", [0.0]),
                ("Composite-MMR", cfg.mmr_grid),
            ]

            for mode, lambdas in modes:
                for lam in lambdas:
                    for q in queries:
                        slug = slugify(q)
                        mmr_lambda = 0.0 if lam is None else lam
                        composite_enabled = (
                            False if mode == "Baseline-VectorOnly" else True
                        )
                        if mode == "Composite-NoMMR":
                            mmr_lambda = 0.0

                        # Build request body
                        payload = {
                            "question": q,
                            "composite_enabled": composite_enabled,
                            "scoring_profile": profile,
                            "mmr_lambda": float(mmr_lambda),
                            "top_k": int(cfg.topk),
                            "top_n": int(cfg.topn),
                        }

                        # Call /retrieve and capture memory_debug
                        url = f"http://{cfg.host}:{cfg.port}/retrieve"
                        try:
                            resp = requests.post(url, json=payload, timeout=cfg.timeout)
                            resp.raise_for_status()
                            obj = resp.json() if resp.content else {}
                            memdbg = obj.get("memory_debug") or {}
                        except Exception as e:
                            memdbg = {"error": str(e)}

                        # Write detailed JSON log
                        log_dir = cfg.out_dir / profile / f"{mode}_mmr{mmr_lambda}"
                        ensure_dir(log_dir)
                        log_path = log_dir / f"{timestamp()}_{slug}.json"
                        with open(log_path, "w", encoding="utf-8") as outf:
                            json.dump(
                                {
                                    "query": q,
                                    "profile": profile,
                                    "mode": mode,
                                    "mmr_lambda": float(mmr_lambda),
                                    "request": payload,
                                    "memory_debug": memdbg,
                                },
                                outf,
                                ensure_ascii=False,
                                indent=2,
                            )

                        # Aggregate metrics for summary
                        items = (
                            memdbg.get("items")
                            or memdbg.get("last", {}).get("items")
                            or []
                        )
                        latency_ms = (
                            memdbg.get("latency_ms")
                            or memdbg.get("last", {}).get("latency_ms")
                            or None
                        )
                        # Extract vectors if present for diversity; fallback to None
                        vectors: List[List[float]] = []
                        for it in items[: cfg.topn]:
                            vec = it.get("_vector") or it.get("vector")
                            if (
                                isinstance(vec, list)
                                and vec
                                and isinstance(vec[0], (float, int))
                            ):
                                vectors.append([float(v) for v in vec])

                        mean_pair, redundancy = pairwise_cosine_stats(vectors)

                        # Final score stats
                        final_scores = [
                            float(it.get("final_score", 0.0))
                            for it in items[: cfg.topn]
                        ]
                        avg_final = (
                            float(np.mean(final_scores)) if final_scores else 0.0
                        )
                        std_final = float(np.std(final_scores)) if final_scores else 0.0

                        # Factor averages (may be missing in vector-only)
                        def avg_field(name: str) -> float:
                            vals = [it.get(name) for it in items[: cfg.topn]]
                            vals = [float(v) for v in vals if v is not None]
                            return float(np.mean(vals)) if vals else 0.0

                        sim_avg = avg_field("sim")
                        rec_avg = avg_field("rec")
                        cred_avg = avg_field("cred")
                        conf_avg = avg_field("conf")
                        bel_avg = avg_field("bel")
                        use_avg = avg_field("use")
                        nov_avg = avg_field("nov")

                        writer.writerow(
                            [
                                slug,
                                profile,
                                mode,
                                f"{mmr_lambda:.2f}",
                                cfg.topn,
                                f"{avg_final:.6f}",
                                f"{std_final:.6f}",
                                f"{mean_pair:.6f}",
                                f"{redundancy:.6f}",
                                f"{sim_avg:.6f}",
                                f"{rec_avg:.6f}",
                                f"{cred_avg:.6f}",
                                f"{conf_avg:.6f}",
                                f"{bel_avg:.6f}",
                                f"{use_avg:.6f}",
                                f"{nov_avg:.6f}",
                                (
                                    int(latency_ms)
                                    if isinstance(latency_ms, (int, float))
                                    else ""
                                ),
                            ]
                        )

    # Print best per query
    best: Dict[str, Tuple[str, str, float, float]] = (
        {}
    )  # slug -> (profile, mode_mmr, avg_final, redundancy)
    with open(summary_path, "r", encoding="utf-8") as csvf:
        reader = csv.DictReader(csvf)
        rows = list(reader)
        for row in rows:
            slug = row["query_slug"]
            avg_final = float(row["avg_final_score"]) if row["avg_final_score"] else 0.0
            redund = float(row["redundancy_rate"]) if row["redundancy_rate"] else 0.0
            mode_mmr = f"{row['mode']}@{row['mmr_lambda']}"
            cand = best.get(slug)
            if (
                cand is None
                or avg_final > cand[2]
                or (avg_final == cand[2] and redund < cand[3])
            ):
                best[slug] = (row["profile"], mode_mmr, avg_final, redund)

    print("\nBest configuration per query:")
    print("query_slug,profile,mode@mmr,avg_final,redundancy")
    for slug, (prof, mmr, avgf, red) in best.items():
        print(f"{slug},{prof},{mmr},{avgf:.6f},{red:.6f}")


# ---------- CLI ----------


def parse_args() -> EvalConfig:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.getenv("MEMORY_API_HOST", "localhost"))
    p.add_argument(
        "--port", type=int, default=int(os.getenv("MEMORY_API_PORT", "5000"))
    )
    p.add_argument("--queries", default="tests/resources/sample_queries.json")
    p.add_argument(
        "--profiles", nargs="*", default=["default", "evergreen", "personal"]
    )
    p.add_argument("--topn", type=int, default=8)
    p.add_argument("--topk", type=int, default=80)
    p.add_argument("--out", default="logs/scoring_eval")
    args = p.parse_args()
    return EvalConfig(
        host=str(args.host),
        port=int(args.port),
        queries_path=Path(args.queries),
        profiles=list(args.profiles),
        topn=int(args.topn),
        topk=int(args.topk),
        mmr_grid=[0.2, 0.4, 0.6],
        out_dir=Path(args.out),
    )


if __name__ == "__main__":
    cfg = parse_args()
    run_eval(cfg)
