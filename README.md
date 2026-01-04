## Axiom (public-safe build)

This directory (`axiom-public/`) is a **copy-and-sanitise** public distribution of the private Axiom repo. It is intended for **local development and demos** only.

Axiom is a modular memory + recall stack (Flask Memory API, optional Qdrant vector recall) plus an optional agent layer (CHAMP decisioning, reflection/journaling, wonder exploration, and graph hooks).

## Docs

- [Systems overview (services + agent layer)](docs/2SYSTEMS_OVERVIEW.md)
- [System architecture (services)](docs/axiom_architecture_map.md)

## Show and tell

If you build something with Axiom — even a small experiment — I’d love to see it.
Open a GitHub issue with a short description, screenshots/logs if useful, and what you’re trying to achieve.
Bugs and rough edges are expected; helpful reports and PRs are very welcome.

- `SHOW: <what you built>`
- `QUESTION: <topic>`
- `BUG: <what broke>`

## Quickstart (dev)

On Homebrew Python (macOS), PEP 668 marks the system environment as externally managed; use a virtual environment for installs.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
python -c "import axiom_agent"
```

## License & Use

Licensed under the **PolyForm Noncommercial License 1.0.0** (see [LICENSE](./LICENSE)).

Commercial use is not permitted under the default license.

Nothing in this README grants rights beyond those in the LICENSE.

### Commercial Use & Partnerships

For commercial inquiries, **open a GitHub issue titled `AXIOM LICENSING`**.

### Ethical Use

If the LICENSE includes an Ethical Use Notice, it applies as written there. See LICENSE for the exact terms.

### Quick start (local-only)

For a full, friendly walkthrough, see `./1GETTING_STARTED.md`.

- **Install**:
  - `python -m venv .venv && . .venv/bin/activate`
  - `pip install -r services/memory/requirements-core.txt`
- **Run the Memory API (dev)**:
  - `MEMORY_API_PORT=8002 MEMORY_POD_URL=http://localhost:8002 python -m pods.memory.pod2_memory_api`

Runs Axiom Memory API in **fallback mode** *(no vector DB, no embeddings, no Rust required)*.

Optional (advanced): enable vector + embeddings:

- `pip install -r services/memory/requirements-vector.txt`

### Quick start (Docker: Qdrant + Memory)

- **Copy env template**:
  - `cp configs/.env.example .env`
- **Run**:
  - `docker compose -f docker-compose.qdrant.yml up --build`
- **Health**:
  - `curl -fsS http://localhost:8002/ping && curl -fsS http://localhost:8002/readyz`

### Configuration

- **Environment templates** live in `configs/`.
- **Do not commit secrets**. Copy `configs/.env.example` to `.env` locally and edit as needed.

### Example data

- **World map example**: `examples/world_map.example.json`
  - Example data only — replace with your own private configuration.

### Layout

- **Core library**: `src/axiom/`
- **Services**: `services/` (memory/vector/cockpit)
- **Docs**: `docs/`
- **Scripts**: `scripts/`
- **Tests**: `tests/`

## GitHub Topics (recommended)

For better discoverability, maintainers should set repository topics in the **GitHub UI** (Settings → Topics): `qdrant`, `rag`, `memory`, `vector-database`, `retrieval`, `agents`, `llm`, `flask`, `embeddings`, `journaling`, `decision-engine`, `cognitive-architecture`.

## Demo (no install)

Run:

```bash
./apps/run_demo.sh
```

This uses `PYTHONPATH=src` and does not require pip/venv; it is intended as a quick sanity check.

Optional rollback demo (expected non-zero):

```bash
AXIOM_DEMO_FORCE_FAIL=1 ./apps/run_demo.sh
```

## Search keywords

- qdrant
- vector database
- embeddings
- retrieval
- RAG
- memory
- LLM agents
- journaling
- decision engine
- Flask
- semantic search
- graph

