#!/usr/bin/env bash
# [discord-fixes] Provider-aware healthcheck script
set -euo pipefail

# [discord-fixes] Use provider-aware logic instead of LLM_API_URL as universal base
LLM_PROVIDER="${LLM_PROVIDER:-openai_compatible}"

if [[ "$LLM_PROVIDER" == "ollama" ]]; then
  # For Ollama, use OLLAMA_URL and check /api/tags
  base="${OLLAMA_URL:-}"
  if [[ -z "$base" ]]; then
    echo "ERROR: LLM_PROVIDER=ollama but OLLAMA_URL is not set"
    exit 1
  fi
  endpoint="/api/tags"
else
  # For openai/openai_compatible, use LLM_API_BASE and check /v1/models
  base="${LLM_API_BASE:-}"
  if [[ -z "$base" ]]; then
    echo "ERROR: LLM_PROVIDER=${LLM_PROVIDER} but LLM_API_BASE is not set"
    exit 1
  fi
  endpoint="/v1/models"
fi

echo "→ Health check LLM @ ${base}${endpoint}"
if curl -sf "${base}${endpoint}" >/dev/null; then
  echo "✅ LLM health check passed"
  exit 0
else
  echo "❌ LLM health check failed"
  exit 1
fi