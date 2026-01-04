# Axiom Public — System Architecture

This document explains how the **public Axiom** repository is structured and how its subsystems relate, based strictly on code and runnable surfaces present in this repo.

## What this repo is / is not

- **This repo provides**
  - A **Memory API** service (Flask) with a JSON-backed fallback store and optional Qdrant integration.
  - Optional **Vector recall** components (Qdrant backend; optional Vector Adapter + embedding service).
  - A lightweight **Cockpit** status model (file-based signals + optional HTTP status server) to report readiness/degradation signals.

- **This repo does not provide**
  - An end-to-end “agent loop” or bundled LLM runtime. Any LLM/agent orchestration is **external by design**; this repo exposes service-layer primitives intended to be called by such a frontend.

## Runtime Components

| Component | Code path | Purpose | When it runs |
|---|---|---|---|
| Memory API (HTTP) | `services/memory/pod2_memory_api.py` (impl), `pods/memory/pod2_memory_api.py` (compat entrypoint) | Primary API for storing/querying memory and world-model data; exposes probe endpoints (`/ping`, `/readyz`) | **Core / Vector (both)** |
| Memory persistence (fallback) | `services/memory/pod2_memory_api.py` (JSON helpers; default store path `/workspace/memory/long_term_memory.json`), `services/memory/memory_manager.py` | JSON-backed local persistence and “load/snapshot” behavior when not using Qdrant as the source of truth | **Core (default)** |
| Qdrant backend (external service) | `docker-compose.qdrant.yml` (`axiom_qdrant`) | Vector database used for semantic recall and (optionally) storing/querying memory items | **Vector (optional)** |
| Vector integration (in Memory API) | `services/memory/qdrant_utils.py`, `services/memory/qdrant_backend.py`, `src/axiom/vector/`, `src/axiom/retrieval/` | Qdrant query/filter helpers, backend wiring, and retrieval logic used by the Memory API when vector is enabled | **Vector (optional)** |
| Vector Adapter (HTTP) | `services/vector/vector_adapter_api.py` | Optional adapter API providing `/recall` and legacy `/v1/*` compatibility endpoints; guarded by optional bearer auth | **Vector (optional)** |
| Vector Adapter (library) | `services/vector/vector_adapter.py`, `pods/vector/vector_adapter.py` (compat import path) | Qdrant-only adapter implementation; includes embedding client logic (remote URL or local sentence-transformers when enabled) | **Vector (optional)** |
| Embedding Service (HTTP) | `services/vector/embedding_service.py` | Optional HTTP embedding service (`POST /embed`) so other components can request embeddings without bundling heavyweight ML deps | **Vector (optional)** |
| Cockpit reporter (signals) | `services/cockpit/cockpit_reporter.py`, `pods/cockpit/cockpit_reporter.py` (compat) | Writes readiness/heartbeat/error and custom JSON “signals” to a directory (default `axiom_boot/`) | **Core / Vector (both)** |
| Cockpit aggregator + status server | `services/cockpit/cockpit_aggregator.py`, `services/cockpit/cockpit_server.py` | Aggregates signal files into a status snapshot; exposes `/status/cockpit` and `/status/metrics` | **Core / Vector (optional, but useful)** |
| Boot orchestration | `boot/phases.py`, `boot/version_banner.py` | Lightweight “boot phases” runner used to emit `boot_complete`/`boot_incomplete` and a safe version banner into Cockpit | **Core / Vector (both)** |
| Optional bearer auth | `security/auth.py` | Simple `Authorization: Bearer <token>` guard for Flask services (disabled by default) | **Core / Vector (both)** |
| Import bootstrap (local dev/test ergonomics) | `sitecustomize.py` | Adds `src/axiom/` to `sys.path` so historical imports (`import config`, `import memory`, …) resolve when running from repo root | **Core / Vector (both)** |

## Supported Operation Modes

Both supported modes expose the **same Memory API** surface; the difference is how semantic recall and storage backends are wired.

### Core Mode (default)

