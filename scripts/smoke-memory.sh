#!/usr/bin/env bash
set -euo pipefail

# Bring up Qdrant + Memory API (local dev)
docker compose -f docker-compose.qdrant.yml up -d --build axiom_qdrant axiom_memory

echo "→ Waiting 2s for startup..."
sleep 2
retry_flags=(--retry 30 --retry-connrefused --retry-delay 1 --max-time 3)

echo "→ Health:"
curl -fsS "${retry_flags[@]}" "http://localhost:${MEMORY_API_PORT:-8002}/ping" >/dev/null || true
curl -fsS "${retry_flags[@]}" "http://localhost:${MEMORY_API_PORT:-8002}/health" || true
echo

echo "→ Add a test memory (if route is enabled):"
curl -sS "${retry_flags[@]}" -X POST "http://localhost:${MEMORY_API_PORT:-8002}/memory/add" \
  -H 'Content-Type: application/json' \
  -d '{"text":"ping from memory-api override","user_id":"test","source":"api"}' || true
echo