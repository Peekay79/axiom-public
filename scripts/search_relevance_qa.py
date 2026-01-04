#!/usr/bin/env python3

import argparse
import json
import os
import sys
import textwrap
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

# Third-party
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception as e:
    print(
        "Error: sentence-transformers is required. Install with: pip install sentence-transformers",
        file=sys.stderr,
    )
    raise

# Project-local imports
try:
    from axiom_qdrant_client import QdrantClient
except Exception as e:
    print(f"Error importing Qdrant client wrapper: {e}", file=sys.stderr)
    raise

try:
    from memory.scoring import composite_score, load_weights
except Exception as e:
    print(f"Error importing composite scoring: {e}", file=sys.stderr)
    raise


@dataclass
class FactorBreakdown:
    sim: float
    rec: float
    cred: float
    conf: float
    bel: float
    use: float
    nov: float


@dataclass
class ResultRow:
    id: str
    content_preview: str
    vector_score: float
    composite_score: Optional[float]
    metadata_contrib: Optional[float]
    factor_values: Optional[FactorBreakdown]
    weights: Optional[Dict[str, float]]
    payload_missing: List[str]
    payload: Dict[str, Any]


@dataclass
class ScoreCandidate:
    vector: List[float]
    timestamp: Any
    source_trust: Any
    confidence: Any
    times_used: Any
    beliefs: Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search Relevance QA Harness for Composite Scoring",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group_q = parser.add_mutually_exclusive_group(required=True)
    group_q.add_argument("--query", type=str, help="Single query string")
    group_q.add_argument(
        "--query-file", type=str, help="Path to a file with queries (one per line)"
    )

    # Default to unified collection names; CLI --collection overrides
    try:
        from memory.memory_collections import memory_collection as _memory_collection

        _default_coll = _memory_collection()
    except Exception:
        _default_coll = "axiom_memories"
    parser.add_argument(
        "--collection",
        type=str,
        default=_default_coll,
        help="Qdrant collection to search",
    )
    parser.add_argument(
        "--limit",
        "--top-k",
        dest="top_k",
        type=int,
        default=10,
        help="Top-K to retrieve",
    )
    parser.add_argument(
        "--filters", type=str, default=None, help="JSON string for Qdrant filters"
    )

    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--baseline", action="store_true", help="Run vector-only scoring")
    mode.add_argument(
        "--composite", action="store_true", help="Run composite scoring pipeline"
    )
    mode.add_argument(
        "--compare", action="store_true", help="Run both and compare side-by-side"
    )

    parser.add_argument(
        "--json", action="store_true", help="Output JSON instead of table"
    )
    parser.add_argument(
        "--save", type=str, default=None, help="Save results JSON to file"
    )
    parser.add_argument(
        "--show-weights",
        action="store_true",
        help="Print current composite scoring weights in use",
    )
    parser.add_argument(
        "--profile", action="store_true", help="Time each retrieval and scoring stage"
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=None,
        help="Discard items older than this many days (client-side filter)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("QDRANT_HOST", "localhost"),
        help="Qdrant host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("QDRANT_PORT", "6333")),
        help="Qdrant port",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("AXIOM_EMBED_MODEL", "all-MiniLM-L6-v2"),
        help="SentenceTransformer model",
    )
    return parser.parse_args()


