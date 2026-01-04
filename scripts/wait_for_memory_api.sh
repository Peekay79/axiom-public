#!/usr/bin/env bash
set -euo pipefail

MEMORY_API_URL="${MEMORY_API_URL:-http://localhost:8002}"
MEMORY_API_URL="${MEMORY_API_URL%/}"

retry_flags=(--retry 30 --retry-connrefused --retry-delay 1 --max-time 3)

log() {
  echo "[wait_for_memory_api] $*" >&2
}

log "Waiting for Memory API probes at: ${MEMORY_API_URL}"

log "Probing /ping (must be immediate)"
curl -fsS "${retry_flags[@]}" "${MEMORY_API_URL}/ping" >/dev/null
log "✅ /ping OK"

log "Probing /readyz (startup readiness)"
curl -fsS "${retry_flags[@]}" "${MEMORY_API_URL}/readyz" >/dev/null
log "✅ /readyz OK"

log "Memory API is ready."
