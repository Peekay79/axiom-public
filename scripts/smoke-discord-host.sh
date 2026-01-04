#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env.discord"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.discord.example -> .env.discord and fill DISCORD_TOKEN."
  exit 1
fi

set -a; source "$ENV_FILE"; set +a
retry_flags=(--retry 30 --retry-connrefused --retry-delay 1 --max-time 3)

# [discord-fixes] Memory /health check against MEMORY_API_URL || MEMORY_POD_URL
MEMORY_URL="${MEMORY_API_URL:-${MEMORY_POD_URL:-}}"
if [[ -n "$MEMORY_URL" ]]; then
  echo "→ Probing Memory API @ ${MEMORY_URL}"
  curl -fsS "${retry_flags[@]}" "${MEMORY_URL}/ping" >/dev/null || { echo; echo "Memory API /ping not reachable"; exit 1; }
  curl -fsS "${retry_flags[@]}" "${MEMORY_URL}/health" | head -c 200 || { echo; echo "Memory API not reachable"; exit 1; }
  echo; echo
else
  echo "ERROR: Neither MEMORY_API_URL nor MEMORY_POD_URL is set"
  exit 1
fi

# [discord-fixes] Provider-aware LLM readiness check
LLM_PROVIDER="${LLM_PROVIDER:-openai_compatible}"
if [[ "$LLM_PROVIDER" == "ollama" ]]; then
  if [[ -n "${OLLAMA_URL:-}" ]]; then
    echo "→ Probing LLM (Ollama) @ ${OLLAMA_URL}"
    if ! curl -fsS "${retry_flags[@]}" "${OLLAMA_URL}/api/tags" | head -c 200 >/dev/null; then
      echo "LLM not reachable (this can be OK if you're not using local LLM)."
    else
      echo "LLM OK."
    fi
  else
    echo "WARNING: LLM_PROVIDER=ollama but OLLAMA_URL not set"
  fi
else
  # openai/openai_compatible
  if [[ -n "${LLM_API_BASE:-}" ]]; then
    echo "→ Probing LLM (OpenAI-compatible) @ ${LLM_API_BASE}"
    if ! curl -fsS "${retry_flags[@]}" "${LLM_API_BASE}/v1/models" | head -c 200 >/dev/null; then
      echo "LLM not reachable (this can be OK if you're not using local LLM)."
    else
      echo "LLM OK."
    fi
  else
    echo "WARNING: LLM_PROVIDER=${LLM_PROVIDER} but LLM_API_BASE not set"
  fi
fi
echo
echo "✅ Smoke checks finished."