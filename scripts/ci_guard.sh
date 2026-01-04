#!/usr/bin/env bash
set -euo pipefail

# Contract guard: prevent legacy vector API drift and ensure adapter shim flag exists.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

pass=true

# Legacy/forbidden patterns outside allowed shim, scoped to vector code
declare -a patterns=("/v1/objects" "weaviate" "http://188.166.")
allow_path="pods/vector/vector_adapter.py"

# Restrict search to vector modules to avoid docs/tests noise
SEARCH_DIRS=("vector" "pods/vector")

for pat in "${patterns[@]}"; do
  for dir in "${SEARCH_DIRS[@]}"; do
    # Only code files; exclude tests, logs, caches
    grep -RIn --binary-files=without-match \
      --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__ \
      --exclude-dir=logs --exclude-dir=tests \
      --include='*.py' --include='*.yml' --include='*.yaml' --include='*.sh' \
      -- "$pat" "$dir" | grep -v "$allow_path" > /tmp/guard_hits.txt || true
    if [[ -s /tmp/guard_hits.txt ]]; then
      echo "FAIL: Forbidden pattern '$pat' found outside $allow_path in $dir:" >&2
      cat /tmp/guard_hits.txt >&2
      pass=false
    fi
  done
done

# Ensure adapter /health still reports adapter_v1_shim flag (no external deps)
if ! grep -RIn --binary-files=without-match "adapter_v1_shim" "$allow_path" >/dev/null 2>&1; then
  echo "FAIL: adapter_v1_shim flag missing from $allow_path /health handler" >&2
  pass=false
fi

if $pass; then
  echo "PASS: Contract guard OK"
  exit 0
else
  exit 1
fi

# Qdrant resolution guard for Memory pod: forbid direct env parsing outside resolver
if grep -R --line-number -E 'QDRANT_HOST|QDRANT_PORT' pods/memory | grep -v resolved_mode.py; then
  echo "❌ Do not resolve QDRANT host/port in pods/memory. Use config/resolved_mode.py only." >&2
  exit 1
fi

