# Axiom Runability Audit

This audit focuses on the public-safe `axiom-public` tree and the “can a competent dev run it locally?” story.

## Run Surfaces & Setup Modes

- **Docker Compose**
  - `docker-compose.qdrant.yml`: Qdrant + Memory API (primary “working stack” surface)
  - `docker-compose-debug.yml`: Memory API debug container (single service)
  - `docker-compose.override.yml` / `docker-compose.override.example.yml`: port overrides + optional vector adapter service
- **Services**
  - `services/memory/`: Flask Memory API (`pod2_memory_api.py`), Qdrant integration, world-map endpoints, memory manager(s)
  - `services/vector/`: vector adapter implementation + API server entrypoints (optional)
  - `services/cockpit/`: “signal file” status aggregation, degradation flags, rate limiter
- **Core library code**
  - `src/axiom/`: core modules (config, memory, retrieval, resilience, observability, …)
- **Configuration**
  - `configs/.env.template`, `configs/.env.example`
- **Scripts**
  - Smoke/health: `scripts/smoke.sh`, `scripts/smoke_ping_ready.sh`, `scripts/smoke_world_map_endpoints.sh`, `scripts/smoke_vector_query.sh`
  - Qdrant diagnostics: `scripts/qdrant_doctor.sh`
- **Tests**
  - Lots of unit tests under `tests/` (including small “probe endpoint” tests and cockpit/boot contract tests)

### Intended setup modes (inferred)

- **Minimal demo (Docker)**: Qdrant + Memory API via `docker-compose.qdrant.yml`
- **Local dev (Python)**: run Memory API directly, optionally pointed at Qdrant
- **Optional components**:
  - Vector adapter service (legacy/compat path)
  - Cockpit aggregation (mostly file-based signals; useful for testing/contracts)

## Doc Reality Check

### Full Docker (Qdrant + Memory)

- ✅ **Works** (after minor fixes in this audit)
- **Commands**:

```bash
cp configs/.env.example .env
docker compose -f docker-compose.qdrant.yml up --build
curl -fsS http://localhost:8002/ping && curl -fsS http://localhost:8002/readyz
```

### Local dev (Python: Memory API)

- ⚠️ **Works, but only if imports resolve correctly**
- **Notes**:
  - In the public tree, many modules historically import `config`, `memory`, `utils`, etc. as **top-level** packages even though code lives under `src/axiom/`.
  - This audit adds `sitecustomize.py` at repo root to automatically add `src/axiom/` to `sys.path` for local runs/tests (no manual `PYTHONPATH` needed when running from repo root).
- **Commands**:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r services/memory/requirements.txt
MEMORY_API_PORT=8002 python -m pods.memory.pod2_memory_api
curl -fsS http://localhost:8002/health | python -m json.tool
```

### World-map ingestion docs

- ⚠️ **Docs were misleading**: `docs/INGEST_WORLD_MAP.md` / `docs/SCHEMA.md` referenced `ingest_world_map.py`, `tools/*`, `make schema`, and pre-commit/CI wiring that do **not** exist in this public repo.
- ✅ **Fixed**: updated docs to use shipped parsers and the Memory API’s `/world_map/*` endpoints instead of missing CLIs.

### Vector sync docs

- ⚠️ **Docs were misleading**: referenced `pip install -e .[vector]` / extras that don’t exist (no `pyproject.toml`).
- ✅ **Fixed**: updated to install via `services/memory/requirements.txt` and to use `docker compose -f docker-compose.qdrant.yml ...`.

## Core Dependencies & Entry Points

### Python dependencies

- **Memory API**: `services/memory/requirements.txt`
- **Vector adapter**: `services/vector/requirements.txt` and `services/vector/vector_requirements.txt` (note: these diverge)

### Primary entry points

- **Memory API (module)**: `python -m pods.memory.pod2_memory_api`
- **Docker**: `docker compose -f docker-compose.qdrant.yml up --build`

### Issues & Proposed Fixes

- **Missing import scaffolding**
  - **Issue**: many modules/tests referenced `pods.*`, `boot.*`, and `security.*` modules that weren’t present in the public tree.
  - **Fix (done)**:
    - Added `pods/*` compatibility wrappers
    - Added `boot/*` minimal orchestration modules used by tests
    - Added `security/auth.py` (optional bearer-token guard used by Memory/Vector APIs)
    - Added `sitecustomize.py` to make `src/axiom/*` importable as top-level modules (`config`, `memory`, `utils`, …)
- **Compose healthchecks / service naming**
  - **Issue**: `docker-compose.qdrant.yml` had a Qdrant healthcheck using `curl` (not guaranteed in the image) and an invalid Memory healthcheck path.
  - **Fix (done)**: simplified Qdrant service (no curl-based healthcheck) and switched Memory healthcheck to `/ping` + `/readyz`.
  - **Issue**: docs referenced `axiom_qdrant` / `axiom_memory` service names while compose used different names.
  - **Fix (done)**: standardized service names in `docker-compose.qdrant.yml`.
- **Debug compose env mismatch**
  - **Issue**: `docker-compose-debug.yml` set `MEMORY_POD_URL` to a different port than it exposed.
  - **Fix (done)**: align to port 5000 for debug compose.

## Environment & Configuration

### Recommended minimal setup (Docker demo)

- **Copy**:
  - `cp configs/.env.example .env`
- **Must be set for a minimal local demo**:
  - **None** strictly required for basic `/ping`/`/readyz` and non-LLM endpoints.
- **For vector-backed features**:
  - `USE_QDRANT_BACKEND=true`
  - One of:
    - `QDRANT_URL=http://localhost:6333`
    - OR `QDRANT_HOST=axiom_qdrant` + `QDRANT_PORT=6333` (in-compose)
- **Optional auth**:
  - `AXIOM_AUTH_ENABLED=true`
  - `AXIOM_AUTH_TOKEN=...`

### Notes / TODOs

- **`configs/.env.template` is long and partially repetitive** (multiple “template” blocks). It’s usable, but hard to know which variables are truly required for the minimal demo.
- **`configs/.env.example` includes Discord/Cloud placeholders**; they appear non-secret, but could be confusing for local-only users. Consider commenting out Discord/Cloud blocks by default.

## Quick Health Checks

### Shell smoke checks (no pytest required)

```bash
# Memory API probes (when running on :8002)
MEMORY_API_URL=http://localhost:8002 ./scripts/smoke_ping_ready.sh

# World-map endpoint smoke (works even if world_map.json missing; may return 404 for entity)
MEMORY_API_URL=http://localhost:8002 ./scripts/smoke_world_map_endpoints.sh
```

### Pytest unit checks (recommended)

This repo does not currently vendor a dev requirements file; you may need:

```bash
python -m pip install -U pytest
pytest -q tests/test_boot.py tests/test_cockpit_contracts.py tests/test_memory_k8s_health_endpoints.py
```

## Open Issues / TODOs for Maintainer

- **Packaging**: no `pyproject.toml` / installable package story. Decide whether the public tree should support `pip install -e .` or remain “run from repo root”.
- **Docs references to private tooling**: some docs may still reference missing CLIs (`ingest_world_map.py`, `tools/*`). This audit fixed the main offenders but a full sweep is still worth doing.
- **Dependency divergence**: `services/vector/requirements.txt` vs `services/vector/vector_requirements.txt` should be reconciled or clearly documented.
- **Compose pinning**: `qdrant/qdrant:latest` is convenient but brittle; consider pinning a known-good version for runability.

