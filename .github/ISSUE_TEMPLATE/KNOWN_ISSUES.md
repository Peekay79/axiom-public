---
name: "START HERE — Known Issues, Setup Notes & Workarounds"
about: "Quick first-run troubleshooting for axiom-public (copy/paste friendly for a pinned issue)."
title: "START HERE — Known Issues, Setup Notes & Workarounds"
labels: ["documentation"]
---

# START HERE — Known Issues, Setup Notes & Workarounds

Welcome! This issue is a **single, copy/paste friendly landing page** for first-run setup problems. The goal is to quickly route you to the right setup mode and capture enough signal for maintainers to help you fast.

## Quick links (recommended reading)

- [1GETTING_STARTED.md](../blob/main/1GETTING_STARTED.md) — primary setup guide
- [AXIOM_RUNABILITY_AUDIT.md](../blob/main/AXIOM_RUNABILITY_AUDIT.md) — setup modes + known gaps and “run surfaces”

Maintainers: if you want this “Start Here” page pinned, create an issue from this template and pin that issue.

## Before you go deep (2-minute checklist)

- [ ] Verify the Memory API is up by running:
  - [ ] `curl -fsS http://localhost:8002/ping`
  - [ ] `curl -fsS http://localhost:8002/readyz`
- [ ] Confirm which setup path you’re using:
  - [ ] **Docker + Qdrant** (`docker compose -f docker-compose.qdrant.yml ...`)
  - [ ] **Local Core Memory API** (`pip install -r services/memory/requirements-core.txt` + `python -m pods.memory.pod2_memory_api`)

If you’re filing a bug, please include `/ping` + `/readyz` outputs in your report (short and very high-signal).

---

## Common First-Run Issues

### 1) “Connection refused” / `/ping` fails

Most common causes:

- **Wrong port**: Docker routes host **`:8002` → container `:5000`**. Use `http://localhost:8002` from your host machine.
- **Service not running yet**: first build can take a bit. Wait for the Memory container to settle, then retry.
- **Port already in use**: something else is listening on `8002`.

Quick check:

- If Docker: `docker compose -f docker-compose.qdrant.yml ps` should show `axiom_memory` running.
- If local Python: make sure the command is started with `MEMORY_API_PORT=8002 ...`.

### 2) `/ping` works but `/readyz` is failing

This usually means the server is up but dependencies (often vector/Qdrant) aren’t in the expected state.

- If you intended **core fallback mode** (no vector DB), make sure you’re using:
  - `pip install -r services/memory/requirements-core.txt`
- If you intended **Qdrant-backed** mode, verify Qdrant is reachable (see Docker/networking notes below).

### 3) Import/module errors when running locally

Run from the repo root and use the documented entrypoint:

- `python -m pods.memory.pod2_memory_api`

If you’re running from a different working directory or invoking a file directly, imports can break.

---

## Mac / ARM Rust toolchain notes

You only need Rust for **vector / embeddings** installs on some machines (commonly macOS on Apple Silicon), due to packages like `tokenizers`.

Practical options:

- **Fastest workaround**: start with **core** (`requirements-core.txt`) or use **Docker + Qdrant**.
- **If you need vector locally**: install a Rust toolchain (via `rustup`) and retry `pip install -r services/memory/requirements-vector.txt`.

If you’re not explicitly using semantic recall / embeddings, you can safely stay on core.

---

## Vector mode vs core mode expectations

### Core (fallback) mode

Intended to be a reliable first-run path:

- ✅ Memory API boots without Qdrant
- ✅ `/ping`, `/readyz`, `/health` should work
- ✅ No embeddings, no vector DB required, **no Rust required**

### Vector / Qdrant-backed mode

Adds semantic recall paths:

- ✅ Qdrant required (local Docker or remote)
- ✅ May require heavier deps (and sometimes Rust) if using local embeddings
- ✅ More moving pieces; use it once core probes are green

---

## Docker + Qdrant networking notes

### When using `docker compose -f docker-compose.qdrant.yml ...`

- **Memory API** is exposed on your host at `http://localhost:8002`
- **Qdrant** is exposed on your host at `http://localhost:6333`
- Inside the Docker network, the Memory service connects to Qdrant via:
  - `QDRANT_HOST=axiom_qdrant`
  - `QDRANT_PORT=6333`

### When running Memory API locally but Qdrant in Docker

From your host process, Qdrant is usually reachable at:

- `QDRANT_URL=http://localhost:6333`

If you’re using a remote Qdrant, set `QDRANT_URL` accordingly (and API key/HTTPS settings if applicable) using the patterns shown in `configs/.env.example`.