def load_queries(args: argparse.Namespace) -> List[str]:
    if args.query is not None:
        return [args.query.strip()]
    # query file
    queries: List[str] = []
    with open(args.query_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(line)
    return queries


def embed_queries(
    embedder: SentenceTransformer, queries: List[str]
) -> List[List[float]]:
    vecs = embedder.encode(queries, normalize_embeddings=True)
    # SentenceTransformer returns numpy array; convert to lists
    try:
        return [v.tolist() for v in vecs]
    except Exception:
        return [list(map(float, v)) for v in vecs]


def parse_filters(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            print(
                "Warning: --filters must be a JSON object; ignoring.", file=sys.stderr
            )
            return None
        return parsed
    except Exception as e:
        print(
            f"Warning: failed to parse --filters JSON: {e}; ignoring.", file=sys.stderr
        )
        return None


def preview_text(text: str, width: int = 96) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def required_fields() -> List[str]:
    return [
        "timestamp",
        "source_trust",
        "confidence",
        "times_used",
        "beliefs",
        "importance",
    ]


def compute_composite_for_hits(
    query_vec: List[float],
    hits: List[Any],
    weights: Dict[str, float],
) -> List[ResultRow]:
    rows: List[ResultRow] = []
    for h in hits:
        payload: Dict[str, Any] = h.payload or {}
        mv = h.vector
        if mv is None:
            # Missing vector; composite cannot compute similarity
            final = None
            factors = None
            meta_contrib = None
        else:
            final, parts = composite_score(
                ScoreCandidate(
                    vector=mv,
                    timestamp=payload.get("timestamp"),
                    source_trust=payload.get("source_trust"),
                    confidence=payload.get("confidence"),
                    times_used=payload.get("times_used"),
                    beliefs=payload.get("beliefs"),
                ),
                query_vec,
                selected=None,
                w=weights,
            )
            base = float(weights.get("w_sim", 1.0)) * float(parts.get("sim", 0.0))
            meta_contrib = float(final) - base
            factors = FactorBreakdown(
                sim=float(parts.get("sim", 0.0)),
                rec=float(parts.get("rec", 0.0)),
                cred=float(parts.get("cred", 0.0)),
                conf=float(parts.get("conf", 0.0)),
                bel=float(parts.get("bel", 0.0)),
                use=float(parts.get("use", 0.0)),
                nov=float(parts.get("nov", 0.0)),
            )

        missing = [
            f
            for f in required_fields()
            if f not in payload or payload.get(f) in (None, "", [])
        ]
        row = ResultRow(
            id=str(h.id),
            content_preview=preview_text(payload.get("content", "")),
            vector_score=float(h.score or 0.0),
            composite_score=(None if mv is None else float(final)),
            metadata_contrib=meta_contrib,
            factor_values=factors,
            weights=weights,
            payload_missing=missing,
            payload=payload,
        )
        rows.append(row)
    return rows


def filter_by_max_age(
    rows: List[ResultRow], max_age_days: Optional[float]
) -> List[ResultRow]:
    if not max_age_days:
        return rows
    cut_ms = max_age_days * 86400.0
    out: List[ResultRow] = []
    from datetime import datetime

    for r in rows:
        ts = r.payload.get("timestamp") if r.payload else None
        try:
            if isinstance(ts, str):
                if ts.endswith("Z"):
                    ts = ts.replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts)
            elif ts is None:
                dt = None
            else:
                dt = ts  # assume datetime
            if dt is None:
                continue
            age_days = (
                datetime.now(datetime.utcnow().astimezone().tzinfo)
                - (
                    dt
                    if dt.tzinfo
                    else dt.replace(tzinfo=datetime.utcnow().astimezone().tzinfo)
                )
            ).total_seconds() / 86400.0
            if age_days <= max_age_days:
                out.append(r)
        except Exception:
            # If timestamp invalid, drop when max age filter is set
            pass
    return out


def print_table(rows: List[ResultRow], title: Optional[str] = None) -> None:
    if title:
        print(title)
        print("=" * len(title))

    # Column headers
    headers = [
        "Rank",
        "UUID",
        "Preview",
        "Vec",
        "Meta",
        "Comp",
        "rec/cred/conf/bel/use/nov",
        "Missing",
    ]
    widths = [4, 8, 48, 6, 6, 7, 26, 16]

    def fmt_num(x: Optional[float], w: int, prec: int = 3) -> str:
        if x is None:
            return " " * w
        return f"{x:.{prec}f}".rjust(w)

    print(
        " ".join(
            [
                "Rank".ljust(widths[0]),
                "UUID".ljust(widths[1]),
                "Preview".ljust(widths[2]),
                "Vec".rjust(widths[3]),
                "Meta".rjust(widths[4]),
                "Comp".rjust(widths[5]),
                "rec/cred/conf/bel/use/nov".ljust(widths[6]),
                "Missing".ljust(widths[7]),
            ]
        )
    )
    print("-" * (sum(widths) + len(widths) - 1))

    for i, r in enumerate(rows, start=1):
        f = r.factor_values
        f_str = ""
        if f is not None:
            f_str = f"{f.rec:.2f}/{f.cred:.2f}/{f.conf:.2f}/{f.bel:.2f}/{f.use:.2f}/{f.nov:.2f}"
        missing_str = ",".join(r.payload_missing[:3]) if r.payload_missing else ""
        print(
            " ".join(
                [
                    str(i).ljust(widths[0]),
                    r.id[: widths[1]].ljust(widths[1]),
                    r.content_preview[: widths[2]].ljust(widths[2]),
                    fmt_num(r.vector_score, widths[3]),
                    fmt_num(r.metadata_contrib, widths[4]),
                    fmt_num(r.composite_score, widths[5]),
                    f_str.ljust(widths[6]),
                    missing_str[: widths[7]].ljust(widths[7]),
                ]
            )
        )
    print()


def print_compare_table(base: List[ResultRow], comp: List[ResultRow]) -> None:
    # Build index by id
    base_idx = {r.id: i for i, r in enumerate(base, start=1)}
    comp_idx = {r.id: i for i, r in enumerate(comp, start=1)}
    all_ids = list({*base_idx.keys(), *comp_idx.keys()})

    headers = ["ΔRank", "UUID", "BaseRank", "CompRank", "Vec", "Comp", "ΔS", "Preview"]
    widths = [6, 8, 9, 9, 6, 7, 6, 48]

    def fmt_num(x: Optional[float], w: int, prec: int = 3) -> str:
        if x is None:
            return " " * w
        return f"{x:.{prec}f}".rjust(w)

    print(
        " ".join(
            [
                "ΔRank".rjust(widths[0]),
                "UUID".ljust(widths[1]),
                "BaseRank".rjust(widths[2]),
                "CompRank".rjust(widths[3]),
                "Vec".rjust(widths[4]),
                "Comp".rjust(widths[5]),
                "ΔS".rjust(widths[6]),
                "Preview".ljust(widths[7]),
            ]
        )
    )
    print("-" * (sum(widths) + len(widths) - 1))

    # Order by comp rank then base rank
    sorted_ids = sorted(
        all_ids, key=lambda mid: (comp_idx.get(mid, 9999), base_idx.get(mid, 9999))
    )
    for mid in sorted_ids:
        b = next((r for r in base if r.id == mid), None)
        c = next((r for r in comp if r.id == mid), None)
        br = base_idx.get(mid, None)
        cr = comp_idx.get(mid, None)
        dr = None
        if br is not None and cr is not None:
            dr = br - cr
        preview = (c or b).content_preview if (c or b) else ""
        ds = None
        if b and c and c.composite_score is not None:
            ds = c.composite_score - b.vector_score
        print(
            " ".join(
                [
                    (str(dr) if dr is not None else "").rjust(widths[0]),
                    mid[: widths[1]].ljust(widths[1]),
                    (str(br) if br is not None else "").rjust(widths[2]),
                    (str(cr) if cr is not None else "").rjust(widths[3]),
                    fmt_num(b.vector_score if b else None, widths[4]),
                    fmt_num(c.composite_score if c else None, widths[5]),
                    fmt_num(ds, widths[6]),
                    preview[: widths[7]].ljust(widths[7]),
                ]
            )
        )
    print()


def to_json_serializable(rows: List[ResultRow]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, r in enumerate(rows, start=1):
        item: Dict[str, Any] = {
            "rank": i,
            "id": r.id,
            "preview": r.content_preview,
            "vector_score": r.vector_score,
            "composite_score": r.composite_score,
            "metadata_contrib": r.metadata_contrib,
            "payload_missing": r.payload_missing,
            "payload": r.payload,
        }
        if r.factor_values is not None:
            item["factors"] = asdict(r.factor_values)
        if r.weights is not None:
            item["weights"] = r.weights
        out.append(item)
    return out


def main() -> None:
    args = parse_args()
    queries = load_queries(args)

    # Load weights based on env profile
    profile_name = os.getenv("AXIOM_SCORING_PROFILE", "default")
    weights = load_weights(
        profile_name, config_path=os.path.join("config", "composite_weights.yaml")
    )
    if args.show_weights:
        print(f"Composite scoring weights (profile={profile_name}):")
        print(json.dumps(weights, indent=2))
        print()

    # Set up embedder and Qdrant client
    embedder = SentenceTransformer(args.model)
    client = QdrantClient(host=args.host, port=args.port, timeout=30)

    filters = parse_filters(args.filters)

    all_results: Dict[str, Any] = {"queries": []}

    for q in queries:
        if args.profile:
            t0 = time.perf_counter()
        qv = embed_queries(embedder, [q])[0]
        if args.profile:
            t_embed = (time.perf_counter() - t0) * 1000.0

        if args.profile:
            t1 = time.perf_counter()
        # Retrieve with vectors for composite scoring
        hits = client.query_memory(
            collection_name=args.collection,
            query_vector=qv,
            limit=args.top_k,
            score_threshold=0.0,
            filter_conditions=filters,
            include_vectors=True,
        )
        if args.profile:
            t_qdrant = (time.perf_counter() - t1) * 1000.0

        # Build baseline rows
        baseline_rows: List[ResultRow] = [
            ResultRow(
                id=str(h.id),
                content_preview=preview_text((h.payload or {}).get("content", "")),
                vector_score=float(h.score or 0.0),
                composite_score=None,
                metadata_contrib=None,
                factor_values=None,
                weights=None,
                payload_missing=[
                    f for f in required_fields() if f not in (h.payload or {})
                ],
                payload=h.payload or {},
            )
            for h in hits
        ]

        # Apply optional recency filter client-side
        baseline_rows = filter_by_max_age(baseline_rows, args.max_age_days)

        # Composite rows
        if args.profile:
            t2 = time.perf_counter()
        composite_rows = compute_composite_for_hits(qv, hits, weights)
        # Keep only those that passed recency filter
        if args.max_age_days:
            allowed_ids = {r.id for r in baseline_rows}
            composite_rows = [r for r in composite_rows if r.id in allowed_ids]
        # Sort by composite score desc, fallback to vector score
        composite_rows.sort(
            key=lambda r: (
                r.composite_score if r.composite_score is not None else -1.0
            ),
            reverse=True,
        )
        if args.profile:
            t_comp = (time.perf_counter() - t2) * 1000.0

        # Determine mode
        if args.compare:
            # Sort baseline by vector desc
            baseline_rows.sort(key=lambda r: r.vector_score, reverse=True)
            # Truncate to top_k
            baseline_rows = baseline_rows[: args.top_k]
            composite_rows = composite_rows[: args.top_k]
            if not args.json:
                print(f"Query: {q}")
                print_compare_table(baseline_rows, composite_rows)
            # Always collect results for saving
            all_results["queries"].append(
                {
                    "query": q,
                    "baseline": to_json_serializable(baseline_rows),
                    "composite": to_json_serializable(composite_rows),
                }
            )
        elif args.baseline and not args.composite:
            baseline_rows.sort(key=lambda r: r.vector_score, reverse=True)
            baseline_rows = baseline_rows[: args.top_k]
            if not args.json:
                print(f"Query: {q}")
                print_table(baseline_rows, title="Baseline (Vector-only)")
            # Always collect results for saving
            all_results["queries"].append(
                {
                    "query": q,
                    "baseline": to_json_serializable(baseline_rows),
                }
            )
        else:
            # default to composite if unspecified or explicitly composite
            composite_rows = composite_rows[: args.top_k]
            if not args.json:
                print(f"Query: {q}")
                print_table(composite_rows, title="Composite Scoring")
            # Always collect results for saving
            all_results["queries"].append(
                {
                    "query": q,
                    "composite": to_json_serializable(composite_rows),
                }
            )

        # Summarize missing fields and suggest backfill if needed
        missing_total = 0
        missing_hits = 0
        for rr in (
            composite_rows if not args.baseline or args.composite else baseline_rows
        ):
            if rr.payload_missing:
                missing_total += len(rr.payload_missing)
                missing_hits += 1
        if missing_hits > 0 and not args.json:
            print(
                f"Warning: missing schema fields detected in {missing_hits}/{len(baseline_rows)} results (total missing: {missing_total})."
            )
            print(
                "Hint: run scripts/verify_schema.py and scripts/backfill_memory_fields.py to populate defaults."
            )
            print()

        if args.profile and not args.json:
            print(
                f"Timing: embed={t_embed:.1f}ms  qdrant={t_qdrant:.1f}ms  composite={t_comp:.1f}ms"
            )
            print()

    # Save JSON if requested
    if args.json:
        payload = all_results
        if args.profile:
            payload["profile"] = True
        if args.show_weights:
            payload["weights_profile"] = os.getenv("AXIOM_SCORING_PROFILE", "default")
            payload["weights"] = weights
        out_str = json.dumps(payload, indent=2)
        print(out_str)
        if args.save:
            with open(args.save, "w", encoding="utf-8") as f:
                f.write(out_str)
    else:
        if args.save:
            # Save the last built payload as JSON with minimal info
            payload = all_results if all_results["queries"] else {}
            with open(args.save, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)


if __name__ == "__main__":
    main()
