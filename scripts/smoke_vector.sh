#!/usr/bin/env bash
set -euo pipefail

MEMORY_API_PORT="${MEMORY_API_PORT:-8002}"
MEM="http://localhost:${MEMORY_API_PORT}"
retry_flags=(--retry 30 --retry-connrefused --retry-delay 1 --max-time 3)

have_jq=1
if ! command -v jq >/dev/null 2>&1; then
  have_jq=0
fi

fail() { echo "[SMOKE][vector] FAIL: $*" >&2; exit 1; }
pass() { echo "[SMOKE][vector] PASS: $*"; exit 0; }

# 1) Health
health_json=$(curl -fsS "${retry_flags[@]}" "$MEM/health" || true)
[[ -n "$health_json" ]] || fail "/health empty"
if (( have_jq )); then
  status=$(echo "$health_json" | jq -r '.status // .ok // empty')
  [[ "$status" == "ok" || "$status" == "true" ]] || fail "/health status not ok"
  echo "$health_json" | jq 'has("vector_ready")' >/dev/null || fail "/health missing vector_ready"
else
  echo "$health_json"
fi

# 2) Basic vector query
body='{"query":"ExamplePerson Axiom","top_k":3}'
resp=$(curl -fsS "${retry_flags[@]}" -H 'Content-Type: application/json' -d "$body" "$MEM/vector/query" || true)
[[ -n "$resp" ]] || fail "/vector/query empty"
if (( have_jq )); then
  echo "$resp" | jq -e '.data.Get.axiom_memories' >/dev/null || fail "missing .data.Get.axiom_memories"
else
  echo "$resp"
fi

# 3) Filtered query (tags.any)
body='{"query":"ExamplePerson Axiom","top_k":3,"filter":{"must":[{"key":"tags","match":{"any":["world_map_entity","world_map_event"]}}]}}'
resp2=$(curl -fsS "${retry_flags[@]}" -H 'Content-Type: application/json' -d "$body" "$MEM/vector/query" || true)
[[ -n "$resp2" ]] || fail "filtered /vector/query empty"
if (( have_jq )); then
  echo "$resp2" | jq -e '.data.Get.axiom_memories | length >= 0' >/dev/null || fail "filtered path parse error"
fi

# 4) Negative filter sanity
body='{"query":"ExamplePerson Axiom","top_k":3,"filter":{"must":[{"key":"tags","match":{"any":["__no_such_tag__"]}}]}}'
resp3=$(curl -fsS "${retry_flags[@]}" -H 'Content-Type: application/json' -d "$body" "$MEM/vector/query" || true)
[[ -n "$resp3" ]] || fail "negative /vector/query empty"
if (( have_jq )); then
  echo "$resp3" | jq -e '.data.Get.axiom_memories | length >= 0' >/dev/null || fail "negative filter parse error"
fi

# 5) Optional canary status
if curl -fsS "${retry_flags[@]}" "$MEM/canary/status" >/dev/null 2>&1; then
  canary=$(curl -fsS "${retry_flags[@]}" "$MEM/canary/status" || true)
  echo "[SMOKE][vector] canary: $canary"
fi

# 6) Optional metrics snapshot
metrics=$(curl -fsS "${retry_flags[@]}" "$MEM/metrics" || true)
if (( have_jq )); then
  echo "$metrics" | jq -e 'has("vector_metrics")' >/dev/null && echo "[SMOKE][vector] metrics: $(echo "$metrics" | jq -c '.vector_metrics')"
else
  echo "$metrics"
fi

pass "vector api ok"

