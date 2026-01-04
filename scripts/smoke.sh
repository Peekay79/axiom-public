#!/usr/bin/env bash
set -euo pipefail

# Simple wrapper for the Python smoke test
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT="${SCRIPT_DIR}/.."

exec python3 "${REPO_ROOT}/scripts/smoke_test.py" "$@"
