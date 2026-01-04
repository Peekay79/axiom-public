# Axiom Public — Systems Overview

This document explains what the **public Axiom** repo contains and how the major subsystems relate. It is intentionally **implementation-facing**: it describes **runnable surfaces and code modules that exist in this repo**, without relying on private infrastructure or philosophical framing.

## What Axiom is (in this repo)

Axiom is a set of **service-layer primitives** plus a small **agent-layer library**:

- **Service layer (HTTP)**
  - A Memory API (Flask) that can run with **JSON fallback storage** or **Qdrant-backed semantic recall**.
  - Optional vector components (Vector Adapter + Embedding Service).
  - A Cockpit “signals” model for boot/readiness/degraded state reporting.

- **Agent layer (library; no network required)**
  - A small, dependency-light package that provides:
    - **CHAMP** decision timing (act vs refine) + explainability
    - **Local store integration** helpers for offline usage

This repo **does not include** a bundled LLM runtime or a full end-to-end agent loop. Orchestration and LLM calls are expected to live in an external frontend, which can import the agent library and call the Memory API.

---

## Runtime Components (services)

| Component | Code path | Purpose | When it runs |
|---|---|---|---|
| Memory API (HTTP) | `services/memory/pod2_memory_api.py` (impl), `pods/memory/pod2_memory_api.py` (compat entrypoint) | Primary API for storing/querying memory and world-model data; probe endpoints (`/ping`, `/readyz`) | **Core / Vector** |
| Memory persistence (fallback) | `services/memory/pod2_memory_api.py` (JSON helpers), `services/memory/memory_manager.py` | JSON-backed local persistence and snapshot/load behavior when Qdrant isn’t used as the source of truth | **Core** |
| Qdrant backend (external service) | `docker-compose.qdrant.yml` (`axiom_qdrant`) | Vector DB for semantic recall | **Vector (optional)** |
| Vector integration (Memory API) | `services/memory/qdrant_utils.py`, `services/memory/qdrant_backend.py`, `src/axiom/vector/`, `src/axiom/retrieval/` | Qdrant query/filter helpers and retrieval logic | **Vector (optional)** |
| Vector Adapter (HTTP) | `services/vector/vector_adapter_api.py` | Optional `/recall` and legacy `/v1/*` compatibility endpoints | **Vector (optional)** |
| Embedding Service (HTTP) | `services/vector/embedding_service.py` | Optional embedding server (`POST /embed`) | **Vector (optional)** |
| Cockpit reporter (signals) | `services/cockpit/cockpit_reporter.py`, `pods/cockpit/cockpit_reporter.py` | Writes readiness/heartbeat/error JSON signals (default dir `axiom_boot/`) | **Core / Vector** |
| Cockpit status server | `services/cockpit/cockpit_server.py` | Optional `/status/cockpit` + `/status/metrics` | **Optional** |
| Boot orchestration | `boot/phases.py`, `boot/version_banner.py` | Boot phases + safe banner; can emit normal/degraded/safe mode via cockpit signals | **Core / Vector** |
| Optional bearer auth | `security/auth.py` | Simple bearer token guard for Flask services (off by default) | **Optional** |
| Import bootstrap | `sitecustomize.py` | Dev ergonomics: adds `src/` to `sys.path` for historical imports | **Dev** |

---

## Agent Layer (library)

The agent layer is **importable Python** under `src/axiom_agent/`. It is designed to be usable without Discord, without LLMs, and without any private services.

### 1) CHAMP — decision timing + explainability

**Goal:** decide whether to **execute now** or **refine more**, using a compact scoring model.

- **Code**
  - `src/axiom_agent/champ/engine.py` — scoring + thresholds (act vs refine)
  - `src/axiom_agent/champ/explain.py` — human-readable rationale (“why did it choose X?”)

- **What it gives you**
  - A consistent, testable decision governor for agent loops
  - Explainability for debugging and demos

### 2) Integrations — local store helpers

**Goal:** keep the agent layer usable offline, without requiring the services.

- `src/axiom_agent/integrations/local_store.py` — small local store adapter

---

## How these parts fit together

A practical way to think about the repo:

```text
External agent / UI / orchestration (your code)
|
|-- imports axiom_agent (CHAMP + local store integration)
|-- calls Memory API (HTTP) for storage + retrieval
|-- optionally calls Vector Adapter / Embedding Service
|
Axiom services (this repo)
- Memory API
- optional Qdrant + vector pieces
- Cockpit signals + boot phases
```

The public repo is designed so that you can:
- run the Memory API standalone (Core mode)
- enable semantic recall (Vector mode)
- build your own agent loop on top, using the agent layer library

---

## Operating modes (repo-supported)

### Core mode (default)

- No Qdrant required
- JSON persistence fallback
- Intended for local dev and demos

### Vector mode (optional)

- Qdrant provides semantic recall
- Optional embedding server or local embedding dependencies (depending on your config)
- Intended for teams that want retrieval beyond keyword/time-ordered memory

---

## Boot & health model (services)

The Memory API exposes multiple probes:

- `GET /ping` — process is up (must be ultra-cheap)
- `GET /readyz` — readiness (cheap, based on in-memory flags)
- `GET /health` — richer status (may do more work)

Cockpit signals provide a file-based “ground truth” of boot/readiness/degraded state, and optionally an HTTP status surface.

---

## Where to look next

- Start here: `README.md` + `docs/1GETTING_STARTED.md`
- Architecture deep dive (services): `docs/` (and the system architecture doc)
- Agent layer code: `src/axiom_agent/`
- Demo entrypoint: `apps/run_demo.sh` (no install) and `apps/agent_cli.py`
