# Getting Started with Axiom Public

Axiom Public is a **public-safe** distribution of Axiom intended for **local development and demos**. This guide gets you to a working **Axiom Memory API** quickly, either with **Docker (recommended)** or by running the service directly with **Python**.

- [Prerequisites](#1-prerequisites)
- [Repository layout (brief)](#2-repository-layout-brief)
- [Quick Start (Docker + Qdrant)](#3-quick-start-docker--qdrant)
- [Quick Start (Local Python Memory API)](#4-quick-start-local-python-memory-api)
- [Basic health & sanity checks](#5-basic-health--sanity-checks)
- [Optional: Protecting your Memory API (bearer token)](#6-optional-protecting-your-memory-api-bearer-token)
- [Optional: Cockpit status server](#7-optional-cockpit-status-server)
- [Next steps](#8-next-steps)

## 1. Prerequisites

- **Supported OS**: Linux or macOS.
- **Python**: **3.10** (matches the service Dockerfiles and the expected runtime).
- **Tools**:
  - `git`
  - `python`/`python3` with `venv`
  - Optional (Docker route): Docker + Docker Compose v2 (`docker compose`)

## 2. Repository layout (brief)

- `services/`: runnable services (Memory, Vector, Cockpit)
- `src/axiom/`: core library modules (config/memory/retrieval/etc.)
- `configs/`: `.env` templates/examples
- `scripts/`: smoke checks and operational helpers
- `docs/`: deeper design and subsystem docs

## 3. Quick Start (Docker + Qdrant)

This is the simplest path to a working stack: **Qdrant + Memory API**.

```bash
git clone https://github.com/<ORG_OR_USER>/axiom-public.git
cd axiom-public

# Local env file (safe defaults). Do NOT commit your .env.
cp configs/.env.example .env

# No mandatory edits are required for a first run.

docker compose -f docker-compose.qdrant.yml up --build
```

In another terminal:

```bash
curl -fsS http://localhost:8002/ping
curl -fsS http://localhost:8002/readyz
```

Optional: run the bundled smoke script (brings up services if needed):

```bash
./scripts/smoke-memory.sh
```

## 4. Quick Start (Local Python Memory API)

This runs the Memory API directly on your machine (no Docker).

```bash
git clone https://github.com/<ORG_OR_USER>/axiom-public.git
cd axiom-public

python -m venv .venv
. .venv/bin/activate

pip install -r services/memory/requirements.txt

# Run Memory API on port 8002
MEMORY_API_PORT=8002 python -m pods.memory.pod2_memory_api
```

Then:

```bash
curl -fsS http://localhost:8002/ping
curl -fsS http://localhost:8002/readyz
```

## 5. Basic health & sanity checks

### Core probes

```bash
curl -fsS http://localhost:8002/ping
curl -fsS http://localhost:8002/readyz
curl -fsS http://localhost:8002/health | python -m json.tool
```

### World map (optional demo data)

The Memory API auto-loads `world_map.json` if present. You can start with the example:

```bash
cp examples/world_map.example.json world_map.json

# reload without restarting the server
curl -fsS -X POST http://localhost:8002/world_map/reload | python -m json.tool
curl -fsS http://localhost:8002/world_map/entity/example_person | python -m json.tool
```

## 6. Optional: Protecting your Memory API (bearer token)

The public tree includes an **optional** bearer-token guard for HTTP endpoints.

- **Off by default**
- Useful for local demos on shared networks
- For any serious deployment, you should also put it behind HTTPS / a reverse proxy (out of scope here)

In your environment:

```bash
export AXIOM_AUTH_ENABLED=true
export AXIOM_AUTH_TOKEN='replace-with-a-strong-random-token'
```

Example request:

```bash
curl -fsS http://localhost:8002/health \
  -H "Authorization: Bearer ${AXIOM_AUTH_TOKEN}"
```

## 7. Optional: Cockpit status server

Cockpit is a tiny status/metrics server that reads “signal files” from `COCKPIT_SIGNAL_DIR` (default `axiom_boot/`).

```bash
# In the same venv as the Memory API
python -m services.cockpit.cockpit_server

# Then:
curl -fsS http://localhost:8088/status/cockpit | python -m json.tool
```

## 8. Next steps

- `AXIOM_RUNABILITY_AUDIT.md`: run surfaces, known gaps, and quick checks
- `docs/INGEST_WORLD_MAP.md`: how to use world-map endpoints in the public tree
- `docs/HYBRID_RETRIEVAL.md`: retrieval design notes (if you’re exploring recall/search behavior)

