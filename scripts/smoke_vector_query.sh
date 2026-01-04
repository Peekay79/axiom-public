#!/usr/bin/env bash
set -euo pipefail

MEMORY_API_PORT="${MEMORY_API_PORT:-8002}"
MEMORY_API_URL="${MEMORY_API_URL:-http://localhost:${MEMORY_API_PORT}}"
QUERY="${SMOKE_VECTOR_QUERY_TEXT:-CHAMP algorithm}"
retry_flags=(--retry 30 --retry-connrefused --retry-delay 1 --max-time 3)

have_jq=1
if ! command -v jq >/dev/null 2>&1; then
  have_jq=0
fi

fail() { echo "[SMOKE][vector_query] FAIL: $*" >&2; exit 1; }
pass() { echo "[SMOKE][vector_query] PASS: $*"; exit 0; }

# 1) /health must be 200 and must expose embeddings readiness explicitly
health_json=$(curl -fsS "${retry_flags[@]}" "$MEMORY_API_URL/health" || true)
[[ -n "$health_json" ]] || fail "/health empty"
embeddings_ready="unknown"
if (( have_jq )); then
  echo "$health_json" | jq -e '.status' >/dev/null || fail "/health missing status"
  echo "$health_json" | jq -e 'has("embeddings_ready") and has("embeddings_mode")' >/dev/null || fail "/health missing embeddings_ready/embeddings_mode"
  embeddings_ready=$(echo "$health_json" | jq -r '.embeddings_ready // false')
else
  echo "$health_json"
fi

# 2) /vector/query must be HTTP 200 and must not report embeddings_unconfigured
body=$(SMOKE_VECTOR_QUERY_TEXT="$QUERY" python3 - <<'PY'
import json, os
q = os.environ.get("SMOKE_VECTOR_QUERY_TEXT") or "CHAMP algorithm"
print(json.dumps({"query": q, "top_k": 5}))
PY
)

resp_headers=$(mktemp)
resp_body=$(mktemp)
trap 'rm -f "$resp_headers" "$resp_body"' EXIT

http_code=$(curl -sS "${retry_flags[@]}" -D "$resp_headers" -o "$resp_body" -H 'Content-Type: application/json' -d "$body" -w '%{http_code}' "$MEMORY_API_URL/vector/query" || true)
[[ "$http_code" == "200" ]] || fail "/vector/query expected 200, got $http_code"

raw=$(cat "$resp_body")
[[ -n "$raw" ]] || fail "/vector/query empty body"

# Fail if the classic error leaks through anywhere
if echo "$raw" | grep -qi 'embeddings_unconfigured'; then
  echo "$raw" >&2
  fail "response contains embeddings_unconfigured"
fi

# Also fail if the explicit error header signals embeddings unconfigured
if grep -qi '^X-Axiom-Error-Code: *embeddings_unconfigured' "$resp_headers"; then
  echo "$raw" >&2
  fail "X-Axiom-Error-Code=embeddings_unconfigured"
fi

if (( have_jq )); then
  # Accept either legacy Weaviate-like shape or simple {items:[]}
  if echo "$raw" | jq -e '.data.Get | type=="object"' >/dev/null 2>&1; then
    n=$(echo "$raw" | jq -r '.data.Get | to_entries[0].value | length')
    [[ "$n" =~ ^[0-9]+$ ]] || fail "unable to parse hit count"
    if [[ "$embeddings_ready" == "true" ]]; then
      [[ "$n" -gt 0 ]] || fail "expected non-empty hits for query (embeddings enabled): $QUERY"
    fi
  elif echo "$raw" | jq -e '.items | type=="array"' >/dev/null 2>&1; then
    n=$(echo "$raw" | jq -r '.items | length')
    if [[ "$embeddings_ready" == "true" ]]; then
      [[ "$n" -gt 0 ]] || fail "expected non-empty items for query (embeddings enabled): $QUERY"
    fi
  else
    echo "$raw" | jq . >&2 || true
    fail "unrecognized /vector/query response shape"
  fi
fi

pass "health + vector query ok"

