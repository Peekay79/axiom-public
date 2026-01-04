#!/usr/bin/env bash
set -euo pipefail

MEMORY_API_URL="${MEMORY_API_URL:-http://localhost:8002}"
MEMORY_API_URL="${MEMORY_API_URL%/}"

retry_flags=(--retry 30 --retry-connrefused --retry-delay 1 --max-time 3)

echo "[SMOKE][ping_ready] base=${MEMORY_API_URL}"

echo "[SMOKE][ping_ready] GET /ping"
curl -fsS "${retry_flags[@]}" "${MEMORY_API_URL}/ping" >/dev/null
echo "[SMOKE][ping_ready] ✅ /ping OK"

echo "[SMOKE][ping_ready] GET /readyz"
curl -fsS "${retry_flags[@]}" "${MEMORY_API_URL}/readyz" >/dev/null
echo "[SMOKE][ping_ready] ✅ /readyz OK"

echo "[SMOKE][ping_ready] done"
