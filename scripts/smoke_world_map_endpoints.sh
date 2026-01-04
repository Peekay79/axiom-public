#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${MEMORY_API_URL:-http://localhost:5000}"
ENTITY_ID="${WORLD_MAP_SMOKE_ENTITY_ID:-example_person}"
retry_flags=(--retry 30 --retry-connrefused --retry-delay 1 --max-time 3)

_tmpfile=""
cleanup() {
  if [[ -n "${_tmpfile}" && -f "${_tmpfile}" ]]; then
    rm -f "${_tmpfile}" || true
  fi
}
trap cleanup EXIT

_tmpfile="$(mktemp)"

require_curl() {
  command -v curl >/dev/null 2>&1 || {
    echo "curl is required" >&2
    exit 2
  }
}

curl_status() {
  local url="$1"
  : >"${_tmpfile}"
  local status
  status="$(curl -sS "${retry_flags[@]}" -o "${_tmpfile}" -w "%{http_code}" "${url}")"
  echo "${status}"
}

print_health_world_map_fields() {
  local url="$1"
  local status
  status="$(curl -fsS "${retry_flags[@]}" "${url}")"
  python3 - <<'PY'
import json,sys
try:
  d=json.loads(sys.stdin.read())
except Exception as e:
  print("health JSON parse failed:", type(e).__name__, file=sys.stderr)
  raise
for k in ["world_map_loaded","world_map_path","world_map_entities_count","world_map_relationships_count"]:
  print(f"{k}={d.get(k)!r}")
PY
}

main() {
  require_curl

  echo "== /health (world_map_* fields) =="
  curl -fsS "${retry_flags[@]}" "${BASE_URL}/health" | python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
for k in ["world_map_loaded","world_map_path","world_map_entities_count","world_map_relationships_count"]:
  print(f"{k}={d.get(k)!r}")
PY

  echo
  echo "== /world_map/entity/${ENTITY_ID} =="
  local st
  st="$(curl_status "${BASE_URL}/world_map/entity/${ENTITY_ID}")"
  if [[ "${st}" == "200" || "${st}" == "404" ]]; then
    echo "status=${st}"
    cat "${_tmpfile}"
    echo
  else
    echo "unexpected status for entity: ${st}" >&2
    cat "${_tmpfile}" >&2 || true
    exit 1
  fi

  echo
  echo "== /world_map/relationships?entity_id=${ENTITY_ID} =="
  st="$(curl_status "${BASE_URL}/world_map/relationships?entity_id=${ENTITY_ID}")"
  if [[ "${st}" == "200" ]]; then
    echo "status=${st}"
    cat "${_tmpfile}"
    echo
  else
    echo "unexpected status for relationships: ${st}" >&2
    cat "${_tmpfile}" >&2 || true
    exit 1
  fi

  echo
  echo "== /world_map/profile/${ENTITY_ID} =="
  st="$(curl_status "${BASE_URL}/world_map/profile/${ENTITY_ID}")"
  if [[ "${st}" == "200" || "${st}" == "404" ]]; then
    echo "status=${st}"
    cat "${_tmpfile}"
    echo
  else
    echo "unexpected status for profile: ${st}" >&2
    cat "${_tmpfile}" >&2 || true
    exit 1
  fi

  echo "OK"
}

main "$@"
