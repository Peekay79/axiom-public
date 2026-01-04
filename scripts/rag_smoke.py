#!/usr/bin/env python3
import os, requests, json, re

# Public-safe default (override via MEMORY_POD_URL)
MEM = os.getenv("MEMORY_POD_URL", "http://localhost:8002").rstrip("/")

# Pattern matching for negation/meta and heading detection
NEGATION_PATTERNS = re.compile(r"\b(doesn'?t exist|can'?t remember|don'?t (have|know).+memory|no (memory|info)\b)", re.I)
META_PATTERNS = re.compile(r"^\s*(recall example|do you know|can you remember)", re.I)
HEADING_PATTERN = re.compile(r"^\s*\*{2}\[[^\]]+\]\*{2}")  # **[ ... ]**


def q(qs: str):
    url = f"{MEM}/api/search"
    try:
        r = requests.post(url, json={"query": qs, "k": 20}, timeout=10)
        r.raise_for_status()
        data = r.json() if r is not None else {}
        hits = data.get("hits", []) or data.get("results", []) or []
        print(f"\nQ: {qs} | hits={len(hits)}")
        for h in hits[:5]:
            try:
                score = h.get("score", h.get("_similarity", 0.0)) if isinstance(h, dict) else 0.0
            except Exception:
                score = 0.0
            try:
                text = (h.get("text") or h.get("content") or "")[:120]
            except Exception:
                text = str(h)[:120]
            try:
                hid = h.get("id", "?")
            except Exception:
                hid = "?"
            print(json.dumps({"score": round(float(score or 0.0), 3), "id": hid, "text": text}, ensure_ascii=False))
    except Exception as e:
        print(f"⚠️  Request failed for '{qs}': {e}")


if __name__ == "__main__":
    import sys
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="append", help="Query string to probe (can repeat)")
    ap.add_argument("--k", type=int, default=20, help="Number of results to retrieve (default: 20)")
    ap.add_argument("--probe-only", action="store_true", help="Exit nonzero if no hits found across probes")
    ap.add_argument("--long-ingest", action="store_true", help="Create a long temp memory and verify chunking")
    ap.add_argument("--plain-logs", action="store_true", help="Force ASCII logging (AXIOM_PLAIN_LOGS=1)")
    args = ap.parse_args()

    # Enable plain logs mode before other imports/logging in children
    if args.plain_logs:
        os.environ["AXIOM_PLAIN_LOGS"] = "1"

    # Example-only probes (avoid any private entities)
    probes = args.probe or ["hello world", "example memory", "test query"]
    k_val = args.k
    total_hits = 0
    for qs in probes:
        url = f"{MEM}/api/search"
        try:
            r = requests.post(url, json={"query": qs, "k": k_val}, timeout=10)
            r.raise_for_status()
            data = r.json() if r is not None else {}
            hits = data.get("hits", []) or data.get("results", []) or []
            total_hits += len(hits)
            print(f"\nQ: {qs} | hits={len(hits)}")
            # Print all hits (score + id + 160 chars)
            for i, h in enumerate(hits):
                try:
                    score = h.get("score", h.get("_similarity", 0.0)) if isinstance(h, dict) else 0.0
                except Exception:
                    score = 0.0
                try:
                    text = (h.get("text") or h.get("content") or "")[:160]
                except Exception:
                    text = str(h)[:160]
                try:
                    hid = h.get("id", "?")
                except Exception:
                    hid = "?"
                # Check if text contains exact phrase
                contains_phrase = qs.lower() in text.lower()
                
                # Check for negation/meta patterns and heading bonus
                full_text = (h.get("text") or h.get("content") or "")
                is_negated = bool(NEGATION_PATTERNS.search(full_text))
                is_meta = bool(META_PATTERNS.search(full_text))
                has_heading = bool(HEADING_PATTERN.search(full_text))
                
                print(json.dumps({
                    "rank": i+1,
                    "id": hid,
                    "score": round(float(score or 0.0), 3),
                    "contains_phrase": contains_phrase,
                    "negated": is_negated,
                    "meta": is_meta,
                    "heading_bonus": has_heading,
                    "text": text
                }, ensure_ascii=False))
        except Exception as e:
            print(f"⚠️  Request failed for '{qs}': {e}")

    if args.long_ingest:
        # Create a long memory via Memory API and verify chunking on retrieval
        long_text = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 200)
        try:
            add_url = f"{MEM}/memory/add"
            r = requests.post(add_url, json={"content": long_text, "type": "episodic", "tags": ["smoke_long"]}, timeout=10)
            r.raise_for_status()
            rid = (r.json() or {}).get("id")
            print(f"[SMOKE] long-ingest created id={rid}")
        except Exception as e:
            print(f"[SMOKE] long-ingest failed to add memory: {e}")
        try:
            # Probe vector query for a substring
            q("Lorem ipsum dolor sit amet")
            # Try listing memories to inspect payloads (best effort)
            mems = requests.get(f"{MEM}/memories?limit=50").json()
            found = [m for m in mems if "smoke_long" in (m.get("tags") or [])]
            if found:
                # Expect parent_id/chunk_index in vectorized payloads (visible when backend stores and serves via vector)
                print(f"[SMOKE] found {len(found)} long-ingest entries (JSON mode snapshot)")
        except Exception as e:
            print(f"[SMOKE] long-ingest verification failed: {e}")

    if args.probe_only:
        # CI gate: require at least one hit across probes
        exit(0 if total_hits > 0 else 2)

    print("\nOK")
