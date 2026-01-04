#!/usr/bin/env bash
set -euo pipefail

QDRANT_URL="${QDRANT_URL:-}"
[[ -n "$QDRANT_URL" ]] || { echo "[DOCTOR] Set QDRANT_URL (e.g., http://host:8011)" >&2; exit 1; }

have_jq=1
if ! command -v jq >/dev/null 2>&1; then
  have_jq=0
fi

fail() { echo "[DOCTOR] FAIL: $*" >&2; exit 1; }
pass() { echo "[DOCTOR] PASS: $*"; exit 0; }

# Basic version (root)
root=$(curl -fsS "$QDRANT_URL" || true)
[[ -n "$root" ]] || fail "root empty"
if (( have_jq )); then
  echo "$root" | jq -r '.version // .result.version // empty' || true
else
  echo "$root"
fi

# Collections list
cols=$(curl -fsS "$QDRANT_URL/collections" || true)
[[ -n "$cols" ]] || fail "/collections empty"
if (( have_jq )); then
  echo "$cols" | jq -e '.result.collections | map(.name) | index("axiom_memories")' >/dev/null || fail "axiom_memories missing"
  echo "$cols" | jq -e '.result.collections | map(.name) | index("axiom_beliefs")' >/dev/null || fail "axiom_beliefs missing"
fi

# Collection config
mem=$(curl -fsS "$QDRANT_URL/collections/axiom_memories" || true)
[[ -n "$mem" ]] || fail "/collections/axiom_memories empty"
if (( have_jq )); then
  echo "$mem" | jq -e '.result.config.params.vectors.size == 384' >/dev/null || fail "vector size != 384"
  echo "$mem" | jq -e '.result.config.params.vectors.distance == "Cosine"' >/dev/null || fail "distance != Cosine"
fi

# Count points with tags any (ok if zero)
read -r -d '' COUNT_BODY <<'JSON'
{
  "filter": {
    "must": [
      {"key":"tags","match": {"any": ["world_map_entity","world_map_event"]}}
    ]
  }
}
JSON

cnt=$(curl -fsS -H 'Content-Type: application/json' -d "$COUNT_BODY" "$QDRANT_URL/collections/axiom_memories/points/count" || true)
if (( have_jq )); then
  echo "$cnt" | jq -e '.result.count >= 0' >/dev/null || fail "count parse error"
  echo "[DOCTOR] count: $(echo "$cnt" | jq -r '.result.count')"
else
  echo "$cnt"
fi

pass "qdrant collections ok"

