## Axiom (public-safe build)

This directory (`axiom-public/`) is a **copy-and-sanitize** public distribution of the private Axiom repo. It is intended for **local development and demos** only.

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

Licensed under the **PolyForm Noncommercial License 1.0.0**. See [LICENSE](./LICENSE) for terms.

Axiom is source-available and intended for personal, academic, research, and other noncommercial use. Commercial use is not permitted under the default license.

Examples of permitted use (non-exhaustive):

- ✅ Run and modify Axiom for personal projects, learning, and experimentation
- ✅ Use Axiom in academic and research settings
- ✅ Use it internally for noncommercial prototypes and exploration

Examples of commercial use not permitted under the default license (non-exhaustive):

- ❌ Offer this software or derivative works as a paid product or service
- ❌ Use it within a revenue-generating platform or workflow
- ❌ Deploy it in support of commercial business operations
- ❌ Use it in exchange for money, equity, or other commercial benefit

### Commercial Use & Partnerships

Commercial rights may be available via separate licensing for aligned teams.

To discuss commercial use, **open a GitHub issue titled “AXIOM LICENSING”**.

### Ethical Use

The license includes an “Ethical Use Notice” that prohibits using Axiom to develop or deploy systems whose primary purpose is:

- physical harm,
- mass surveillance or repression, or
- violation of applicable law or fundamental human rights.

See [LICENSE](./LICENSE) for full terms.

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