- **Intended for**: local development/demos without embeddings, without Qdrant, and without any Rust toolchain requirement.
- **Dependencies**: `services/memory/requirements-core.txt`
- **Runtime shape**
  - Start the Memory API (see `docs/1GETTING_STARTED.md` / `README.md`).
  - Persistence falls back to a local JSON store (default path used by the Memory API: `/workspace/memory/long_term_memory.json`).
  - Vector/embedding features are not required; the system is designed to fail-closed and continue operating.

### Vector Mode (optional)

- **Intended for**: enabling **semantic recall** via Qdrant, optionally with local or remote embeddings.
- **Backend**: Qdrant via `docker-compose.qdrant.yml`
- **Dependencies**: `services/memory/requirements-vector.txt`
  - Note: this profile includes HuggingFace-related dependencies (`tokenizers`, `transformers`, `sentence-transformers`) and may require a Rust toolchain on some systems (per the repo’s own requirements notes).
- **Runtime shape**
  - Run Qdrant (and optionally the Memory API) via `docker compose -f docker-compose.qdrant.yml up --build`.
  - The Memory API uses Qdrant-backed recall when configured (and can probe backend health as part of boot signaling).

## Boot & Health Model

### Probe endpoints (Memory API)

The Memory API intentionally exposes multiple lightweight probes:

- **`GET /ping`**: ultra-light “process is up” probe. It must return immediately and must not invoke Qdrant or embeddings.
- **`GET /readyz`**: readiness probe. Implemented to be **cheap** (no network calls), based on already-computed in-memory flags plus basic memory non-emptiness checks.
- **`GET /healthz` / `GET /livez`**: simple text probes for orchestrator compatibility.
- **`GET /health`**: a richer status response (can include backend counts and world-map related checks and may perform more work than `/ping`/`/readyz`).

### Degraded vs normal mode (boot orchestration + cockpit)

Boot orchestration is implemented in `boot/phases.py` and invoked by services (notably the Memory API; also used by the Vector Adapter’s `main()` path).

- The boot runner can emit a mode of **`normal`**, **`degraded`**, or **`safe`** and writes signals such as `*.boot_complete.json` / `*.boot_incomplete.json` into the Cockpit signal directory (default `axiom_boot/`).
- Degraded-mode eligibility is controlled by env flags in `boot/phases.py` (for example `BOOT_REQUIRE`, `BOOT_DEGRADED_MIN_REQUIRE`, and `BOOT_ALLOW_DEGRADED_ON_TIMEOUT`).
- Cockpit aggregation reads those signal files and computes higher-level flags (see `services/cockpit/degradation_flags.py` and `services/cockpit/cockpit_aggregator.py`). An optional HTTP surface is available via `services/cockpit/cockpit_server.py`.

## High-Level Data Model (non-implementation)

This is a conceptual view of the public repo’s data surfaces (not a private schema, and not a listing of internal fields):

- **Episodic memory / journal entries**
  - Time-ordered records representing events, observations, and interactions.
  - In core mode, these persist via JSON-backed storage; in vector mode, selected records may also be embedded/indexed for semantic recall.

- **Beliefs & metadata**
  - Structured belief-like records and associated metadata used by higher-level reasoning components.
  - Stored and retrieved via the Memory API; optionally indexed in the vector backend when enabled.

- **Semantic vectors (when enabled)**
  - Embeddings stored in Qdrant to support semantic retrieval (“recall”).
  - Embeddings may be produced locally (when explicitly enabled) or requested from an embedding HTTP service, depending on how the environment is configured.

## Integration Expectations

- The Memory API and optional recall components are intended to be called by an **external agent / LLM frontend**. This repo intentionally does not bundle a full agent runtime.
- Treat **memory + recall** as **service-layer primitives**: store/query memory, optionally perform semantic recall, and consume cockpit/health signals for orchestration decisions.
- For concrete run commands and environment setup, follow `docs/1GETTING_STARTED.md` (and the quickstart in `README.md`).

