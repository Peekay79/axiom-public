# Getting Started with Axiom Public

Axiom is a research-grade cognitive architecture designed to support persistent identity, structured memory, belief tracking, and autonomous reasoning across time.

This guide explains how to:

- run Axiom locally
- start the core services (“pods”)
- configure memory + vector recall
- verify the system is working

If you get stuck, open an issue — or email `kurtbannister79@gmail.com` with subject line `AXIOM LICENSING`.

- [Prerequisites](#1-prerequisites)
- [System overview](#2-system-overview)
- [Repository layout (brief)](#3-repository-layout-brief)
- [Quick Start — Docker + Qdrant](#4-quick-start--docker--qdrant)
- [Quick Start — Local dev (no vector required)](#5-quick-start--local-dev-no-vector-required)
- [Enable semantic recall (Qdrant)](#6-enable-semantic-recall-qdrant)
- [Basic health & sanity checks](#7-basic-health--sanity-checks)
- [Optional: Protecting your Memory API (bearer token)](#8-optional-protecting-your-memory-api-bearer-token)
- [Optional: Cockpit status server](#9-optional-cockpit-status-server)
- [Next steps](#10-next-steps)

## 1. Prerequisites

- **Supported OS**: Linux or macOS.
- **Python**: **3.10+** (service containers use Python 3.10; local dev should use 3.10 if possible).
- **Optional**: Docker + Docker Compose v2 (`docker compose`) for the container route.
- **Expected familiarity**: basic Git, Python venvs, and reading `.env` files.

## 2. System overview

Axiom Public’s runnable “core” is the **Memory API**, optionally backed by **Qdrant** for semantic recall.

- **Memory API (“Memory pod”)**: episodic/semantic memory + journaling + belief surfaces, served over HTTP.
- **Vector backend (Qdrant)**: optional; enables semantic recall and vector queries.
- **Cockpit** (optional): aggregates “signal files” into a status endpoint for observability.

The system is designed to:

- run in **fallback** mode (no vector DB)
- or switch to **Qdrant-backed** semantic recall when available

## 3. Repository layout (brief)

- `services/`: runnable services (Memory, Vector, Cockpit)
- `src/axiom/`: core library modules (config/memory/retrieval/etc.)
- `configs/`: `.env` templates/examples
- `scripts/`: smoke checks and operational helpers
- `docs/`: deeper design and subsystem docs

## 4. Quick Start — Docker + Qdrant

This is the easiest path to a working stack (**Qdrant + Memory API**).

```bash
git clone https://github.com/Peekay79/axiom-public.git
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

Optional: run the bundled smoke script (brings up services in the background):

```bash
./scripts/smoke-memory.sh
```

## 5. Quick Start — Local dev (no vector required)

This is the fastest way to get the Memory API running locally (no Docker).

```bash
git clone https://github.com/Peekay79/axiom-public.git
cd axiom-public

python3 -m venv .venv
source .venv/bin/activate

pip install -r services/memory/requirements.txt

# Run the Memory API on port 8002 (recommended default for this repo)
MEMORY_API_PORT=8002 python -m pods.memory.pod2_memory_api
```

Check health:

```bash
curl -fsS http://localhost:8002/ping
curl -fsS http://localhost:8002/readyz
curl -fsS http://localhost:8002/health | python -m json.tool
```

You now have a local Memory API with:

- fallback memory behavior (even without Qdrant)
- journaling and belief endpoints
- world-map endpoints (if you provide a `world_map.json`)

## 6. Enable semantic recall (Qdrant)

Start Qdrant locally (Docker):

```bash
docker compose -f docker-compose.qdrant.yml up -d axiom_qdrant
```

Then configure Axiom (in `.env` at repo root):

```bash
cp configs/.env.example .env
$EDITOR .env
```

Minimum recommended values (self-hosted Qdrant):

```bash
USE_QDRANT_BACKEND=true
QDRANT_URL=http://127.0.0.1:6333
VECTOR_PATH=qdrant
```

Restart the Memory API (so it picks up `.env` changes):

```bash
MEMORY_API_PORT=8002 python -m pods.memory.pod2_memory_api
```

Verify Qdrant is reachable:

```bash
curl -fsS "$QDRANT_URL/health"
curl -fsS "$QDRANT_URL/collections"
```

## 7. Basic health & sanity checks

```bash
curl -fsS http://localhost:8002/ping
curl -fsS http://localhost:8002/readyz
curl -fsS http://localhost:8002/health | python -m json.tool
```

Optional world-map sanity (example data):

```bash
cp examples/world_map.example.json world_map.json
curl -fsS -X POST http://localhost:8002/world_map/reload | python -m json.tool
curl -fsS http://localhost:8002/world_map/entity/example_person | python -m json.tool
```

## 8. Optional: Protecting your Memory API (bearer token)

The public tree includes an optional bearer-token guard for HTTP endpoints.

- **Off by default**
- For any serious internet-facing deployment, also put this behind HTTPS / a reverse proxy (out of scope here)

```bash
export AXIOM_AUTH_ENABLED=true
export AXIOM_AUTH_TOKEN='replace-with-a-strong-random-token'
```

Example request:

```bash
curl -fsS http://localhost:8002/health \
  -H "Authorization: Bearer ${AXIOM_AUTH_TOKEN}"
```

## 9. Optional: Cockpit status server

Cockpit is a tiny status/metrics server that reads “signal files” from `COCKPIT_SIGNAL_DIR` (default `axiom_boot/`).

```bash
python3 -m services.cockpit.cockpit_server
curl -fsS http://localhost:8088/status/cockpit | python -m json.tool
```

## 10. Next steps

- `AXIOM_RUNABILITY_AUDIT.md`: run surfaces, known gaps, and quick checks
- `docs/INGEST_WORLD_MAP.md`: using world-map endpoints in the public tree
- `docs/HYBRID_RETRIEVAL.md`: retrieval design notes

