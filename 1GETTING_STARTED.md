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
- [Quick Start — Local Python Memory API (no Docker)](#5-quick-start--local-python-memory-api-no-docker)
- [Basic health & sanity checks](#6-basic-health--sanity-checks)
- [Optional: Protecting your Memory API (bearer token)](#7-optional-protecting-your-memory-api-bearer-token)
- [Optional: Cockpit status server](#8-optional-cockpit-status-server)
- [Next steps](#9-next-steps)
- [Why two dependency profiles?](#10-why-two-dependency-profiles)

## 1. Prerequisites

- **Supported OS**: Linux or macOS.
- **Python**: **3.10+** (service containers use Python 3.10; local dev should use 3.10 if possible).
- **Optional**: Docker + Docker Compose v2 (`docker compose`) for the container route.
- **Expected familiarity**: basic Git, Python venvs, and reading `.env` files.

## 2. System overview

In the full (private) Axiom system, you can think of “pods” like an LLM pod, a memory pod, and a vector backend working together.

In **axiom-public**, the runnable “core” you can bring up from this repo today is the **Memory API**, optionally backed by **Qdrant** for semantic recall.

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
cp configs/.env.example .env
docker compose -f docker-compose.qdrant.yml up --build

curl -fsS http://localhost:8002/ping
curl -fsS http://localhost:8002/readyz
```

Optional: run the bundled smoke script (brings up services in the background):

```bash
./scripts/smoke-memory.sh
```

## 5. Quick Start — Local Python Memory API (no Docker)

This runs the Memory API directly on your machine (no Docker).

```bash
git clone https://github.com/Peekay79/axiom-public.git
cd axiom-public

python3 -m venv .venv
source .venv/bin/activate

pip install -r services/memory/requirements-core.txt

MEMORY_API_PORT=8002 python -m pods.memory.pod2_memory_api

curl -fsS http://localhost:8002/ping
curl -fsS http://localhost:8002/readyz
```

Runs Axiom Memory API in **fallback mode** *(no vector DB, no embeddings, no Rust required)*.

This runs **Axiom Memory API in fallback mode**:

- no vector DB required
- no embeddings / HuggingFace stack
- **no Rust toolchain required**

### Optional: Vector / Embeddings mode (advanced)

If you want semantic recall + embedding adapters, install the vector profile:

```bash
pip install -r services/memory/requirements-vector.txt
```

Notes:

- **May require a Rust toolchain** on some systems (commonly macOS / ARM) due to `tokenizers`
- Recommended if you’re using **Qdrant** or want **semantic recall**
- Safe to ignore when experimenting

Core vs Vector:

- **Core** = cognition + journaling + beliefs
- **Vector** = semantic recall + embeddings + rerank

## 6. Basic health & sanity checks

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

## 7. Optional: Protecting your Memory API (bearer token)

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

## 8. Optional: Cockpit status server

Cockpit is a tiny status/metrics server that reads “signal files” from `COCKPIT_SIGNAL_DIR` (default `axiom_boot/`).

```bash
python3 -m services.cockpit.cockpit_server
curl -fsS http://localhost:8088/status/cockpit | python -m json.tool
```

## 9. Next steps

- `AXIOM_RUNABILITY_AUDIT.md`: run surfaces, known gaps, and quick checks
- `docs/INGEST_WORLD_MAP.md`: using world-map endpoints in the public tree
- `docs/HYBRID_RETRIEVAL.md`: retrieval design notes

## 10. Why two dependency profiles?

Some Python packages used for local embeddings (notably `tokenizers` / `transformers`) can require a **Rust toolchain** to compile on certain platforms.

To keep first-run setup friendly and reliable:

- **`requirements-core.txt`**: runs the Memory API in fallback mode (no Rust / no HuggingFace stack)
- **`requirements-vector.txt`**: keeps full vector + embedding functionality available, but opt-in

